"""Tests for the Admin domain entity."""

import pytest

from spacefractions.admin.admin import Admin
from spacefractions.game.question import Question


def test_admin_accepts_valid_questions():
    admin = Admin(id="a1", username="root")
    q = Question(
        id="q1",
        prompt="1/2 + 1/2",
        options=["1", "2"],
        correct_answer="1",
    )
    admin.updateQuestions([q])  # should not raise


def test_admin_rejects_empty_prompt():
    admin = Admin(id="a1", username="root")
    q = Question(id="q1", prompt="  ", options=["1"], correct_answer="1")
    with pytest.raises(ValueError):
        admin.updateQuestions([q])


def test_admin_rejects_answer_not_in_options():
    admin = Admin(id="a1", username="root")
    q = Question(
        id="q1", prompt="1/2 + 1/2", options=["1", "2"], correct_answer="3"
    )
    with pytest.raises(ValueError):
        admin.updateQuestions([q])
