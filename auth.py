"""
auth.py
=======
Multi-user Authentication, Session Management, and User Profile Store for SMAR v2.
Pre-seeded with default admin user:
  Username: lovekesh
  Password: lovekesh123
"""

import os
import json
import time
import uuid
import hashlib
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger("smar.auth")

USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "users.json")


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Generate salted PBKDF2-SHA256 password hash."""
    if not salt:
        salt = uuid.uuid4().hex[:16]
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${key.hex()}"


def verify_password(stored_hash: str, provided_password: str) -> bool:
    """Verify password against salted PBKDF2-SHA256 hash with backward compatibility."""
    if not stored_hash:
        return False
    if "$" not in stored_hash:
        # Plaintext fallback check
        return stored_hash == provided_password
    try:
        salt, hash_val = stored_hash.split("$", 1)
        key = hashlib.pbkdf2_hmac("sha256", provided_password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return key.hex() == hash_val
    except Exception as e:
        logger.warning(f"Error verifying password: {e}")
        return False


class UserManager:
    """
    Manages multi-user authentication, user persistence, and session tokens.
    """

    def __init__(self, users_file: str = USERS_FILE):
        self.users_file = users_file
        self.sessions: Dict[str, Dict[str, Any]] = {}
        os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
        self._ensure_default_users()

    def _load_users(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error reading users file, reinitializing: {e}")
        return {}

    def _save_users(self, users: Dict[str, Dict[str, Any]]) -> None:
        try:
            with open(self.users_file, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save users file: {e}")

    def _ensure_default_users(self) -> None:
        users = self._load_users()
        modified = False

        # Pre-seed lovekesh / lovekesh123
        if "lovekesh" not in users:
            users["lovekesh"] = {
                "username": "lovekesh",
                "name": "Lovekesh",
                "role": "admin",
                "password_hash": hash_password("lovekesh123"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            modified = True

        # Pre-seed secondary user for multi-user switching demonstration
        if "guest" not in users:
            users["guest"] = {
                "username": "guest",
                "name": "Guest User",
                "role": "user",
                "password_hash": hash_password("guest123"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            modified = True

        if modified:
            self._save_users(users)
            logger.info("Initialized default users: lovekesh (admin) and guest (user).")

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Verify username & password; returns user dict (without password_hash) if valid."""
        clean_user = username.strip().lower()
        users = self._load_users()
        user_record = users.get(clean_user)
        if not user_record:
            return None

        if verify_password(user_record.get("password_hash", ""), password):
            token = f"smar_sess_{uuid.uuid4().hex}"
            safe_user = {
                "username": user_record["username"],
                "name": user_record["name"],
                "role": user_record["role"],
                "created_at": user_record.get("created_at"),
            }
            self.sessions[token] = {
                "user": safe_user,
                "created_at": time.time(),
                "expires_at": time.time() + (30 * 86400),  # 30 days
            }
            return {
                "token": token,
                "user": safe_user,
            }
        return None

    def register_user(self, username: str, password: str, name: Optional[str] = None, role: str = "user") -> Dict[str, Any]:
        """Register a new user in the multi-user system."""
        clean_user = username.strip().lower()
        if not clean_user or len(clean_user) < 2:
            raise ValueError("Username must be at least 2 characters.")
        if not password or len(password) < 4:
            raise ValueError("Password must be at least 4 characters.")

        users = self._load_users()
        if clean_user in users:
            raise ValueError(f"User '{clean_user}' already exists.")

        user_record = {
            "username": clean_user,
            "name": name.strip() if name else clean_user.capitalize(),
            "role": role,
            "password_hash": hash_password(password),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        users[clean_user] = user_record
        self._save_users(users)

        token = f"smar_sess_{uuid.uuid4().hex}"
        safe_user = {
            "username": user_record["username"],
            "name": user_record["name"],
            "role": user_record["role"],
            "created_at": user_record.get("created_at"),
        }
        self.sessions[token] = {
            "user": safe_user,
            "created_at": time.time(),
            "expires_at": time.time() + (30 * 86400),
        }
        return {
            "token": token,
            "user": safe_user,
        }

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        clean_user = username.strip().lower()
        users = self._load_users()
        u = users.get(clean_user)
        if not u:
            return None
        return {
            "username": u["username"],
            "name": u["name"],
            "role": u["role"],
            "created_at": u.get("created_at"),
        }

    def list_users(self) -> List[Dict[str, Any]]:
        users = self._load_users()
        return [
            {
                "username": u["username"],
                "name": u["name"],
                "role": u["role"],
                "created_at": u.get("created_at"),
            }
            for u in users.values()
        ]

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate an existing session token."""
        if not token or token not in self.sessions:
            return None
        sess = self.sessions[token]
        if time.time() > sess.get("expires_at", 0):
            del self.sessions[token]
            return None
        return sess.get("user")


# Global singleton instance
user_manager = UserManager()
