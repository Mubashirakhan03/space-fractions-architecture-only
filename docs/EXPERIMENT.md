# Architecture-only variant — experiment design

**Question:** how good is an application that an LLM coding agent builds from the architecture alone — the
architecture document and its UML views — with no requirements from anyone else?

The original agent (repository `space-fractions-code-agent`, release v1.0.1) was improved run by run. Many of
those improvements were *requirements* added by the user and the developer (an animated intro, an admin PIN, an
admin list with Add / Edit / Delete, ≥ 20 seed questions, random rounds, a kid-friendly look…). They made the
generated game better, but they also mean the result no longer shows what the agent makes **from the architecture
alone**. This variant removes all of them. It lives in a separate local folder and is not pushed to GitHub.

## What the model receives

| Input | Source | Kept? |
|---|---|---|
| Architecture document + UML views (deterministic extraction, plus the original files in `agent_run/inputs/`) | the professor | ✅ |
| Desktop application (Tkinter), not web | the professor's instruction (e-mail) | ✅ |
| Python standard library only (bundled module list) | technical condition of the `.exe` (no Python on the target PC) | ✅ |
| Deliverables: source, `requirements.txt`, README, tests, optional Dockerfile | the professor's Task 1 output list | ✅ |
| Agent working rules: tools, plan → implement → verify → fix, request efficiency, memory file | the agent itself (Claude-Code mechanisms) | ✅ |
| UI rules: maximized window, F11, fonts ≥ 18 pt, palette in `ui/theme.py`, UI design brief, Submit buttons, visible inputs, window title, no pack/grid mixing, `create_app` contract, UI smoke test | developer / user | ❌ removed |
| App rules: animated intro + Skip, admin PIN, admin list + Add / Edit / Delete, ≥ 20 seed items, random rounds, generated items, "one correct option", score-dependent result screen, message-before-state-change rule | developer / user | ❌ removed |
| Spec-derived checklist ("introductory movie", "Admin" → PIN, "Update Questions" → list) | developer | ❌ removed |
| Task profile `profiles/space_fractions.md` (kid-friendly look, question kinds…) | user | ❌ removed (a selected profile is ignored) |
| `target_platform` in spec.json — it said **"persistence: SQLite file"** | developer's choice | ❌ removed (it decided the data store for the model) |
| `input_issues`, `platform_conflicts` (the parser's own analysis of the documents) | developer | ❌ removed |
| Required files `DESIGN_DECISIONS.md`, `TRACEABILITY.csv`, `tests/test_ui_smoke.py` | developer | ❌ removed (DESIGN_DECISIONS.md only with the switch ON) |

The exact text is in [`MODEL_INPUT.md`](MODEL_INPUT.md) (regenerate with `python scripts/dump_model_input.py`).
`tests/test_arch_only.py` fails if any of the removed words or rules come back into the system prompt.

## What the harness verifies ("does it run?", not "is it good?")

1. The deliverables exist: `main.py`, `README.md`, `requirements.txt`, at least one `tests/test_*.py`.
2. Every Python file compiles.
3. The agent's **own** tests pass.
4. Every module imports (a wrong import would crash the app on start).
5. **Launch check:** `main.py` is started as `python main.py`, with Tk's main loop limited to 3 seconds. A crash,
   an exception in a Tk callback, or no window at all fails.

The earlier UI probe (layout at two window sizes, clipped buttons, PIN input, moving intro, admin list) is removed:
it judged design quality, which is exactly what the experiment wants to observe instead of enforce. Failures go back
to the model in up to 3 fix rounds, as before.

## The one experimental switch: "record deviations"

Research step 2 of OP2 in the report compares agents that are told to record a reason whenever they leave the
design with agents that are not. The switch does exactly that:

| | OFF (default, baseline) | ON |
|---|---|---|
| Extra rule | none | rule 9: every deviation (technology, data store, component, connector, interface, element merged / split / added / left out) → a row *architecture element → implemented instead → reason* in `DESIGN_DECISIONS.md` |
| Plan | saved to `agent_run/plan.md` (not part of the delivered project) | becomes `DESIGN_DECISIONS.md`; `submit_plan` refuses a plan without a deviation table |
| Verify | — | `DESIGN_DECISIONS.md` must exist |

GUI: checkbox *"Ask the agent to record every deviation from the architecture (and why)"*. CLI:

```bat
:: baseline (OFF)
.venv\Scripts\python scripts\run_agent_cli.py --out runs\arch_off --max-cost 1.0 --max-requests 80
:: with the deviation instruction (ON)
.venv\Scripts\python scripts\run_agent_cli.py --out runs\arch_on --max-cost 1.0 --max-requests 80 --record-deviations
```

## What can be compared afterwards

- Which architecture elements were implemented, changed or left out (components, use cases, states, sequences,
  data entities, the "introductory movie", the Admin role and "Update Questions").
- Which deviations are **visible with a reason** (OFF: does the agent write reasons on its own? ON: are they
  complete?) and which stay **hidden** — the OP2 question.
- Whether the agent's own tests check conformance with the design, or only what the code does.
- The same game built by the earlier agent with extra requirements (`examples/space_fractions_run1…run9`) is a
  comparison point: what did the extra requirements add, and what does the architecture alone produce?

Nothing in the generated code is edited by hand.
