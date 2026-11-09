# Space Fractions

A Windows desktop fraction-learning game built with the Python standard library
(Tkinter + SQLite). Inspired by the game architecture: three components
(Game, Question, User + Admin), a game state machine, and a persisted question
bank backed by SQLite.

## Features

- **Introductory movie** — an animated space-themed splash screen (click/key to skip).
- **Main menu** — Play Game, View Score, View Help, Admin, Quit.
- **Series of fraction questions** — multiple-choice with exact fraction arithmetic.
- **Ending scene** — mission report with score and personalized feedback.
- **Admin mode** — sign in to add/edit/remove questions (persisted).
- **Persistence** — questions, games (JSON game state) and score history in SQLite.

## Requirements

- Python 3.8+ (standard library only; no third-party packages).
- Tkinter (bundled with standard Python on Windows).

## Run

```bash
python main.py
```

The database is stored at `~/.spacefractions/spacefractions.db`. To override
its location set the `SPACEFRACTIONS_DB` environment variable.

Default admin credentials: username `admin`, password `admin123`.
(Change them via the admin login flow after first run.)

## Test

```bash
python -m pytest tests
```

## Architecture mapping

| Component | Module |
|-----------|--------|
| GameComponent | `spacefractions/service.py` (state machine, scoring) |
| QuestionComponent | `spacefractions/repository.py` (question CRUD + seed data) |
| UserComponent | `spacefractions/auth.py` (authentication/authorization) |
| Game / Question / User / Admin | `spacefractions/models.py` |
| UI views | `spacefractions/ui.py` |

The `games` table persists a JSON game state, mirroring the architecture's
`CREATE TABLE games (... game_state JSONB)` DDL (JSON versus JSONB).
