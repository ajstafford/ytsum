"""Web interface for ytsum using Flask."""

import logging
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy.orm import joinedload
from functools import wraps

from .config import get_config
from .database import YouTubeChannel, Database, Video, User
from .youtube import YouTubeClient
from .telegram import generate_verification_code

logger = logging.getLogger(__name__)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            logger.warning(f"Unauthorized access attempt to {request.endpoint} by user {current_user if current_user.is_authenticated else 'Anonymous'}")
            flash("You do not have permission to access this page.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function


def create_app(db_path=None):
    """Create and configure the Flask application."""
    import os
    import secrets
    
    app = Flask(__name__)
    # Generate a random secret key if not provided via environment variable
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.init_app(app)

    # Load config
    config = get_config()

    # Initialize database
    db = Database(db_path or config.database_path)

    # Telegram bot runs in a separate container, no need to start here

    @login_manager.user_loader
    def load_user(user_id):
        return db.get_user(int(user_id))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")
            user = db.get_user_by_username(username)
            
            if user and user.check_password(password):
                login_user(user)
                next_page = request.args.get("next")
                return redirect(next_page or url_for("index"))
            flash("Invalid username or password", "danger")
        
        return render_template("login.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
            
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")
            
            if not username or not password:
                flash("Username and password are required", "warning")
            elif db.get_user_by_username(username):
                flash("Username already exists", "warning")
            else:
                db.add_user(username, password)
                flash("Registration successful! Please login.", "success")
                return redirect(url_for("login"))
                
        return render_template("register.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def index():
        """Dashboard page."""
        # TODO: Update get_stats to support user_id
        stats = db.get_stats(user_id=current_user.id)

        # Get recent summaries
        recent_summaries = db.get_summaries_with_videos(limit=10, user_id=current_user.id)

        return render_template(
            "dashboard.html",
            stats=stats,
            recent_summaries=recent_summaries,
        )

    @app.route("/channels")
    @login_required
    def channels():
        """Channels management page."""
        channels_list = db.get_all_channels(user_id=current_user.id)
        return render_template("channels.html", channels=channels_list)

    @app.route("/channels/add", methods=["POST"])
    @login_required
    def add_channel():
        """Add a new channel."""
        channel_input = request.form.get("channel_input", "").strip()

        if not channel_input:
            flash("Please enter a channel URL or ID", "warning")
            return redirect(url_for("channels"))

        try:
            yt_client = YouTubeClient(
                api_key=config.youtube_api_key,
                proxy_list=config.proxy_list,
                proxy_rate_limit=config.proxy_rate_limit,
                proxy_max_retries=config.proxy_max_retries,
                proxy_retry_delay=config.proxy_retry_delay,
            )

            # Extract channel ID if it's a URL
            channel_id = yt_client.extract_channel_id(channel_input)
            if not channel_id:
                channel_id = channel_input

            # Get channel info
            channel_info = yt_client.get_channel_info(channel_id)

            if not channel_info:
                flash("Channel not found. Please check the URL or ID.", "danger")
                return redirect(url_for("channels"))

            # Add to database
            result = db.add_channel(
                channel_info["id"], channel_info["name"], channel_info["url"], user_id=current_user.id
            )

            if result:
                flash(f"Added channel: {channel_info['name']}", "success")
            else:
                flash("Channel already exists", "warning")

        except Exception as e:
            logger.error(f"Error adding channel: {e}")
            flash(f"Error adding channel: {str(e)}", "danger")

        return redirect(url_for("channels"))

    @app.route("/channels/delete/<channel_id>", methods=["POST"])
    @login_required
    def delete_channel(channel_id):
        """Delete a channel."""
        try:
            if db.remove_channel(channel_id, user_id=current_user.id):
                flash("Channel removed successfully", "success")
            else:
                flash("Channel not found", "warning")
        except Exception as e:
            logger.error(f"Error deleting channel: {e}")
            flash(f"Error deleting channel: {str(e)}", "danger")

        return redirect(url_for("channels"))

    @app.route("/videos")
    @login_required
    def videos():
        """Videos list page."""
        # Get filter parameters
        search = request.args.get("search", "").strip()
        has_summary = request.args.get("has_summary", "all")
        channel_filter = request.args.get("channel", "all")
        page = int(request.args.get("page", 1))
        per_page = 50

        # Get all channels for the dropdown
        all_channels = db.get_all_channels(user_id=current_user.id)

        # Get videos
        with db.get_session() as session:
            query = (
                session.query(Video)
                .join(Video.youtube_channel)
                .join(YouTubeChannel.users)
                .filter(User.id == current_user.id)
                .options(joinedload(Video.youtube_channel), joinedload(Video.summary))
                .order_by(Video.published_at.desc())
            )

            # Apply filters (case-insensitive)
            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    (Video.title.ilike(search_pattern)) |
                    (Video.youtube_channel.has(YouTubeChannel.channel_name.ilike(search_pattern)))
                )

            if channel_filter != "all":
                # Ensure the filtered channel belongs to the user (implicit via above join, but good to check)
                query = query.filter(Video.youtube_channel_id == int(channel_filter))

            if has_summary == "yes":
                query = query.filter(Video.summary.has())
            elif has_summary == "no":
                query = query.filter(~Video.summary.has())

            # Pagination
            total = query.count()
            videos_list = query.offset((page - 1) * per_page).limit(per_page).all()
            session.expunge_all()

        total_pages = (total + per_page - 1) // per_page

        return render_template(
            "videos.html",
            videos=videos_list,
            channels=all_channels,
            search=search,
            has_summary=has_summary,
            channel_filter=channel_filter,
            page=page,
            total_pages=total_pages,
        )

    @app.route("/summary/<int:video_id>")
    @login_required
    def summary(video_id):
        """Individual summary view page."""
        with db.get_session() as session:
            video = (
                session.query(Video)
                .join(Video.youtube_channel)
                .join(YouTubeChannel.users)
                .filter(User.id == current_user.id)
                .options(joinedload(Video.youtube_channel), joinedload(Video.summary))
                .filter(Video.id == video_id)
                .first()
            )

            if not video:
                flash("Video not found", "danger")
                return redirect(url_for("videos"))

            # Extract data before expunging
            video_data = {
                "id": video.id,
                "title": video.title,
                "url": video.url,
                "published_at": video.published_at,
                "channel_name": video.youtube_channel.channel_name,
                "has_summary": video.summary is not None,
            }

            if video.summary:
                video_data["summary_text"] = video.summary.summary_text
                video_data["key_points"] = video.summary.get_key_points()
                video_data["model_used"] = video.summary.model_used
                video_data["created_at"] = video.summary.created_at

            session.expunge_all()

        return render_template("summary.html", video=video_data)

    @app.route("/key-points-by-creator")
    @login_required
    def key_points_by_creator():
        """View all key points grouped by creator/channel."""
        # Get filter parameter
        channel_filter = request.args.get("channel", "all")

        # Get all channels for the dropdown
        all_channels = db.get_all_channels(user_id=current_user.id)

        # Get all summaries with channels
        results = db.get_all_summaries_with_channels(user_id=current_user.id)

        # Group results by channel
        grouped_data = {}
        for video, summary in results:
            if summary is None:
                continue

            channel_name = video.youtube_channel.channel_name
            if channel_name not in grouped_data:
                grouped_data[channel_name] = {
                    "channel_id": video.youtube_channel.id,
                    "videos": [],
                }

            grouped_data[channel_name]["videos"].append({
                "title": video.title,
                "url": video.url,
                "published_at": video.published_at,
                "key_points": summary.get_key_points(),
                "summary_id": summary.id,
            })

        # Filter by channel if specified
        if channel_filter != "all":
            filtered_data = {}
            for channel_name, data in grouped_data.items():
                if str(data["channel_id"]) == channel_filter:
                    filtered_data[channel_name] = data
            grouped_data = filtered_data

        # Sort channels by name
        sorted_channels = sorted(grouped_data.items())

        return render_template(
            "key_points.html",
            grouped_data=sorted_channels,
            channels=all_channels,
            channel_filter=channel_filter,
        )

    @app.route("/history")
    @login_required
    @admin_required
    def history():
        """Run history page."""
        # TODO: Filter history by user if we implement user-specific runs
        history_list = db.get_run_history(limit=100)
        return render_template("history.html", history=history_list)

    @app.route("/run", methods=["POST"])
    @login_required
    @admin_required
    def run_check():
        """Trigger a manual run."""
        try:
            from .scheduler import check_and_process

            flash("Starting check and process... This may take a few minutes.", "info")

            # Run in background (simple approach - could be improved with Celery)
            result = check_and_process(db, config)

            flash(
                f"Processing complete! Found: {result['videos_found']}, "
                f"Processed: {result['videos_processed']}",
                "success",
            )

            if result["errors"]:
                flash(f"Encountered {len(result['errors'])} errors", "warning")

        except Exception as e:
            logger.error(f"Error running check: {e}")
            flash(f"Error running check: {str(e)}", "danger")

        return redirect(url_for("index"))

    @app.route("/api/stats")
    @login_required
    def api_stats():
        """API endpoint for stats (for AJAX updates)."""
        stats = db.get_stats(user_id=current_user.id)
        
        response_data = {
            "total_channels": stats["total_channels"],
            "total_videos": stats["total_videos"],
            "videos_with_transcripts": stats["videos_with_transcripts"],
            "videos_with_summaries": stats["videos_with_summaries"],
        }
        
        if current_user.is_admin:
            response_data["total_runs"] = stats["total_runs"]
            
        return jsonify(response_data)

    @app.route("/settings")
    @login_required
    def settings():
        """User settings page."""
        config = get_config()
        return render_template(
            "settings.html",
            telegram_enabled=config.telegram_enabled,
            user=current_user
        )

    @app.route("/settings/telegram/generate-code", methods=["POST"])
    @login_required
    def generate_telegram_code():
        """Generate a new Telegram verification code."""
        code = generate_verification_code()
        db.set_telegram_verification_code(current_user.id, code)
        flash(f"Your Telegram verification code is: {code}", "info")
        flash("Open Telegram and message this code to your bot to link your account.", "info")
        return redirect(url_for("settings"))

    @app.route("/settings/telegram/unlink", methods=["POST"])
    @login_required
    def unlink_telegram():
        """Unlink Telegram account."""
        if db.unlink_telegram(current_user.id):
            flash("Telegram account unlinked successfully.", "success")
        else:
            flash("Failed to unlink Telegram account.", "danger")
        return redirect(url_for("settings"))

    @app.route("/settings/telegram/test-message", methods=["POST"])
    @login_required
    def test_telegram_message():
        """Send a test Telegram message to verify notifications are working."""
        user = current_user
        
        if not user.telegram_enabled or not user.telegram_chat_id:
            flash("Telegram is not configured. Please link your Telegram account first.", "warning")
            return redirect(url_for("settings"))
        
        try:
            message = "🧪 Test message from ytsum! Your Telegram notifications are working correctly."
            
            # Add message to the queue - bot runs in separate container
            db.add_telegram_message_to_queue(
                chat_id=user.telegram_chat_id,
                message=message,
                user_id=user.id
            )
            flash("Test message queued successfully! Check your Telegram.", "success")
        except Exception as e:
            logger.error(f"Failed to queue test Telegram message: {e}")
            flash(f"Failed to queue test message: {str(e)}", "danger")
        
        return redirect(url_for("settings"))

    @app.route("/telegram/webhook", methods=["POST"])
    def telegram_webhook():
        """Handle Telegram webhook updates."""
        # Telegram bot runs in separate container - webhook processed there
        update_data = request.get_json()
        logger.info(f"Received Telegram webhook: {update_data}")
        return "OK", 200

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Server error: {e}")
        return render_template("500.html"), 500

    return app


def run_web_server(host="0.0.0.0", port=5000, debug=False):
    """Run the Flask web server.

    Args:
        host: Host to bind to (0.0.0.0 for all interfaces).
        port: Port to listen on.
        debug: Enable debug mode.
    """
    app = create_app()
    app.run(host=host, port=port, debug=debug)
