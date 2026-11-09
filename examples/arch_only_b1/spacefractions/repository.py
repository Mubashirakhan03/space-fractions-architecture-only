"""SQLite persistence layer (QuestionComponent + persistence).

The schema mirrors the architecture's SQL DDL intent:
    CREATE TABLE games (id ..., game_state ...);
with JSON persisted as the game state (JSONB in Postgres, TEXT/JSON here).
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import List, Optional

from .models import Game, Question


DEFAULT_DB_PATH = os.path.join(
    os.path.expanduser("~"), ".spacefractions", "spacefractions.db"
)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    options TEXT NOT NULL,   -- JSON list of strings
    correct_index INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    game_state TEXT NOT NULL  -- JSON object
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL,          -- 'user' or 'admin'
    salt TEXT NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS score_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    game_id TEXT NOT NULL,
    score INTEGER NOT NULL,
    total INTEGER NOT NULL,
    played_at TEXT NOT NULL
);
"""

_SEED_QUESTIONS = [
    ("What is 1/2 + 1/4 ?", ["3/4", "2/6", "1/2", "1"], 0),
    ("What is 3/4 - 1/4 ?", ["1/2", "2/4", "1", "1/4"], 0),
    ("What is 1/3 + 1/3 ?", ["2/3", "1/6", "2/6", "1/3"], 0),
    ("What is 1/2 * 1/2 ?", ["1/4", "1", "1/2", "2/4"], 0),
    ("What is 2/3 - 1/6 ?", ["1/2", "1/3", "1/6", "3/6"], 0),
    ("What is 3/4 + 1/2 ?", ["5/4", "1", "4/6", "3/8"], 0),
    ("What fraction equals 0.5 ?", ["1/2", "1/3", "1/4", "2/5"], 0),
    ("What is 5/6 - 1/3 ?", ["1/2", "2/3", "1/3", "4/6"], 0),
    ("What is 1/5 + 2/5 ?", ["3/5", "3/10", "2/5", "1"], 0),
    ("What is 2/3 * 3/4 ?", ["1/2", "6/7", "5/12", "2/4"], 0),
]


class Database:
    """Thin connection helper wrapping the sqlite3 module."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row

    def conn(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()

    def initialize(self) -> None:
        with self._conn:
            self._conn.executescript(_SCHEMA)

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class QuestionRepository:
    """CRUD for the question bank."""

    def __init__(self, db: Database):
        self._db = db

    def seed(self) -> None:
        """Insert default questions if the bank is empty."""
        if self.count() == 0:
            for prompt, options, correct_index in _SEED_QUESTIONS:
                self.add(Question(prompt, options, correct_index))

    def all(self) -> List[Question]:
        cur = self._db.conn().execute(
            "SELECT id, prompt, options, correct_index FROM questions ORDER BY rowid"
        )
        rows = cur.fetchall()
        return [
            Question(
                prompt=r["prompt"],
                options=json.loads(r["options"]),
                correct_index=r["correct_index"],
                id=r["id"],
            )
            for r in rows
        ]

    def get(self, question_id: str) -> Optional[Question]:
        cur = self._db.conn().execute(
            "SELECT id, prompt, options, correct_index FROM questions WHERE id = ?",
            (question_id,),
        )
        r = cur.fetchone()
        if r is None:
            return None
        return Question(
            prompt=r["prompt"],
            options=json.loads(r["options"]),
            correct_index=r["correct_index"],
            id=r["id"],
        )

    def add(self, question: Question) -> None:
        with self._db.conn():
            self._db.conn().execute(
                "INSERT INTO questions (id, prompt, options, correct_index) "
                "VALUES (?, ?, ?, ?)",
                (
                    question.id,
                    question.prompt,
                    json.dumps(question.options),
                    question.correct_index,
                ),
            )

    def update(self, question: Question) -> None:
        with self._db.conn():
            self._db.conn().execute(
                "UPDATE questions SET prompt = ?, options = ?, correct_index = ? "
                "WHERE id = ?",
                (
                    question.prompt,
                    json.dumps(question.options),
                    question.correct_index,
                    question.id,
                ),
            )

    def delete(self, question_id: str) -> None:
        with self._db.conn():
            self._db.conn().execute(
                "DELETE FROM questions WHERE id = ?", (question_id,)
            )

    def count(self) -> int:
        cur = self._db.conn().execute("SELECT COUNT(*) AS c FROM questions")
        return cur.fetchone()["c"]


class GameRepository:
    """Persist games (game_state JSON) and score history."""

    def __init__(self, db: Database):
        self._db = db

    def save(self, game: Game) -> None:
        state = {
            "id": game.id,
            "score": game.score,
            "current_index": game.current_index,
            "answers": game._answers,
            "question_ids": [q.id for q in game.questions],
        }
        with self._db.conn():
            self._db.conn().execute(
                "INSERT OR REPLACE INTO games (id, game_state) VALUES (?, ?)",
                (game.id, json.dumps(state)),
            )

    def load(self, game_id: str, questions: List[Question]) -> Optional[Game]:
        cur = self._db.conn().execute(
            "SELECT game_state FROM games WHERE id = ?", (game_id,)
        )
        r = cur.fetchone()
        if r is None:
            return None
        state = json.loads(r["game_state"])
        by_id = {q.id: q for q in questions}
        qs = [by_id[qid] for qid in state.get("question_ids", []) if qid in by_id]
        game = Game(
            questions=qs,
            score=state.get("score", 0),
            id=state.get("id", game_id),
        )
        game.current_index = state.get("current_index", 0)
        game._answers = state.get("answers", [])
        return game

    def record_score(
        self, username: str, game_id: str, score: int, total: int
    ) -> None:
        import datetime

        with self._db.conn():
            self._db.conn().execute(
                "INSERT INTO score_history "
                "(username, game_id, score, total, played_at) VALUES (?, ?, ?, ?, ?)",
                (
                    username,
                    game_id,
                    score,
                    total,
                    datetime.datetime.now().isoformat(timespec="seconds"),
                ),
            )

    def history(self, username: Optional[str] = None) -> List[dict]:
        if username:
            cur = self._db.conn().execute(
                "SELECT * FROM score_history WHERE username = ? ORDER BY id DESC",
                (username,),
            )
        else:
            cur = self._db.conn().execute(
                "SELECT * FROM score_history ORDER BY id DESC"
            )
        return [dict(r) for r in cur.fetchall()]
