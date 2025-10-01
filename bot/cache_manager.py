import asyncio
from datetime import datetime, date
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    def __init__(self, table_manager):
        self.table_manager = table_manager
        self.cache = {
            'date': None,
            'tasks': [],
            'shifts_today': [],
            'completed_local': {},
            'last_sheets_sync': None
        }
        self._sync_lock = asyncio.Lock()
    
    async def initialize(self):
        await self.refresh_from_sheets()
    
    async def refresh_from_sheets(self):
        async with self._sync_lock:
            try:
                now = datetime.now()
                today = now.date()
                
                logger.info(f"Refreshing cache from Google Sheets for {today}")
                
                tasks = await asyncio.to_thread(self.table_manager.get_equipment_tasks)
                shifts = await asyncio.to_thread(self.table_manager.get_today_shifts, now)
                
                self.cache['date'] = today
                self.cache['tasks'] = tasks
                self.cache['shifts_today'] = shifts
                self.cache['completed_local'] = {}
                self.cache['last_sheets_sync'] = now
                
                logger.info(f"Cache refreshed: {len(tasks)} tasks, {len(shifts)} shifts")
                
            except Exception as e:
                logger.error(f"Error refreshing cache: {e}")
    
    def invalidate_if_date_changed(self):
        today = date.today()
        if self.cache['date'] != today:
            logger.info(f"Date changed from {self.cache['date']} to {today}, invalidating cache")
            self.cache['date'] = today
            self.cache['tasks'] = []
            self.cache['shifts_today'] = []
            self.cache['completed_local'] = {}
            return True
        return False
    
    def get_tasks_for_user(self, username: str, now: datetime) -> List[Dict]:
        self.invalidate_if_date_changed()
        
        if not self.cache['tasks']:
            return []
        
        today = now
        tasks_today = []
        
        for task in self.cache['tasks']:
            if self._should_clean_today(task, today):
                task_copy = task.copy()
                
                if username in self.cache['completed_local']:
                    if task['row_index'] in self.cache['completed_local'][username]:
                        task_copy['status'] = '✅'
                        task_copy['completed_at'] = self.cache['completed_local'][username][task['row_index']]
                
                tasks_today.append(task_copy)
        
        return tasks_today
    
    def get_shift_for_user(self, username: str) -> Optional[Dict]:
        self.invalidate_if_date_changed()
        
        for shift in self.cache['shifts_today']:
            if shift['username'].lower() == username.lower():
                return shift
        
        return None
    
    def mark_completed_local(self, row_index: int, username: str, completed_at: datetime):
        if username not in self.cache['completed_local']:
            self.cache['completed_local'][username] = {}
        
        self.cache['completed_local'][username][row_index] = completed_at
        logger.info(f"Marked task {row_index} as completed locally by {username}")
    
    async def sync_to_sheets(self, row_index: int, completed_by: str, completed_at: datetime, period_str: str):
        try:
            success = await asyncio.to_thread(
                self.table_manager.mark_task_completed,
                row_index,
                completed_by,
                completed_at,
                period_str
            )
            
            if success:
                logger.info(f"Successfully synced task {row_index} to Google Sheets")
            else:
                logger.error(f"Failed to sync task {row_index} to Google Sheets")
            
            return success
            
        except Exception as e:
            logger.error(f"Error syncing to sheets: {e}")
            return False
    
    def _should_clean_today(self, task: Dict, today: datetime) -> bool:
        if task.get('status') == '✅':
            last_cleaned_str = task.get('last_cleaned', '')
            if last_cleaned_str and last_cleaned_str != '-':
                try:
                    last_cleaned = datetime.strptime(last_cleaned_str, "%d.%m.%Y")
                    if last_cleaned.date() == today.date():
                        return False
                except ValueError:
                    pass
        
        next_cleaning_str = task.get('next_cleaning', '')
        
        if not next_cleaning_str or next_cleaning_str == '-':
            last_cleaned_str = task.get('last_cleaned', '')
            period_str = task.get('period', '')
            
            if not last_cleaned_str or last_cleaned_str == '-':
                return True
            
            period_days = self.table_manager._parse_period_days(period_str)
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