import logging
import sys
import os
from pathlib import Path
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from dotenv import load_dotenv

from .config import Config
from .sheets_manager import SheetsManager
from .handlers import start_command, help_command, tasks_command, history_command, button_callback, setup_table_command
from .scheduler import check_and_send_notifications

Path('./logs').mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/info.log', mode='w', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


async def post_init(application: Application):
    logger.info("Bot initialized successfully")
    
    config: Config = application.bot_data['config']
    sheets_manager: SheetsManager = application.bot_data['sheets_manager']
    
    scheduler = AsyncIOScheduler(timezone=config.timezone)
    
    scheduler.add_job(
        check_and_send_notifications,
        trigger=CronTrigger(minute='*/5', timezone=config.timezone),
        args=[application.bot, sheets_manager, config.timezone, config.notification_offset_minutes],
        id='check_notifications',
        name='Check and send notifications',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"Scheduler started. Checking every 5 minutes for shifts starting in {config.notification_offset_minutes} minutes")
    
    application.bot_data['scheduler'] = scheduler


async def post_shutdown(application: Application):
    scheduler = application.bot_data.get('scheduler')
    if scheduler:
        scheduler.shutdown()
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
    application.add_handler(CommandHandler("setup_table", setup_table_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
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
        logger.info("Bot stopped")


if __name__ == '__main__':
    main()