# Space Fractions — Implementation Plan

The architecture describes **"Space Fractions"**, a fraction-learning game with:
- 3 components: GameComponent, QuestionComponent, UserComponent (plus Admin).
- Domain model: Game, Question, User, Admin classes with specified attributes/methods.
- Use cases: Play Game, View Score, View Help, Update Questions (Admin).
- A game state machine: [*] → Playing → Paused → GameOver (pause/resume/gameOver).
- Implied features: introductory movie, main menu, series of fraction questions, ending scene with feedback.
- Data durability (ASR-1): questions persisted in SQLite (mirrors `sql/game_ddl.sql` — a `games` table with JSON game_state).

**Target**: a Windows desktop Tkinter application, Python stdlib only, no third-party runtime code, no network.

## Module layout

- `spacefractions/models.py` — dataclass-based domain model: `Question`, `Game`, `User`, `Admin` (composition relationships preserved: Game holds Questions, User holds Games, Admin manages Questions). Pure logic, easily unit-tested.
- `spacefractions/repository.py` — SQLite persistence (QuestionComponent + GameComponent persistence): `QuestionRepository` (CRUD + seed data), `GameRepository` (save/load game state as JSON, mirroring the SQL DDL), `Database` helper.
- `spacefractions/auth.py` — UserComponent: simple local authentication/authorization (admin vs end-user), stored in SQLite, hashed passwords (hashlib/salt).
- `spacefractions/service.py` — GameComponent orchestration: the game loop/state machine (Playing/Paused/GameOver), scoring, answer checking, fraction problem generation, session management. Thin, testable, UI-agnostic.
- `spacefractions/ui.py` — Tkinter views: introductory movie (animated canvas), main menu, question screen (series of fraction questions), pause dialog, ending scene with feedback/score, help, and admin question editor.
- `main.py` — entry point; sets up DB, builds the app, runs mainloop (guarded by `if __name__ == "__main__":`).
- `tests/` — pytest: `test_models.py`, `test_repository.py`, `test_service.py`, `test_auth.py`.
- `README.md`, `requirements.txt`, `AGENT_NOTES.md`.

## Key design decisions
- Persistence via `sqlite3` (stdlib) with a `games` table storing `game_state` JSON — directly mirrors the architecture's `CREATE TABLE games (... game_state JSONB)`.
- The "introductory movie" is a Tkinter canvas animation (space theme) skippable by click/key.
- Fraction questions: generated (random fractions, 4 options, correct answer) and seeded; answers validated with the `fractions.Fraction` module for exactness.
- Admin login (from db) unlocks "Update Questions" (add/edit/remove persisted questions).
- Score + feedback shown in an ending scene; score persisted to history.

## Testing
- compile check + pytest for models, repository, service, auth logic. UI is kept thin so it isn't unit-tested beyond import.