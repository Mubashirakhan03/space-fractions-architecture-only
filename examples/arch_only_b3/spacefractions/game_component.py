"""GameComponent — game logic, scoring, and answer evaluation."""

from __future__ import annotations

import json
import uuid
from typing import List, Optional

from fractions import Fraction

from .db import Database
from .models import Game, Question, User
from .state_machine import GameStateMachine


def parse_fraction(value: str) -> Fraction:
    """Parse a fraction from rational, decimal, or 'num den' notation."""
    value = value.strip()
    if not value:
        raise ValueError("Empty value")
    parts = value.split()
    if len(parts) == 2:
        return Fraction(int(parts[0]), int(parts[1]))
    if "/" in value:
        num, _, den = value.partition("/")
        return Fraction(int(num), int(den))
    if "." in value:
        return Fraction(value)  # Fraction accepts exact decimals
    return Fraction(int(value))


def is_correct(answer_text: str, expected: str) -> bool:
    """Return True if the free-text/option answer equals the expected value."""
    try:
        return parse_fraction(answer_text) == parse_fraction(expected)
    except (ValueError, ZeroDivisionError):
        return False


class GameComponent:
    """Drives a Game through its questions, tracking score and state."""

    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db if db is not None else Database()

    def new_game(
        self, user: Optional[User], questions: List[Question]
    ) -> Game:
        game = Game(id=uuid.uuid4().hex, questions=list(questions))
        if user is not None:
            # User --* Game composition: record the game against the user.
            pass
        self._persist(game, user)
        return game

    def _persist(self, game: Game, user: Optional[User]) -> None:
        self.db.execute(
            "INSERT INTO games (id, user_id, game_state) VALUES (?, ?, ?)",
            (
                game.id,
                user.id if user is not None else None,
                json.dumps(game.to_dict()),
            ),
        )

    def save(self, game: Game, user: Optional[User] = None) -> None:
        cur = self.db.execute(
            "UPDATE games SET game_state = ? WHERE id = ?",
            (json.dumps(game.to_dict()), game.id),
        )
        if cur.rowcount == 0:
            self._persist(game, user)

    def load(self, game_id: str) -> Optional[Game]:
        rows = self.db.query("SELECT * FROM games WHERE id = ?", (game_id,))
        if not rows:
            return None
        return Game.from_dict(json.loads(rows[0]["game_state"]))

    def answer(self, game: Game, answer_text: str) -> bool:
        """Evaluate the current question and advance the game."""
        if game.state == "GameOver":
            return False
        if game.current_index >= len(game.questions):
            return False
        question = game.questions[game.current_index]
        correct = is_correct(answer_text, question.answer)
        if correct:
            game.score += 1
        game.current_index += 1
        if game.current_index >= len(game.questions):
            game.state = "GameOver"
        return correct
