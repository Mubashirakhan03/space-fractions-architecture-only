"""Domain model entities mirroring the architecture's class diagram.

Classes: Question, Game, User, Admin.
Kept free of Tkinter imports so they are unit-testable headlessly.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class Question:
    """A single fraction question.

    Attributes mirror the class diagram (id, prompt, options) plus an answer
    needed to evaluate correctness. The answer is stored as a string and
    interpreted as a `fractions.Fraction` at evaluation time.
    """

    id: str
    prompt: str
    options: List[str] = field(default_factory=list)
    answer: str = ""

    def getPrompt(self) -> str:  # noqa: N802 - mirror spec method names
        return self.prompt

    def getOptions(self) -> List[str]:  # noqa: N802
        return list(self.options)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Question":
        return cls(
            id=str(data["id"]),
            prompt=str(data["prompt"]),
            options=list(data.get("options", [])),
            answer=str(data.get("answer", "")),
        )


@dataclass
class Game:
    """A game session with a score and a list of questions.

    Composition: Game --* Question.
    """

    id: str
    score: int = 0
    questions: List[Question] = field(default_factory=list)
    state: str = "Playing"
    current_index: int = 0

    def play(self) -> None:
        """Begin / continue the game (state machine handled upstream)."""
        self.state = "Playing"

    def viewScore(self) -> int:  # noqa: N802
        return self.score

    def add_question(self, question: Question) -> None:
        self.questions.append(question)

    def to_dict(self) -> dict:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Game":
        return cls(
            id=str(data["id"]),
            score=int(data.get("score", 0)),
            questions=[
                Question.from_dict(q) for q in data.get("questions", [])
            ],
            state=str(data.get("state", "Playing")),
            current_index=int(data.get("current_index", 0)),
        )


@dataclass
class User:
    """A registered end user."""

    id: str
    username: str
    password_hash: str = ""

    def playGame(self, game: Game) -> None:  # noqa: N802
        game.play()

    def viewScore(self, game: Game) -> int:  # noqa: N802
        return game.viewScore()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Admin:
    """An administrator who can update the question bank."""

    id: str
    username: str

    def updateQuestions(self, questions: List[Question]) -> None:  # noqa: N802
        # The persistence side is handled by QuestionComponent.update_questions.
        for q in questions:
            if not q.prompt:
                raise ValueError("Question prompt must not be empty")
