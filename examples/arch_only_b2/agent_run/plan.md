# Space Fractions — Implementation Plan

## Overview
A Windows desktop application (Tkinter) implementing the "Space Fractions" educational game where users answer a series of fraction questions and view their score. Follows the architecture's domain model (Game, Question, User, Admin), state machine (Playing/Paused/GameOver), and implied features (intro screen, main menu, fraction questions, ending scene with feedback).

## Package Structure (mirrors domain_model.packages)
- `spacefractions/game/` — Game + Question domain and game logic (state machine, scoring, fraction generation).
- `spacefractions/user/` — User domain.
- `spacefractions/admin/` — Admin domain.
- `spacefractions/persistence/` — SQLite-backed repositories implementing `QuestionComponent` (data durability, ASR-1).
- `spacefractions/ui/` — Tkinter views (intro, menu, game, score, admin panel).

## Components → Modules mapping
- **GameComponent**: `spacefractions/game/game.py` (play/score orchestration), `spacefractions/game/fractions.py` (question generation + answer checking), `spacefractions/game/state.py` (Playing/Paused/GameOver).
- **QuestionComponent**: `spacefractions/persistence/repository.py` (SQLite CRUD for questions/games/users via sqlite3).
- **UserComponent**: `spacefractions/user/user.py` (authentication with hashlib password hashing).

## Domain Model (dataclasses)
- `Game(id, score, questions, state)`: `start()`, `play()`, `viewScore()`, `pause()`, `resume()`, `gameOver()`, `submitAnswer()`.
- `Question(id, prompt, options, correct_answer)`: `getPrompt()`, `getOptions()`, `check()`.
- `User(id, username)`: `playGame(game)`, `viewScore(game)`.
- `Admin(id, username)`: `updateQuestions(questions)`.

## UI Flow
1. Intro screen (introductory movie substitute — animated welcome frame).
2. Main menu (Play Game, View Score, View Help, Admin).
3. Game screen (series of fraction questions, pause/resume, progress).
4. Ending scene (final score + feedback).
5. Admin panel (add/update/delete questions → persisted to SQLite).

## Persistence (ASR-1 data durability)
SQLite database `spacefractions.db` with tables: `questions`, `users`, `games`. Seed questions loaded on first run.

## Tests (pytest)
- Domain: Game scoring, state transitions, Question checking.
- Fractions: answer correctness, option generation.
- Persistence: CRUD round-trip, durability.
- User: authentication hashing.

## Conventions
- Python stdlib only (tkinter, sqlite3, hashlib, dataclasses, enum, etc.).
- `main.py` starts app under `if __name__ == "__main__":`.
- Repositories use parameterized SQL, no network.