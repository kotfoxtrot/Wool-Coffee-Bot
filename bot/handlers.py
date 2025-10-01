from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime
import logging
from .sheets_manager import SheetsManager

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """
☕️ Добро пожаловать в систему управления чисткой оборудования!

Я помогу тебе отслеживать задачи по чистке оборудования в кофейне.

📋 Доступные команды:
/tasks - Показать мои задачи на сегодня
/history - История выполненных задач (7 дней)
/help - Справка по командам

Каждое утро я буду присылать список задач на день.
Просто нажми кнопку "✅ Выполнено" когда закончишь задачу!
    """
    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 Справка по командам:

/start - Приветствие и инструкция
/tasks - Показать задачи на сегодня
/history - История за последние 7 дней
/help - Эта справка

🔔 Как работает бот:
• Каждое утро я проверяю твою смену
• Отправляю список задач по чистке
• Ты отмечаешь выполненные задачи кнопками
• Данные автоматически сохраняются в таблицу

⚠️ Важно:
• Красный текст = просроченная задача
• ✅ = задача выполнена
• ⏳ = задача в ожидании
    """
    await update.message.reply_text(help_text)


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheets_manager: SheetsManager = context.bot_data['sheets_manager']
    username = update.effective_user.username
    
    if not username:
        await update.message.reply_text(
            "❌ У тебя не установлен Telegram username. "
            "Пожалуйста, установи username в настройках Telegram."
        )
        return
    
    today = datetime.now()
    shifts = sheets_manager.get_today_shifts(today)
    
    user_shift = next((s for s in shifts if s['username'].lower() == username.lower()), None)
    
    if not user_shift:
        await update.message.reply_text(
            f"📅 На {today.strftime('%d.%m.%Y')} у тебя нет смены или ты не добавлен в расписание."
        )
        return
    
    tasks = sheets_manager.get_tasks_for_today(today)
    
    if not tasks:
        await update.message.reply_text(
            f"✨ На {today.strftime('%d.%m.%Y')} нет задач по чистке!"
        )
        return
    
    message_text, keyboard = _build_tasks_message(tasks, user_shift['name'], today)
    
    await update.message.reply_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheets_manager: SheetsManager = context.bot_data['sheets_manager']
    username = update.effective_user.username
    
    if not username:
        await update.message.reply_text("❌ У тебя не установлен Telegram username.")
        return
    
    history = sheets_manager.get_history(days=7)
    
    if not history:
        await update.message.reply_text("📜 История за последние 7 дней пуста.")
        return
    
    user_history = [h for h in history if username.lower() in h.get('completed_by', '').lower()]
    
    if not user_history:
        await update.message.reply_text("📜 Ты не выполнял задач за последние 7 дней.")
        return
    
    text = "📜 <b>История выполненных задач (7 дней):</b>\n\n"
    for item in user_history:
        status_icon = item.get('status', '✅')
        text += f"{status_icon} <b>{item['name']}</b>\n"
        text += f"   📅 {item['date']}\n"
        text += f"   👤 {item['completed_by']}\n\n"
    
    await update.message.reply_text(text, parse_mode='HTML')


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    sheets_manager: SheetsManager = context.bot_data['sheets_manager']
    
    callback_data = query.data
    
    if not callback_data.startswith('complete_'):
        return
    
    row_index = int(callback_data.split('_')[1])
    username = update.effective_user.username
    
    today = datetime.now()
    shifts = sheets_manager.get_today_shifts(today)
    user_shift = next((s for s in shifts if s['username'].lower() == username.lower()), None)
    
    if not user_shift:
        await query.edit_message_text("❌ Ты не найден в расписании на сегодня.")
        return
    
    completed_at = datetime.now()
    success = sheets_manager.mark_task_completed(
        row_index, 
        user_shift['name'], 
        completed_at
    )
    
    if success:
        tasks = sheets_manager.get_tasks_for_today(today)
        message_text, keyboard = _build_tasks_message(tasks, user_shift['name'], today)
        
        await query.edit_message_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    else:
        await query.edit_message_text("❌ Ошибка при обновлении данных. Попробуй позже.")


def _build_tasks_message(tasks: list, employee_name: str, today: datetime):
    completed_tasks = [t for t in tasks if t['status'] == '✅']
    total_tasks = len(tasks)
    completed_count = len(completed_tasks)
    
    text = f"☕️ <b>Доброе утро, {employee_name.split()[0]}!</b>\n"
    text += f"Задачи на {today.strftime('%d.%m.%Y')}:\n\n"
    
    keyboard = []
    
    for task in tasks:
        is_completed = task['status'] == '✅'
        is_overdue = _is_task_overdue(task, today)
        
        if is_completed:
            completed_time = "сегодня"
            text += f"✅ <b>{task['name']}</b> (выполнено {completed_time})\n"
        else:
            if is_overdue:
                days_overdue = _get_days_overdue(task, today)
                text += f"⏳ <b>{task['name']}</b> <i>(просрочена с {task['last_cleaned']}!)</i>\n"
            else:
                text += f"⏳ <b>{task['name']}</b>\n"
            
            button = InlineKeyboardButton(
                text="✅ Выполнено",
                callback_data=f"complete_{task['row_index']}"
            )
            keyboard.append([button])
    
    text += f"\n<b>Выполнено: {completed_count}/{total_tasks}</b>"
    
    return text, keyboard


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


def _get_days_overdue(task: dict, today: datetime) -> int:
    last_cleaned_str = task['last_cleaned']
    
    if not last_cleaned_str or last_cleaned_str == '-':
        return 0
    
    try:
        last_cleaned = datetime.strptime(last_cleaned_str, "%d.%m.%Y")
        return (today - last_cleaned).days
    except ValueError:
        return 0