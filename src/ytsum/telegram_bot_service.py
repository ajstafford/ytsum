"""Telegram Bot Service - Runs as a separate container to handle all Telegram communication.

This service acts as a message broker:
- INCOMING: Polls Telegram API for user commands (/verify, /start, etc.)
- OUTGOING: Polls database queue and sends messages to users

Runs continuously in its own Docker container.
"""

import asyncio
import logging
import signal
import sys
import time
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .config import get_config
from .database import Database

logger = logging.getLogger(__name__)


class TelegramBotService:
    """Telegram bot service that handles both incoming and outgoing messages."""

    def __init__(self, token: str, database: Database):
        """Initialize the Telegram bot service.

        Args:
            token: Bot token from BotFather.
            database: Database instance for storing queue and linking users.
        """
        self.token = token
        self.database = database
        self.application: Optional[Application] = None
        self.running = False
        self.outgoing_task = None
        self._shutdown_event = asyncio.Event()

    async def start(self):
        """Start the Telegram bot service with both incoming and outgoing handlers."""
        if not self.token:
            logger.error("No Telegram bot token configured. Cannot start service.")
            return False

        try:
            logger.info("Initializing Telegram bot application...")
            self.application = Application.builder().token(self.token).build()

            # Add command handlers for incoming messages
            self.application.add_handler(CommandHandler("start", self._handle_start))
            self.application.add_handler(CommandHandler("help", self._handle_help))
            self.application.add_handler(CommandHandler("stop", self._handle_stop))
            self.application.add_handler(CommandHandler("verify", self._handle_verify))

            # Initialize and start the application
            await self.application.initialize()
            await self.application.start()

            # Start polling for incoming messages
            logger.info("Starting incoming message polling...")
            await self.application.updater.start_polling(
                poll_interval=1.0,
                timeout=10,
                bootstrap_retries=-1,  # Retry forever
                drop_pending_updates=True  # Don't process old updates on restart
            )

            # Start outgoing message processor in background
            logger.info("Starting outgoing message processor...")
            self.outgoing_task = asyncio.create_task(self._process_outgoing_messages())

            self.running = True
            logger.info("✅ Telegram bot service started successfully")
            logger.info("📥 Listening for incoming messages (commands)")
            logger.info("📤 Processing outgoing message queue")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to start Telegram bot service: {e}", exc_info=True)
            self.application = None
            return False

    async def stop(self):
        """Stop the Telegram bot service gracefully."""
        logger.info("Stopping Telegram bot service...")
        self.running = False
        self._shutdown_event.set()

        try:
            # Stop outgoing processor
            if self.outgoing_task:
                self.outgoing_task.cancel()
                try:
                    await self.outgoing_task
                except asyncio.CancelledError:
                    pass
                logger.info("Outgoing message processor stopped")

            # Stop polling and application
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                logger.info("Telegram application stopped")

            logger.info("✅ Telegram bot service stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping Telegram bot service: {e}", exc_info=True)

    async def _process_outgoing_messages(self):
        """Background task to process outgoing messages from the queue."""
        logger.info("Outgoing message processor started (checking queue every 5 seconds)")

        while self.running and not self._shutdown_event.is_set():
            try:
                # Get pending messages from queue
                pending_messages = self.database.get_pending_telegram_messages(limit=50)

                if pending_messages:
                    logger.info(f"📤 Found {len(pending_messages)} pending messages to send")

                    for msg in pending_messages:
                        try:
                            # Send the message
                            await self.application.bot.send_message(
                                chat_id=msg.chat_id,
                                text=msg.message,
                                parse_mode="Markdown",
                                disable_web_page_preview=False
                            )

                            # Mark as sent
                            self.database.mark_telegram_message_sent(msg.id)
                            logger.info(f"✅ Message sent to chat {msg.chat_id}")

                            # Small delay to avoid rate limiting
                            await asyncio.sleep(0.5)

                        except Exception as e:
                            error_msg = str(e)
                            logger.error(f"❌ Failed to send message to {msg.chat_id}: {error_msg}")
                            self.database.mark_telegram_message_failed(msg.id, error_msg)

                # Wait before checking again
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=5.0
                )

            except asyncio.TimeoutError:
                # Normal timeout, continue loop
                continue
            except asyncio.CancelledError:
                logger.info("Outgoing message processor cancelled")
                break
            except Exception as e:
                logger.error(f"Error in outgoing message processor: {e}", exc_info=True)
                await asyncio.sleep(5)  # Wait before retrying

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        logger.info(f"Received /start from chat {update.effective_chat.id}")

        message = (
            "👋 Welcome to ytsum notifications!\n\n"
            "To link your Telegram account with your ytsum profile, "
            "you need a verification code.\n\n"
            "1. Go to your ytsum web app Settings\n"
            "2. Click 'Link Telegram Account'\n"
            "3. A verification code will be generated\n"
            "4. Send it here using: /verify YOUR_CODE\n\n"
            "Use /help to see all available commands."
        )

        await update.message.reply_text(message)
        logger.info(f"Sent welcome message to chat {update.effective_chat.id}")

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        logger.info(f"Received /help from chat {update.effective_chat.id}")

        message = (
            "🤖 ytsum Telegram Bot Commands:\n\n"
            "/start - Get started with ytsum notifications\n"
            "/verify CODE - Link your account with verification code\n"
            "/stop - Information about stopping notifications\n"
            "/help - Show this help message\n\n"
            "Once linked, you'll receive notifications when new video "
            "summaries are available for channels you follow."
        )

        await update.message.reply_text(message)

    async def _handle_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command."""
        logger.info(f"Received /stop from chat {update.effective_chat.id}")

        message = (
            "🛑 To stop receiving notifications:\n\n"
            "1. Log into ytsum web app\n"
            "2. Go to Settings → Telegram\n"
            "3. Click 'Unlink Telegram Account'\n\n"
            "You can always re-link your account later."
        )

        await update.message.reply_text(message)

    async def _handle_verify(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /verify command - link account with verification code."""
        chat_id = str(update.effective_chat.id)
        logger.info(f"Received /verify from chat {chat_id}")

        # Get the verification code from command arguments
        if not context.args or len(context.args) == 0:
            logger.warning(f"No verification code provided by chat {chat_id}")
            await update.message.reply_text(
                "❌ Please provide a verification code.\n\n"
                "Usage: /verify YOUR_CODE\n\n"
                "Get your code from the ytsum web app Settings page."
            )
            return

        code = context.args[0].strip().upper()
        logger.info(f"Processing verification code '{code}' from chat {chat_id}")

        if not self.database:
            logger.error("Database not available for verification")
            await update.message.reply_text(
                "❌ Error: Database not configured. Please contact the administrator."
            )
            return

        # Try to link the account
        result = self.database.link_telegram_by_code(code, chat_id)

        if result:
            user_id, username = result
            success_msg = (
                f"✅ Success! Your Telegram account has been linked to ytsum user '{username}'.\n\n"
                f"You'll now receive notifications when new video summaries are available "
                f"for channels you follow.\n\n"
                f"Use /help to see available commands."
            )
            await update.message.reply_text(success_msg)
            logger.info(f"✅ Successfully linked Telegram for user {username} (chat_id: {chat_id})")
        else:
            await update.message.reply_text(
                "❌ Invalid or expired verification code.\n\n"
                "Please generate a new code from the ytsum web app Settings page "
                "and try again."
            )
            logger.warning(f"❌ Failed to link with code '{code}' - invalid or expired")


def setup_logging():
    """Setup logging for the Telegram bot service."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    # Set specific loggers
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)


async def run_telegram_bot_service():
    """Main entry point for the Telegram bot service."""
    setup_logging()
    logger.info("=" * 60)
    logger.info("Starting ytsum Telegram Bot Service")
    logger.info("=" * 60)

    # Load configuration
    config = get_config()

    if not config.telegram_bot_token:
        logger.error("❌ TELEGRAM_BOT_TOKEN not configured. Cannot start service.")
        logger.error("Please set TELEGRAM_BOT_TOKEN in your environment or docker.env")
        sys.exit(1)

    logger.info(f"✅ Configuration loaded (token: {config.telegram_bot_token[:15]}...)")

    # Initialize database
    logger.info(f"Connecting to database: {config.database_path}")
    database = Database(config.database_path)
    logger.info("✅ Database connected")

    # Create and start bot service
    service = TelegramBotService(config.telegram_bot_token, database)

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(service.stop())

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Start the service
    if not await service.start():
        logger.error("Failed to start service. Exiting.")
        sys.exit(1)

    # Keep running until shutdown signal
    try:
        while service.running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await service.stop()

    logger.info("=" * 60)
    logger.info("Telegram Bot Service stopped")
    logger.info("=" * 60)
