from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime
import logging
import asyncio
from .table_manager import TableManager
from .table_setup import TableSetup
from .config import Config
from .members_manager import MembersManager
from .cache_manager import CacheManager

logger = logging.getLogger(__name__)


async def check_employee(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    members_manager: MembersManager = context.bot_data['members_manager']
    username = update.effective_user.username
    
    if not username:
        await update.message.reply_text(
            "❌ У тебя не установлен Telegram username. "
            "Пожалуйста, установи username в настройках Telegram."
        )
        return False
    
    if not members_manager.is_member(username):
        await update.message.reply_text(
            "❌ Доступ запрещен. Этот бот доступен только для сотрудников."
        )
        return False
    
    return True


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    members_manager: MembersManager = context.bot_data['members_manager']
    table_manager: TableManager = context.bot_data['table_manager']
    
    username = update.effective_user.username
    user_id = update.effective_user.id
    
    if not username:
        await update.message.reply_text(
            "❌ У тебя не установлен Telegram username. "
            "Пожалуйста, установи username в настройках Telegram."
        )
        return
    
    employee = table_manager.get_employee_by_username(username)
    
    if not employee:
        await update.message.reply_text(
            "❌ Доступ запрещен. Этот бот доступен только для сотрудников."
        )
        return
    
    members_manager.add_member(username, user_id, employee['name'])
    
    welcome_text = """
☕️ Добро пожаловать в Wool Coffee Bot!

Я помогу тебе отслеживать задачи по работе в кофейне.

📋 Доступные команды:
/tasks - Показать задачи на смену
/history - История выполненных задач (7 дней)
/help - Справка по командам

В начале каждой смены я буду присылать список задач.
Просто нажми кнопку "✅ Выполнено" когда закончишь задачу!
    """
    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_employee(update, context):
        return
    
    help_text = """
📖 Справка по командам:

/start - Приветствие и инструкция
/tasks - Показать задачи на смену
/history - История за последние 7 дней
/help - Эта справка

🔔 Как работает бот:
• В начале смены я присылаю список задач
• Ты отмечаешь выполненные задачи кнопками
• Данные автоматически сохраняются в таблицу

⚠️ Важно:
• Красный текст = просроченная задача
• ✅ = задача выполнена
• ⏳ = задача в ожидании
    """
    await update.message.reply_text(help_text)


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_employee(update, context):
        return
    
    cache_manager: CacheManager = context.bot_data['cache_manager']
    table_manager: TableManager = context.bot_data['table_manager']
    username = update.effective_user.username
    now = datetime.now()
    
    current_shift = cache_manager.get_shift_for_user(username)
    
    if current_shift:
        shift = current_shift
        shift_date = now
        is_current = True
    else:
        next_shift = table_manager.get_user_next_shift(username, now)
        if not next_shift:
            await update.message.reply_text(
                "📅 У тебя нет предстоящих смен в ближайшие 30 дней."
            )
            return
        shift = next_shift
        shift_date = shift['date']
        is_current = False
    
    if is_current:
        tasks = cache_manager.get_tasks_for_user(username, shift_date)
    else:
        tasks = table_manager.get_tasks_for_today(shift_date)
    
    if not tasks:
        await update.message.reply_text(
            "Ура! Сегодня ничего не требуется 🎉"
        )
        return
    
    message_text, keyboard = _build_tasks_message(tasks, shift, shift_date, is_current)
    
    await update.message.reply_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_employee(update, context):
        return
    
    table_manager: TableManager = context.bot_data['table_manager']
    username = update.effective_user.username
    
    history = table_manager.get_history(days=7)
    
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
    
    cache_manager: CacheManager = context.bot_data['cache_manager']
    members_manager: MembersManager = context.bot_data['members_manager']
    username = update.effective_user.username
    
    if not members_manager.is_member(username):
        await query.edit_message_text("❌ Доступ запрещен.")
        return
    
    callback_data = query.data
    
    if not callback_data.startswith('complete_'):
        return
    
    row_index = int(callback_data.split('_')[1])
    
    now = datetime.now()
    shift = cache_manager.get_shift_for_user(username)
    
    if not shift:
        await query.edit_message_text("❌ У тебя нет активной смены.")
        return
    
    tasks = cache_manager.get_tasks_for_user(username, now)
    task = next((t for t in tasks if t['row_index'] == row_index), None)
    
    if not task:
        await query.edit_message_text("❌ Задача не найдена.")
        return
    
    completed_at = datetime.now()
    
    cache_manager.mark_completed_local(row_index, username, completed_at)
    
    updated_tasks = cache_manager.get_tasks_for_user(username, now)
    message_text, keyboard = _build_tasks_message(updated_tasks, shift, now, True)
    
    await query.edit_message_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    asyncio.create_task(
        cache_manager.sync_to_sheets(
            row_index,
            shift['name'],
            completed_at,
            task['period']
        )
    )


def _build_tasks_message(tasks: list, shift: dict, shift_date: datetime, is_current: bool):
    completed_tasks = [t for t in tasks if t['status'] == '✅']
    total_tasks = len(tasks)
    completed_count = len(completed_tasks)
    
    if is_current:
        text = f"☕️ <b>Задачи на текущую смену</b>\n\n"
        text += f"Смена: {shift['start_time']} - {shift['end_time']}\n"
        text += f"Дата: {shift_date.strftime('%d.%m.%Y')}\n\n"
    else:
        text = f"☕️ <b>Задачи на следующую смену</b>\n\n"
        text += f"Смена: {shift['start_time']} - {shift['end_time']}\n"
        text += f"Дата: {shift_date.strftime('%d.%m.%Y')}\n\n"
    
    keyboard = []
    
    for task in tasks:
        is_completed = task['status'] == '✅'
        is_overdue = _is_task_overdue(task, shift_date)
        
        if is_completed:
            completed_time = "сегодня"
            text += f"✅ <b>{task['name']}</b> (выполнено {completed_time})\n"
        else:
            if is_overdue:
                days = _get_days_overdue(task, shift_date)
                text += f"⚠️ <b>{task['name']}</b> <i>(просрочена на {days} дн.!)</i>\n"
            else:
                text += f"⏳ <b>{task['name']}</b>\n"
            
            button = InlineKeyboardButton(
                text=f"✅ {task['name']}",
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
            "❌ У тебя нет прав для выполнения этой команды."
        )
        return
    
    await update.message.reply_text("⏳ Начинаю проверку и настройку таблицы...")
    
    try:
        table_manager: TableManager = context.bot_data['table_manager']
        members_manager: MembersManager = context.bot_data['members_manager']
        cache_manager: CacheManager = context.bot_data['cache_manager']
        
        table_setup = TableSetup(table_manager.spreadsheet)
        report = table_setup.setup()
        
        table_manager.reload_employees()
        table_manager._initialize_next_cleaning_dates()
        
        synced = members_manager.sync_with_table(table_manager.employees_cache)
        
        await cache_manager.refresh_from_sheets()
        
        await update.message.reply_text(
            f"{report}\n\n🔄 Данные перезагружены.\n"
            f"📝 Синхронизировано сотрудников: {len(table_manager.employees_cache)}"
        )
        
    except Exception as e:
        logger.error(f"Error in setup_table_command: {e}")
        await update.message.reply_text(f"❌ Ошибка при настройке таблицы: {str(e)}")


async def member_update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config: Config = context.bot_data['config']
    
    user_id = update.effective_user.id
    
    if config.admin_user_id is None:
        await update.message.reply_text(
            "❌ Команда недоступна: не указан ADMIN_USER_ID в настройках."
        )
        return
    
    if user_id != config.admin_user_id:
        await update.message.reply_text(
            "❌ У тебя нет прав для выполнения этой команды."
        )
        return
    
    await update.message.reply_text("⏳ Обновляю данные сотрудников...")
    
    try:
        table_manager: TableManager = context.bot_data['table_manager']
        members_manager: MembersManager = context.bot_data['members_manager']
        cache_manager: CacheManager = context.bot_data['cache_manager']
        
        old_count = len(table_manager.employees_cache)
        
        table_manager.reload_employees()
        
        new_count = len(table_manager.employees_cache)
        
        synced = members_manager.sync_with_table(table_manager.employees_cache)
        
        await cache_manager.refresh_from_sheets()
        
        registered_count = sum(1 for m in members_manager.get_all_members().values() if m['user_id'] is not None)
        
        await update.message.reply_text(
            f"✅ Данные успешно обновлены!\n\n"
            f"📊 Статистика:\n"
            f"• Сотрудников в таблице: {new_count}\n"
            f"• Изменение: {new_count - old_count:+d}\n"
            f"• Зарегистрировано в боте: {registered_count}\n"
            f"• Не зарегистрировано: {new_count - registered_count}"
        )
        
    except Exception as e:
        logger.error(f"Error in member_update_command: {e}")
        await update.message.reply_text(f"❌ Ошибка при обновлении данных: {str(e)}")