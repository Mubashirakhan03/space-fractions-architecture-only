"""Tests for the User domain entity and auth (UserComponent)."""

from spacefractions.user.user import User, hash_password
from spacefractions.game.game import Game
from spacefractions.game.question import Question


def test_password_set_and_verify():
    user = User(id="u1", username="alice")
    user.set_password("secret")
    assert user.verify_password("secret")
    assert not user.verify_password("wrong")


def test_password_hash_is_salted():
    u1 = User(id="u1", username="a")
    u2 = User(id="u2", username="b")
    u1.set_password("same")
    u2.set_password("same")
    assert u1.password_hash != u2.password_hash


def test_hash_password_deterministic():
    assert hash_password("pw", "salt") == hash_password("pw", "salt")
    assert hash_password("pw", "salt") != hash_password("pw", "other")


def test_play_game_and_view_score():
    q = Question(
        id="q1",
        prompt="1/2 + 1/2",
        options=["1", "2"],
        correct_answer="1",
    )
    game = Game(id="g1", questions=[q])
    user = User(id="u1", username="alice")
    user.playGame(game)
    game.submit_answer("1")
    assert user.viewScore(game) == 1
