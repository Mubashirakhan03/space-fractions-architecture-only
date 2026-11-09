# AGENT_NOTES.md — agent memory

# AGENT_NOTES.md — Space Fractions

## Key decisions
- Desktop Tkinter app (per harness rules), not the web/server stack listed in the spec's tech_stack.
- Three components mirror the spec: GameComponent, QuestionComponent, UserComponent.
- SQLite (stdlib sqlite3) provides persistence for ASR-1 data durability; JSON for trivial data, JSON columns for game_state.
- State machine (Playing/Paused/GameOver) implemented explicitly, matching spec transitions.
- Fraction answers use the stdlib `fractions.Fraction` for exact comparison (accepts "3/4", "0.75", "3 4", etc.).
- UI flow = implied features: introductory movie → main menu → game loop → ending scene with feedback.

## Conventions
- Pure-logic modules (models, state_machine, components) have no Tkinter imports so they are unit-testable headlessly.
- All Tkinter imports live only in ui.py; entry point guarded by `if __name__ == "__main__":`.
- DB path stored in a module-level function; tests use tmp_path / in-memory SQLite.
- stdlib only; requirements.txt is effectively empty.
