import json
import os
from pathlib import Path
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class MembersManager:
    def __init__(self, config_dir: str = 'configs'):
        self.config_dir = Path(config_dir)
        self.members_file = self.config_dir / 'members.json'
        self.members: Dict[str, int] = {}
        self._ensure_config_dir()
        self._load_members()
    
    def _ensure_config_dir(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
    def _load_members(self):
        if self.members_file.exists():
            try:
                with open(self.members_file, 'r', encoding='utf-8') as f:
                    self.members = json.load(f)
                logger.info(f"Loaded {len(self.members)} members from cache")
            except Exception as e:
                logger.error(f"Error loading members file: {e}")
                self.members = {}
        else:
            self.members = {}
            self._save_members()
    
    def _save_members(self):
        try:
            with open(self.members_file, 'w', encoding='utf-8') as f:
                json.dump(self.members, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving members file: {e}")
    
    def add_member(self, username: str, user_id: int, name: str) -> bool:
        try:
            key = username.lower()
            
            if key in self.members:
                if self.members[key]['user_id'] == user_id:
                    return True
                logger.info(f"Updating user_id for {username}: {self.members[key]['user_id']} -> {user_id}")
            
            self.members[key] = {
                'user_id': user_id,
                'username': username,
                'name': name
            }
            self._save_members()
            logger.info(f"Added/updated member: {username} (ID: {user_id})")
            return True
        except Exception as e:
            logger.error(f"Error adding member: {e}")
            return False
    
    def get_user_id(self, username: str) -> Optional[int]:
        key = username.lower()
        member = self.members.get(key)
        return member['user_id'] if member else None
    
    def is_member(self, username: str) -> bool:
        if not username:
            return False
        return username.lower() in self.members
    
    def is_member_by_id(self, user_id: int) -> bool:
        return any(m['user_id'] == user_id for m in self.members.values())
    
    def get_member_info(self, username: str) -> Optional[Dict]:
        key = username.lower()
        return self.members.get(key)
    
    def sync_with_table(self, table_employees: Dict[str, Dict]) -> int:
        added_count = 0
        
        for name, info in table_employees.items():
            username = info['username']
            key = username.lower()
            
            if key not in self.members:
                self.members[key] = {
                    'user_id': None,
                    'username': username,
                    'name': name
                }
                added_count += 1
        
        keys_to_remove = []
        for key in self.members.keys():
            username = self.members[key]['username']
            if not any(emp['username'].lower() == username.lower() for emp in table_employees.values()):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.members[key]
        
        self._save_members()
        logger.info(f"Synced with table: +{added_count} new, -{len(keys_to_remove)} removed")
        return added_count
    
    def get_all_members(self) -> Dict[str, Dict]:
        return self.members.copy()