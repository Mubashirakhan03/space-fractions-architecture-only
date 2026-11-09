"""Admin domain entity."""

from dataclasses import dataclass
from typing import List

from ..game.question import Question


@dataclass
class Admin:
    """An administrator who can update the question bank.

    Attributes:
        id: unique identifier.
        username: display name.
    """

    id: str
    username: str

    def updateQuestions(self, questions: List[Question]) -> None:
        """Replace the question bank with a new list.

        The actual persistence is delegated to the QuestionComponent's
        repository by the caller; this method exists to mirror the domain
        contract and facilitate validation before saving.
        """
        self._validate(questions)

    @staticmethod
    def _validate(questions: List[Question]) -> None:
        """Ensure every question has a prompt and its correct answer in options."""
        for q in questions:
            if not q.prompt.strip():
                raise ValueError(f"Question {q.id} has an empty prompt")
            if q.options and q.correct_answer not in q.options:
                raise ValueError(
                    f"Question {q.id}: correct answer not among options"
                )
