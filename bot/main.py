import logging
import sys
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from dotenv import load_dotenv

from .config import Config
from .sheets_manager import SheetsManager
from .handlers import start_command, help_command, tasks_command, history_command, button_callback
from .scheduler import send_daily_notifications

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def setup_scheduler(application: Application, config: Config, sheets_manager: SheetsManager):
    scheduler = AsyncIOScheduler(timezone=config.timezone)
    
    hour, minute = map(int, config.notification_time.split(':'))
    
    scheduler.add_job(
        send_daily_notifications,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=config.timezone),
        args=[application.bot, sheets_manager, config.timezone],
        id='daily_notifications',
        name='Send daily task notifications',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"Scheduler started. Notifications will be sent at {config.notification_time} {config.timezone}")
    
    return scheduler


async def post_init(application: Application):
    logger.info("Bot initialized successfully")


async def post_shutdown(application: Application):
    logger.info("Bot shutdown completed")


def main():
    load_dotenv()
    
    config = Config.from_env()
    
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    sheets_manager = SheetsManager(
        config.google_credentials_file,
        config.google_sheets_id
    )
    
    try:
        sheets_manager.connect()
    except Exception as e:
        logger.error(f"Failed to connect to Google Sheets: {e}")
        sys.exit(1)
    
    application = Application.builder().token(config.telegram_token).build()
    
    application.bot_data['sheets_manager'] = sheets_manager
    application.bot_data['config'] = config
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("tasks", tasks_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    scheduler = setup_scheduler(application, config, sheets_manager)
    
    application.post_init = post_init
    application.post_shutdown = post_shutdown
    
    logger.info("Starting bot...")
    
    try:
        application.run_polling(
            allowed_updates=['message', 'callback_query'],
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        scheduler.shutdown()
        logger.info("Bot stopped")


if __name__ == '__main__':
    main()