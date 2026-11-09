"""Fraction question generation and answer checking."""

from fractions import Fraction
from typing import List, Optional

from .question import Question


def make_fraction_question(number: int) -> Question:
    """Generate a fraction addition question for the given index number.

    Builds two random simple fractions (quarters/halves/thirds), asks their
    sum, and produces a set of answer options including the correct one.
    """
    a_num, a_den = _random_simple_fraction(number)
    b_num, b_den = _random_simple_fraction(number * 7 + 3)
    a = Fraction(a_num, a_den)
    b = Fraction(b_num, b_den)
    total = a + b

    prompt = f"What is {a} + {b}?"
    correct = _format_fraction(total)

    options = _make_options(correct, number)

    return Question(
        id=f"q{number}",
        prompt=prompt,
        options=options,
        correct_answer=correct,
    )


def check_fraction_answer(question: Question, answer: str) -> bool:
    """Check whether the supplied answer string equals the correct answer.

    Accepts equivalent fractions (e.g. "2/4" matches "1/2").
    """
    a = _parse_fraction(answer)
    c = _parse_fraction(question.correct_answer)
    if a is None or c is None:
        return question.check(answer)
    return a == c


def _random_simple_fraction(seed: int) -> tuple:
    """Deterministically pick a simple fraction based on a seed int.

    Denominator chosen from a small set; numerator in [1, denominator).
    Returns (numerator, denominator).
    """
    denominators = (2, 2, 3, 3, 4, 4, 5, 6, 8)
    den = denominators[seed % len(denominators)]
    num = 1 + (seed // len(denominators)) % (den - 1)
    return num, den


def _format_fraction(value: Fraction) -> str:
    """Render a Fraction as a string (whole number, or numerator/denominator)."""
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _parse_fraction(text: str) -> Optional[Fraction]:
    """Parse a fraction string, tolerating plain ints and mixed numbers."""
    text = text.strip()
    if not text:
        return None
    if "/" in text:
        parts = text.split("/")
        if len(parts) != 2:
            return None
        try:
            return Fraction(int(parts[0]), int(parts[1]))
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return Fraction(int(text))
    except ValueError:
        return None


def _make_options(correct: str, seed: int) -> List[str]:
    """Build a list of distinct answer options including the correct one."""
    correct_fraction = _parse_fraction(correct)
    options = {correct}

    candidates = [
        Fraction(1, 2),
        Fraction(1, 3),
        Fraction(2, 3),
        Fraction(1, 4),
        Fraction(3, 4),
        Fraction(1, 1),
        Fraction(5, 6),
        Fraction(1, 6),
        Fraction(5, 8),
        Fraction(3, 8),
        Fraction(2, 5),
        Fraction(3, 5),
        Fraction(7, 8),
        Fraction(1, 8),
    ]

    idx = seed
    while len(options) < 4 and idx < len(candidates) + seed:
        cand = candidates[idx % len(candidates)]
        if cand != correct_fraction:
            options.add(_format_fraction(cand))
        idx += 1

    # Fallback in case fewer than 4 unique values were produced.
    offset = 1
    while len(options) < 4:
        cand = Fraction(offset, max(2, offset + 1))
        options.add(_format_fraction(cand))
        offset += 1

    result = list(options)[:4]
    # Keep a stable, seed-based order while ensuring the correct answer stays.
    result.sort(key=lambda x: (x != correct, x))
    return result
