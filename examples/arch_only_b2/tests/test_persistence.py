"""Tests for the SQLite persistence layer (QuestionComponent)."""

import pytest

from spacefractions.game.question import Question
from spacefractions.game.state import GameState
from spacefractions.persistence.repository import Repository


def _sample_questions():
    return [
        Question(
            id="q1",
            prompt="What is 1/2 + 1/4?",
            options=["3/4", "1/2", "2/3"],
            correct_answer="3/4",
        ),
        Question(
            id="q2",
            prompt="What is 1/3 + 1/3?",
            options=["2/3", "1/3", "1/2"],
            correct_answer="2/3",
        ),
    ]


@pytest.fixture
def repo(tmp_path):
    r = Repository(db_path=str(tmp_path / "test.db"))
    yield r
    r.close()


def test_seeds_questions_on_first_run(repo):
    questions = repo.get_questions()
    assert len(questions) >= 1
    for q in questions:
        assert q.prompt
        assert q.correct_answer in q.options


def test_question_roundtrip(repo):
    q = _sample_questions()[0]
    repo.save_question(q)
    loaded = repo.get_question("q1")
    assert loaded is not None
    assert loaded.prompt == q.prompt
    assert loaded.options == q.options
    assert loaded.correct_answer == q.correct_answer


def test_save_questions_and_order(repo):
    repo.save_questions(_sample_questions())
    ids = [q.id for q in repo.get_questions()]
    assert "q1" in ids
    assert "q2" in ids


def test_delete_question(repo):
    repo.save_questions(_sample_questions())
    repo.delete_question("q1")
    assert repo.get_question("q1") is None
    assert repo.get_question("q2") is not None


def test_data_durability_across_reopen(tmp_path):
    path = str(tmp_path / "durable.db")
    r1 = Repository(db_path=path)
    r1.save_question(_sample_questions()[0])
    r1.close()

    r2 = Repository(db_path=path)
    loaded = r2.get_question("q1")
    assert loaded is not None
    assert loaded.correct_answer == "3/4"
    r2.close()


def test_user_create_and_verify(repo):
    user = repo.create_user("alice", "secret")
    assert user.username == "alice"
    assert repo.verify_user("alice", "secret") is not None
    assert repo.verify_user("alice", "wrong") is None


def test_game_result_and_best_score(repo):
    user = repo.create_user("bob", "pw")
    repo.save_game_result("g1", user.id, 3, 5, GameState.GAMEOVER)
    repo.save_game_result("g2", user.id, 5, 5, GameState.GAMEOVER)
    assert repo.get_best_score(user.id) == 5
