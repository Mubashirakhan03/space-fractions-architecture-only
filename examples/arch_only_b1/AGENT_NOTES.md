# AGENT_NOTES.md — agent memory

## Space Fractions — key decisions

- **Target**: Windows desktop Tkinter app, Python stdlib only, no network, no third-party runtime deps.
- **Modules**: `spacefractions/models.py` (domain), `repository.py` (SQLite persistence), `auth.py` (login), `service.py` (game logic/state machine), `ui.py` (Tkinter views), `main.py` (entry, guarded main).
- **Persistence**: sqlite3; `games` table with JSON game_state (mirrors spec SQL DDL); `questions` table for question CRUD; `users` table for auth; `score_history` table.
- **Fractions**: use `fractions.Fraction` for exact arithmetic; random generator (FractionGenerator) + admin-managed questions; 10 seeded questions.
- **State machine**: Playing → Paused (pause()/resume()) → GameOver (gameOver()); GameService owns GameState and Game.
- **Roles**: end-user (play/score/help) and admin (update questions) via local auth (PBKDF2-HMAC-SHA256 + salt). Default admin: admin/admin123.
- **Tests**: pytest for models/repository/service/auth; UI kept thin (not unit-tested beyond import).
- **Conventions**: dataclasses for models; composition relationships (Game→Question, User→Game, Admin→Question); DB path default `~/.spacefractions/spacefractions.db`, overridable via `SPACEFRACTIONS_DB`.
- **Entry point**: `main.py`; start-up code under `if __name__ == "__main__":`.
