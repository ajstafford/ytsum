"""Database models and operations for ytsum."""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Table,
    create_engine,
    UniqueConstraint,
    inspect,
    text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker, joinedload
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

Base = declarative_base()

# Junction table for many-to-many relationship between users and channels
user_channels = Table(
    'user_channels',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('youtube_channel_id', Integer, ForeignKey('youtube_channels.id'), primary_key=True),
    Column('added_date', DateTime, default=datetime.utcnow),
)


class User(UserMixin, Base):
    """User account."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(128))
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Telegram notification settings
    telegram_chat_id = Column(String(64), nullable=True)
    telegram_enabled = Column(Boolean, default=False)
    telegram_verification_code = Column(String(16), nullable=True)
    telegram_linked_at = Column(DateTime, nullable=True)

    # Many-to-many relationship with YouTube channels
    youtube_channels = relationship(
        "YouTubeChannel",
        secondary=user_channels,
        back_populates="users"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class YouTubeChannel(Base):
    """YouTube channel (global, unique by channel_id)."""

    __tablename__ = "youtube_channels"

    id = Column(Integer, primary_key=True)
    channel_id = Column(String, unique=True, nullable=False, index=True)  # YouTube channel ID (e.g., UC...)
    channel_name = Column(String, nullable=False)
    channel_url = Column(String, nullable=False)
    added_date = Column(DateTime, default=datetime.utcnow)
    last_checked = Column(DateTime, nullable=True)

    # Many-to-many relationship with users
    users = relationship(
        "User",
        secondary=user_channels,
        back_populates="youtube_channels"
    )
    
    # One-to-many relationship with videos
    videos = relationship("Video", back_populates="youtube_channel", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<YouTubeChannel(name='{self.channel_name}', id='{self.channel_id}')>"


class Video(Base):
    """YouTube video from a followed channel."""

    __tablename__ = "videos"

    id = Column(Integer, primary_key=True)
    video_id = Column(String, unique=True, nullable=False, index=True)
    youtube_channel_id = Column(Integer, ForeignKey("youtube_channels.id"), nullable=False)
    title = Column(String, nullable=False)
    published_at = Column(DateTime, nullable=False)
    duration = Column(String, nullable=True)  # ISO 8601 duration format
    url = Column(String, nullable=False)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    failed_attempts = Column(Integer, default=0)  # Track failed transcript attempts
    max_failed_attempts = 10  # Class constant for max retries

    youtube_channel = relationship("YouTubeChannel", back_populates="videos")
    transcript = relationship("Transcript", back_populates="video", uselist=False)
    summary = relationship("Summary", back_populates="video", uselist=False)

    def __repr__(self):
        return f"<Video(title='{self.title}', id='{self.video_id}')>"


class Transcript(Base):
    """Transcript for a YouTube video."""

    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, unique=True)
    transcript_text = Column(Text, nullable=False)
    language = Column(String, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    video = relationship("Video", back_populates="transcript")

    def __repr__(self):
        return f"<Transcript(video_id={self.video_id}, length={len(self.transcript_text)})>"


class Summary(Base):
    """AI-generated summary of a video."""

    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, unique=True)
    summary_text = Column(Text, nullable=False)
    key_points = Column(Text, nullable=True)  # JSON array of key points
    model_used = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    video = relationship("Video", back_populates="summary")

    def get_key_points(self) -> List[str]:
        """Parse and return key points as a list."""
        if self.key_points:
            return json.loads(self.key_points)
        return []

    def set_key_points(self, points: List[str]):
        """Set key points from a list."""
        self.key_points = json.dumps(points)

    def __repr__(self):
        return f"<Summary(video_id={self.video_id}, model='{self.model_used}')>"


class RunHistory(Base):
    """History of automation runs."""

    __tablename__ = "run_history"

    id = Column(Integer, primary_key=True)
    run_timestamp = Column(DateTime, default=datetime.utcnow)
    videos_found = Column(Integer, default=0)
    videos_processed = Column(Integer, default=0)
    errors = Column(Text, nullable=True)  # JSON array of errors
    success = Column(Boolean, default=True)
    duration_seconds = Column(Integer, nullable=True)

    def get_errors(self) -> List[str]:
        """Parse and return errors as a list."""
        if self.errors:
            return json.loads(self.errors)
        return []

    def set_errors(self, error_list: List[str]):
        """Set errors from a list."""
        self.errors = json.dumps(error_list)

    def __repr__(self):
        return f"<RunHistory(timestamp={self.run_timestamp}, processed={self.videos_processed})>"


class TelegramQueue(Base):
    """Queue for Telegram messages to be sent.
    
    This table acts as a message broker between web/scheduler and the Telegram bot.
    Web/scheduler insert messages here, Telegram bot polls and sends them.
    """

    __tablename__ = "telegram_queue"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    chat_id = Column(String(64), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(20), default="pending")  # pending, sent, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    user = relationship("User", back_populates="telegram_queue_items")

    def __repr__(self):
        return f"<TelegramQueue(id={self.id}, chat_id={self.chat_id}, status={self.status})>"


# Add relationship to User model
User.telegram_queue_items = relationship("TelegramQueue", back_populates="user")


class Database:
    """Database manager for ytsum."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            db_path = Path.home() / ".local" / "share" / "ytsum" / "ytsum.db"

        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.SessionLocal = sessionmaker(bind=self.engine)

        # Check if we need to migrate from old schema
        self._migrate_if_needed()

    def _migrate_if_needed(self):
        """Check and perform database migrations if needed."""
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        
        # Check if we have the old schema (channels table with user_id column)
        if "channels" in tables:
            columns = {c["name"]: c for c in inspector.get_columns("channels")}
            if "user_id" in columns:
                # Old schema detected - need to migrate
                self._perform_migration_v2()
                return
        
        # Check if we need to add is_admin to users
        if "users" in tables:
            columns = [c["name"] for c in inspector.get_columns("users")]
            if "is_admin" not in columns:
                with self.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
                    conn.commit()
        
        # Check if we need to add failed_attempts to videos
        if "videos" in tables:
            columns = [c["name"] for c in inspector.get_columns("videos")]
            if "failed_attempts" not in columns:
                with self.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE videos ADD COLUMN failed_attempts INTEGER DEFAULT 0"))
                    conn.commit()
        
        # Check if we need to add telegram columns to users
        if "users" in tables:
            columns = [c["name"] for c in inspector.get_columns("users")]
            if "telegram_chat_id" not in columns:
                with self.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN telegram_chat_id VARCHAR(64)"))
                    conn.commit()
            if "telegram_enabled" not in columns:
                with self.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN telegram_enabled BOOLEAN DEFAULT 0"))
                    conn.commit()
            if "telegram_verification_code" not in columns:
                with self.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN telegram_verification_code VARCHAR(16)"))
                    conn.commit()
            if "telegram_linked_at" not in columns:
                with self.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN telegram_linked_at DATETIME"))
                    conn.commit()
        
        # Create all tables with new schema
        Base.metadata.create_all(self.engine)

    def _perform_migration_v2(self):
        """Migrate from old schema to new normalized schema.
        
        Old schema: channels table with user_id, videos linked to channels
        New schema: youtube_channels (global), user_channels (junction), videos linked to youtube_channels
        """
        print("Performing database migration to v2 (normalized schema)...")
        
        with self.engine.connect() as conn:
            # Rename old tables to backup
            conn.execute(text("ALTER TABLE channels RENAME TO channels_old"))
            conn.execute(text("ALTER TABLE videos RENAME TO videos_old"))
            conn.execute(text("ALTER TABLE transcripts RENAME TO transcripts_old"))
            conn.execute(text("ALTER TABLE summaries RENAME TO summaries_old"))
            conn.commit()
        
        # Create new schema tables
        Base.metadata.create_all(self.engine)
        
        with self.engine.connect() as conn:
            # Migrate channels to youtube_channels (deduplicated)
            conn.execute(text("""
                INSERT INTO youtube_channels (id, channel_id, channel_name, channel_url, added_date, last_checked)
                SELECT MIN(id), channel_id, channel_name, channel_url, MIN(added_date), MAX(last_checked)
                FROM channels_old
                GROUP BY channel_id
            """))
            
            # Create user_channels junction table
            conn.execute(text("""
                INSERT INTO user_channels (user_id, youtube_channel_id, added_date)
                SELECT c.user_id, yc.id, c.added_date
                FROM channels_old c
                JOIN youtube_channels yc ON c.channel_id = yc.channel_id
                WHERE c.user_id IS NOT NULL
            """))
            
            # Migrate videos - remap channel_id to youtube_channel_id
            conn.execute(text("""
                INSERT INTO videos (id, video_id, youtube_channel_id, title, published_at, duration, url, discovered_at)
                SELECT v.id, v.video_id, yc.id, v.title, v.published_at, v.duration, v.url, v.discovered_at
                FROM videos_old v
                JOIN channels_old c ON v.channel_id = c.id
                JOIN youtube_channels yc ON c.channel_id = yc.channel_id
            """))
            
            # Migrate transcripts
            conn.execute(text("""
                INSERT INTO transcripts (id, video_id, transcript_text, language, fetched_at)
                SELECT id, video_id, transcript_text, language, fetched_at
                FROM transcripts_old
            """))
            
            # Migrate summaries
            conn.execute(text("""
                INSERT INTO summaries (id, video_id, summary_text, key_points, model_used, created_at)
                SELECT id, video_id, summary_text, key_points, model_used, created_at
                FROM summaries_old
            """))
            
            # Drop old tables
            conn.execute(text("DROP TABLE channels_old"))
            conn.execute(text("DROP TABLE videos_old"))
            conn.execute(text("DROP TABLE transcripts_old"))
            conn.execute(text("DROP TABLE summaries_old"))
            
            conn.commit()
        
        print("Database migration to v2 completed successfully.")

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    # User operations
    def add_user(self, username, password):
        """Add a new user."""
        with self.get_session() as session:
            # Check if this is the first user
            user_count = session.query(User).count()
            is_admin = (user_count == 0)

            user = User(username=username, is_admin=is_admin)
            user.set_password(password)
            session.add(user)
            session.commit()
            session.refresh(user)
            session.expunge(user)
            return user

    def get_user(self, user_id):
        """Get user by ID."""
        with self.get_session() as session:
            user = session.query(User).get(int(user_id))
            if user:
                session.expunge(user)
            return user

    def get_user_by_username(self, username):
        """Get user by username."""
        with self.get_session() as session:
            user = session.query(User).filter_by(username=username).first()
            if user:
                session.expunge(user)
            return user

    # Channel operations
    def add_channel(
        self, channel_id: str, channel_name: str, channel_url: str, user_id: Optional[int] = None
    ) -> Optional[YouTubeChannel]:
        """Add a new channel to follow.

        If the channel already exists globally, it will be associated with the user
        if not already associated.

        Returns:
            The YouTubeChannel object, or None if the user already follows this channel.
        """
        with self.get_session() as session:
            # Check if YouTube channel already exists globally
            youtube_channel = session.query(YouTubeChannel).filter_by(channel_id=channel_id).first()
            
            if not youtube_channel:
                # Create new global channel
                youtube_channel = YouTubeChannel(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    channel_url=channel_url,
                )
                session.add(youtube_channel)
                session.commit()
                session.refresh(youtube_channel)
            
            if user_id is not None:
                # Check if user already follows this channel
                user = session.query(User).get(user_id)
                if youtube_channel in user.youtube_channels:
                    return None
                
                # Associate user with channel
                user.youtube_channels.append(youtube_channel)
                session.commit()
            
            session.expunge(youtube_channel)
            return youtube_channel

    def get_all_channels(self, user_id: Optional[int] = None) -> List[YouTubeChannel]:
        """Get all followed channels.
        
        Args:
            user_id: If provided, only return channels for this user.
                    If None, return all unique YouTube channels globally.
        
        Returns:
            List of YouTubeChannel objects.
        """
        with self.get_session() as session:
            if user_id is not None:
                # Get channels for specific user via junction table
                user = session.query(User).get(user_id)
                if user:
                    channels = list(user.youtube_channels)
                    session.expunge_all()
                    return channels
                return []
            else:
                # Get all unique YouTube channels
                channels = session.query(YouTubeChannel).all()
                session.expunge_all()
                return channels

    def remove_channel(self, channel_id: str, user_id: Optional[int] = None) -> bool:
        """Remove a channel from a user's follows.

        If user_id is provided, only removes the association for that user.
        The channel and its videos remain for other users.

        Returns:
            True if removed, False if not found.
        """
        with self.get_session() as session:
            youtube_channel = session.query(YouTubeChannel).filter_by(channel_id=channel_id).first()
            if not youtube_channel:
                return False
            
            if user_id is not None:
                user = session.query(User).get(user_id)
                if user and youtube_channel in user.youtube_channels:
                    user.youtube_channels.remove(youtube_channel)
                    session.commit()
                    return True
            else:
                # Remove channel entirely (and all videos via cascade)
                session.delete(youtube_channel)
                session.commit()
                return True
            
            return False

    def update_channel_check_time(self, id: int):
        """Update the last_checked timestamp for a channel."""
        with self.get_session() as session:
            channel = session.query(YouTubeChannel).get(id)
            if channel:
                channel.last_checked = datetime.utcnow()
                session.commit()

    def is_channel_followed_by_user(self, channel_id: str, user_id: int) -> bool:
        """Check if a specific user follows a channel."""
        with self.get_session() as session:
            youtube_channel = session.query(YouTubeChannel).filter_by(channel_id=channel_id).first()
            if not youtube_channel:
                return False
            
            user = session.query(User).get(user_id)
            if not user:
                return False
            
            return youtube_channel in user.youtube_channels

    # Video operations
    def add_video(
        self,
        video_id: str,
        youtube_channel_id: int,
        title: str,
        published_at: datetime,
        url: str,
        duration: Optional[str] = None,
    ) -> Optional[Video]:
        """Add a new video.

        Returns:
            The created Video object, or None if it already exists.
        """
        with self.get_session() as session:
            existing = session.query(Video).filter_by(video_id=video_id).first()
            if existing:
                return None

            video = Video(
                video_id=video_id,
                youtube_channel_id=youtube_channel_id,
                title=title,
                published_at=published_at,
                url=url,
                duration=duration,
            )
            session.add(video)
            session.commit()
            session.refresh(video)
            return video

    def get_videos_without_transcripts(self, max_failed_attempts: int = 10) -> List[Video]:
        """Get all videos that don't have transcripts yet.
        
        Excludes videos that have exceeded the max failed attempts threshold.
        
        Args:
            max_failed_attempts: Maximum number of failed attempts before giving up.
        
        Returns:
            List of videos needing transcript fetching.
        """
        with self.get_session() as session:
            videos = (
                session.query(Video)
                .filter(~Video.transcript.has())
                .filter(Video.failed_attempts < max_failed_attempts)
                .all()
            )
            session.expunge_all()
            return videos

    def increment_video_failed_attempts(self, video_id: int) -> int:
        """Increment the failed attempts counter for a video.
        
        Args:
            video_id: The video ID to increment.
            
        Returns:
            The new failed attempts count.
        """
        with self.get_session() as session:
            video = session.query(Video).get(video_id)
            if video:
                video.failed_attempts = (video.failed_attempts or 0) + 1
                session.commit()
                return video.failed_attempts
            return 0

    def get_videos_without_summaries(self) -> List[Video]:
        """Get all videos that have transcripts but no summaries."""
        with self.get_session() as session:
            videos = (
                session.query(Video)
                .options(joinedload(Video.transcript), joinedload(Video.youtube_channel))
                .filter(Video.transcript.has())
                .filter(~Video.summary.has())
                .all()
            )
            session.expunge_all()
            return videos

    def get_recent_videos(self, limit: int = 20) -> List[Video]:
        """Get recent videos ordered by published date."""
        with self.get_session() as session:
            videos = (
                session.query(Video)
                .options(joinedload(Video.youtube_channel), joinedload(Video.summary))
                .order_by(Video.published_at.desc())
                .limit(limit)
                .all()
            )
            # Detach from session to avoid lazy loading issues
            session.expunge_all()
            return videos
    
    def get_videos_for_user(self, user_id: int, limit: int = 20) -> List[Video]:
        """Get recent videos for channels followed by a specific user."""
        with self.get_session() as session:
            videos = (
                session.query(Video)
                .join(Video.youtube_channel)
                .join(YouTubeChannel.users)
                .filter(User.id == user_id)
                .options(joinedload(Video.youtube_channel), joinedload(Video.summary))
                .order_by(Video.published_at.desc())
                .limit(limit)
                .all()
            )
            session.expunge_all()
            return videos

    # Transcript operations
    def add_transcript(
        self, video_id: int, transcript_text: str, language: Optional[str] = None
    ) -> Transcript:
        """Add a transcript for a video."""
        with self.get_session() as session:
            transcript = Transcript(
                video_id=video_id, transcript_text=transcript_text, language=language
            )
            session.add(transcript)
            session.commit()
            session.refresh(transcript)
            return transcript

    # Summary operations
    def add_summary(
        self, video_id: int, summary_text: str, key_points: List[str], model_used: str
    ) -> Summary:
        """Add a summary for a video."""
        with self.get_session() as session:
            summary = Summary(
                video_id=video_id, summary_text=summary_text, model_used=model_used
            )
            summary.set_key_points(key_points)
            session.add(summary)
            session.commit()
            session.refresh(summary)
            return summary

    def get_summaries_with_videos(self, limit: int = 20, user_id: Optional[int] = None) -> List[tuple]:
        """Get recent summaries with their video information.

        Returns:
            List of (Video, Summary) tuples.
        """
        with self.get_session() as session:
            query = (
                session.query(Video, Summary)
                .join(Summary)
                .join(Video.youtube_channel)
                .options(joinedload(Video.youtube_channel))
                .order_by(Summary.created_at.desc())
            )
            if user_id is not None:
                query = (
                    query.join(YouTubeChannel.users)
                    .filter(User.id == user_id)
                )

            results = query.limit(limit).all()
            session.expunge_all()
            return results

    def get_all_summaries_with_channels(self, user_id: Optional[int] = None) -> List[tuple]:
        """Get all summaries with their video and channel information.

        Used for grouping key points by creator/channel.

        Returns:
            List of (Video, Summary) tuples with eager-loaded channel data.
        """
        with self.get_session() as session:
            query = (
                session.query(Video, Summary)
                .join(Summary)
                .join(Video.youtube_channel)
                .options(joinedload(Video.youtube_channel))
                .order_by(Video.youtube_channel_id, Video.published_at.desc())
            )
            if user_id is not None:
                query = (
                    query.join(YouTubeChannel.users)
                    .filter(User.id == user_id)
                )

            results = query.all()
            session.expunge_all()
            return results

    # Run history operations
    def add_run_history(
        self,
        videos_found: int,
        videos_processed: int,
        errors: Optional[List[str]] = None,
        success: bool = True,
        duration_seconds: Optional[int] = None,
    ) -> RunHistory:
        """Add a run history entry."""
        with self.get_session() as session:
            run = RunHistory(
                videos_found=videos_found,
                videos_processed=videos_processed,
                success=success,
                duration_seconds=duration_seconds,
            )
            if errors:
                run.set_errors(errors)
            session.add(run)
            session.commit()
            session.refresh(run)
            return run

    def get_run_history(self, limit: int = 50) -> List[RunHistory]:
        """Get recent run history."""
        with self.get_session() as session:
            history = (
                session.query(RunHistory).order_by(RunHistory.run_timestamp.desc()).limit(limit).all()
            )
            session.expunge_all()
            return history

    # Telegram operations
    def set_telegram_verification_code(self, user_id: int, code: str) -> bool:
        """Set a verification code for Telegram linking."""
        with self.get_session() as session:
            user = session.query(User).get(user_id)
            if user:
                user.telegram_verification_code = code
                session.commit()
                return True
            return False

    def link_telegram_by_code(self, code: str, chat_id: str) -> Optional[tuple[int, str]]:
        """Link Telegram account by verification code.
        
        Returns:
            A tuple (user_id, username) if successfully linked, None otherwise.
        """
        with self.get_session() as session:
            user = session.query(User).filter_by(telegram_verification_code=code).first()
            if user:
                user.telegram_chat_id = chat_id
                user.telegram_enabled = True
                user.telegram_linked_at = datetime.utcnow()
                user.telegram_verification_code = None  # Clear the code
                session.commit()
                username = user.username
                user_id = user.id
                session.expunge(user)
                return (user_id, username)
            return None

    def unlink_telegram(self, user_id: int) -> bool:
        """Unlink Telegram account for a user."""
        with self.get_session() as session:
            user = session.query(User).get(user_id)
            if user:
                user.telegram_chat_id = None
                user.telegram_enabled = False
                user.telegram_linked_at = None
                session.commit()
                return True
            return False

    def get_users_for_telegram_notification(self, youtube_channel_id: int) -> List[User]:
        """Get all users who should be notified about a new video from a channel.
        
        Args:
            youtube_channel_id: The ID of the YouTube channel that has a new video.
            
        Returns:
            List of users with telegram_enabled=True who follow this channel.
        """
        with self.get_session() as session:
            users = (
                session.query(User)
                .join(User.youtube_channels)
                .filter(
                    User.telegram_enabled == True,
                    User.telegram_chat_id.isnot(None),
                    YouTubeChannel.id == youtube_channel_id
                )
                .all()
            )
            session.expunge_all()
            return users

    # Telegram Queue operations
    def add_telegram_message_to_queue(
        self,
        chat_id: str,
        message: str,
        user_id: Optional[int] = None
    ) -> TelegramQueue:
        """Add a message to the Telegram queue.
        
        Args:
            chat_id: Telegram chat ID to send message to.
            message: Message text to send.
            user_id: Optional user ID for reference.
            
        Returns:
            The created TelegramQueue entry.
        """
        with self.get_session() as session:
            queue_item = TelegramQueue(
                user_id=user_id,
                chat_id=chat_id,
                message=message,
                status="pending",
                retry_count=0
            )
            session.add(queue_item)
            session.commit()
            session.refresh(queue_item)
            return queue_item

    def get_pending_telegram_messages(self, limit: int = 50) -> List[TelegramQueue]:
        """Get pending messages from the queue.
        
        Args:
            limit: Maximum number of messages to retrieve.
            
        Returns:
            List of pending TelegramQueue entries.
        """
        with self.get_session() as session:
            messages = (
                session.query(TelegramQueue)
                .filter(TelegramQueue.status == "pending")
                .filter(TelegramQueue.retry_count < TelegramQueue.max_retries)
                .order_by(TelegramQueue.created_at)
                .limit(limit)
                .all()
            )
            session.expunge_all()
            return messages

    def mark_telegram_message_sent(self, message_id: int) -> bool:
        """Mark a message as successfully sent.
        
        Args:
            message_id: ID of the queue message.
            
        Returns:
            True if successful, False otherwise.
        """
        with self.get_session() as session:
            message = session.query(TelegramQueue).get(message_id)
            if message:
                message.status = "sent"
                message.sent_at = datetime.utcnow()
                session.commit()
                return True
            return False

    def mark_telegram_message_failed(
        self,
        message_id: int,
        error_message: str
    ) -> bool:
        """Mark a message as failed with error details.
        
        Args:
            message_id: ID of the queue message.
            error_message: Error description.
            
        Returns:
            True if successful, False otherwise.
        """
        with self.get_session() as session:
            message = session.query(TelegramQueue).get(message_id)
            if message:
                message.retry_count += 1
                message.error_message = error_message
                if message.retry_count >= message.max_retries:
                    message.status = "failed"
                session.commit()
                return True
            return False

    def get_stats(self, user_id: Optional[int] = None) -> dict:
        """Get database statistics."""
        with self.get_session() as session:
            if user_id is not None:
                # Get channels followed by user
                channel_count = (
                    session.query(YouTubeChannel)
                    .join(YouTubeChannel.users)
                    .filter(User.id == user_id)
                    .count()
                )
                
                # Get videos from channels followed by user
                video_query = (
                    session.query(Video)
                    .join(Video.youtube_channel)
                    .join(YouTubeChannel.users)
                    .filter(User.id == user_id)
                )
                
                transcript_query = (
                    session.query(Transcript)
                    .join(Video)
                    .join(YouTubeChannel)
                    .join(YouTubeChannel.users)
                    .filter(User.id == user_id)
                )
                
                summary_query = (
                    session.query(Summary)
                    .join(Video)
                    .join(YouTubeChannel)
                    .join(YouTubeChannel.users)
                    .filter(User.id == user_id)
                )
            else:
                channel_count = session.query(YouTubeChannel).count()
                video_query = session.query(Video)
                transcript_query = session.query(Transcript).join(Video)
                summary_query = session.query(Summary).join(Video)

            last_run = session.query(RunHistory).order_by(RunHistory.run_timestamp.desc()).first()
            if last_run:
                session.expunge(last_run)

            return {
                "total_channels": channel_count,
                "total_videos": video_query.count(),
                "videos_with_transcripts": transcript_query.count(),
                "videos_with_summaries": summary_query.count(),
                "total_runs": session.query(RunHistory).count(),
                "last_run": last_run,
            }
