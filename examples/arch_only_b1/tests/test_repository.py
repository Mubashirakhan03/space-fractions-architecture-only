"""Tests for the SQLite persistence layer."""

import os

from spacefractions.models import Question
from spacefractions.repository import Database, GameRepository, QuestionRepository


def test_question_crud(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.initialize()
    repo = QuestionRepository(db)
    assert repo.count() == 0
    repo.seed()
    assert repo.count() == 10
    q = Question("What is 1/2 + 1/2 ?", ["1", "1/2", "2", "0"], 0)
    repo.add(q)
    assert repo.get(q.id).prompt == q.prompt
    q.prompt = "changed"
    repo.update(q)
    assert repo.get(q.id).prompt == "changed"
    repo.delete(q.id)
    assert repo.get(q.id) is None
    db.close()


def test_game_save_and_load(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.initialize()
    qrepo = QuestionRepository(db)
    qrepo.seed()
    questions = qrepo.all()
    from spacefractions.models import Game

    game = Game(questions=questions)
    game.play()
    game.submit(questions[0].options[questions[0].correct_index])
    grepo = GameRepository(db)
    grepo.save(game)
    loaded = grepo.load(game.id, questions)
    assert loaded is not None
    assert loaded.score == 1
    assert loaded.current_index == 1
    grepo.record_score("alice", game.id, 1, 10)
    assert len(grepo.history("alice")) == 1
    db.close()
