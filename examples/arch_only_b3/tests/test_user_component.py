import pytest

from spacefractions.db import Database
from spacefractions.user_component import UserComponent


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "users.db")
    yield d
    d.close()


def test_register_and_authenticate(db):
    uc = UserComponent(db)
    user = uc.register("alice", "secret123")
    assert user.username == "alice"
    assert user.password_hash != "secret123"
    authed = uc.authenticate("alice", "secret123")
    assert authed is not None
    assert authed.id == user.id


def test_authenticate_wrong_password(db):
    uc = UserComponent(db)
    uc.register("alice", "secret123")
    assert uc.authenticate("alice", "wrong") is None


def test_authenticate_unknown_user(db):
    uc = UserComponent(db)
    assert uc.authenticate("nobody", "x") is None


def test_duplicate_username(db):
    uc = UserComponent(db)
    uc.register("alice", "pw")
    with pytest.raises(ValueError):
        uc.register("alice", "other")


def test_empty_username(db):
    uc = UserComponent(db)
    with pytest.raises(ValueError):
        uc.register("", "pw")


def test_empty_password(db):
    uc = UserComponent(db)
    with pytest.raises(ValueError):
        uc.register("alice", "")


def test_find_and_get(db):
    uc = UserComponent(db)
    user = uc.register("bob", "pw")
    assert uc.find_by_username("bob").id == user.id
    assert uc.get_user(user.id).username == "bob"
    assert uc.get_user("missing") is None
