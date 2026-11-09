"""SQLite persistence layer (ASR-1 data durability).

Tables mirror the architecture DDL:
    users(id, username, password_hash)
    questions(id, prompt, options, answer)
    games(id, user_id, game_state JSON)
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    options TEXT NOT NULL,
    answer TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    game_state TEXT NOT NULL
);
"""


def default_db_path() -> Path:
    """Return the default persistent DB location (user data dir)."""
    base = os.environ.get("SPACE_FRACTIONS_DATA_DIR")
    if base:
        directory = Path(base)
    else:
        home = Path.home()
        directory = home / ".space_fractions"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "spacefractions.db"


class Database:
    """Thin wrapper around sqlite3 with schema creation and JSON helpers."""

    def __init__(self, path: Optional[Path] = None) -> None:
        if path is None:
            path = default_db_path()
        self.path = Path(path)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def query(self, sql: str, params: tuple = ()) -> list:
        return [dict(row) for row in self.conn.execute(sql, params).fetchall()]
