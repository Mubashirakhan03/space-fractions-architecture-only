from spacefractions.models import Admin, Game, Question, User


def test_question_methods():
    q = Question(id="q1", prompt="P", options=["a", "b"], answer="a")
    assert q.getPrompt() == "P"
    assert q.getOptions() == ["a", "b"]


def test_game_composition():
    g = Game(id="g1")
    q = Question(id="q1", prompt="Q", options=[], answer="1/2")
    g.add_question(q)
    assert len(g.questions) == 1
    assert g.play() is None
    assert g.state == "Playing"
    assert g.viewScore() == 0


def test_game_roundtrip_dict():
    g = Game(id="g1", score=7)
    g.add_question(Question(id="q1", prompt="Q", options=["1/2"], answer="1/2"))
    g2 = Game.from_dict(g.to_dict())
    assert g2.id == "g1"
    assert g2.score == 7
    assert g2.questions[0].prompt == "Q"


def test_user_methods():
    u = User(id="u1", username="alice", password_hash="h")
    g = Game(id="g1")
    u.playGame(g)
    assert g.state == "Playing"
    assert u.viewScore(g) == 0


def test_admin_update_questions():
    a = Admin(id="a1", username="root")
    q = Question(id="q1", prompt="Q", options=[], answer="1/2")
    a.updateQuestions([q])  # should not raise
