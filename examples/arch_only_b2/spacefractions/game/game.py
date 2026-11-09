"""Game domain entity and orchestration."""

from dataclasses import dataclass, field
from typing import List, Optional

from .question import Question
from .state import GameState


@dataclass
class Game:
    """A single play session: a series of questions and a running score.

    Attributes:
        id: unique identifier.
        questions: the questions to present.
        state: current GameState.
        score: number of correctly answered questions.
        current_index: index of the next question to answer.
    """

    id: str
    questions: List[Question] = field(default_factory=list)
    state: GameState = GameState.PLAYING
    score: int = 0
    current_index: int = 0

    # ---- lifecycle --------------------------------------------------------

    def start(self) -> None:
        """(Re)start the game from the beginning."""
        self.state = GameState.PLAYING
        self.score = 0
        self.current_index = 0

    def play(self) -> None:
        """Mark the game as being played (resume from Paused if needed)."""
        if self.state is GameState.GAMEOVER:
            self.start()
            return
        self.state = GameState.PLAYING

    def pause(self) -> None:
        """Pause the running game."""
        if self.state is GameState.PLAYING:
            self.state = GameState.PAUSED

    def resume(self) -> None:
        """Resume a paused game."""
        if self.state is GameState.PAUSED:
            self.state = GameState.PLAYING

    def gameOver(self) -> None:
        """End the game."""
        self.state = GameState.GAMEOVER

    # ---- question flow ----------------------------------------------------

    def current_question(self) -> Optional[Question]:
        """Return the question currently being asked, or None when done."""
        if self.current_index < len(self.questions):
            return self.questions[self.current_index]
        return None

    def submit_answer(self, answer: str) -> bool:
        """Submit an answer for the current question.

        Advances to the next question and, when all questions are answered,
        transitions the game to GameOver. Returns True if correct.
        """
        question = self.current_question()
        if question is None:
            return False

        correct = question.check(answer)
        if correct:
            self.score += 1

        self.current_index += 1
        if self.current_index >= len(self.questions):
            self.gameOver()

        return correct

    def viewScore(self) -> int:
        """Return the current score."""
        return self.score

    @property
    def total_questions(self) -> int:
        return len(self.questions)

    @property
    def is_finished(self) -> bool:
        return self.state is GameState.GAMEOVER
