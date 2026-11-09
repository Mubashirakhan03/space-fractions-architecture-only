"""Domain model for Space Fractions.

The classes mirror the architecture domain_model:
    Game      --* Question  (composition)
    User      --* Game      (composition)
    Admin     --* Question  (composition)

All logic here is UI-agnostic and easily unit-tested.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Question:
    """A single fraction question with its multiple-choice options."""

    prompt: str
    options: List[str]
    correct_index: int
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def getPrompt(self) -> str:
        """Return the prompt text."""
        return self.prompt

    def getOptions(self) -> List[str]:
        """Return the list of answer options."""
        return list(self.options)

    def checkAnswer(self, answer: str) -> bool:
        """Return True when *answer* matches the correct option.

        Matching is exact against the correct option string.
        """
        if 0 <= self.correct_index < len(self.options):
            return answer.strip() == self.options[self.correct_index].strip()
        return False


@dataclass
class Game:
    """A single game session: a series of questions plus a running score."""

    questions: List[Question] = field(default_factory=list)
    score: int = 0
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    # current question index (state handled by GameService)
    current_index: int = 0
    _answers: List[str] = field(default_factory=list)

    def play(self) -> None:
        """Begin the game (reset progress)."""
        self.score = 0
        self.current_index = 0
        self._answers = []

    def viewScore(self) -> int:
        """Return the current score."""
        return self.score

    def currentQuestion(self) -> Optional[Question]:
        """Return the question at the cursor, or None when finished."""
        if 0 <= self.current_index < len(self.questions):
            return self.questions[self.current_index]
        return None

    def submit(self, answer: str) -> bool:
        """Submit an answer; advance the cursor and update the score."""
        question = self.currentQuestion()
        if question is None:
            return False
        self._answers.append(answer)
        correct = question.checkAnswer(answer)
        if correct:
            self.score += 1
        self.current_index += 1
        return correct

    @property
    def is_over(self) -> bool:
        return self.current_index >= len(self.questions)


@dataclass
class User:
    """An end user, who owns and plays games."""

    username: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    games: List[Game] = field(default_factory=list)

    def playGame(self, game: Game) -> None:
        """Play a game (add it to the user's collection and start it)."""
        if game not in self.games:
            self.games.append(game)
        game.play()

    def viewScore(self, game: Game) -> int:
        """Return the score of a game owned by this user."""
        if game in self.games:
            return game.viewScore()
        return 0


@dataclass
class Admin:
    """An administrator who manages the question bank."""

    username: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def updateQuestions(self, questions: List[Question]) -> None:
        """Replace the question bank (persistence handled by repository)."""
        # The domain method receives the new list; persistence is injected
        # by the repository layer, so here we just record the intent.
        self._last_questions = list(questions)
