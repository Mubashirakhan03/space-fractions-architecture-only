"""Tests for the Game domain entity and state machine."""

from spacefractions.game.game import Game
from spacefractions.game.question import Question
from spacefractions.game.state import GameState


def _make_question(qid, correct):
    return Question(
        id=qid,
        prompt=f"Q {qid}",
        options=["a", "b", "c"],
        correct_answer=correct,
    )


def test_game_starts_in_playing_state():
    game = Game(id="g1", questions=[_make_question("q1", "a")])
    assert game.state is GameState.PLAYING
    assert game.score == 0
    assert game.current_index == 0


def test_submit_correct_answer_increments_score():
    game = Game(
        id="g1",
        questions=[_make_question("q1", "a"), _make_question("q2", "b")],
    )
    assert game.submit_answer("a") is True
    assert game.score == 1
    assert game.current_index == 1


def test_submit_wrong_answer_no_score():
    game = Game(id="g1", questions=[_make_question("q1", "a")])
    assert game.submit_answer("b") is False
    assert game.score == 0


def test_game_over_when_questions_exhausted():
    game = Game(id="g1", questions=[_make_question("q1", "a")])
    game.submit_answer("a")
    assert game.state is GameState.GAMEOVER
    assert game.is_finished


def test_pause_resume_transitions():
    game = Game(id="g1", questions=[_make_question("q1", "a")])
    game.pause()
    assert game.state is GameState.PAUSED
    game.resume()
    assert game.state is GameState.PLAYING


def test_pause_only_from_playing():
    game = Game(id="g1", questions=[_make_question("q1", "a")])
    game.gameOver()
    game.pause()
    assert game.state is GameState.GAMEOVER


def test_play_restarts_finished_game():
    game = Game(id="g1", questions=[_make_question("q1", "a")])
    game.submit_answer("wrong")
    assert game.state is GameState.GAMEOVER
    game.play()
    assert game.state is GameState.PLAYING
    assert game.score == 0
    assert game.current_index == 0


def test_view_score():
    game = Game(
        id="g1",
        questions=[_make_question("q1", "a"), _make_question("q2", "b")],
    )
    game.submit_answer("a")
    assert game.viewScore() == 1


def test_current_question_progression_and_none():
    game = Game(id="g1", questions=[_make_question("q1", "a")])
    assert game.current_question().id == "q1"
    game.submit_answer("a")
    assert game.current_question() is None
