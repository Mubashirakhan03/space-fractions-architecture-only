"""Layered prompts — ARCHITECTURE-ONLY variant (research baseline).

The model receives the architecture documents (as a deterministic spec.json plus the original Markdown files)
and the task owner's fixed conditions: a Windows desktop application in Python (standard library only, so it
runs inside the agent's exe), with source files, requirements.txt, README, tests and an optional Dockerfile.
Nothing else: no application-level requirements, UI style rules, feature checklists or task profiles. What the
application does comes ONLY from the architecture.

One experimental switch: `record_deviations` adds the instruction to document every place where the code departs
from the architecture (and why). OFF = the model gets no such instruction (baseline).

Order inside every request — kept byte-identical across requests so DeepSeek's prefix cache hits:
  [system]  ROLE → RULES → TOOL USAGE → OUTPUT CONTRACT          (static for the run, no timestamps)
  [user]    compact spec.json                                      (static for the whole run)
  [user]    phase instructions + AGENT_NOTES.md (memory)           (appended later, never prepended)
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sfagent.agent.profile import TaskProfile
from sfagent.bundled import BUNDLED_STDLIB

ROLE = """# Role
You are a Code Agent, an autonomous software engineer. You receive the architecture of a software system
(an architecture document and its UML views) and you implement that system as a complete, working Python
application in the project directory you are given. You work only through the provided tools."""

RULES_TEMPLATE = """# Rules
1. The architecture documents are the only source of requirements for the application. Implement the system they
   describe.
2. Deliver a Windows DESKTOP application (Tkinter user interface), not a web application or server.
3. Python standard library only, and ONLY these modules (they are bundled with the program that runs the
   application; anything else will not exist on the target PC): {stdlib}.
   Tests use pytest. No third-party runtime packages, no network access.
4. Prefer edit_file (exact, unique search-and-replace) over rewriting a file. You must read_file a
   whole file before editing it. Create new files with write_files, several per call; its `files` argument is
   an object keyed by path: {{"pkg/a.py": "<full content>", "pkg/b.py": "<full content>"}}.
5. Be request-efficient: every model call costs money and runs have a request limit. Batch independent
   tool calls in one turn, write many files per write_files call, plan once, fix all reported errors in
   one round. When several files need changes, send ALL the edit_file calls in ONE reply.
6. Paths are relative to the project root. The folder agent_run/ belongs to the harness (read-only); the
   original input documents are in agent_run/inputs/.
7. Never start main.py or anything that opens a window or waits for input from run_python (it would block).
8. Keep AGENT_NOTES.md (your memory file) up to date with key decisions when they change."""

DEVIATION_RULE = """9. Deviations from the architecture: wherever your implementation differs from what the architecture
   documents specify — a different technology, data store, protocol or deployment, a component, connector, interface or
   element you merge, split, add or leave out — record it in DESIGN_DECISIONS.md, one row per deviation:
   architecture element → what you implemented instead → reason. Keep this table complete and up to date until
   you finish; no deviation may stay unrecorded."""

TOOL_USAGE = """# Tool usage
- update_todos: keep a todo list; exactly one item in_progress; mark items completed as you go.
- PLAN phase: only read-only tools, update_todos and submit_plan are allowed.
- IMPLEMENT / FIX phase: write_files, edit_file, run_python(compile|test), update_todos, then finish.
- Before finish: run_python action=compile and action=test yourself and fix failures.
- Verification by the harness: every file must compile, your tests must pass, every module must import, and
  main.py is started for a few seconds; a crash in any of these fails verification. Keep main.py's start-up
  code under `if __name__ == "__main__":`.
- Change project files only with write_files / edit_file / delete_file. run_python scripts are for checks and
  diagnostics; they must not create, modify or delete project files. Delete temporary helper files with
  delete_file before finish.
- Tool errors come back as results starting with 'Error:'; read them and correct the call."""

OUTPUT_CONTRACT = """# Output
- The project directory layout and the full source code; start the application with `python main.py`.
- requirements.txt (dependency manifest).
- README.md (project README).
- tests/ with pytest test cases.
- Dockerfile (optional).
- AGENT_NOTES.md (your memory file)."""

DEVIATION_OUTPUT = "- DESIGN_DECISIONS.md with the deviation table (rule 9)."


def system_prompt(record_deviations: bool = False) -> str:
    rules = RULES_TEMPLATE.format(stdlib=", ".join(BUNDLED_STDLIB))
    output = OUTPUT_CONTRACT
    if record_deviations:
        rules += "\n" + DEVIATION_RULE
        output += "\n" + DEVIATION_OUTPUT
    return "\n\n".join([ROLE, rules, TOOL_USAGE, output])


SYSTEM_PROMPT = system_prompt(False)


def plan_instructions(record_deviations: bool = False) -> str:
    target = ("the full Markdown content of DESIGN_DECISIONS.md: your plan plus the deviation table (rule 9)"
              if record_deviations else "your implementation plan in Markdown")
    return f"""## PHASE 1/3 — ANALYSE & PLAN (plan mode: read-only)
Study the architecture and plan the implementation. Then, in as few turns as possible:
1. Call update_todos with the implementation plan (concrete items, first one in_progress).
2. Call submit_plan with:
   - plan: {target},
   - file_tree: every file you will create (relative paths),
   - notes: short content for AGENT_NOTES.md (key decisions, module responsibilities, conventions).
You may call both tools in the same turn."""


PLAN_INSTRUCTIONS = plan_instructions(False)

IMPLEMENT_INSTRUCTIONS = """## PHASE 2/3 — IMPLEMENT
Your plan was accepted. Create every file of the plan with write_files: complete working code, no placeholders or
TODOs, 4-6 files per write_files call so no single reply gets cut off (a cut-off reply loses the whole call).
Keep the todo list updated. Then run_python compile and test, fix any failures with edit_file, and call finish
with a short summary."""


def fix_instructions(report: str, round_no: int, max_rounds: int) -> str:
    return (f"## PHASE 3/3 — FIX (round {round_no}/{max_rounds})\n"
            "The harness verified the project and found problems. Fix ALL of them in this round "
            "(read the failing files, then edit_file), re-run run_python compile and test, then call "
            f"finish.\n\n### Verification report\n{report}")


def notes_block(notes: str | None) -> str:
    if not notes:
        return ""
    return f"\n\n### Current AGENT_NOTES.md (your memory file)\n{notes[:3000]}"


ANALYSIS_KEYS = ("target_platform", "input_issues", "platform_conflicts")  # the parser's own findings, not the input
DOC_ANALYSIS_KEYS = ("issues", "platform_terms")


def architecture_only(spec: dict[str, Any]) -> dict[str, Any]:
    """spec.json without the harness's own analysis (platform choice such as 'SQLite', input issues, platform
    conflicts): only what the architecture documents themselves contain. This is what the model may see."""
    out = {k: v for k, v in spec.items() if k not in ANALYSIS_KEYS}
    out["document"] = {k: v for k, v in spec["document"].items() if k not in DOC_ANALYSIS_KEYS}
    return out


def compact_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """The parts of the extraction the model needs; the full file stays at agent_run/spec.json."""
    spec = architecture_only(spec)
    doc = spec["document"]
    pick = ("traceability", "risks", "qa_mapping", "testing_matrix", "components", "tech_stack",
            "assumptions", "open_questions", "deliverables", "implied_features")
    seen: set[str] = set()
    data_blocks = []
    for b in doc["code_blocks"]:  # API contracts and schemas, each distinct block once
        digest = hashlib.sha1(b["content"].encode()).hexdigest()
        if b["kind"] in {"sql", "openapi", "proto"} and digest not in seen:
            seen.add(digest)
            data_blocks.append({k: b.get(k) for k in ("section", "kind", "content")})
    return {
        "domain_model": spec["domain_model"],
        "requirements": spec["requirements"],
        "document": {k: doc.get(k) for k in pick} | {"contracts_and_schemas": data_blocks},
    }


def initial_messages(spec: dict[str, Any], profile: TaskProfile | None = None,
                     record_deviations: bool = False) -> list[dict[str, Any]]:
    """`profile` is accepted for API compatibility but ignored: this variant takes no task hints."""
    spec_json = json.dumps(compact_spec(spec), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    sources = spec.get("sources", {})
    names = " and ".join(s.get("file", "?") for s in sources.values()) or "the input files"
    user = (f"# Architecture (compact spec.json)\nExtracted deterministically from {names}; the original files "
            "are in agent_run/inputs/ and the full extraction is agent_run/spec.json.\n\n```json\n"
            + spec_json + "\n```")
    return [{"role": "system", "content": system_prompt(record_deviations)}, {"role": "user", "content": user}]
