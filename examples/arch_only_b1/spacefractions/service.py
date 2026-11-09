"""GameComponent: game orchestration and the state machine.

States: Playing, Paused, GameOver.
Transitions:
    [*]      -> Playing   (start)
    Playing  -> Paused    pause()
    Paused   -> Playing   resume()
    Playing  -> GameOver  gameOver()
"""

from __future__ import annotations

import random
from enum import Enum
from fractions import Fraction
from typing import List, Optional

from .models import Game, Question


class GameState(str, Enum):
    PLAYING = "Playing"
    PAUSED = "Paused"
    GAME_OVER = "GameOver"


class FractionGenerator:
    """Generate random fraction questions with exact Fraction arithmetic."""

    _OPERATIONS = [("+", lambda a, b: a + b), ("-", lambda a, b: a - b)]

    @staticmethod
    def _render(f: Fraction) -> str:
        if f.denominator == 1:
            return str(f.numerator)
        return f"{f.numerator}/{f.denominator}"

    @classmethod
    def generate(cls, rng: Optional[random.Random] = None) -> Question:
        """Build one question with 4 options (exact, unique)."""
        rng = rng or random
        op_text, op = rng.choice(cls._OPERATIONS)
        d1 = rng.randint(2, 6)
        d2 = rng.randint(2, 6)
        n1 = rng.randint(1, d1 - 1)
        n2 = rng.randint(1, d2 - 1)
        a = Fraction(n1, d1)
        b = Fraction(n2, d2)
        correct = op(a, b)
        prompt = f"What is {cls._render(a)} {op_text} {cls._render(b)} ?"

        # Build distractors near the correct value.
        options = {cls._render(correct)}
        while len(options) < 4:
            candidate = correct + Fraction(rng.randint(-3, 3), rng.randint(2, 5))
            if candidate <= 0:
                candidate = correct + Fraction(1, rng.randint(2, 5))
            options.add(cls._render(candidate))
        ordered = list(options)
        rng.shuffle(ordered)
        correct_index = ordered.index(cls._render(correct))
        return Question(prompt=prompt, options=ordered, correct_index=correct_index)


class GameService:
    """Runs a game session: state, scoring, and answer checking."""

    def __init__(
        self,
        questions: List[Question],
        username: str = "guest",
        generator: Optional[FractionGenerator] = None,
        num_questions: int = 6,
    ):
        self._username = username
        self.generator = generator or FractionGenerator()
        self.state: GameState = GameState.PLAYING
        self.game = Game(
            questions=self._pick_questions(questions, num_questions)
        )
        self.game.play()

    def _pick_questions(
        self, questions: List[Question], num_questions: int
    ) -> List[Question]:
        """Choose up to num_questions from the bank; top up with generated ones."""
        bank = list(questions)
        random.shuffle(bank)
        chosen = bank[:num_questions]
        while len(chosen) < num_questions:
            chosen.append(self.generator.generate())
        return chosen

    @property
    def currentQuestion(self) -> Optional[Question]:
        return self.game.currentQuestion()

    def submitAnswer(self, answer: str) -> bool:
        """Submit an answer; return True if correct."""
        if self.state != GameState.PLAYING:
            return False
        correct = self.game.submit(answer)
        if self.game.is_over:
            self.state = GameState.GAME_OVER
        return correct

    def pause(self) -> None:
        if self.state == GameState.PLAYING:
            self.state = GameState.PAUSED

    def resume(self) -> None:
        if self.state == GameState.PAUSED:
            self.state = GameState.PLAYING

    def gameOver(self) -> None:
        self.state = GameState.GAME_OVER

    def viewScore(self) -> int:
        return self.game.viewScore()

    def totalQuestions(self) -> int:
        return len(self.game.questions)

    @property
    def is_over(self) -> bool:
        return self.state == GameState.GAME_OVER or self.game.is_over
