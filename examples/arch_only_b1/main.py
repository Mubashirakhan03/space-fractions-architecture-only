"""Space Fractions — application entry point.

Run with:  python main.py
"""

from __future__ import annotations

import os
import sys

from spacefractions.auth import AuthService
from spacefractions.repository import Database, QuestionRepository


def build_app():
    """Construct the database, repositories and the Tk app."""
    db_path = os.environ.get("SPACEFRACTIONS_DB")
    db = Database(db_path)
    db.initialize()
    qrepo = QuestionRepository(db)
    qrepo.seed()
    auth = AuthService(db)
    auth.ensure_admin()

    from spacefractions.ui import App

    return App(db, qrepo, auth)


def main() -> None:
    app = build_app()
    app.mainloop()


if __name__ == "__main__":
    main()
