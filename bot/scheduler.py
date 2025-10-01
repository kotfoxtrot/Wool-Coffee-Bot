from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime
import logging
import pytz
from .sheets_manager import SheetsManager

logger = logging.getLogger(__name__)


async def send_daily_notifications(bot: Bot, sheets_manager: SheetsManager, timezone_str: str):
    try:
        tz = pytz.timezone(timezone_str)
        today = datetime.now(tz)
        
        logger.info(f"Starting daily notifications for {today.strftime('%d.%m.%Y')}")
        
        shifts = sheets_manager.get_today_shifts(today)
        
        if not shifts:
            logger.info("No shifts found for today")
            return
        
        tasks = sheets_manager.get_tasks_for_today(today)
        
        if not tasks:
            logger.info("No tasks found for today")
            return
        
        for shift in shifts:
            await _send_employee_tasks(bot, shift, tasks, today)
        
        logger.info(f"Sent notifications to {len(shifts)} employees")
        
    except Exception as e:
        logger.error(f"Error in send_daily_notifications: {e}")


async def _send_employee_tasks(bot: Bot, shift: dict, tasks: list, today: datetime):
    try:
        username = shift['username']
        employee_name = shift['name']
        
        user = await _get_user_by_username(bot, username)
        
        if not user:
            logger.warning(f"User @{username} not found")
            return
        
        message_text = _build_notification_message(tasks, employee_name, today)
        keyboard = _build_tasks_keyboard(tasks)
        
        await bot.send_message(
            chat_id=user.id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
        logger.info(f"Notification sent to {employee_name} (@{username})")
        
    except Exception as e:
        logger.error(f"Error sending notification to {shift['name']}: {e}")


async def _get_user_by_username(bot: Bot, username: str):
    try:
        if username.startswith('@'):
            username = username[1:]
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        return None


def _build_notification_message(tasks: list, employee_name: str, today: datetime) -> str:
    total_tasks = len(tasks)
    
    text = f"☕️ <b>Доброе утро, {employee_name.split()[0]}!</b>\n"
    text += f"Задачи на {today.strftime('%d.%m.%Y')}:\n\n"
    
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