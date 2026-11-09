# Space Fractions

An educational desktop game for Windows that helps players practice adding
fractions, wrapped in a playful space theme. Built entirely with the Python
standard library (Tkinter GUI, SQLite persistence).

## Features

- **Introductory movie** — an animated welcome screen before the game starts.
- **Main menu** — Play Game, View Score, View Help, and Admin options.
- **Fraction questions** — a series of multiple-choice fraction addition
  problems.
- **Ending scene** — final score with tailored feedback.
- **Admin panel** — add and delete questions (persisted to SQLite).
- **User accounts** — salted SHA-256 password hashing.
- **Data durability (ASR-1)** — questions, users, and game results are stored
  in a local SQLite database.

## Requirements

- Python 3.9+ with Tkinter (included in the standard Windows Python installer).
- No third-party runtime dependencies.

## Running

```bash
python main.py
```

## Architecture

The implementation mirrors the domain model from the architecture document:

| Component           | Module                                   |
|---------------------|------------------------------------------|
| `GameComponent`     | `spacefractions/game/` (game, fractions, state) |
| `QuestionComponent` | `spacefractions/persistence/repository.py` |
| `UserComponent`     | `spacefractions/user/user.py`            |
| `AdminComponent`    | `spacefractions/admin/admin.py`          |

Domain entities (`dataclasses`): `Game`, `Question`, `User`, `Admin`.
Game states follow the state machine: `Playing`, `Paused`, `GameOver`.

## Persistence

SQLite file `spacefractions.db` (created in the user home directory by
default; override with the `SPACEFRACTIONS_DB` environment variable). Tables:
`questions`, `users`, `games`.

## Testing

```bash
pip install pytest
pytest
```
