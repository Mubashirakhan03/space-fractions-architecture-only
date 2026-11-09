"""QuestionComponent — question management and data persistence."""

from __future__ import annotations

import json
import uuid
from typing import List, Optional

from .db import Database
from .models import Question


class QuestionComponent:
    """CRUD + persistence for the question bank."""

    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db if db is not None else Database()

    def _make_id(self) -> str:
        return uuid.uuid4().hex

    def add_question(
        self, prompt: str, options: List[str], answer: str
    ) -> Question:
        question = Question(
            id=self._make_id(), prompt=prompt, options=list(options), answer=answer
        )
        self.db.execute(
            "INSERT INTO questions (id, prompt, options, answer) "
            "VALUES (?, ?, ?, ?)",
            (question.id, question.prompt, json.dumps(question.options), question.answer),
        )
        return question

    def get_question(self, question_id: str) -> Optional[Question]:
        rows = self.db.query(
            "SELECT * FROM questions WHERE id = ?", (question_id,)
        )
        if not rows:
            return None
        return self._row_to_question(rows[0])

    def list_questions(self) -> List[Question]:
        rows = self.db.query("SELECT * FROM questions ORDER BY id")
        return [self._row_to_question(r) for r in rows]

    def update_question(self, question: Question) -> bool:
        cur = self.db.execute(
            "UPDATE questions SET prompt = ?, options = ?, answer = ? "
            "WHERE id = ?",
            (
                question.prompt,
                json.dumps(question.options),
                question.answer,
                question.id,
            ),
        )
        return cur.rowcount > 0

    def update_questions(self, questions: List[Question]) -> None:
        for q in questions:
            self.update_question(q)

    def delete_question(self, question_id: str) -> bool:
        cur = self.db.execute(
            "DELETE FROM questions WHERE id = ?", (question_id,)
        )
        return cur.rowcount > 0

    def count(self) -> int:
        rows = self.db.query("SELECT COUNT(*) AS n FROM questions")
        return int(rows[0]["n"])

    @staticmethod
    def _row_to_question(row: dict) -> Question:
        return Question(
            id=row["id"],
            prompt=row["prompt"],
            options=json.loads(row["options"]) if row["options"] else [],
            answer=row["answer"],
        )


SEED_QUESTIONS = [
    Question(
        id="seed-1",
        prompt="What is 1/2 + 1/4 ?",
        options=["1/4", "3/4", "2/6", "1/8"],
        answer="3/4",
    ),
    Question(
        id="seed-2",
        prompt="What is 2/3 - 1/6 ?",
        options=["1/2", "1/3", "1/6", "5/6"],
        answer="1/2",
    ),
    Question(
        id="seed-3",
        prompt="What is 3/5 * 2/3 ?",
        options=["6/15", "2/5", "5/8", "1/5"],
        answer="2/5",
    ),
    Question(
        id="seed-4",
        prompt="What is 3/4 divided by 1/2 ?",
        options=["3/8", "1/2", "3/2", "2/3"],
        answer="3/2",
    ),
    Question(
        id="seed-5",
        prompt="Which fraction is equivalent to 1/2 ?",
        options=["2/3", "2/4", "3/5", "4/9"],
        answer="2/4",
    ),
    Question(
        id="seed-6",
        prompt="What is 1/3 + 1/6 ?",
        options=["1/2", "2/9", "1/9", "2/6"],
        answer="1/2",
    ),
]


def seed_questions(component: QuestionComponent) -> None:
    """Insert the built-in fraction questions if the bank is empty."""
    if component.count() > 0:
        return
    for q in SEED_QUESTIONS:
        component.db.execute(
            "INSERT INTO questions (id, prompt, options, answer) "
            "VALUES (?, ?, ?, ?)",
            (q.id, q.prompt, json.dumps(q.options), q.answer),
        )
