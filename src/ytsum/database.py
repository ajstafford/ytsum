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


class User(UserMixin, Base):
    """User account."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(128))
    created_at = Column(DateTime, default=datetime.utcnow)

    channels = relationship("Channel", back_populates="user")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class Channel(Base):
    """YouTube channel to follow."""

    __tablename__ = "channels"

    id = Column(Integer, primary_key=True)
    # channel_id is unique per user, not globally
    channel_id = Column(String, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    channel_name = Column(String, nullable=False)
    channel_url = Column(String, nullable=False)
    added_date = Column(DateTime, default=datetime.utcnow)
    last_checked = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="channels")
    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('channel_id', 'user_id', name='_user_channel_uc'),
    )

    def __repr__(self):
        return f"<Channel(name='{self.channel_name}', id='{self.channel_id}')>"


class Video(Base):
    """YouTube video from a followed channel."""

    __tablename__ = "videos"

    id = Column(Integer, primary_key=True)
    video_id = Column(String, unique=True, nullable=False, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    title = Column(String, nullable=False)
    published_at = Column(DateTime, nullable=False)
    duration = Column(String, nullable=True)  # ISO 8601 duration format
    url = Column(String, nullable=False)
    discovered_at = Column(DateTime, default=datetime.utcnow)

    channel = relationship("Channel", back_populates="videos")
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

        # Migration: Check schema
        inspector = inspect(self.engine)
        if "channels" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("channels")]
            if "user_id" not in columns:
                # Perform migration
                with self.engine.connect() as conn:
                    # 1. Rename old table
                    conn.execute(text("ALTER TABLE channels RENAME TO channels_old"))
                    conn.commit()
        
        # Create all tables (including new 'channels' if we renamed the old one)
        Base.metadata.create_all(self.engine)
        
        # Complete migration if needed
        inspector = inspect(self.engine)
        if "channels_old" in inspector.get_table_names():
             with self.engine.connect() as conn:
                # 3. Copy data
                conn.execute(text("""
                    INSERT INTO channels (id, channel_id, channel_name, channel_url, added_date, last_checked)
                    SELECT id, channel_id, channel_name, channel_url, added_date, last_checked
                    FROM channels_old
                """))
                
                # 4. Drop old table
                conn.execute(text("DROP TABLE channels_old"))
                conn.commit()

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    # User operations
    def add_user(self, username, password):
        """Add a new user."""
        with self.get_session() as session:
            user = User(username=username)
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
    ) -> Optional[Channel]:
        """Add a new channel to follow.

        Returns:
            The created Channel object, or None if it already exists for this user.
        """
        with self.get_session() as session:
            query = session.query(Channel).filter_by(channel_id=channel_id)
            if user_id is not None:
                query = query.filter_by(user_id=user_id)
            else:
                query = query.filter(Channel.user_id.is_(None))

            existing = query.first()
            if existing:
                return None

            channel = Channel(
                channel_id=channel_id, 
                channel_name=channel_name, 
                channel_url=channel_url,
                user_id=user_id
            )
            session.add(channel)
            session.commit()
            session.refresh(channel)
            return channel

    def get_all_channels(self, user_id: Optional[int] = None) -> List[Channel]:
        """Get all followed channels."""
        with self.get_session() as session:
            query = session.query(Channel)
            if user_id is not None:
                query = query.filter_by(user_id=user_id)
            channels = query.all()
            session.expunge_all()
            return channels

    def remove_channel(self, channel_id: str, user_id: Optional[int] = None) -> bool:
        """Remove a channel and all its videos.

        Returns:
            True if removed, False if not found.
        """
        with self.get_session() as session:
            query = session.query(Channel).filter_by(channel_id=channel_id)
            if user_id is not None:
                query = query.filter_by(user_id=user_id)
            
            channel = query.first()
            if channel:
                session.delete(channel)
                session.commit()
                return True
            return False

    def update_channel_check_time(self, id: int):
        """Update the last_checked timestamp for a channel."""
        with self.get_session() as session:
            channel = session.query(Channel).get(id)
            if channel:
                channel.last_checked = datetime.utcnow()
                session.commit()

    # Video operations
    def add_video(
        self,
        video_id: str,
        channel_id: int,
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
                channel_id=channel_id,
                title=title,
                published_at=published_at,
                url=url,
                duration=duration,
            )
            session.add(video)
            session.commit()
            session.refresh(video)
            return video

    def get_videos_without_transcripts(self) -> List[Video]:
        """Get all videos that don't have transcripts yet."""
        with self.get_session() as session:
            videos = session.query(Video).filter(~Video.transcript.has()).all()
            session.expunge_all()
            return videos

    def get_videos_without_summaries(self) -> List[Video]:
        """Get all videos that have transcripts but no summaries."""
        with self.get_session() as session:
            videos = (
                session.query(Video)
                .options(joinedload(Video.transcript))
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
                .options(joinedload(Video.channel), joinedload(Video.summary))
                .order_by(Video.published_at.desc())
                .limit(limit)
                .all()
            )
            # Detach from session to avoid lazy loading issues
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
                .join(Channel)
                .options(joinedload(Video.channel))
                .order_by(Summary.created_at.desc())
            )
            if user_id is not None:
                query = query.filter(Channel.user_id == user_id)

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
                .join(Channel)
                .options(joinedload(Video.channel))
                .order_by(Video.channel_id, Video.published_at.desc())
            )
            if user_id is not None:
                query = query.filter(Channel.user_id == user_id)

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

    def get_stats(self, user_id: Optional[int] = None) -> dict:
        """Get database statistics."""
        with self.get_session() as session:
            channel_query = session.query(Channel)
            video_query = session.query(Video).join(Channel)
            transcript_query = session.query(Transcript).join(Video).join(Channel)
            summary_query = session.query(Summary).join(Video).join(Channel)

            if user_id is not None:
                channel_query = channel_query.filter(Channel.user_id == user_id)
                video_query = video_query.filter(Channel.user_id == user_id)
                transcript_query = transcript_query.filter(Channel.user_id == user_id)
                summary_query = summary_query.filter(Channel.user_id == user_id)

            last_run = session.query(RunHistory).order_by(RunHistory.run_timestamp.desc()).first()
            if last_run:
                session.expunge(last_run)

            return {
                "total_channels": channel_query.count(),
                "total_videos": video_query.count(),
                "videos_with_transcripts": transcript_query.count(),
                "videos_with_summaries": summary_query.count(),
                "total_runs": session.query(RunHistory).count(),
                "last_run": last_run,
            }
