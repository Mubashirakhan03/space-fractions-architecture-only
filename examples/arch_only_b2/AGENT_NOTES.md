# AGENT_NOTES.md — agent memory

Space Fractions — educational fraction game (Tkinter desktop app).

Key decisions:
- Windows desktop app via tkinter; standard library only (tkinter, sqlite3, hashlib, dataclasses, enum, etc.).
- Components map: GameComponent -> spacefractions/game/ (game.py, fractions.py, state.py); QuestionComponent -> spacefractions/persistence/repository.py (SQLite); UserComponent -> spacefractions/user/user.py.
- Domain dataclasses: Game(id, score, questions, state), Question(id, prompt, options, correct_answer), User(id, username), Admin(id, username).
- State machine: Playing/Paused/GameOver (pause/resume/gameOver triggers).
- Persistence: SQLite file spacefractions.db, tables questions/users/games; seeded fraction questions on first run (ASR-1 data durability).
- UI flow: intro -> main menu (Play/View Score/Help/Admin) -> game (fraction questions) -> ending scene (score + feedback); admin panel for question CRUD.
- User auth: hashlib SHA-256 salted password hashing.
- Conventions: dataclasses for entities; parameterized SQL; main.py entry guard for Tk.

Tests (pytest): game scoring/state, fraction math, persistence CRUD, user auth.
