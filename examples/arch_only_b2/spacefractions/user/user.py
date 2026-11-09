"""User domain entity and credential hashing."""

import hashlib
import secrets
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..game.game import Game


@dataclass
class User:
    """An end user who can play games and view scores.

    Attributes:
        id: unique identifier.
        username: display name.
        password_hash: salted SHA-256 hex digest, or None if not set.
        salt: per-user salt for password hashing.
    """

    id: str
    username: str
    password_hash: Optional[str] = None
    salt: str = field(default_factory=lambda: secrets.token_hex(16))

    # ---- authentication ---------------------------------------------------

    def set_password(self, password: str) -> None:
        """Store a salted hash of the given password."""
        self.salt = secrets.token_hex(16)
        self.password_hash = hash_password(password, self.salt)

    def verify_password(self, password: str) -> bool:
        """Return True if the password matches the stored hash."""
        if not self.password_hash or not self.salt:
            return False
        return hash_password(password, self.salt) == self.password_hash

    # ---- gameplay ---------------------------------------------------------

    def playGame(self, game: "Game") -> None:
        """Start playing the given game."""
        game.play()

    def viewScore(self, game: "Game") -> int:
        """Return the score of the given game."""
        return game.viewScore()


def hash_password(password: str, salt: str) -> str:
    """Hash a password with the provided salt using SHA-256."""
    digest = hashlib.sha256()
    digest.update((salt + password).encode("utf-8"))
    return digest.hexdigest()
