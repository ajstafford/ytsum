"""AI summarization using OpenRouter API."""

import json
import logging
from typing import List, Tuple

from openai import OpenAI

logger = logging.getLogger(__name__)


class Summarizer:
    """LLM-based summarizer using OpenRouter."""

    def __init__(
        self,
        api_key: str,
        model: str = "anthropic/claude-3.5-sonnet",
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        """Initialize summarizer.

        Args:
            api_key: OpenRouter API key.
            model: Model to use (e.g., 'anthropic/claude-3.5-sonnet').
            base_url: OpenRouter API base URL.
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

        # Initialize OpenAI client with OpenRouter settings
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def summarize(
        self,
        transcript: str,
        video_title: str,
        max_length: int = 500,
        max_key_points: int = 5,
    ) -> Tuple[str, List[str]]:
        """Generate a summary and key points from a video transcript.

        Args:
            transcript: The video transcript text.
            video_title: The video title for context.
            max_length: Maximum length of summary in words.
            max_key_points: Maximum number of key points to extract.

        Returns:
            Tuple of (summary_text, list_of_key_points).
        """
        prompt = self._build_prompt(transcript, video_title, max_length, max_key_points)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that summarizes YouTube video transcripts. "
                        "Provide clear, concise summaries with actionable key points.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=2000,
            )

            content = response.choices[0].message.content

            # Parse the response to extract summary and key points
            summary, key_points = self._parse_response(content)

            return summary, key_points

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            raise

    def _build_prompt(
        self, transcript: str, video_title: str, max_length: int, max_key_points: int
    ) -> str:
        """Build the prompt for summarization.

        Args:
            transcript: Video transcript.
            video_title: Video title.
            max_length: Maximum summary length in words.
            max_key_points: Maximum number of key points.

        Returns:
            Formatted prompt string.
        """
        # Truncate very long transcripts to avoid token limits
        max_transcript_length = 15000  # roughly 4000 tokens
        if len(transcript) > max_transcript_length:
            transcript = transcript[:max_transcript_length] + "... [truncated]"

        prompt = f"""Please analyze this YouTube video transcript and provide a summary.

Video Title: {video_title}

Transcript:
{transcript}

Please provide:
1. A concise summary (maximum {max_length} words) that captures the main message and important details
2. A list of {max_key_points} key takeaways or main points

Format your response as JSON with this structure:
{{
    "summary": "Your summary here...",
    "key_points": [
        "First key point",
        "Second key point",
        ...
    ]
}}

Focus on:
- Main topics and themes
- Important facts, statistics, or insights
- Actionable takeaways
- Conclusions or recommendations

Keep the language clear and concise."""

        return prompt

    def _parse_response(self, content: str) -> Tuple[str, List[str]]:
        """Parse the LLM response to extract summary and key points.

        Args:
            content: Raw response from LLM.

        Returns:
            Tuple of (summary, key_points).
        """
        try:
            # Try to parse as JSON first
            # Remove markdown code blocks if present
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)
            summary = data.get("summary", "")
            key_points = data.get("key_points", [])

            return summary, key_points

        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract manually
            logger.warning("Failed to parse JSON response, attempting manual extraction")

            lines = content.split("\n")
            summary = ""
            key_points = []
            in_key_points = False

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Look for summary
                if "summary" in line.lower() and ":" in line:
                    summary = line.split(":", 1)[1].strip().strip('"')
                    continue

                # Look for key points section
                if "key" in line.lower() and "point" in line.lower():
                    in_key_points = True
                    continue

                # Extract key points
                if in_key_points:
                    # Remove list markers
                    point = line.lstrip("- •*1234567890.() ").strip('"')
                    if point and len(point) > 10:  # Filter out very short lines
                        key_points.append(point)

            # Fallback: use first paragraph as summary if not found
            if not summary:
                paragraphs = content.split("\n\n")
                summary = paragraphs[0] if paragraphs else content[:500]

            # Fallback: try to extract bullet points if no key points found
            if not key_points:
                for line in lines:
                    line = line.strip()
                    if line.startswith(("-", "•", "*")) or (
                        line[:2].replace(".", "").replace(")", "").isdigit()
                    ):
                        point = line.lstrip("- •*1234567890.() ").strip()
                        if point and len(point) > 10:
                            key_points.append(point)

            return summary, key_points[:5]  # Limit to 5 key points


def test_openrouter_api(api_key: str, model: str = "anthropic/claude-3.5-sonnet") -> bool:
    """Test OpenRouter API connection.

    Args:
        api_key: OpenRouter API key.
        model: Model to test.

    Returns:
        True if successful, False otherwise.
    """
    try:
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say 'API connection successful' if you can read this."}],
            max_tokens=50,
        )

        return bool(response.choices[0].message.content)

    except Exception as e:
        logger.error(f"OpenRouter API test failed: {e}")
        return False
