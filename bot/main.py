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
from .table_manager import TableManager
from .members_manager import MembersManager
from .cache_manager import CacheManager
from .handlers import start_command, help_command, tasks_command, history_command, button_callback, setup_table_command, member_update_command
from .scheduler import check_and_send_notifications, refresh_cache_job

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
    table_manager: TableManager = application.bot_data['table_manager']
    members_manager: MembersManager = application.bot_data['members_manager']
    cache_manager: CacheManager = application.bot_data['cache_manager']
    
    members_manager.sync_with_table(table_manager.employees_cache)
    
    await cache_manager.initialize()
    
    scheduler = AsyncIOScheduler(timezone=config.timezone)
    
    scheduler.add_job(
        check_and_send_notifications,
        trigger=CronTrigger(minute='*/5', timezone=config.timezone),
        args=[application.bot, cache_manager, members_manager, config.timezone, config.notification_offset_minutes],
        id='check_notifications',
        name='Check and send notifications',
        replace_existing=True
    )
    
    scheduler.add_job(
        refresh_cache_job,
        trigger=CronTrigger(minute='*/5', timezone=config.timezone),
        args=[cache_manager],
        id='refresh_cache',
        name='Refresh cache from Google Sheets',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"Scheduler started. Checking every 5 minutes for shifts and refreshing cache")
    
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
    
    table_manager = TableManager(
        config.google_credentials_file,
        config.google_sheets_id
    )
    
    try:
        table_manager.connect()
    except Exception as e:
        logger.error(f"Failed to connect to Google Sheets: {e}")
        sys.exit(1)
    
    members_manager = MembersManager()
    
    cache_manager = CacheManager(table_manager)
    
    application = Application.builder().token(config.telegram_token).build()
    
    application.bot_data['table_manager'] = table_manager
    application.bot_data['members_manager'] = members_manager
    application.bot_data['cache_manager'] = cache_manager
    application.bot_data['config'] = config
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("tasks", tasks_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("setup_table", setup_table_command))
    application.add_handler(CommandHandler("member_update", member_update_command))
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