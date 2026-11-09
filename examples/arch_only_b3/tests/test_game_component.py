import pytest

from fractions import Fraction

from spacefractions.db import Database
from spacefractions.game_component import (
    GameComponent,
    is_correct,
    parse_fraction,
)
from spacefractions.models import Game, Question


def test_parse_fraction_forms():
    assert parse_fraction("3/4") == Fraction(3, 4)
    assert parse_fraction("0.75") == Fraction(3, 4)
    assert parse_fraction("3 4") == Fraction(3, 4)
    assert parse_fraction("2") == Fraction(2)


def test_is_correct():
    assert is_correct("3/4", "6/8")
    assert is_correct("0.75", "3/4")
    assert is_correct("1", "2/2")
    assert not is_correct("1/2", "3/4")
    assert not is_correct("garbage", "1/2")


def make_question(_, idx, answer):
    return Question(id=f"q{idx}", prompt=f"Q{idx}", options=[], answer=answer)


def test_game_scoring(tmp_path):
    db = Database(tmp_path / "game.db")
    gc = GameComponent(db)
    questions = [
        Question(id="q1", prompt="Q1", options=[], answer="1/2"),
        Question(id="q2", prompt="Q2", options=[], answer="3/4"),
    ]
    game = gc.new_game(None, questions)
    assert game.viewScore() == 0
    assert game.state == "Playing"
    assert gc.answer(game, "1/2") is True
    assert game.viewScore() == 1
    assert game.current_index == 1
    assert gc.answer(game, "1/4") is False
    assert game.viewScore() == 1
    assert game.state == "GameOver"


def test_save_and_load(tmp_path):
    db = Database(tmp_path / "game.db")
    gc = GameComponent(db)
    game = gc.new_game(
        None, [Question(id="q1", prompt="Q1", options=["1/2"], answer="1/2")]
    )
    game.score = 42
    gc.save(game)
    loaded = gc.load(game.id)
    assert loaded is not None
    assert loaded.viewScore() == 42
    assert loaded.questions[0].prompt == "Q1"


def test_load_missing(tmp_path):
    db = Database(tmp_path / "game.db")
    gc = GameComponent(db)
    assert gc.load("missing") is None


def test_answer_when_game_over(tmp_path):
    db = Database(tmp_path / "game.db")
    gc = GameComponent(db)
    game = gc.new_game(
        None, [Question(id="q1", prompt="Q1", options=[], answer="1/2")]
    )
    gc.answer(game, "1/2")  # completes the game
    assert game.state == "GameOver"
    assert gc.answer(game, "1/2") is False
    assert game.score == 1  # score does not change
