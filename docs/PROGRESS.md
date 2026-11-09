# Progress Tracker

Read this first when resuming work in a new session.

> **This folder is the ARCHITECTURE-ONLY variant** (own GitHub repo https://github.com/Mubashirakhan03/space-fractions-architecture-only; the original repo https://github.com/Mubashirakhan03/space-fractions-code-agent is not changed by this variant). See
> `docs/EXPERIMENT.md`. Status 2026-11-09: variant built and tested (175 passed); no real run yet — ask the user
> before every paid run. The rest of this file describes the original project it was copied from.

**Last updated:** 2026-10-19
**Current phase:** ✅ ALL PHASES DONE — Release **v1.0.1** published (https://github.com/Mubashirakhan03/space-fractions-code-agent/releases/tag/v1.0.1); v1.0.0 before it. Remaining for the user: record the video, then add its link to README.

| Phase | Status | Tag |
|---|---|---|
| 0 — Research & plan | ✅ done | `phase-0` |
| 1 — Skeleton, config, providers, parsers | ✅ done | `phase-1` |
| 2 — Tools, sandbox, loop, context, prompts | ✅ done | `phase-2` |
| 3 — GUI | ✅ done | `phase-3` |
| 4 — Exe build + GitHub Actions | ✅ done | `phase-4` |
| 5 — Real runs → examples/ | ✅ done (5 runs, ≈ $0.68, final = run 5) | `phase-5` |
| 6 — README, video script, release | ✅ done — v1.0.0 released | `phase-6`, `v1.0.0` |

## Environment facts
- Python 3.12.6 via `py`; tkinter 8.6; sqlite 3.45 — OK
- git 2.51; gh 2.102 at `C:\Program Files\GitHub CLI\gh.exe` (logged in as Mubashirakhan03)
- Repo: https://github.com/Mubashirakhan03/space-fractions-code-agent
- `.venv` with all deps; run tests: `.venv/Scripts/python -m pytest`; lint: `.venv/Scripts/python -m ruff check .`
- Pre-commit secret hook: `python scripts/install_hooks.py` (re-run after a fresh clone)

## Scope decisions (2026-10-18, see DECISIONS.md D-008…D-011)
- Model: **only `deepseek-v4-pro`**, official API `https://api.deepseek.com`. No flash anywhere.
- Providers: **DeepSeek official + MockProvider (+ replay)**. No OpenRouter / custom.
- Dev + tests: MockProvider only (zero cost).
- Phase 5: STOP first → tell user exact balance to add (with margin), runs covered, cost per run → wait for confirmation.

## How the agent works (quick map)
- `sfagent/agent/loop.py` Agent.run(): plan (read-only + submit_plan) → implement → verify (harness: deliverables,
  compile, pytest) ⇄ fix (≤ fix_rounds) → RUN_REPORT.md. State saved after every step → `run(resume=True)`.
- Tools: `sfagent/tools/builtin.py`; permissions: `sandbox.py`; generated code runs via `runner.py` → `sfagent/main.py`.
- Replay: `ReplayProvider(transcript.jsonl)` re-runs recorded model replies with zero cost.
- GUI: `python -m sfagent.main` (dev). Mock mode checkbox = zero-cost scripted demo.
- Exe: `scripts\build_exe.bat` → `dist\SpaceFractionsAgent.exe` (26 MB); check with `python scripts/verify_exe.py`.
- CI: `.github/workflows/build-windows.yml` builds + verifies on every push; `v*` tag → GitHub Release with exe.

## Real runs
- See `docs/REAL_RUNS.md`. Final example: `examples/space_fractions_run9_final/` (profile none). Balance after run 9: $1.82.
- Headless run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python scripts/run_agent_cli.py --out <empty dir> --profile profiles/space_fractions.md`
  (off-peak only: avoid Mon–Fri 06–09 and 11–15 PKT). Always ask the user before a paid run.

## Open decisions / waiting on user
- none right now (v1.0.1 released 2026-10-20 with the user's permission).

## Key files
- Plan & requirements: `docs/PROMPT.md`
- Research + mechanism table: `docs/RESEARCH_NOTES.md`
- Decisions: `docs/DECISIONS.md`
- Change log + rollback: `docs/CHANGELOG_WORK.md`
- Roman Urdu notes: `docs/LEARNING_NOTES_UR.md`
