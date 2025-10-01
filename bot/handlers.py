from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime
import logging
from .sheets_manager import SheetsManager
from .table_setup import TableSetup
from .config import Config

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
    
    all_tasks = sheets_manager.get_equipment_tasks()
    task = next((t for t in all_tasks if t['row_index'] == row_index), None)
    
    if not task:
        await query.edit_message_text("❌ Задача не найдена.")
        return
    
    completed_at = datetime.now()
    success = sheets_manager.mark_task_completed(
        row_index, 
        user_shift['name'], 
        completed_at,
        task['period']
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
                days = _get_days_overdue(task, today)
                text += f"⚠️ <b>{task['name']}</b> <i>(просрочена на {days} дн.!)</i>\n"
            else:
                next_date = task.get('next_cleaning', '-')
                text += f"⏳ <b>{task['name']}</b> <i>(до {next_date})</i>\n"
            
            button = InlineKeyboardButton(
                text="✅ Выполнено",
                callback_data=f"complete_{task['row_index']}"
            )
            keyboard.append([button])
    
    text += f"\n<b>Выполнено: {completed_count}/{total_tasks}</b>"
    
    return text, keyboard


def _is_task_overdue(task: dict, today: datetime) -> bool:
    next_cleaning_str = task.get('next_cleaning', '')
    
    if not next_cleaning_str or next_cleaning_str == '-':
        return False
    
    try:
        next_cleaning = datetime.strptime(next_cleaning_str, "%d.%m.%Y")
        days_overdue = (today - next_cleaning).days
        return days_overdue > 0
    except ValueError:
        return False


def _get_days_overdue(task: dict, today: datetime) -> int:
    next_cleaning_str = task.get('next_cleaning', '')
    
    if not next_cleaning_str or next_cleaning_str == '-':
        return 0
    
    try:
        next_cleaning = datetime.strptime(next_cleaning_str, "%d.%m.%Y")
        return max(0, (today - next_cleaning).days)
    except ValueError:
        return 0


async def setup_table_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config: Config = context.bot_data['config']
    
    user_id = update.effective_user.id
    
    if config.admin_user_id is None:
        await update.message.reply_text(
            "❌ Команда недоступна: не указан ADMIN_USER_ID в настройках."
        )
        return
    
    if user_id != config.admin_user_id:
        await update.message.reply_text(
            "❌ У вас нет прав для выполнения этой команды."
        )
        return
    
    await update.message.reply_text("⏳ Начинаю проверку и настройку таблицы...")
    
    try:
        sheets_manager: SheetsManager = context.bot_data['sheets_manager']
        
        table_setup = TableSetup(sheets_manager.spreadsheet)
        report = table_setup.setup()
        
        sheets_manager.reload_employees()
        sheets_manager._initialize_next_cleaning_dates()
        
        await update.message.reply_text(f"{report}\n\n🔄 Данные перезагружены.")
        
    except Exception as e:
        logger.error(f"Error in setup_table_command: {e}")
        await update.message.reply_text(f"❌ Ошибка при настройке таблицы: {str(e)}")