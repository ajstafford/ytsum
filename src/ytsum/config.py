"""Configuration management for ytsum."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


class Config:
    """Application configuration."""

    def __init__(self, env_file: Optional[Path] = None):
        """Load configuration from environment variables.

        Args:
            env_file: Path to .env file. If None, searches in standard locations.
        """
        # Search for .env file in standard locations
        if env_file is None:
            possible_locations = [
                Path.cwd() / ".env",
                Path.home() / ".config" / "ytsum" / ".env",
                Path("/etc/ytsum/.env"),
            ]
            for location in possible_locations:
                if location.exists():
                    env_file = location
                    break

        if env_file and env_file.exists():
            load_dotenv(env_file)

        # YouTube API Configuration
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY", "")

        # OpenRouter API Configuration
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.openrouter_model = os.getenv(
            "OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"
        )
        self.openrouter_base_url = os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )

        # Application Configuration
        self.app_name = os.getenv("APP_NAME", "ytsum")
        self.check_schedule = os.getenv(
            "CHECK_SCHEDULE", "08:00"
        )  # Time to run daily check (HH:MM)

        # Database Configuration
        db_path_str = os.getenv("DATABASE_PATH", "")
        if db_path_str:
            self.database_path = Path(db_path_str)
        else:
            self.database_path = (
                Path.home() / ".local" / "share" / "ytsum" / "ytsum.db"
            )

        # Logging Configuration
        log_path_str = os.getenv("LOG_PATH", "")
        if log_path_str:
            self.log_path = Path(log_path_str)
        else:
            self.log_path = Path.home() / ".local" / "share" / "ytsum" / "logs"

        # Ensure directories exist
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.mkdir(parents=True, exist_ok=True)

        # Summarization Configuration
        self.summary_max_length = int(os.getenv("SUMMARY_MAX_LENGTH", "500"))
        self.max_key_points = int(os.getenv("MAX_KEY_POINTS", "5"))

        # Video Processing Configuration
        self.max_videos_per_check = int(os.getenv("MAX_VIDEOS_PER_CHECK", "50"))
        self.days_to_look_back = int(
            os.getenv("DAYS_TO_LOOK_BACK", "7")
        )  # How far back to check for new videos

    def validate(self) -> tuple[bool, list[str]]:
        """Validate configuration.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        if not self.youtube_api_key:
            errors.append(
                "YOUTUBE_API_KEY is not set. Get one from https://console.cloud.google.com/"
            )

        if not self.openrouter_api_key:
            errors.append(
                "OPENROUTER_API_KEY is not set. Get one from https://openrouter.ai/"
            )

        return (len(errors) == 0, errors)

    def to_dict(self) -> dict:
        """Convert configuration to dictionary (for display purposes)."""
        return {
            "youtube_api_key": "***" if self.youtube_api_key else "Not set",
            "openrouter_api_key": "***" if self.openrouter_api_key else "Not set",
            "openrouter_model": self.openrouter_model,
            "database_path": str(self.database_path),
            "log_path": str(self.log_path),
            "check_schedule": self.check_schedule,
            "summary_max_length": self.summary_max_length,
            "max_key_points": self.max_key_points,
            "max_videos_per_check": self.max_videos_per_check,
            "days_to_look_back": self.days_to_look_back,
        }

    @staticmethod
    def create_example_env(output_path: Optional[Path] = None):
        """Create an example .env file.

        Args:
            output_path: Where to save the file. If None, saves to current directory.
        """
        if output_path is None:
            output_path = Path.cwd() / ".env.example"

        content = """# YouTube Data API v3 Key
# Get from: https://console.cloud.google.com/
YOUTUBE_API_KEY=your_youtube_api_key_here

# OpenRouter API Key
# Get from: https://openrouter.ai/
OPENROUTER_API_KEY=your_openrouter_api_key_here

# OpenRouter Model to use for summarization
# Options: anthropic/claude-3.5-sonnet, openai/gpt-4, meta-llama/llama-3.1-70b-instruct, etc.
# See: https://openrouter.ai/models
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# OpenRouter Base URL (usually don't need to change)
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Application name
APP_NAME=ytsum

# Daily check schedule (24-hour format HH:MM)
CHECK_SCHEDULE=08:00

# Database path (optional, defaults to ~/.local/share/ytsum/ytsum.db)
# DATABASE_PATH=/custom/path/to/ytsum.db

# Log path (optional, defaults to ~/.local/share/ytsum/logs)
# LOG_PATH=/custom/path/to/logs

# Summarization settings
SUMMARY_MAX_LENGTH=500
MAX_KEY_POINTS=5

# Video processing settings
MAX_VIDEOS_PER_CHECK=50
DAYS_TO_LOOK_BACK=7
"""

        output_path.write_text(content)
        return output_path


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config):
    """Set the global configuration instance."""
    global _config
    _config = config
