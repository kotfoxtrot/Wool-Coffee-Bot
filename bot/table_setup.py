import gspread
from datetime import datetime, timedelta
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class TableSetup:
    MONTH_NAMES = {
        1: 'ЯНВАРЬ', 2: 'ФЕВРАЛЬ', 3: 'МАРТ', 4: 'АПРЕЛЬ',
        5: 'МАЙ', 6: 'ИЮНЬ', 7: 'ИЮЛЬ', 8: 'АВГУСТ',
        9: 'СЕНТЯБРЬ', 10: 'ОКТЯБРЬ', 11: 'НОЯБРЬ', 12: 'ДЕКАБРЬ'
    }
    
    EMPLOYEES_HEADERS = ['ФИО', 'Telegram', 'Должность']
    CLEANING_HEADERS = ['Название', 'Периодичность', 'Последняя чистка', 'Следующая чистка', 'Выполнил', 'Статус']
    
    SAMPLE_EMPLOYEES = [
        ['Иванова Мария', 'maria_manager', 'Управляющий'],
        ['Петров Иван', 'ivan_barista', 'Бариста'],
        ['Сидорова Анна', 'anna_barista', 'Бариста']
    ]
    
    SAMPLE_EQUIPMENT = [
        ['Кофемолка ЕК-65', '7 дней', '-', '-', '-', '⏳'],
        ['Кофемолка ЕК-43', '30 дней', '-', '-', '-', '⏳'],
        ['Темпер для кофе', '7 дней', '-', '-', '-', '⏳'],
        ['Форсунки кофемашины', '14 дней', '-', '-', '-', '⏳'],
        ['Микроволновка', '7 дней', '-', '-', '-', '⏳'],
        ['Гриль', '7 дней', '-', '-', '-', '⏳']
    ]
    
    def __init__(self, spreadsheet: gspread.Spreadsheet):
        self.spreadsheet = spreadsheet
        self.existing_sheets = {ws.title: ws for ws in spreadsheet.worksheets()}
        
    def setup(self) -> str:
        report = []
        
        report.append("🔍 Проверка структуры таблицы...")
        
        employees_status = self._setup_employees_sheet()
        report.append(employees_status)
        
        cleaning_status = self._setup_cleaning_sheet()
        report.append(cleaning_status)
        
        month_status = self._setup_month_sheets()
        report.extend(month_status)
        
        report.append("\n✅ Проверка завершена!")
        
        return "\n".join(report)
    
    def _setup_employees_sheet(self) -> str:
        sheet_name = "Сотрудники"
        
        if sheet_name in self.existing_sheets:
            sheet = self.existing_sheets[sheet_name]
            headers = sheet.row_values(1) if sheet.row_count > 0 else []
            
            if headers == self.EMPLOYEES_HEADERS:
                row_count = len(sheet.get_all_values())
                return f"✓ Лист '{sheet_name}' существует ({row_count-1} сотрудников)"
            else:
                sheet.update('A1:C1', [self.EMPLOYEES_HEADERS])
                return f"↻ Лист '{sheet_name}' - обновлены заголовки"
        else:
            sheet = self.spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=3)
            sheet.update('A1:C1', [self.EMPLOYEES_HEADERS])
            sheet.update('A2:C4', self.SAMPLE_EMPLOYEES)
            
            sheet.format('A1:C1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 1.0, 'green': 0.9, 'blue': 0.6}
            })
            
            self.existing_sheets[sheet_name] = sheet
            return f"+ Создан лист '{sheet_name}' с примерными данными"
    
    def _setup_cleaning_sheet(self) -> str:
        sheet_name = "График чистки"
        
        if sheet_name in self.existing_sheets:
            sheet = self.existing_sheets[sheet_name]
            headers = sheet.row_values(1) if sheet.row_count > 0 else []
            
            if headers == self.CLEANING_HEADERS:
                row_count = len(sheet.get_all_values())
                return f"✓ Лист '{sheet_name}' существует ({row_count-1} позиций)"
            else:
                sheet.update('A1:F1', [self.CLEANING_HEADERS])
                return f"↻ Лист '{sheet_name}' - обновлены заголовки"
        else:
            sheet = self.spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=6)
            sheet.update('A1:F1', [self.CLEANING_HEADERS])
            sheet.update('A2:F7', self.SAMPLE_EQUIPMENT)
            
            sheet.format('A1:F1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 1.0, 'green': 0.9, 'blue': 0.6}
            })
            
            self.existing_sheets[sheet_name] = sheet
            return f"+ Создан лист '{sheet_name}' с примерным оборудованием"
    
    def _setup_month_sheets(self) -> List[str]:
        reports = []
        today = datetime.now()
        
        for month_offset in [0, 1]:
            target_date = today + timedelta(days=30 * month_offset)
            month_name = self.MONTH_NAMES[target_date.month]
            year_short = str(target_date.year)[2:]
            sheet_name = f"{month_name} {year_short}"
            
            if sheet_name in self.existing_sheets:
                reports.append(f"✓ Лист '{sheet_name}' существует")
            else:
                sheet = self._create_month_sheet(sheet_name, target_date)
                self.existing_sheets[sheet_name] = sheet
                reports.append(f"+ Создан лист '{sheet_name}' с примерным графиком")
        
        return reports
    
    def _create_month_sheet(self, sheet_name: str, target_date: datetime) -> gspread.Worksheet:
        days_in_month = self._get_days_in_month(target_date.year, target_date.month)
        
        sheet = self.spreadsheet.add_worksheet(
            title=sheet_name,
            rows=40,
            cols=17
        )
        
        month_header = [[sheet_name.split()[0]]]
        sheet.update('A1:A1', month_header)
        sheet.merge_cells('A1:B1')
        sheet.format('A1:B1', {
            'textFormat': {'bold': True, 'fontSize': 14},
            'backgroundColor': {'red': 1.0, 'green': 0.9, 'blue': 0.6},
            'horizontalAlignment': 'CENTER'
        })
        
        self._fill_period(sheet, target_date, 1, 15, 2)
        
        separator_row = 6 + len(self.SAMPLE_EMPLOYEES)
        
        self._fill_period(sheet, target_date, 16, days_in_month, separator_row + 1)
        
        return sheet
    
    def _fill_period(self, sheet: gspread.Worksheet, target_date: datetime, start_day: int, end_day: int, start_row: int):
        days_range = list(range(start_day, end_day + 1))
        num_days = len(days_range)
        
        weekdays = []
        for day in days_range:
            date = datetime(target_date.year, target_date.month, day)
            weekday = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'][date.weekday()]
            weekdays.append(weekday)
        
        sheet.update(f'C{start_row}', [weekdays])
        
        days_str = [str(d) for d in days_range]
        sheet.update(f'C{start_row + 1}', [days_str])
        
        headers = ['ФИО', 'Должность'] + days_str
        sheet.update(f'A{start_row + 1}', [headers])
        
        sheet.format(f'A{start_row}:Q{start_row + 1}', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 1.0, 'green': 0.9, 'blue': 0.6},
            'horizontalAlignment': 'CENTER'
        })
        
        if 'Сотрудники' in self.existing_sheets:
            emp_sheet = self.existing_sheets['Сотрудники']
            employees = emp_sheet.get_all_values()[1:]
            
            for idx, emp in enumerate(employees[:3]):
                name = emp[0] if len(emp) > 0 else ''
                position = emp[2] if len(emp) > 2 else ''
                
                row_data = [name, position] + ['в'] * num_days
                
                for day_idx in range(0, num_days, 3):
                    if day_idx < num_days:
                        row_data[2 + day_idx] = '08-15' if idx % 2 == 0 else '15-22'
                
                sheet.update(f'A{start_row + 2 + idx}', [row_data])
    
    def _get_days_in_month(self, year: int, month: int) -> int:
        if month == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month + 1, 1)
        
        last_day = next_month - timedelta(days=1)
        return last_day.day