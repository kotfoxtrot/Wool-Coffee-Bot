from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
import logging
import pytz
from .sheets_manager import SheetsManager

logger = logging.getLogger(__name__)


async def check_and_send_notifications(bot: Bot, sheets_manager: SheetsManager, timezone_str: str, offset_minutes: int):
    try:
        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)
        target_time = now + timedelta(minutes=offset_minutes)
        
        logger.info(f"Checking for shifts starting at {target_time.strftime('%H:%M')}")
        
        shifts = sheets_manager.get_today_shifts(now)
        
        if not shifts:
            logger.info("No shifts found for today")
            return
        
        tasks = sheets_manager.get_tasks_for_today(now)
        
        if not tasks:
            logger.info("No tasks found for today")
        
        for shift in shifts:
            if _should_notify(shift, now, target_time, offset_minutes):
                await _send_employee_tasks(bot, shift, tasks, now)
        
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


async def _send_employee_tasks(bot: Bot, shift: dict, tasks: list, today: datetime):
    try:
        username = shift['username']
        employee_name = shift['name']
        start_time = shift['start_time']
        
        user = await _find_user_chat_id(bot, username)
        
        if not user:
            logger.warning(f"User @{username} ({employee_name}) not found or hasn't started the bot")
            return
        
        message_text = _build_notification_message(tasks, employee_name, start_time, today)
        keyboard = _build_tasks_keyboard(tasks)
        
        await bot.send_message(
            chat_id=user,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
        logger.info(f"Notification sent to {employee_name} (@{username})")
        
    except Exception as e:
        logger.error(f"Error sending notification to {shift['name']}: {e}")


async def _find_user_chat_id(bot: Bot, username: str):
    return None


def _build_notification_message(tasks: list, employee_name: str, start_time: str, today: datetime) -> str:
    first_name = employee_name.split()[0] if employee_name else "Коллега"
    total_tasks = len(tasks)
    
    text = f"☕️ <b>Доброе утро, {first_name}!</b>\n"
    text += f"Твоя смена начинается в {start_time}\n"
    text += f"Задачи на {today.strftime('%d.%m.%Y')}:\n\n"
    
    if not tasks:
        text += "✨ Сегодня нет задач по чистке!\n"
    else:
        for task in tasks:
            is_overdue = _is_task_overdue(task, today)
            
            if is_overdue:
                text += f"⏳ <b>{task['name']}</b> <i>(просрочена с {task['last_cleaned']}!)</i>\n"
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
    last_cleaned_str = task['last_cleaned']
    frequency = task['frequency'].lower()
    
    if not last_cleaned_str or last_cleaned_str == '-':
        return False
    
    try:
        last_cleaned = datetime.strptime(last_cleaned_str, "%d.%m.%Y")
        days_passed = (today - last_cleaned).days
        
        if frequency == 'ежедневно' and days_passed > 1:
            return True
        elif frequency == 'еженедельно' and days_passed > 7:
            return True
        elif frequency == 'ежемесячно' and days_passed > 30:
            return True
    except ValueError:
        return False
    
    return False