"""UserComponent — user authentication and authorization."""

from __future__ import annotations

import hashlib
import uuid
from typing import Optional

from .db import Database
from .models import User


class UserComponent:
    """Local user store with salted-hash password verification."""

    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db if db is not None else Database()

    @staticmethod
    def hash_password(password: str, salt: str = "") -> str:
        salted = (salt + password).encode("utf-8")
        return hashlib.sha256(salted).hexdigest()

    def register(self, username: str, password: str) -> User:
        username = username.strip()
        if not username:
            raise ValueError("Username must not be empty")
        if not password:
            raise ValueError("Password must not be empty")
        if self.find_by_username(username) is not None:
            raise ValueError(f"Username {username!r} already exists")
        user = User(
            id=uuid.uuid4().hex,
            username=username,
            password_hash=self.hash_password(password),
        )
        self.db.execute(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
            (user.id, user.username, user.password_hash),
        )
        return user

    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self.find_by_username(username)
        if user is None:
            return None
        if user.password_hash == self.hash_password(password):
            return user
        return None

    def find_by_username(self, username: str) -> Optional[User]:
        rows = self.db.query(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        )
        if not rows:
            return None
        row = rows[0]
        return User(
            id=row["id"], username=row["username"], password_hash=row["password_hash"]
        )

    def get_user(self, user_id: str) -> Optional[User]:
        rows = self.db.query("SELECT * FROM users WHERE id = ?", (user_id,))
        if not rows:
            return None
        row = rows[0]
        return User(
            id=row["id"], username=row["username"], password_hash=row["password_hash"]
        )
