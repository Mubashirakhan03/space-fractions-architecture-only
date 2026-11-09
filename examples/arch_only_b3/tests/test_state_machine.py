import pytest

from spacefractions.state_machine import GameStateMachine


def test_initial_state():
    sm = GameStateMachine()
    assert sm.state == "Playing"


def test_start_playing_from_paused():
    sm = GameStateMachine(initial_state="Paused")
    assert sm.state == "Paused"
    assert sm.resume() == "Playing"


def test_pause_and_resume():
    sm = GameStateMachine()
    assert sm.pause() == "Paused"
    assert sm.resume() == "Playing"


def test_game_over():
    sm = GameStateMachine()
    assert sm.game_over() == "GameOver"
    # No further transitions out of GameOver.
    with pytest.raises(ValueError):
        sm.pause()
    with pytest.raises(ValueError):
        sm.resume()


def test_illegal_transition():
    sm = GameStateMachine()
    with pytest.raises(ValueError):
        sm.resume()  # resume from Playing is not allowed


def test_can():
    sm = GameStateMachine()
    assert sm.can("pause")
    assert not sm.can("resume")
    sm.pause()
    assert sm.can("resume")
    assert not sm.can("pause")


def test_invalid_initial_state():
    with pytest.raises(ValueError):
        GameStateMachine(initial_state="Nonsense")
