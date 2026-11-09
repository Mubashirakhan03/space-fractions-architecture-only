# Space Fractions

An educational desktop game that teaches fractions through an intergalactic
adventure. Built as a Windows desktop application using Tkinter and the Python
standard library (no third-party runtime dependencies).

## Features

- **Introductory movie** — an animated starfield welcome scene.
- **Main menu** — Play Game, View Score, Help, Admin (Update Questions), Quit.
- **Game scene** — a series of fraction questions with multiple-choice options
  and free-text entry (accepts `3/4`, `0.75`, or `3 4`), pause/resume, and a
  live score.
- **Ending scene** — feedback and your final score.
- Persistent question bank and game records via SQLite (ASR-1 data durability).

## Running

```bash
python main.py
```

Or as a module:

```bash
python -m spacefractions
```

## Architecture

The application mirrors the three components in the architecture specification:

- `spacefractions/game_component.py` — game logic, scoring, answer evaluation.
- `spacefractions/question_component.py` — question management & persistence.
- `spacefractions/user_component.py` — user authentication & authorization.

Supporting modules:

- `spacefractions/models.py` — domain entities (Question, Game, User, Admin).
- `spacefractions/state_machine.py` — Playing / Paused / GameOver state machine.
- `spacefractions/db.py` — SQLite schema & connection helper.
- `spacefractions/ui.py` — Tkinter scenes.

## Tests

```bash
python -m pytest
```
