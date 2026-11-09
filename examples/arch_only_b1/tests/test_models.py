"""Unit tests for the domain model."""

from spacefractions.models import Admin, Game, Question, User


def test_question_getters_and_check():
    q = Question("1/2+1/4", ["3/4", "1/2", "1", "2/6"], 0)
    assert q.getPrompt() == "1/2+1/4"
    assert q.getOptions() == ["3/4", "1/2", "1", "2/6"]
    assert q.checkAnswer("3/4") is True
    assert q.checkAnswer("1/2") is False


def test_game_play_and_submit():
    q1 = Question("a", ["x", "y"], 0)
    q2 = Question("b", ["x", "y"], 1)
    game = Game(questions=[q1, q2])
    game.play()
    assert game.viewScore() == 0
    assert game.currentQuestion() is q1
    assert game.submit("x") is True
    assert game.viewScore() == 1
    assert game.currentQuestion() is q2
    assert game.submit("y") is True
    assert game.is_over is True
    assert game.currentQuestion() is None
    assert game.submit("x") is False  # no more questions


def test_user_composition():
    u = User("alice")
    game = Game(questions=[])
    u.playGame(game)
    assert game in u.games
    assert u.viewScore(game) == 0


def test_admin_update_questions():
    a = Admin("root")
    qs = [Question("p", ["a", "b", "c", "d"], 0)]
    a.updateQuestions(qs)
    assert a._last_questions == qs
