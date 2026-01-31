"""Telegram bot integration for ytsum notifications."""

import logging
import secrets
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)


def generate_verification_code() -> str:
    """Generate a unique verification code for Telegram linking."""
    return secrets.token_urlsafe(8)[:10].upper()


class TelegramBot:
    """Telegram bot for sending notifications."""

    def __init__(self, token: str, database=None):
        """Initialize the Telegram bot.

        Args:
            token: Bot token from BotFather.
            database: Database instance for linking users.
        """
        self.token = token
        self.database = database
        self.application: Optional[Application] = None

    async def start_bot(self):
        """Start the bot application."""
        if not self.token:
            logger.warning("No Telegram bot token configured")
            return

        try:
            self.application = Application.builder().token(self.token).build()
            
            # Add command handlers
            self.application.add_handler(CommandHandler("start", self._handle_start))
            self.application.add_handler(CommandHandler("help", self._handle_help))
            self.application.add_handler(CommandHandler("stop", self._handle_stop))
            self.application.add_handler(CommandHandler("verify", self._handle_verify))

            # Start the bot
            await self.application.initialize()
            await self.application.start()
            logger.info("Telegram bot started successfully")
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
            self.application = None

    async def stop_bot(self):
        """Stop the bot application."""
        if self.application:
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram bot stopped")

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - generates verification code."""
        chat_id = update.effective_chat.id
        
        message = (
            "👋 Welcome to ytsum notifications!\n\n"
            "To link your Telegram account with your ytsum profile, "
            "you need a verification code.\n\n"
            "1. Go to your ytsum web app Settings\n"
            "2. Click 'Link Telegram Account'\n"
            "3. A verification code will be generated\n"
            "4. Enter it here by typing: /verify YOUR_CODE\n\n"
            "Or if you already have a code, send it here with: /verify YOUR_CODE"
        )
        
        await update.message.reply_text(message)

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        message = (
            "🤖 ytsum Telegram Bot Commands:\n\n"
            "/start - Get instructions for linking your account\n"
            "/verify CODE - Link your account with a verification code\n"
            "/stop - Stop receiving notifications\n"
            "/help - Show this help message\n\n"
            "You'll receive notifications when new video summaries are available "
            "for channels you follow."
        )
        
        await update.message.reply_text(message)

    async def _handle_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command - unlink account."""
        chat_id = str(update.effective_chat.id)
        
        # Note: We can't unlink from Telegram side without knowing the user_id
        # User needs to unlink from web UI
        message = (
            "To stop receiving notifications, please unlink your Telegram account "
            "from the ytsum web app:\n\n"
            "1. Log into ytsum web app\n"
            "2. Go to Settings → Telegram\n"
            "3. Click 'Unlink Telegram Account'"
        )
        
        await update.message.reply_text(message)

    async def _handle_verify(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /verify command - link account with verification code."""
        chat_id = str(update.effective_chat.id)
        
        # Get the verification code from the command arguments
        if not context.args or len(context.args) == 0:
            await update.message.reply_text(
                "❌ Please provide a verification code.\n\n"
                "Usage: /verify YOUR_CODE\n\n"
                "Get your code from the ytsum web app Settings page."
            )
            return
        
        code = context.args[0].strip().upper()
        
        if not self.database:
            await update.message.reply_text(
                "❌ Error: Database not configured. Please contact the administrator."
            )
            return
        
        # Try to link the account
        user = self.database.link_telegram_by_code(code, chat_id)
        
        if user:
            await update.message.reply_text(
                f"✅ Success! Your Telegram account has been linked to ytsum user '{user.username}'.\n\n"
                f"You'll now receive notifications when new video summaries are available "
                f"for channels you follow.\n\n"
                f"Use /help to see available commands."
            )
            logger.info(f"Telegram account linked for user {user.username} (chat_id: {chat_id})")
        else:
            await update.message.reply_text(
                "❌ Invalid or expired verification code.\n\n"
                "Please generate a new code from the ytsum web app Settings page "
                "and try again."
            )
            logger.warning(f"Failed to link Telegram account with code: {code}")

    async def send_notification(
        self,
        chat_id: str,
        video_title: str,
        channel_name: str,
        duration: str,
        video_url: str,
        summary_url: str
    ):
        """Send a notification about a new summary.

        Args:
            chat_id: Telegram chat ID.
            video_title: Title of the video.
            channel_name: Name of the channel.
            duration: Video duration.
            video_url: Direct URL to the video.
            summary_url: URL to view the summary in ytsum.
        """
        if not self.application:
            logger.warning("Telegram bot not initialized, cannot send notification")
            return

        try:
            message = (
                f"🎥 *New Summary Available*\n\n"
                f"*{video_title}*\n"
                f"Channel: {channel_name}\n"
                f"Duration: {duration}\n\n"
                f"[Watch Video]({video_url})\n"
                f"[View Summary]({summary_url})"
            )
            
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=False
            )
            logger.info(f"Telegram notification sent to {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification to {chat_id}: {e}")


# Global bot instance
_bot_instance: Optional[TelegramBot] = None


def init_telegram_bot(token: str, database=None) -> TelegramBot:
    """Initialize the global Telegram bot instance.

    Args:
        token: Bot token from BotFather.
        database: Database instance.

    Returns:
        TelegramBot instance.
    """
    global _bot_instance
    _bot_instance = TelegramBot(token, database)
    return _bot_instance


def get_telegram_bot() -> Optional[TelegramBot]:
    """Get the global Telegram bot instance.

    Returns:
        TelegramBot instance or None if not initialized.
    """
    return _bot_instance
