import json

import pytest

from spacefractions.db import Database
from spacefractions.question_component import (
    QuestionComponent,
    SEED_QUESTIONS,
    seed_questions,
)
from spacefractions.models import Question


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    yield d
    d.close()


def test_add_and_get_question(db):
    qc = QuestionComponent(db)
    q = qc.add_question("What is 1/2 + 1/2 ?", ["1", "1/4", "2/4"], "1")
    assert q.id
    fetched = qc.get_question(q.id)
    assert fetched is not None
    assert fetched.prompt == q.prompt
    assert fetched.options == q.options
    assert fetched.answer == q.answer


def test_list_and_count(db):
    qc = QuestionComponent(db)
    assert qc.count() == 0
    qc.add_question("q1", [], "1/2")
    qc.add_question("q2", [], "1/3")
    assert qc.count() == 2
    assert len(qc.list_questions()) == 2


def test_update_question(db):
    qc = QuestionComponent(db)
    q = qc.add_question("old", ["a"], "1/2")
    q.prompt = "new"
    q.answer = "3/4"
    assert qc.update_question(q) is True
    fetched = qc.get_question(q.id)
    assert fetched.prompt == "new"
    assert fetched.answer == "3/4"


def test_update_questions_bulk(db):
    qc = QuestionComponent(db)
    q = qc.add_question("a", [], "1/2")
    q.answer = "1"
    qc.update_questions([q])
    assert qc.get_question(q.id).answer == "1"


def test_delete_question(db):
    qc = QuestionComponent(db)
    q = qc.add_question("gone", [], "1")
    assert qc.delete_question(q.id) is True
    assert qc.get_question(q.id) is None
    assert qc.delete_question(q.id) is False


def test_get_missing_question(db):
    qc = QuestionComponent(db)
    assert qc.get_question("nope") is None


def test_seed_questions(db):
    qc = QuestionComponent(db)
    seed_questions(qc)
    assert qc.count() == len(SEED_QUESTIONS)
    # Idempotent
    seed_questions(qc)
    assert qc.count() == len(SEED_QUESTIONS)
