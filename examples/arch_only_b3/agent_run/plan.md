# Space Fractions — Desktop Implementation Plan

## Overview
Implement "Space Fractions" — an educational fraction game as a Windows desktop Tkinter application, following the architecture spec. The spec describes a domain model with Game, Question, User, and Admin entities plus the four implied features (introductory movie, main menu, series of fraction questions, ending scene with feedback). Although the spec's tech stack lists web/server technologies, the deliverable is a self-contained desktop app (per harness rules), so I implement an embedded SQLite persistence layer (satisfying ASR-1 data durability) and a clean three-component architecture mirroring GameComponent, QuestionComponent, and UserComponent.

## Modules & Responsibilities
- `spacefractions/__init__.py` — package init, version.
- `spacefractions/models.py` — dataclasses: Question, Game, User, Admin (mirroring class diagram attributes/methods).
- `spacefractions/question_component.py` — QuestionComponent: question management + SQLite persistence (CRUD, seed data of fraction questions).
- `spacefractions/user_component.py` — UserComponent: user authentication/authorization (simple local user store).
- `spacefractions/game_component.py` — GameComponent: game logic, state machine (Playing/Paused/GameOver), scoring, answer checking.
- `spacefractions/state_machine.py` — explicit state machine (states + transitions from spec).
- `spacefractions/db.py` — SQLite schema and connection helpers (games, questions, users tables; mirrors DDL).
- `spacefractions/ui.py` — Tkinter UI: introductory movie scene, main menu, game scene (question loop), ending scene with feedback and score.
- `spacefractions/__main__.py` / `main.py` — entry point (guarded by `if __name__ == "__main__":`).

## UI flow (implied features)
1. Introductory "movie" — animated welcome scene (starfield text animation).
2. Main menu — Play, View Score, Help, Admin (Update Questions).
3. Game scene — series of fraction questions, pause/resume, score.
4. Ending scene — feedback + final score, return to menu.

## State machine
States: Playing, Paused, GameOver. Transitions: [*]→Playing (start), Playing→Paused (pause), Paused→Playing (resume), Playing→GameOver (gameOver).

## Persistence (ASR-1 data durability)
SQLite DB (`spacefractions.db` in a user data dir) with `users`, `questions`, `games` tables. Seed with fraction questions. Games persist game_state as JSON.

## Testing
pytest tests in `tests/` covering: question component CRUD + persistence, user auth, game logic/scoring/state machine, and fraction answer evaluation. UI not launched in tests.

## Deliverables
- `main.py`, `spacefractions/` package
- `requirements.txt` (empty — stdlib only)
- `README.md`
- `tests/test_*.py`
- `AGENT_NOTES.md`