import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SheetsManager:
    def __init__(self, credentials_file: str, spreadsheet_id: str):
        self.credentials_file = credentials_file
        self.spreadsheet_id = spreadsheet_id
        self.client = None
        self.spreadsheet = None
        
    def connect(self):
        try:
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            creds = Credentials.from_service_account_file(
                self.credentials_file, 
                scopes=scopes
            )
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            logger.info("Successfully connected to Google Sheets")
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            raise

    def get_today_shifts(self, today: datetime) -> List[Dict]:
        try:
            sheet = self.spreadsheet.worksheet("Смены")
            data = sheet.get_all_records()
            
            today_str = today.strftime("%d.%m.%Y")
            shifts = []
            
            for row in data:
                if row.get('Дата') == today_str:
                    shifts.append({
                        'name': row.get('ФИО', ''),
                        'username': row.get('Telegram Username', '').replace('@', ''),
                        'start_time': row.get('Время начала', '')
                    })
            
            logger.info(f"Found {len(shifts)} shifts for {today_str}")
            return shifts
            
        except Exception as e:
            logger.error(f"Error getting shifts: {e}")
            return []

    def get_equipment_tasks(self) -> List[Dict]:
        try:
            sheet = self.spreadsheet.worksheet("Оборудование")
            data = sheet.get_all_records()
            
            tasks = []
            for idx, row in enumerate(data, start=2):
                tasks.append({
                    'row_index': idx,
                    'name': row.get('Название', ''),
                    'frequency': row.get('Периодичность', ''),
                    'last_cleaned': row.get('Последняя чистка', ''),
                    'completed_by': row.get('Выполнил', ''),
                    'status': row.get('Статус', '')
                })
            
            logger.info(f"Loaded {len(tasks)} equipment tasks")
            return tasks
            
        except Exception as e:
            logger.error(f"Error getting equipment: {e}")
            return []

    def get_tasks_for_today(self, today: datetime) -> List[Dict]:
        all_tasks = self.get_equipment_tasks()
        tasks_today = []
        
        for task in all_tasks:
            if self._should_clean_today(task, today):
                tasks_today.append(task)
        
        return tasks_today

    def _should_clean_today(self, task: Dict, today: datetime) -> bool:
        frequency = task['frequency'].lower()
        last_cleaned_str = task['last_cleaned']
        
        if not last_cleaned_str or last_cleaned_str == '-':
            return True
        
        try:
            last_cleaned = datetime.strptime(last_cleaned_str, "%d.%m.%Y")
        except ValueError:
            return True
        
        days_passed = (today - last_cleaned).days
        
        if frequency == 'ежедневно':
            return days_passed >= 1
        elif frequency == 'еженедельно':
            return days_passed >= 7
        elif frequency == 'ежемесячно':
            return days_passed >= 30
        
        return False

    def mark_task_completed(self, row_index: int, completed_by: str, completed_at: datetime):
        try:
            sheet = self.spreadsheet.worksheet("Оборудование")
            
            date_str = completed_at.strftime("%d.%m.%Y")
            time_str = completed_at.strftime("%H:%M")
            
            sheet.update_cell(row_index, 3, date_str)
            sheet.update_cell(row_index, 4, completed_by)
            sheet.update_cell(row_index, 5, "✅")
            
            logger.info(f"Task at row {row_index} marked as completed by {completed_by} at {time_str}")
            return True
            
        except Exception as e:
            logger.error(f"Error marking task completed: {e}")
            return False

    def get_history(self, days: int = 7) -> List[Dict]:
        try:
            sheet = self.spreadsheet.worksheet("Оборудование")
            data = sheet.get_all_records()
            
            cutoff_date = datetime.now() - timedelta(days=days)
            history = []
            
            for row in data:
                last_cleaned = row.get('Последняя чистка', '')
                if last_cleaned and last_cleaned != '-':
                    try:
                        cleaned_date = datetime.strptime(last_cleaned, "%d.%m.%Y")
                        if cleaned_date >= cutoff_date:
                            history.append({
                                'name': row.get('Название', ''),
                                'date': last_cleaned,
                                'completed_by': row.get('Выполнил', ''),
                                'status': row.get('Статус', '')
                            })
                    except ValueError:
                        continue
            
            history.sort(key=lambda x: datetime.strptime(x['date'], "%d.%m.%Y"), reverse=True)
            return history
            
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []