"""UserComponent: local authentication and authorization.

Passwords are salted and hashed with hashlib (PBKDF2-HMAC-SHA256).
Roles: 'user' (end user) and 'admin' (administrator).
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Optional

from .models import Admin, User
from .repository import Database

_ITERATIONS = 100_000


def _hash_password(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _ITERATIONS
    )
    return dk.hex()


class AuthService:
    """Manages users and validates credentials."""

    def __init__(self, db: Database):
        self._db = db

    def register(
        self, username: str, password: str, role: str = "user"
    ) -> Optional[User]:
        """Create a new account. Returns the User or None if taken."""
        username = username.strip()
        if not username or not password:
            return None
        salt = secrets.token_hex(16)
        phash = _hash_password(password, salt)
        user_id = (User(username).id if role == "user" else Admin(username).id)
        try:
            with self._db.conn():
                self._db.conn().execute(
                    "INSERT INTO users (id, username, role, salt, password_hash) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (user_id, username, role, salt, phash),
                )
        except Exception:
            return None
        if role == "admin":
            return Admin(username=username, id=user_id)
        return User(username=username, id=user_id)

    def authenticate(
        self, username: str, password: str
    ) -> Optional[dict]:
        """Validate credentials; returns {id, username, role} or None."""
        cur = self._db.conn().execute(
            "SELECT id, username, role, salt, password_hash FROM users "
            "WHERE username = ?",
            (username,),
        )
        r = cur.fetchone()
        if r is None:
            return None
        expected = _hash_password(password, r["salt"])
        if not secrets.compare_digest(expected, r["password_hash"]):
            return None
        return {"id": r["id"], "username": r["username"], "role": r["role"]}

    def exists(self, username: str) -> bool:
        cur = self._db.conn().execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        )
        return cur.fetchone() is not None

    def ensure_admin(self, username: str = "admin", password: str = "admin123") -> None:
        """Ensure a default admin account exists (for first run)."""
        if not self.exists(username):
            self.register(username, password, role="admin")
