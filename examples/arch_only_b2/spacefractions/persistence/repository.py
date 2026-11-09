"""SQLite-backed repositories (QuestionComponent).

Implements ASR-1 (data durability): questions, users, and game results are
persisted to a local SQLite database file so they survive application restarts.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..game.question import Question
from ..game.fractions import make_fraction_question
from ..game.state import GameState


_DEFAULT_DB = "spacefractions.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    options TEXT NOT NULL,
    correct_answer TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    salt TEXT
);

CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    score INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    state TEXT NOT NULL,
    played_at TEXT NOT NULL
);
"""


def _default_path() -> Path:
    """Resolve the DB path, preferring the user home dir when writable."""
    env = os.environ.get("SPACEFRACTIONS_DB")
    if env:
        return Path(env)
    home = Path.home()
    candidate = home / _DEFAULT_DB
    try:
        # Probe writability of home; fall back to cwd if unavailable.
        if os.access(home, os.W_OK):
            return candidate
    except OSError:
        pass
    return Path(_DEFAULT_DB)


class Repository:
    """Persistence facade for questions, users, and games."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else _default_path()
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._initialize()

    # ---- connection management -------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @property
    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = self._connect()
        return self._conn

    def _initialize(self) -> None:
        with self._lock:
            conn = self._connection
            conn.executescript(_SCHEMA)
            conn.commit()
            self._seed_if_empty(conn)

    def _seed_if_empty(self, conn: sqlite3.Connection) -> None:
        count = conn.execute("SELECT COUNT(*) AS c FROM questions").fetchone()
        if count["c"] == 0:
            for i in range(1, 11):
                q = make_fraction_question(i)
                self._insert_question(conn, q)
            conn.commit()

    # ---- questions --------------------------------------------------------

    @staticmethod
    def _insert_question(conn: sqlite3.Connection, q: Question) -> None:
        conn.execute(
            "INSERT OR REPLACE INTO questions (id, prompt, options, correct_answer) "
            "VALUES (?, ?, ?, ?)",
            (q.id, q.prompt, json.dumps(q.options), q.correct_answer),
        )

    @staticmethod
    def _row_to_question(row: sqlite3.Row) -> Question:
        return Question(
            id=row["id"],
            prompt=row["prompt"],
            options=json.loads(row["options"]),
            correct_answer=row["correct_answer"],
        )

    def get_questions(self) -> List[Question]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM questions ORDER BY id"
            ).fetchall()
            return [self._row_to_question(r) for r in rows]

    def get_question(self, question_id: str) -> Optional[Question]:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM questions WHERE id = ?", (question_id,)
            ).fetchone()
            return self._row_to_question(row) if row else None

    def save_question(self, question: Question) -> None:
        with self._lock:
            conn = self._connection
            self._insert_question(conn, question)
            conn.commit()

    def save_questions(self, questions: List[Question]) -> None:
        with self._lock:
            conn = self._connection
            for q in questions:
                self._insert_question(conn, q)
            conn.commit()

    def delete_question(self, question_id: str) -> None:
        with self._lock:
            self._connection.execute(
                "DELETE FROM questions WHERE id = ?", (question_id,)
            )
            self._connection.commit()

    # ---- users ------------------------------------------------------------

    def create_user(self, username: str, password: str) -> "object":
        from ..user.user import User

        user = User(id=_new_id("u"), username=username)
        user.set_password(password)
        with self._lock:
            conn = self._connection
            conn.execute(
                "INSERT INTO users (id, username, password_hash, salt) "
                "VALUES (?, ?, ?, ?)",
                (user.id, user.username, user.password_hash, user.salt),
            )
            conn.commit()
        return user

    def get_user(self, username: str) -> Optional["object"]:
        from ..user.user import User

        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            if not row:
                return None
            return User(
                id=row["id"],
                username=row["username"],
                password_hash=row["password_hash"],
                salt=row["salt"],
            )

    def verify_user(self, username: str, password: str) -> Optional["object"]:
        user = self.get_user(username)
        if user is not None and user.verify_password(password):
            return user
        return None

    # ---- games ------------------------------------------------------------

    def save_game_result(
        self,
        game_id: str,
        user_id: str,
        score: int,
        total: int,
        state: GameState,
    ) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT OR REPLACE INTO games "
                "(id, user_id, score, total, state, played_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    game_id,
                    user_id,
                    score,
                    total,
                    state.name,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self._connection.commit()

    def get_best_score(self, user_id: str) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT MAX(score) AS best FROM games WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return row["best"] if row["best"] is not None else 0

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None


def _new_id(prefix: str) -> str:
    import uuid

    return f"{prefix}-{uuid.uuid4().hex[:12]}"
