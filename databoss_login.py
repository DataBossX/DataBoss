"""
Login system for DataBoss
Handles user authentication and session management
"""

import os
import json
import time
import uuid
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("databoss.login")
logging.basicConfig(level=logging.INFO)

DEFAULT_USERS_FILE = "users.json"
SESSION_TIMEOUT_MINUTES = 60
DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASSWORD = "databoss123"  # Should be changed in production

class LoginManager:
    def __init__(self, users_file: str = DEFAULT_USERS_FILE):
        self.users_file = users_file
        self.active_sessions = {}
        self.initialize_users()
        
    def initialize_users(self):
        """Initialize users database if it doesn't exist"""
        if not os.path.exists(self.users_file):
            logger.info(f"Creating new users file: {self.users_file}")
            admin_password_hash = self._hash_password(DEFAULT_ADMIN_PASSWORD)
            users_data = {
                DEFAULT_ADMIN_USER: {
                    "password_hash": admin_password_hash,
                    "role": "admin",
                    "created_at": datetime.now().isoformat()
                }
            }
            with open(self.users_file, "w") as f:
                json.dump(users_data, f, indent=2)
                
    def _hash_password(self, password: str) -> str:
        """Create secure hash of password"""
        salt = uuid.uuid4().hex
        return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt
        
    def _verify_password(self, stored_password: str, provided_password: str) -> bool:
        """Verify password against stored hash"""
        hash_part, salt = stored_password.split(':')
        return hash_part == hashlib.sha256(salt.encode() + provided_password.encode()).hexdigest()
    
    def login(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and return session token if successful"""
        try:
            with open(self.users_file, "r") as f:
                users = json.load(f)
                
            if username not in users:
                logger.warning(f"Login attempt for unknown user: {username}")
                return None
                
            if not self._verify_password(users[username]["password_hash"], password):
                logger.warning(f"Failed login attempt for user: {username}")
                return None
                
            session_id = str(uuid.uuid4())
            self.active_sessions[session_id] = {
                "username": username,
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(minutes=SESSION_TIMEOUT_MINUTES)).isoformat()
            }
            
            logger.info(f"User '{username}' logged in successfully")
            return session_id
            
        except Exception as e:
            logger.error(f"Login error: {str(e)}", exc_info=True)
            return None
            
    def validate_session(self, session_id: str) -> Optional[str]:
        """Validate session and return username if valid"""
        if session_id not in self.active_sessions:
            return None
            
        session = self.active_sessions[session_id]
        expires_at = datetime.fromisoformat(session["expires_at"])
        
        if datetime.now() > expires_at:
            del self.active_sessions[session_id]
            return None
            
        return session["username"]
        
    def logout(self, session_id: str) -> bool:
        """End user session"""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            return True
        return False
