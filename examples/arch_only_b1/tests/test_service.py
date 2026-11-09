"""Tests for the game service / state machine."""

import random

from spacefractions.models import Question
from spacefractions.service import FractionGenerator, GameService, GameState


def _questions(n=6):
    qs = []
    for i in range(n):
        qs.append(Question(f"q{i}", ["a", "b", "c", "d"], 0))
    return qs


def test_service_state_transitions():
    svc = GameService(_questions(), num_questions=4, generator=FractionGenerator())
    assert svc.state == GameState.PLAYING
    svc.pause()
    assert svc.state == GameState.PAUSED
    svc.resume()
    assert svc.state == GameState.PLAYING
    svc.gameOver()
    assert svc.state == GameState.GAME_OVER


def test_service_full_run():
    qs = _questions(3)
    svc = GameService(qs, num_questions=3, generator=FractionGenerator())
    assert svc.totalQuestions() == 3
    total = 0
    while not svc.is_over:
        q = svc.currentQuestion
        assert q is not None
        correct = svc.submitAnswer(q.options[q.correct_index])
        assert correct is True
        total += 1
    assert total == 3
    assert svc.viewScore() == 3
    assert svc.state == GameState.GAME_OVER


def test_generator_valid_question():
    rng = random.Random(42)
    for _ in range(50):
        q = FractionGenerator.generate(rng)
        assert len(q.options) == 4
        assert len(set(q.options)) == 4
        assert 0 <= q.correct_index < 4
        assert q.checkAnswer(q.options[q.correct_index]) is True
