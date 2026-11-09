"""Tests for authentication."""

from spacefractions.auth import AuthService
from spacefractions.repository import Database


def test_register_authenticate(tmp_path):
    db = Database(str(tmp_path / "auth.db"))
    db.initialize()
    auth = AuthService(db)
    u = auth.register("alice", "secret")
    assert u is not None
    assert auth.authenticate("alice", "secret")["role"] == "user"
    assert auth.authenticate("alice", "wrong") is None
    assert auth.register("alice", "other") is None  # duplicate
    db.close()


def test_admin_role(tmp_path):
    db = Database(str(tmp_path / "auth2.db"))
    db.initialize()
    auth = AuthService(db)
    auth.ensure_admin()
    result = auth.authenticate("admin", "admin123")
    assert result is not None
    assert result["role"] == "admin"
    db.close()
