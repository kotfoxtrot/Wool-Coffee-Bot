from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
import logging
import pytz
from .table_manager import TableManager
from .members_manager import MembersManager
from .cache_manager import CacheManager

logger = logging.getLogger(__name__)


async def refresh_cache_job(cache_manager: CacheManager):
    try:
        logger.info("Running scheduled cache refresh")
        await cache_manager.refresh_from_sheets()
        logger.info("Cache refresh completed")
    except Exception as e:
        logger.error(f"Error in refresh_cache_job: {e}")


async def check_and_send_notifications(bot: Bot, cache_manager: CacheManager, members_manager: MembersManager, timezone_str: str, offset_minutes: int):
    try:
        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)
        target_time = now + timedelta(minutes=offset_minutes)
        
        logger.info(f"Checking for shifts starting at {target_time.strftime('%H:%M')}")
        
        cache_manager.invalidate_if_date_changed()
        
        shifts = cache_manager.cache.get('shifts_today', [])
        
        if not shifts:
            logger.info("No shifts found for today")
            return
        
        tasks = cache_manager.cache.get('tasks', [])
        tasks_today = [t for t in tasks if cache_manager._should_clean_today(t, now)]
        
        if not tasks_today:
            logger.info("No tasks found for today")
        
        for shift in shifts:
            if _should_notify(shift, now, target_time, offset_minutes):
                await _send_employee_tasks(bot, shift, tasks_today, now, members_manager)
        
    except Exception as e:
        logger.error(f"Error in check_and_send_notifications: {e}")


def _should_notify(shift: dict, now: datetime, target_time: datetime, offset_minutes: int) -> bool:
    try:
        start_time_str = shift['start_time']
        
        if not start_time_str:
            return False
        
        shift_start = datetime.strptime(start_time_str, "%H:%M").time()
        
        shift_datetime = now.replace(
            hour=shift_start.hour,
            minute=shift_start.minute,
            second=0,
            microsecond=0
        )
        
        time_diff = (shift_datetime - now).total_seconds() / 60
        
        if offset_minutes - 5 <= time_diff <= offset_minutes + 5:
            logger.info(f"Should notify {shift['name']} - shift starts at {start_time_str}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking notification time: {e}")
        return False


async def _send_employee_tasks(bot: Bot, shift: dict, tasks: list, today: datetime, members_manager: MembersManager):
    try:
        username = shift['username']
        employee_name = shift['name']
        start_time = shift['start_time']
        
        user_id = members_manager.get_user_id(username)
        
        if not user_id:
            logger.warning(f"User @{username} ({employee_name}) hasn't started the bot yet")
            return
        
        message_text = _build_notification_message(tasks, start_time, today)
        keyboard = _build_tasks_keyboard(tasks)
        
        await bot.send_message(
            chat_id=user_id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
        logger.info(f"Notification sent to {employee_name} (@{username})")
        
    except Exception as e:
        logger.error(f"Error sending notification to {shift['name']}: {e}")


def _build_notification_message(tasks: list, start_time: str, today: datetime) -> str:
    total_tasks = len(tasks)
    
    text = f"☕️ <b>Привет!</b>\n\n"
    text += f"Твоя смена начинается в {start_time}\n"
    text += f"Задачи на {today.strftime('%d.%m.%Y')}:\n\n"
    
    if not tasks:
        text += "Ура! Сегодня ничего не требуется 🎉\n"
    else:
        for task in tasks:
            is_overdue = _is_task_overdue(task, today)
            
            if is_overdue:
                days = (today - datetime.strptime(task['next_cleaning'], "%d.%m.%Y")).days
                text += f"⚠️ <b>{task['name']}</b> <i>(просрочена на {days} дн.!)</i>\n"
            else:
                text += f"⏳ <b>{task['name']}</b>\n"
    
        text += f"\n<b>Всего задач: {total_tasks}</b>"
    
    text += "\n\n💡 Нажми кнопку \"✅ Выполнено\" после завершения каждой задачи."
    
    return text


def _build_tasks_keyboard(tasks: list) -> list:
    keyboard = []
    
    for task in tasks:
        button = InlineKeyboardButton(
            text=f"✅ {task['name']}",
            callback_data=f"complete_{task['row_index']}"
        )
        keyboard.append([button])
    
    return keyboard


def _is_task_overdue(task: dict, today: datetime) -> bool:
    next_cleaning_str = task.get('next_cleaning', '')
    
    if not next_cleaning_str or next_cleaning_str == '-':
        return False
    
    try:
        next_cleaning = datetime.strptime(next_cleaning_str, "%d.%m.%Y")
        return (today - next_cleaning).days > 0
    except ValueError:
        return False