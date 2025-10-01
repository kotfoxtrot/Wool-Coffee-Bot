import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    telegram_token: str
    google_sheets_id: str
    google_credentials_file: str
    notification_offset_minutes: int
    timezone: str
    manager_chat_id: Optional[int] = None
    admin_user_id: Optional[int] = None

    @classmethod
    def from_env(cls) -> 'Config':
        return cls(
            telegram_token=os.getenv('TELEGRAM_BOT_TOKEN', ''),
            google_sheets_id=os.getenv('GOOGLE_SHEETS_ID', ''),
            google_credentials_file=os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json'),
            notification_offset_minutes=int(os.getenv('NOTIFICATION_OFFSET_MINUTES', '30')),
            timezone=os.getenv('TIMEZONE', 'Europe/Moscow'),
            manager_chat_id=int(os.getenv('MANAGER_CHAT_ID')) if os.getenv('MANAGER_CHAT_ID') else None,
            admin_user_id=int(os.getenv('ADMIN_USER_ID')) if os.getenv('ADMIN_USER_ID') else None
        )

    def validate(self) -> bool:
        if not self.telegram_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set")
        if not self.google_sheets_id:
            raise ValueError("GOOGLE_SHEETS_ID not set")
        return True