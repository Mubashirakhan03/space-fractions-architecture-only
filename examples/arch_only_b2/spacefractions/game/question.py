"""Question domain entity."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Question:
    """A fraction question with a prompt, multiple-choice options, and answer.

    Attributes:
        id: unique identifier.
        prompt: the question text.
        options: list of answer choices (strings).
        correct_answer: the correct option (must be one of options).
    """

    id: str
    prompt: str
    options: List[str] = field(default_factory=list)
    correct_answer: str = ""

    def getPrompt(self) -> str:
        """Return the question prompt."""
        return self.prompt

    def getOptions(self) -> List[str]:
        """Return the list of answer options."""
        return list(self.options)

    def check(self, answer: str) -> bool:
        """Return True if the given answer is correct."""
        return answer.strip() == self.correct_answer.strip()

    def to_dict(self) -> dict:
        """Serialize the question to a JSON-friendly dict."""
        return {
            "id": self.id,
            "prompt": self.prompt,
            "options": list(self.options),
            "correct_answer": self.correct_answer,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Question":
        """Reconstruct a Question from a dict."""
        return cls(
            id=data["id"],
            prompt=data["prompt"],
            options=list(data.get("options", [])),
            correct_answer=data.get("correct_answer", ""),
        )
