import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
import re

logger = logging.getLogger(__name__)


class SheetsManager:
    MONTH_NAMES = {
        1: 'ЯНВАРЬ', 2: 'ФЕВРАЛЬ', 3: 'МАРТ', 4: 'АПРЕЛЬ',
        5: 'МАЙ', 6: 'ИЮНЬ', 7: 'ИЮЛЬ', 8: 'АВГУСТ',
        9: 'СЕНТЯБРЬ', 10: 'ОКТЯБРЬ', 11: 'НОЯБРЬ', 12: 'ДЕКАБРЬ'
    }
    
    def __init__(self, credentials_file: str, spreadsheet_id: str):
        self.credentials_file = credentials_file
        self.spreadsheet_id = spreadsheet_id
        self.client = None
        self.spreadsheet = None
        self.employees_cache = {}
        
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
            self._load_employees()
            self._initialize_next_cleaning_dates()
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            raise

    def _load_employees(self):
        try:
            sheet = self.spreadsheet.worksheet("Сотрудники")
            data = sheet.get_all_records()
            
            for row in data:
                name = row.get('ФИО', '').strip()
                username = row.get('Telegram', '').strip().replace('@', '')
                position = row.get('Должность', '').strip()
                
                if name and username and username.lower() != 'none':
                    self.employees_cache[name] = {
                        'username': username,
                        'position': position
                    }
            
            logger.info(f"Loaded {len(self.employees_cache)} employees")
            
        except Exception as e:
            logger.error(f"Error loading employees: {e}")
            self.employees_cache = {}

    def _parse_period_days(self, period_str: str) -> Optional[int]:
        try:
            match = re.search(r'(\d+)', period_str)
            if match:
                return int(match.group(1))
            return None
        except Exception as e:
            logger.error(f"Error parsing period '{period_str}': {e}")
            return None

    def _initialize_next_cleaning_dates(self):
        try:
            sheet = self.spreadsheet.worksheet("График чистки")
            all_data = sheet.get_all_values()
            
            if len(all_data) < 2:
                return
            
            updates = []
            today = datetime.now()
            
            for idx in range(1, len(all_data)):
                row = all_data[idx]
                
                if len(row) < 4:
                    continue
                
                name = row[0].strip() if len(row) > 0 else ''
                period_str = row[1].strip() if len(row) > 1 else ''
                last_cleaned_str = row[2].strip() if len(row) > 2 else ''
                next_cleaning_str = row[3].strip() if len(row) > 3 else ''
                
                if not name or not period_str:
                    continue
                
                if next_cleaning_str and next_cleaning_str != '-':
                    continue
                
                period_days = self._parse_period_days(period_str)
                if not period_days:
                    continue
                
                if last_cleaned_str and last_cleaned_str != '-':
                    try:
                        last_cleaned = datetime.strptime(last_cleaned_str, "%d.%m.%Y")
                        next_cleaning = last_cleaned + timedelta(days=period_days)
                    except ValueError:
                        next_cleaning = today + timedelta(days=period_days)
                else:
                    next_cleaning = today + timedelta(days=period_days)
                
                next_cleaning_str = next_cleaning.strftime("%d.%m.%Y")
                updates.append({
                    'range': f'D{idx + 1}',
                    'values': [[next_cleaning_str]]
                })
            
            if updates:
                for update in updates:
                    sheet.update(update['range'], update['values'])
                logger.info(f"Initialized {len(updates)} next cleaning dates")
            
        except Exception as e:
            logger.error(f"Error initializing next cleaning dates: {e}")

    def get_today_shifts(self, today: datetime) -> List[Dict]:
        try:
            month_name = self.MONTH_NAMES[today.month]
            year_short = str(today.year)[2:]
            sheet_name = f"{month_name} {year_short}"
            
            logger.info(f"Looking for sheet: {sheet_name}")
            
            try:
                sheet = self.spreadsheet.worksheet(sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                logger.warning(f"Sheet '{sheet_name}' not found")
                return []
            
            all_data = sheet.get_all_values()
            
            if len(all_data) < 4:
                logger.warning(f"Not enough rows in sheet {sheet_name}")
                return []
            
            header_row = None
            data_start_row = None
            
            for idx, row in enumerate(all_data):
                if 'ФИО' in row and 'Должность' in row:
                    header_row = row
                    data_start_row = idx + 1
                    break
            
            if not header_row or data_start_row is None:
                logger.warning(f"Could not find header row in {sheet_name}")
                return []
            
            day_column_index = None
            for idx, cell in enumerate(header_row):
                if cell.strip() == str(today.day):
                    day_column_index = idx
                    break
            
            if day_column_index is None:
                logger.warning(f"Could not find column for day {today.day}")
                return []
            
            shifts = []
            
            for row in all_data[data_start_row:]:
                if len(row) <= day_column_index:
                    continue
                
                name = row[0].strip() if len(row) > 0 else ''
                shift_time = row[day_column_index].strip() if len(row) > day_column_index else ''
                
                if not name or not shift_time or shift_time.lower() == 'в':
                    continue
                
                employee_info = self.employees_cache.get(name)
                
                if not employee_info:
                    logger.warning(f"Employee {name} not found in cache")
                    continue
                
                start_time, end_time = self._parse_shift_time(shift_time)
                
                if start_time:
                    shifts.append({
                        'name': name,
                        'username': employee_info['username'],
                        'position': employee_info['position'],
                        'start_time': start_time,
                        'end_time': end_time,
                        'shift_raw': shift_time
                    })
            
            logger.info(f"Found {len(shifts)} shifts for {today.strftime('%d.%m.%Y')}")
            return shifts
            
        except Exception as e:
            logger.error(f"Error getting shifts: {e}")
            return []

    def _parse_shift_time(self, shift_str: str) -> Tuple[Optional[str], Optional[str]]:
        try:
            if '-' not in shift_str:
                return None, None
            
            parts = shift_str.split('-')
            if len(parts) != 2:
                return None, None
            
            start = parts[0].strip()
            end = parts[1].strip()
            
            if len(start) == 2:
                start = f"{start}:00"
            elif len(start) == 4:
                start = f"{start[:2]}:{start[2:]}"
            elif len(start) == 5 and ':' in start:
                pass
            else:
                start = f"{start}:00"
            
            if len(end) == 2:
                end = f"{end}:00"
            elif len(end) == 4:
                end = f"{end[:2]}:{end[2:]}"
            elif len(end) == 5 and ':' in end:
                pass
            else:
                end = f"{end}:00"
            
            return start, end
            
        except Exception as e:
            logger.error(f"Error parsing shift time '{shift_str}': {e}")
            return None, None

    def get_equipment_tasks(self) -> List[Dict]:
        try:
            sheet = self.spreadsheet.worksheet("График чистки")
            data = sheet.get_all_records()
            
            tasks = []
            for idx, row in enumerate(data, start=2):
                tasks.append({
                    'row_index': idx,
                    'name': row.get('Название', ''),
                    'period': row.get('Периодичность', ''),
                    'last_cleaned': row.get('Последняя чистка', ''),
                    'next_cleaning': row.get('Следующая чистка', ''),
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
        
        logger.info(f"Found {len(tasks_today)} tasks for today")
        return tasks_today

    def _should_clean_today(self, task: Dict, today: datetime) -> bool:
        next_cleaning_str = task['next_cleaning']
        
        if not next_cleaning_str or next_cleaning_str == '-':
            last_cleaned_str = task['last_cleaned']
            period_str = task['period']
            
            if not last_cleaned_str or last_cleaned_str == '-':
                return True
            
            period_days = self._parse_period_days(period_str)
            if not period_days:
                return False
            
            try:
                last_cleaned = datetime.strptime(last_cleaned_str, "%d.%m.%Y")
                days_passed = (today - last_cleaned).days
                return days_passed >= period_days
            except ValueError:
                return True
        
        try:
            next_cleaning = datetime.strptime(next_cleaning_str, "%d.%m.%Y")
            return next_cleaning.date() <= today.date()
        except ValueError:
            return False

    def mark_task_completed(self, row_index: int, completed_by: str, completed_at: datetime, period_str: str):
        try:
            sheet = self.spreadsheet.worksheet("График чистки")
            
            last_cleaned_str = completed_at.strftime("%d.%m.%Y")
            
            period_days = self._parse_period_days(period_str)
            if period_days:
                next_cleaning = completed_at + timedelta(days=period_days)
                next_cleaning_str = next_cleaning.strftime("%d.%m.%Y")
            else:
                next_cleaning_str = "-"
            
            sheet.update_cell(row_index, 3, last_cleaned_str)
            sheet.update_cell(row_index, 4, next_cleaning_str)
            sheet.update_cell(row_index, 5, completed_by)
            sheet.update_cell(row_index, 6, "✅")
            
            logger.info(f"Task at row {row_index} marked as completed by {completed_by}, next cleaning: {next_cleaning_str}")
            return True
            
        except Exception as e:
            logger.error(f"Error marking task completed: {e}")
            return False

    def get_history(self, days: int = 7) -> List[Dict]:
        try:
            sheet = self.spreadsheet.worksheet("График чистки")
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
                                'status': row.get('Статус', ''),
                                'next_cleaning': row.get('Следующая чистка', '')
                            })
                    except ValueError:
                        continue
            
            history.sort(key=lambda x: datetime.strptime(x['date'], "%d.%m.%Y"), reverse=True)
            return history
            
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []

    def get_employee_username(self, name: str) -> Optional[str]:
        employee = self.employees_cache.get(name)
        return employee['username'] if employee else None

    def reload_employees(self):
        self._load_employees()