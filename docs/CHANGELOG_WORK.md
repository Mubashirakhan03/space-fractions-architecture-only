# Work Change Log (backup & rollback guide)

Every change is recorded here: what changed, why, which files, the commit, and **how to undo it**.

## How to roll back
| I want to… | Command |
|---|---|
| See all restore points | `git tag` and `git log --oneline` |
| Undo one commit (safe, keeps history) | `git revert <commit-hash>` then `git push` |
| Look at the project as it was at a phase | `git checkout phase-N` (go back: `git checkout main`) |
| Restore one file from a phase | `git checkout phase-N -- path/to/file` |
| Throw away uncommitted local edits to a file | `git restore path/to/file` |

Original inputs are also kept untouched in `D:\professor project\Task1\`.

---

## Entries

### 2026-10-18 — Phase 0 (research & setup)
- **Created** folder `space-fractions-code-agent/` with `docs/` and `samples/`.
- **Copied** `PROMPT (1).md` → `docs/PROMPT.md`; `Task1-EN.docx` (removed from the repo on 2026-10-20), `Architecture_Documentation.md`,
  `Architecture_View.md` → `docs/`; the two `.md` inputs → `samples/`.
- **Copied** `Task1/env` → `.env` (secret, gitignored).
- **Added** `.gitignore` (secrets, Python, build outputs).
- **Added** docs: `RESEARCH_NOTES.md`, `DECISIONS.md`, `CHANGELOG_WORK.md`, `PROGRESS.md`, `LEARNING_NOTES_UR.md`.
- Commit: `d37cc8f` — tag `phase-0`
- Rollback: delete the `space-fractions-code-agent/` folder; `Task1/` is unchanged.

### 2026-10-18 — Phase 1 start (git + GitHub)
- Installed GitHub CLI 2.102.0 (`winget install GitHub.cli`); user logged in as `Mubashirakhan03`.
- `git init -b main`, identity `Mubashira <mubashirakhan1001@gmail.com>`; verified `.env` ignored (`git check-ignore`).
- Added `.env.example`, `LICENSE` (MIT), starter `README.md`.
- Created public repo https://github.com/Mubashirakhan03/space-fractions-code-agent and pushed `main` + tag `phase-0`.
- Recorded scope decisions D-008…D-011 (only deepseek-v4-pro, DeepSeek + Mock only, mock-only dev, stop before paid runs).
- Commit: `d37cc8f` (same first commit)
- Rollback: `gh repo delete Mubashirakhan03/space-fractions-code-agent` (irreversible, ask first) / `rm -rf .git`.

### 2026-10-18 — Phase 1 (skeleton, config, providers, parsers)
- `.venv` (Python 3.12) with openai 3.35, customtkinter 6.0, PyYAML, python-dotenv, jsonschema, pytest, ruff, pyinstaller.
- Added `pyproject.toml` (ruff + pytest config), `requirements.txt`, `requirements-dev.txt`, `.gitattributes`.
- `b04d26d` feat(llm): `app/llm/provider.py` (interface + types), `deepseek.py` (v4-pro only, thinking off, retry/backoff,
  friendly 401/402 errors), `mock.py` (scripted, zero cost), `pricing.py` (off-peak/peak), `app/config.py`
  (%APPDATA% config, env/.env key, `mask_key`). Tests: `test_config.py`, `test_providers.py`.
- `b84f0b0` feat(parser): `app/parsers/doc_parser.py`, `uml_parser.py`, `spec.py` + `schemas/spec.schema.json`.
  Tests: `test_doc_parser.py`, `test_uml_parser.py`, `test_spec.py` (35 tests total, all passing, ruff clean).
- (this commit) `scripts/check_secrets.py` + `scripts/install_hooks.py` — pre-commit hook blocks keys (verified with a fake key).
- Rollback: `git revert <hash>` for one commit, or `git checkout phase-0 -- <file>`; whole phase: `git reset --hard phase-0` (destructive, ask first).

### 2026-10-18 — Phase 2 (tools, sandbox, agent loop, context, prompts)
- `abc710f` feat(tools): `app/tools/sandbox.py` (path guard, harness dir read-only, blocked script types, ReadState
  read-before-edit + mtime), `registry.py` (JSON-schema tools, mode permissions, parallel read-only batches,
  errors as results), `builtin.py` (list_dir, read_file, glob, search_text, write_file, write_files, edit_file,
  run_python, update_todos, submit_plan, finish), `runner.py` (bundled interpreter via `app.main --run-pytest/
  --run-script`, timeout + process-tree kill, secrets stripped from env), `app/main.py` (hidden sub-commands),
  `app/agent/planner.py` (TodoList). Tests: `tests/test_tools.py`.
- `087b40e` feat(agent): `app/agent/loop.py` (two-layer loop + pipeline plan → implement → verify ⇄ fix → report,
  limits, resume), `context.py` (tool-output cap → disk, microcompact, auto-compact with restated instructions;
  cached prefix not counted), `prompts.py` (layered system prompt + output contract + compact spec), `state.py`,
  `transcript.py`, `replay.py` (ReplayProvider), `report.py` (RUN_REPORT.md, required deliverables).
  Tests: `tests/test_agent_loop.py` (15 mock end-to-end scenarios). Total 74 passed, 1 skipped (symlink test on Windows).
- Measured fixed prompt prefix ≈ 5.2K tokens (system 1.4K + compact spec 2.9K + tool schemas 1K).
- Rollback: `git revert 087b40e` / `git revert abc710f`, or `git checkout phase-1 -- app/` to restore Phase 1 code.

### 2026-10-18 — Phase 3 (GUI)
- `04c72c5` feat(gui): `app/gui/app.py` (customtkinter window: provider/key, inputs, output, limits, fixed action bar,
  phase strip, MOCK/REPLAY banner, tabs Log/Todos/Spec preview/Report, usage+cost line), `app/gui/controller.py`
  (worker thread + queue, provider factory, ask-before-write bridge, input pre-fill, launch generated game),
  `app/llm/demo_script.py` (scripted MOCK DEMO project, clearly labelled as not LLM-generated).
  Tests: `tests/test_gui.py` (controller + real-window smoke run). Total 81 passed, 1 skipped.
- New runs require an empty output folder (prevents mixing two runs; nothing is ever deleted).
- Paid run asks for confirmation with prices and the run's hard limits.
- Screenshot: `docs/screenshots/gui_mock_run.png`. Pillow installed in `.venv` only for screenshots (not a dependency).
- Verified manually: "Run generated game" opens the generated Tk window via the bundled interpreter.
- Rollback: `git revert 04c72c5` or `git checkout phase-2 -- app/` (GUI files are new, so revert removes them).

### 2026-10-18 — Phase 4 (exe build, verification, CI)
- `a193ed2` build: `SpaceFractionsAgent.spec` (one-file, windowed, icon; bundles customtkinter assets, openai SDK,
  pytest via `pytest.freeze_includes()`, samples, schema, and the stdlib list in `app/bundled.py`), `run_agent.py`
  entry, `scripts/build_exe.bat`, `scripts/make_icon.py` → `assets/icon.ico/.png`, `app/selftest.py`
  (`--doctor`, `--self-test`), `scripts/verify_exe.py`, `.github/workflows/build-windows.yml`.
- System prompt now lists exactly the bundled stdlib modules (generated code can only use what the exe contains).
- Local build: `dist/SpaceFractionsAgent.exe` 26.1 MB in ~1 min. `verify_exe.py` with PATH = Windows dirs only:
  6/6 PASS (--version, --doctor, --self-test incl. child-exe pytest "2 passed", --run-script frozen=True,
  GUI window, generated game window).
- Note: "no Python" is simulated by stripping PATH/PYTHON* env vars; a clean-PC test (e.g. Windows Sandbox or
  another laptop) is still recommended before submission.
- Rollback: `git revert a193ed2`; build outputs (`build/`, `dist/`) are gitignored and can simply be deleted.
- CI run 39153253009 on windows-latest: lint, 81 tests, build and verify_exe 6/6 PASS on a clean GitHub runner;
  artifact `SpaceFractionsAgent-windows` uploaded.
- Bumped actions to checkout@v7, setup-python@v7, upload-artifact@v7, action-gh-release@v3 (Node 20 deprecation).
- CI run 39153490927 green with Node 24 actions (no warnings).
- `max_output_tokens` default 8192 → 32768 and implement prompt asks for 4-6 files per `write_files` call
  (a full module batch does not fit in 8K output tokens; a cut-off reply would break the tool-call JSON).

### 2026-10-19 — Pre-Phase-5 improvements (user request: generic agent + GUI polish)
- `e8bf914` feat(agent): generic system prompt + output contract; `app/agent/profile.py`; `profiles/space_fractions.md`;
  generic required deliverables (+ profile `required_files`); `samples/library_tracker/`; samples/profiles copied
  to `Documents\SpaceFractionsAgent` in the exe; parser testing-matrix lookup made generic. Tests: `tests/test_generic.py`.
- (this commit) feat(gui): redesigned window (`app/gui/app.py`, new `app/gui/theme.py`): header + subtitle +
  provider/model badge, cards with labels, phase bar with states incl. "skipped (not needed)", colour-coded log,
  status bar (requests / tokens / cache-hit % / cost / elapsed), fit-to-screen sizing, friendly key/balance errors
  (`friendly_key_problem`, DeepSeek 401/402 messages). README: "The agent is generic" + "How to use with your own
  architecture docs". Screenshots: `docs/screenshots/gui_idle.png`, `gui_mock_run.png`.
- `scripts/verify_exe.py`: only counts NEW windows (ignores windows the user already has open) and kills both
  bootloader and child processes.
- Tests: 94 passed, 1 skipped. New exe built to `build/dist_new/` (old one was locked by open windows), verified
  6/6 PASS without Python, then copied to `dist/`.
- Rollback: `git revert <this hash>` (GUI) and/or `git revert e8bf914` (generic agent); `git checkout phase-4 -- app/`.

### 2026-10-19 — UI/UX round 2 (user request: 4 items + maximized apps)
- GUI: success dialog "Project generated successfully! … Tests: PASSED" with Run generated app / Open folder /
  Close, green banner; failure/stop → red banner + dialog with the reason and "View report".
- "Run generated app" enabled only when the selected folder holds a completed, verified run (`run_succeeded`);
  then bold green with a pulsing border; disabled/grey otherwise (re-checked when the folder changes).
- Non-empty output folder → dialog: Create new subfolder `run-YYYY-MM-DD_HHMM` (recommended) / Overwrite
  (deletes ONLY files recorded in the previous run's state + `agent_run/`; user files kept) / Resume / Cancel.
- API key button toggles "👁 Show" ⇄ "🙈 Hide".
- Agent: generic **UI quality rules** in the system prompt (≥1100×750, maximized, F11/Esc, big fonts, hover
  buttons, Enter submits, auto-clear input, coloured feedback, screens as Frames + `create_app(root)`);
  `tests/test_ui_smoke.py` is now a required deliverable and verify checks it asserts `minsize`.
  Kid-friendly rules added to `profiles/space_fractions.md` (space theme, 36/30/20 pt fonts, progress, pause,
  feedback then auto-next, end screen with stars + confetti).
- Mock demo (clearly labelled MOCK): maximized space-themed window, 3 questions, auto-clear, coloured feedback,
  Congratulations screen with stars + confetti, its own headless UI smoke test.
- Robustness found while testing: re-creating `tk.Tk()` after `destroy()` can crash the frozen exe on Windows
  (fatal 0x80000003) and Tk init can fail transiently ("Can't find a usable init.tcl"). Fixes: ONE session Tk
  root in UI tests (rule also added to the system prompt), retries for Tk creation, `create_window()` retry in
  the GUI launcher, test teardown cancels pending `after()` callbacks.
- Tests: 98 passed, 1 skipped. Frozen exe: demo UI tests 8/8 runs green; verify_exe 2/2 ALL PASSED.
- Screenshots: `docs/screenshots/gui_success.png`, `mock_demo_feedback.png`, `mock_demo_end.png`.
- Rollback: `git revert <this hash>`.

### 2026-10-19 — Phase 5, real run 1 + agent improvements
- `scripts/run_agent_cli.py`: headless run (same Agent as the GUI) printing one line per event.
- Balance check via `GET /user/balance` (no tokens): $2.00 topped up.
- Real run 1 (deepseek-v4-pro, profile space_fractions): 40 requests → stopped at cap → Resume +4 → completed,
  VERIFY PASSED, $0.103 total. Saved as `examples/space_fractions_run1/` (+ CLI logs). Details: `docs/REAL_RUNS.md`.
- Visual check found canvas drawn with `winfo_width()==1` (stars collapsed, title/question text invisible).
  NOT fixed by hand. Instead: `app/agent/ui_probe.py` (harness UI layout probe in Verify), new UI rules in the system
  prompt (<Configure> drawing, create_app/screens/show contract), batch-edit rule; mock demo follows the contract.
  Tests: `tests/test_ui_probe.py` (bad layout flagged, good passes, crashing screen flagged, no-UI skipped).
- Tests: 102 passed, 1 skipped.
- Rollback: `git revert <this hash>`; run-1 folder can be deleted without affecting the agent.

### 2026-10-19 — Generic UI style: "UI design brief"
- System prompt: removed all app-specific style words (stars/planets, "question/game" examples, children);
  style now comes from a **UI design brief** the agent derives from the spec in the Plan phase and writes as
  DESIGN_DECISIONS.md section 5 (users, mood, hex palette with roles, fonts, layout, key screens). Examples:
  Tic-Tac-Toe → playful big 3x3 board; library tracker → calm, table based; learning app → bright, encouraging.
  Implement phase must follow it (palette/fonts in ui/theme.py). Generic quality rules kept.
- `submit_plan` rejects design_decisions without a "UI design brief" section.
- Tests: generic prompt contains none of 21 Space-Fractions words (whole-word check, stdlib module names excluded);
  plan/contract/implement mention the brief; submit_plan brief enforcement. 120 passed, 1 skipped.

### 2026-10-19 — Phase 5, real run 2 (final example)
- Run 2 with the improved agent: completed on the first attempt, VERIFY PASSED + UI PROBE OK on 9 screens,
  27 requests, $0.096 (balance $1.89 → $1.72). Output: `examples/space_fractions_generated/` (+ `agent_run/cli_log.txt`).
- Screenshots of every screen: `docs/screenshots/run2/`. Findings (incl. the feedback-shows-next-answer logic bug,
  left unedited) in `docs/REAL_RUNS.md`. `.gitignore`: `examples/**/*.db` (created when the generated app runs).

### 2026-10-19 — Option B: agent rules from run 2's findings (Run 3 deferred to off-peak, after 15:00 PKT)
- System prompt rule 10: compute every value a user-visible message needs BEFORE advancing/mutating state and
  test every message incl. the wrong-input path (generic wording — targets run 2's "feedback shows the next
  item's expected value" bug). UI smoke test must cover one correct AND one wrong submission. New rule: buttons
  never cover text on text-heavy screens.
- UI probe: detects a button covering a text label on the visible screen (flags run 2's Help screen, no false
  positives on its other 8 screens); a broken `ui/app.py` is now a failure instead of "skipped".
- Tests: 123 passed, 1 skipped.

### 2026-10-19 — Phase 5, real run 3 (after 15:00 PKT, off-peak)
- Run 3 → `examples/space_fractions_run3/`: probe caught off-window buttons → agent fixed in 1 fix round → VERIFY PASSED
  + UI PROBE OK; 54 requests, $0.131 (balance $1.59). Rule 10 fixed the wrong-feedback bug; Help overlap fixed.
- New finding: pack/grid mix freezes the round after a typed→choice transition; feedback text partly behind buttons.
  Screenshots `docs/screenshots/run3/`; review in `docs/REAL_RUNS.md`. Generated code not edited.

### 2026-10-19 — Option C: agent improvements from run 3 (before run 4)
- UI rules: never mix pack and grid in one container (separate inner frames per layout); the UI smoke test must
  play ONE complete flow to the result screen covering every input variant with real-time pumping and
  `report_callback_exception` (no Tk callback errors allowed).
- Tool usage: project files change only via write_files/edit_file/**delete_file**; run_python scripts are for
  checks only. New sandboxed `delete_file` tool (files only, not agent_run/, not in plan mode, ask-before-write aware).
- UI probe: pumps each screen for 1.2 s so the app's timers run and fails on any Tk callback exception; timeout 120 s.
- Tests: delete_file sandbox, probe callback-error detection, rule presence. 126 passed, 1 skipped.

### 2026-10-19 — Phase 5, real run 4 (final example)
- Run 4 → `examples/space_fractions_run4/`: 54 requests stopped at the 2M token cap (cache-heavy), Resume +3 →
  VERIFY PASSED + UI PROBE OK; 57 requests, $0.142 (balance $1.45). 5 real-timer rounds with mixed inputs: 0 errors.
- Renamed `examples/space_fractions_generated` (run 2) → `examples/space_fractions_run2` so all runs are named
  consistently (older log entries above refer to the old name). `scripts/run_agent_cli.py --max-tokens`.
- Screenshots `docs/screenshots/run4/`; review + summary of all runs in `docs/REAL_RUNS.md`. Total spend ≈ $0.55.

### 2026-10-19 — Phase 6 (README, docs, v1.0.0 build)
- README rewritten for the professor (quick start, diagram, 16-mechanism table, web→desktop, input issues, real-run
  summary, known limitations, build/test, credits); `docs/ARCHITECTURE.md`; `docs/VIDEO_SCRIPT.md`; `CHANGELOG.md`.
- Version 1.0.0 (`app/__init__.py`, `pyproject.toml`); `verify_exe.py` reads the version from `app`.
- Exe rebuilt from the final code: verify_exe 6/6 PASS without Python. Tests: 128 passed, 1 skipped.
- Release v1.0.0 = push tag `v1.0.0` (CI builds, verifies and attaches the exe) — waiting for the user's OK.

### 2026-10-19 — Three more generic improvements before run 5 (user request)
- UI probe checks every screen at 1280x800 AND at the minimum size (app minsize, never below 1100x750).
- Probe flags button text that is cut off (squeezed by pack, or overflowing its container) and shown text inputs
  without a visible button next to them.
- Rule: every text input has a visible Submit/Check button (Enter also submits); "design every screen to fit 1100x750".
- On run 4's game the new probe reports 8 problems (incl. the hidden Exit and clipped buttons); mock demo stays OK.

### 2026-10-19 — Real run 5 (final example) + probe false-positive fix
- Run 5 → `examples/space_fractions_run5/`: 47 requests, $0.122 (balance $1.32). In-run verify FAILED after 3 fix rounds;
  the agent fixed real problems in rounds 1–2 (screens never placed; admin too tall → scrollable list), and round 3's
  remaining "problems" were rows of the scrollable list = probe false positive.
- `app/agent/ui_probe.py`: widgets inside a scrollable Canvas are skipped for off-window/clipped/overlap checks
  (+ test). Unchanged output re-verified without API: compile OK, 41 tests, probe OK @1280x800 and @1100x750 →
  `docs/run5_reverification.txt`.
- Play-test: 5 real-timer rounds, heavy typed/choice mixing, 0 Tk errors. Found: intro 8 s auto-advance not cancelled by
  Skip (documented). Screenshots `docs/screenshots/run5/` (14).
- Final example switched to run 5 in README / VIDEO_SCRIPT / CHANGELOG.md (D-019). Total spend ≈ $0.68. Tests: 134.

### 2026-10-19 — Release v1.0.0 (user approved)
- Pushed tags `v1.0.0` and `phase-6` on `48fcc02`. CI run 39251682136 built + verified the exe and published
  https://github.com/Mubashirakhan03/space-fractions-code-agent/releases/tag/v1.0.0 with `SpaceFractionsAgent.exe` (26.6 MB).
- Release notes set from CHANGELOG.md. The released exe was downloaded and re-verified without Python: 6/6 PASS.
- Rollback: `gh release delete v1.0.0 --cleanup-tag` (irreversible for downloaders; ask first).
- Remaining: user records the video (script in docs/VIDEO_SCRIPT.md), then the link is added to README.

### 2026-10-19 — User report: quiz app "cannot import name 'centered' from 'ui.widgets'" (+ 3 fixes)
- Diagnosis (generated code read, NOT edited): `main.py` imports `centered` but that run's own `ui/widgets.py` has no
  such function → a genuine generated bug; verify missed it because tests never import main.py. Separately, the
  "new subfolder" option nested runs (run-0050/run-0116/run-0117/run-1725) — a real UX bug, not the cause.
- `app/agent/import_check.py` (new, in Verify; prompt mentions it); catches the user's case, passes run 5.
- `run_folder_base()`: new run folders become siblings of a run folder; dialog shows the full path.
- Resume: agent emits `resume` event; GUI marks completed phases done.
- Defaults: max_requests 80, config migration (CONFIG_VERSION 2).
- Tests: test_import_check.py, sibling folders, resume phases, config migration. 139 passed, 1 skipped.
- After the user closed the old exe: copied the new build to `dist/`; verify_exe on `dist/SpaceFractionsAgent.exe` 6/6 PASS.
  Import check run INSIDE the frozen exe on a copy of the user's quiz app reports the `centered` ImportError → works
  with the bundled interpreter too. Next: v1.0.1 release (version bump + tag) when the user approves.

### 2026-10-19 — Zero-score end screen (user report on the mock demo)
- Mock demo (written by Claude, so editing it is allowed): `stars_for` 0–3 (0 correct → 0), new `end_message`
  (<50 % "Good try! Keep practising", 50–79 % "Well done!", ≥80 % "Congratulations!"), confetti only at 3 stars,
  percentage shown; demo tests for 0/1/2/3 and a zero-score UI test (8 demo tests pass).
- `profiles/space_fractions.md`: end screen rule rewritten (score-dependent message, 0–3 stars, test zero and full
  score). Generic prompt: result message/rating must match the outcome (no praise for zero/failing).
- Run 5 checked at 0/10 (copy, not edited): title "Congratulations, Ayesha!" (wrong), ☆☆☆ (right), sub-message
  right → documented as a known limitation (README, REAL_RUNS) + screenshot `run5/14_end_zero_score.png`. No run 6.

### 2026-10-19 — User's quiz run (profile none): incomplete admin form, no seed data, "tk" title
- Generic UI rules added: forms include every required field (no silent defaults, validate, test add/edit),
  never ship empty (seed data on first start, ≥ 20 items for quiz-style apps, test seeding), `create_app` sets the
  window title. Output contract: data/ is required when the app manages content.
- UI probe: fails a default "tk" title unless main.py sets one (run 5 OK, user's quiz app flagged) + 2 tests.
- Profile: ≥ 20 seed questions (typed + choice), code-generated random questions every round, full admin form.
- Tests: 144 total (143 passed, 1 skipped). No paid run (run 6 only with the user's permission).

### 2026-10-19 — Generic random-rounds rule (all profiles) + exe to dist
- Prompt (generic, any domain): random draw from the whole pool incl. admin-added items, shuffled order; computable
  content also generated in code each round (computed answers, distinct wrong choices); tests required.
- UI probe: if nothing is mapped right after a resize, deiconify/lift and re-check once (fixed an intermittent
  "no labels visible" false alarm, 6/6 stable). Full suite 144 passed, 1 skipped.
- New exe copied to `dist/` (user closed all windows) and verified 6/6 without Python.

### 2026-10-19 — Real run 6 stopped: generated `app/` package collided with the agent's own `app` package
- Run 6 (profile none, $1 cap): the model created its own `app/` package (`app/controller.py`). Every `run_python`
  script/test then failed with "(no output, exit code 1)": dev mode ran `python -m app.main` from the output folder
  and Python found the GENERATED `app` ("No module named app.main"). In the exe the same name would have shadowed
  the generated package. The model spent requests diagnosing a harness bug, so the run was STOPPED at 52 requests,
  $0.127 (state saved → resumable).
- Fix: renamed the agent package `app/` → **`sfagent/`** (git mv; imports, spec, scripts, tests, docs). Older log
  entries above still say `app/…` = today's `sfagent/…`. Regression test: a generated project with its own `app/`
  package runs scripts and pytest. 145 passed, 1 skipped.
- Run 6 resumed twice (2nd stop: max_steps 60 → default now 100 + migration + `--max-steps`), completed: VERIFY
  PASSED, 110 requests, $0.378 (balance $0.57). Play-check found wrong generated "equivalent" items and invisible
  admin inputs → new generic rules (independent recomputation in generator tests, no ambiguous items, visible
  inputs) + UI probe input-visibility check + profile hint. Screenshots `docs/screenshots/run6/`; REAL_RUNS run 6.
  Final example remains run 5. Tests: 148 passed, 1 skipped.

### 2026-10-19 — Run 7 (user's GUI run) = final example; `write_files` keyed by path
- Run 7 = the user's own GUI run (profile none, `run-2026-10-19_2320`): VERIFY PASSED after 2 fix rounds, 42 requests,
  $0.144. Copied unchanged to `examples/space_fractions_run7_gui/` (caches removed, no keys found). Re-verified with
  the current harness → `docs/run7_reverification.txt` (33 files compile, 29 tests, import check, probe OK at both
  sizes). Played a copy: 25 seeds, random rounds, 1000 generated items checked (all correct except trivial
  equivalent items), 0/5 result without praise, 0 Tk errors. Screenshots `docs/screenshots/run7/`.
- README (final example, screenshots, real-runs table incl. runs 6–7, known limitations: no score/progress on the
  game screen, free-text admin Kind, trivial equivalent items, admin items only after restart), REAL_RUNS (run 7 +
  summary), DECISIONS D-020/D-021, CHANGELOG [1.0.1].
- `write_files`: `files` is now an object keyed by path; the list form still works (`sfagent/tools/builtin.py`
  `_file_entries`), schema/description, prompt rule 4, log summary (`loop.py`), mock demo uses the object form;
  4 new/updated tests in `tests/test_tools.py`. Tests: 151 passed, 1 skipped. No paid run.
- Rollback: `git revert <this commit>` (or `git checkout e467af1 -- sfagent/tools/builtin.py` for the tool only).
- Exe rebuilt → `build/dist_new/SpaceFractionsAgent.exe` (26 MB), `verify_exe.py` 6/6 PASSED without Python
  (self-test exercises the path-keyed `write_files`). Not copied to `dist/` yet: the old exe was still open.
  Version is still 1.0.0; it is bumped to 1.0.1 only when the release is approved.

### 2026-10-19 — Spec coverage, animated scene and admin PIN (generic rules + harness checks)
- New `sfagent/agent/spec_rules.py`: derives from the spec the named screens/scenes (`implied_features`), use cases,
  animation phrases ("introductory movie", "animated …", "splash screen", "opening scene"…) and administrator-type
  actors. A "Harness checklist" with this spec's exact names is appended to the first user message (system prompt
  unchanged per spec → cache prefix stable).
- System prompt (generic, no app words): "Spec coverage", "Animated scenes" (Canvas, moving objects, 5–10 s, Skip,
  auto-advance, cancel after() on leave, test) and "Protected roles" (in-window PIN screen, masked Entry, wrong PIN
  refused, lock on leave, default PIN in README, tests).
- UI probe: canvas snapshots at 0 / 0.6 / 1.2 s per screen; fails if the spec asks for an animation and nothing
  moves, or the animated screen has no Skip button; fails if a protected role exists and no screen has a masked
  input. Real examples: run 7 (static intro, no PIN) is flagged for both; run 5 (rocket intro) passes the animation
  check and is flagged only for the missing PIN.
- Mock demo: 6-second rocket intro with Skip + auto-advance, admin PIN screen (1234) and admin screen; 2 new UI tests.
  Profile: admin behind a PIN. Tests: test_spec_rules.py (4), test_ui_probe.py (+4). 159 passed, 1 skipped.
- Rollback: `git revert <this commit>`.

### 2026-10-19 — Real run 8 (final example) + choice-item rule
- Run 8: profile none, $1 cap, off-peak (19:16 UTC), `runs/run8_final` → VERIFY PASSED after 1 fix round, 58 requests,
  $0.159, 0 write_files errors. Copied to `examples/space_fractions_run8_final/` (without the `game.db` its tests
  created; CLI log in `agent_run/cli_log.txt`). Re-verified incl. animation/PIN checks → `docs/run8_reverification.txt`.
  Play-check + screenshots `docs/screenshots/run8/`. Findings → REAL_RUNS run 8, README known limitations, D-022.
- Prompt: "every choice item has exactly ONE option that satisfies the prompt" (+ test). Not tested in a real run.
- Rollback: `git revert <this commit>`; previous final example = run 7 (D-020).

### 2026-10-19 — Rule: a role that manages records gets a full list with Add/Edit/Delete
- User finding: their GUI run `run-2026-10-20_0038` had an admin screen with only "Add Question" (no list of the seed
  records, no Edit/Delete), although the spec has Admin → "Update Questions".
- `spec_rules`: use cases starting with update/manage/maintain/administer/edit/curate → `managed` (role, use case),
  listed in the harness checklist. Prompt rule "Data management by a role" (list of ALL records incl. seed data, Add,
  Edit, Delete, tests for each).
- UI probe: on the screen named after the role, fails if data/*.json has seed records but the list is empty, or Add /
  Edit / Delete buttons are missing (Listbox, Treeview or one row per Edit/Delete button; a list filled only when
  unlocked is re-checked after setting the app's own unlock flag). Real outputs: run 7 and run 8 pass, the user's
  0038 run is flagged. Mock demo admin: Listbox + Add/Edit/Delete. Tests 163 passed, 1 skipped.
- Rollback: `git revert <this commit>`.

### 2026-10-20 — Real run 9 = final example
- Run 9 (profile none, $1 cap): 402 at 34 requests → user topped up → resumed at peak (user's choice) → stopped by the
  user at 48 → auto-resumed 15:01 PKT off-peak → VERIFY PASSED, 59 requests, ≈ $0.38 actual ($0.284 estimated).
- Copied to `examples/space_fractions_run9_final/` (without `.db` files; CLI log in `agent_run/cli_log.txt`).
  Re-verified incl. animation / PIN / admin-list checks → `docs/run9_reverification.txt`. Play-check + screenshots
  `docs/screenshots/run9/`. README (final example, run table, known limitations), REAL_RUNS run 9, D-023, CHANGELOG.
- Rollback: `git revert <this commit>`; previous final example = run 8 (D-022).
- Exe rebuilt with the data-management rule → `build/dist_v101/` (build/dist_new was locked by an open exe),
  verify_exe 6/6 PASSED without Python, copied to `dist/`. Version still 1.0.0 until the release is approved.

### 2026-10-20 — Release v1.0.1 (user approved: "Run 9 final rahe, v1.0.1 release kar do")
- Version 1.0.0 → 1.0.1 (`pyproject.toml`, `sfagent/__init__.py`); CHANGELOG [1.0.1] dated 2026-10-20.
- Tag `v1.0.1` pushed → GitHub Actions builds, verifies and attaches `SpaceFractionsAgent.exe` to the release.
- Final example: run 9 (`examples/space_fractions_run9_final/`).
- Rollback: delete the release on GitHub + `git push --delete origin v1.0.1` + `git revert <this commit>`.

### 2026-10-20 — Cleanup after v1.0.1 (no new release)
- README "Real runs" table (and the REAL_RUNS summary table): removed the blank lines before the run 8 / run 9 rows,
  which split the table on GitHub.
- `docs/Task1-EN.docx` removed from the repo (`git rm`); its mentions in `docs/PROMPT.md` removed.
- `docs/PROMPT.md`: personal part removed (who I am, Master's application, deadline, the professor's e-mails, personal
  e-mail address, "interviews"); the technical instructions and the verbatim Task 1 instructions are kept.
- Rollback: `git revert <this commit>` (the docx comes back with it). The files stay in older history and in v1.0.1.

---

# Architecture-only variant (separate folder and repo `space-fractions-architecture-only`)

### 2026-11-09 — Variant created from v1.0.1 (commit 283156b)
- Why: the user's research needs an agent that builds the application from the architecture alone, with no
  requirements from the user or the developer (see `docs/EXPERIMENT.md`). The original repo and GitHub stay as they are.
- Folder: `git clone` of the original into `D:\professor project\space-fractions-architecture-only`, `origin` removed
  (nothing can be pushed by accident), own `.venv`, `.env` copied (gitignored), secret hook installed.
- Prompt (`sfagent/agent/prompts.py`): only the task's conditions + agent working rules; removed UI_QUALITY, rule 3
  (Tkinter-free domain), rule 10, UI design brief, TRACEABILITY / DESIGN_DECISIONS / UI-smoke deliverables, the
  spec checklist and the task profile. `architecture_only()` strips `target_platform` (it said "SQLite file"),
  `input_issues` and `platform_conflicts` from what the model sees and from `agent_run/spec.json`.
- Switch `record_deviations` (config, GUI checkbox, CLI `--record-deviations`): adds rule 9 (deviation table in
  DESIGN_DECISIONS.md). OFF: the plan is saved to `agent_run/plan.md` instead of the project.
- Original input files are copied to `agent_run/inputs/` for the model to read.
- Verify: deliverables (main.py, README.md, requirements.txt, tests) + compile + own tests + import check + new
  **launch check** (`sfagent/agent/launch_check.py`: main.py runs 3 s; crash / Tk callback error / no window fails).
  Removed: `ui_probe.py`, `spec_rules.py`, `profiles/space_fractions.md` and their tests.
- App identity: `APP_NAME = SpaceFractionsArchOnly` (own %APPDATA% config and Documents folder), window title
  "… — architecture only", exe `SpaceFractionsArchOnly.exe`.
- Tests: new `tests/test_arch_only.py` (no requirement words in the system prompt for both switch states, harness
  analysis never shown, profile ignored, switch behaviour, launch check); old generic/probe tests removed.
  175 passed, 1 skipped. `docs/MODEL_INPUT.md` written by `scripts/dump_model_input.py`.
- Rollback: delete the folder `space-fractions-architecture-only` (the original project is untouched).

- Exe: `profiles` removed from the PyInstaller spec and `list_profiles()` from the controller; built
  `dist/SpaceFractionsArchOnly.exe` (26.5 MB), verify_exe 6/6 PASSED without Python.

### 2026-11-09 — Own GitHub repository (user request)
- The user asked for a separate GitHub repository for this variant with all files and logs.
- Created https://github.com/Mubashirakhan03/space-fractions-architecture-only (public), `origin` set to it, `main` pushed (all code, docs, logs and example transcripts). No release yet; the push to `main` runs the CI build, whose exe is downloadable as an Actions artifact.
- The original repository https://github.com/Mubashirakhan03/space-fractions-code-agent is not changed.
- Rollback: `gh repo delete Mubashirakhan03/space-fractions-architecture-only` (and `git remote remove origin`).

### 2026-11-09 - Study protocol and freeze (user's 5 points)
- docs/EXPERIMENT.md: section 'Study protocol (Agent B)': minimal saved prompt, desktop as the only condition, no 'give reasons' instruction (study runs use the switch OFF), agent frozen at tag `agent-b-frozen` before the first run, same model/inputs/tools as A, 2-3 runs (one run = pilot).
- No code change. Rollback: `git revert` this commit and `git tag -d agent-b-frozen`.
