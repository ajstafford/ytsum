"""YouTube API integration for fetching videos and transcripts."""

import logging
import re
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

logger = logging.getLogger(__name__)


class YouTubeClient:
    """Client for interacting with YouTube."""

    def __init__(self, api_key: str):
        """Initialize YouTube client.

        Args:
            api_key: YouTube Data API v3 key.
        """
        self.api_key = api_key
        self.youtube = build("youtube", "v3", developerKey=api_key)

    @staticmethod
    def extract_channel_id(url_or_id: str) -> Optional[str]:
        """Extract channel ID from various YouTube URL formats.

        Supports:
        - Channel URLs: youtube.com/channel/UC...
        - Custom URLs: youtube.com/c/ChannelName or youtube.com/@ChannelName
        - Direct channel IDs: UC...

        Args:
            url_or_id: YouTube channel URL or ID.

        Returns:
            Channel ID or None if not found.
        """
        # If it looks like a channel ID already (starts with UC)
        if url_or_id.startswith("UC") and len(url_or_id) == 24:
            return url_or_id

        # Extract from URL patterns
        patterns = [
            r"youtube\.com/channel/(UC[\w-]+)",
            r"youtube\.com/c/([\w-]+)",
            r"youtube\.com/@([\w-]+)",
            r"youtube\.com/user/([\w-]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)

        return None

    def get_channel_info(self, channel_identifier: str) -> Optional[dict]:
        """Get channel information by ID, username, or custom URL.

        Args:
            channel_identifier: Channel ID, username, or handle.

        Returns:
            Dictionary with channel info (id, name, url) or None if not found.
        """
        try:
            # First, try as channel ID
            if channel_identifier.startswith("UC"):
                request = self.youtube.channels().list(
                    part="snippet", id=channel_identifier
                )
                response = request.execute()

                if response.get("items"):
                    item = response["items"][0]
                    return {
                        "id": item["id"],
                        "name": item["snippet"]["title"],
                        "url": f"https://www.youtube.com/channel/{item['id']}",
                    }

            # Try as username
            request = self.youtube.channels().list(
                part="snippet", forUsername=channel_identifier
            )
            response = request.execute()

            if response.get("items"):
                item = response["items"][0]
                return {
                    "id": item["id"],
                    "name": item["snippet"]["title"],
                    "url": f"https://www.youtube.com/channel/{item['id']}",
                }

            # Try as handle (custom URL)
            request = self.youtube.search().list(
                part="snippet", q=channel_identifier, type="channel", maxResults=1
            )
            response = request.execute()

            if response.get("items"):
                item = response["items"][0]
                channel_id = item["snippet"]["channelId"]
                return {
                    "id": channel_id,
                    "name": item["snippet"]["title"],
                    "url": f"https://www.youtube.com/channel/{channel_id}",
                }

        except HttpError as e:
            logger.error(f"Error fetching channel info: {e}")

        return None

    def get_recent_videos(
        self, channel_id: str, days_back: int = 7, max_results: int = 50
    ) -> List[dict]:
        """Get recent videos from a channel.

        Args:
            channel_id: YouTube channel ID.
            days_back: Number of days to look back.
            max_results: Maximum number of videos to return.

        Returns:
            List of video dictionaries with id, title, published_at, url, duration.
        """
        try:
            published_after = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"

            # Search for videos
            request = self.youtube.search().list(
                part="snippet",
                channelId=channel_id,
                type="video",
                order="date",
                publishedAfter=published_after,
                maxResults=max_results,
            )
            response = request.execute()

            if not response.get("items"):
                return []

            # Get video IDs
            video_ids = [item["id"]["videoId"] for item in response["items"]]

            # Get video details (including duration)
            videos_request = self.youtube.videos().list(
                part="snippet,contentDetails", id=",".join(video_ids)
            )
            videos_response = videos_request.execute()

            videos = []
            for item in videos_response.get("items", []):
                videos.append(
                    {
                        "id": item["id"],
                        "title": item["snippet"]["title"],
                        "published_at": datetime.fromisoformat(
                            item["snippet"]["publishedAt"].replace("Z", "+00:00")
                        ),
                        "url": f"https://www.youtube.com/watch?v={item['id']}",
                        "duration": item["contentDetails"]["duration"],
                    }
                )

            return videos

        except HttpError as e:
            logger.error(f"Error fetching recent videos for channel {channel_id}: {e}")
            return []

    @staticmethod
    def get_transcript(video_id: str) -> Optional[Tuple[str, str]]:
        """Fetch transcript for a video.

        Args:
            video_id: YouTube video ID.

        Returns:
            Tuple of (transcript_text, language_code) or None if unavailable.
        """
        try:
            # Create API instance
            api = YouTubeTranscriptApi()

            # Try to get English transcript first
            try:
                transcript_result = api.fetch(video_id, languages=['en'])
            except:
                # Fall back to any available transcript
                try:
                    transcript_result = api.fetch(video_id)
                except:
                    # No transcript available
                    logger.warning(f"No transcript found for video {video_id}")
                    return None

            # Extract language code
            language = transcript_result.language_code if hasattr(transcript_result, 'language_code') else 'unknown'

            # Combine all text segments from the transcript snippets
            # The result is iterable and contains FetchedTranscriptSnippet objects
            full_text = " ".join([snippet.text for snippet in transcript_result])

            return (full_text, language)

        except TranscriptsDisabled:
            logger.warning(f"Transcripts are disabled for video {video_id}")
            return None
        except NoTranscriptFound:
            logger.warning(f"No transcript found for video {video_id}")
            return None
        except VideoUnavailable:
            logger.warning(f"Video {video_id} is unavailable")
            return None
        except Exception as e:
            logger.error(f"Error fetching transcript for video {video_id}: {e}")
            return None

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extract video ID from YouTube URL.

        Args:
            url: YouTube video URL.

        Returns:
            Video ID or None if not found.
        """
        patterns = [
            r"youtube\.com/watch\?v=([\w-]+)",
            r"youtu\.be/([\w-]+)",
            r"youtube\.com/embed/([\w-]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        # If it looks like a video ID already (11 characters)
        if len(url) == 11 and re.match(r"^[\w-]+$", url):
            return url

        return None


def validate_api_key(api_key: str) -> bool:
    """Validate YouTube API key by making a simple request.

    Args:
        api_key: YouTube Data API v3 key.

    Returns:
        True if valid, False otherwise.
    """
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        request = youtube.channels().list(part="snippet", id="UC_x5XG1OV2P6uZZ5FSM9Ttw")
        request.execute()
        return True
    except HttpError:
        return False
