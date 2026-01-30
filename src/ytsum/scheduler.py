"""Scheduler for automated video checking and summarization."""

import logging
import time
from datetime import datetime
from typing import Dict, List

import schedule

from .config import Config
from .database import Database
from .summarizer import Summarizer
from .youtube import YouTubeClient

logger = logging.getLogger(__name__)


def check_and_process(db: Database, config: Config) -> Dict:
    """Check for new videos and process them.

    This is the main processing function that:
    1. Checks all followed channels for new videos
    2. Fetches transcripts for videos without them
    3. Generates summaries for videos with transcripts but no summaries

    Args:
        db: Database instance.
        config: Configuration instance.

    Returns:
        Dictionary with processing results.
    """
    start_time = datetime.utcnow()
    errors: List[str] = []
    videos_found = 0
    videos_processed = 0

    try:
        # Initialize clients
        yt_client = YouTubeClient(config.youtube_api_key)
        summarizer = Summarizer(
            config.openrouter_api_key,
            config.openrouter_model,
            config.openrouter_base_url,
        )

        # Step 1: Check for new videos from all channels
        logger.info("Checking for new videos from followed channels...")
        channels = db.get_all_channels()

        for channel in channels:
            try:
                logger.info(f"Checking channel: {channel.channel_name}")

                # Get recent videos
                videos = yt_client.get_recent_videos(
                    channel.channel_id,
                    days_back=config.days_to_look_back,
                    max_results=config.max_videos_per_check,
                )

                # Add new videos to database
                for video_data in videos:
                    result = db.add_video(
                        video_id=video_data["id"],
                        channel_id=channel.id,
                        title=video_data["title"],
                        published_at=video_data["published_at"],
                        url=video_data["url"],
                        duration=video_data.get("duration"),
                    )

                    if result:
                        videos_found += 1
                        logger.info(f"Found new video: {video_data['title']}")

                # Update last checked time
                db.update_channel_check_time(channel.id)

            except Exception as e:
                error_msg = f"Error checking channel {channel.channel_name}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Step 2: Fetch transcripts for videos without them
        logger.info("Fetching transcripts for videos...")
        videos_without_transcripts = db.get_videos_without_transcripts()

        for video in videos_without_transcripts[:50]:  # Limit to 50 per run
            try:
                logger.info(f"Fetching transcript for: {video.title}")

                transcript_data = yt_client.get_transcript(video.video_id)

                if transcript_data:
                    transcript_text, language = transcript_data
                    db.add_transcript(video.id, transcript_text, language)
                    logger.info(f"Transcript fetched ({language})")
                else:
                    error_msg = f"No transcript available for: {video.title}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

            except Exception as e:
                error_msg = f"Error fetching transcript for {video.title}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Step 3: Generate summaries for videos with transcripts but no summaries
        logger.info("Generating summaries...")
        videos_without_summaries = db.get_videos_without_summaries()

        for video in videos_without_summaries[:30]:  # Limit to 30 per run (API cost)
            try:
                logger.info(f"Summarizing: {video.title}")

                # Get transcript
                transcript = video.transcript.transcript_text

                # Generate summary
                summary_text, key_points = summarizer.summarize(
                    transcript,
                    video.title,
                    max_length=config.summary_max_length,
                    max_key_points=config.max_key_points,
                )

                # Save summary
                db.add_summary(
                    video.id,
                    summary_text,
                    key_points,
                    config.openrouter_model,
                )

                videos_processed += 1
                logger.info(f"Summary generated successfully")

            except Exception as e:
                error_msg = f"Error summarizing {video.title}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

    except Exception as e:
        error_msg = f"Fatal error in check_and_process: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)

    # Record run history
    end_time = datetime.utcnow()
    duration = int((end_time - start_time).total_seconds())

    db.add_run_history(
        videos_found=videos_found,
        videos_processed=videos_processed,
        errors=errors if errors else None,
        success=len(errors) == 0,
        duration_seconds=duration,
    )

    result = {
        "videos_found": videos_found,
        "videos_processed": videos_processed,
        "errors": errors,
        "duration": duration,
    }

    logger.info(f"Check completed: {videos_found} found, {videos_processed} processed")

    return result


def run_scheduler(db: Database, config: Config):
    """Run the scheduler daemon.

    This function runs continuously and executes check_and_process
    according to the configured schedule.

    Args:
        db: Database instance.
        config: Configuration instance.
    """
    logger.info(f"Scheduler started. Will run daily at {config.check_schedule}")

    # Schedule the job
    schedule.every().day.at(config.check_schedule).do(
        lambda: check_and_process(db, config)
    )

    # Also run immediately on startup if there's pending work
    videos_without_summaries = db.get_videos_without_summaries()
    if videos_without_summaries:
        logger.info("Found pending work, running check immediately...")
        check_and_process(db, config)

    # Run scheduler loop
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            break
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            time.sleep(300)  # Wait 5 minutes on error before retrying


def run_once(db: Database, config: Config) -> Dict:
    """Run check and process once (for cron or manual execution).

    Args:
        db: Database instance.
        config: Configuration instance.

    Returns:
        Dictionary with processing results.
    """
    logger.info("Running one-time check and process")
    return check_and_process(db, config)
