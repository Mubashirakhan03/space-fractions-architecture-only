"""Tests for fraction question generation and answer checking."""

from fractions import Fraction

from spacefractions.game.fractions import (
    check_fraction_answer,
    make_fraction_question,
    _parse_fraction,
    _format_fraction,
)
from spacefractions.game.question import Question


def test_make_fraction_question_structure():
    q = make_fraction_question(1)
    assert q.id
    assert q.prompt.startswith("What is")
    assert len(q.options) == 4
    assert q.correct_answer in q.options


def test_question_options_unique():
    for i in range(1, 30):
        q = make_fraction_question(i)
        assert len(set(q.options)) == len(q.options)


def test_correct_answer_is_truly_correct():
    for i in range(1, 30):
        q = make_fraction_question(i)
        assert check_fraction_answer(q, q.correct_answer)


def test_equivalent_fraction_accepted():
    q = Question(
        id="q",
        prompt="What is 1/4 + 1/4?",
        options=["1/2", "2/4"],
        correct_answer="1/2",
    )
    assert check_fraction_answer(q, "2/4")


def test_wrong_answer_rejected():
    q = Question(
        id="q",
        prompt="What is 1/2 + 1/2?",
        options=["1", "2"],
        correct_answer="1",
    )
    assert not check_fraction_answer(q, "2")


def test_parse_fraction_variants():
    assert _parse_fraction("1/2") == Fraction(1, 2)
    assert _parse_fraction("3") == Fraction(3, 1)
    assert _parse_fraction("nonsense") is None
    assert _parse_fraction("1/0") is None


def test_format_fraction():
    assert _format_fraction(Fraction(3, 4)) == "3/4"
    assert _format_fraction(Fraction(2, 1)) == "2"
