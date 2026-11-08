"""Required-deliverable check and agent_run/RUN_REPORT.md generation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sfagent.agent.state import RunState
from sfagent.config import AppConfig
from sfagent.tools.runner import SKIP_DIRS

REQUIRED_FILES = ["main.py", "README.md", "requirements.txt"]  # the task's deliverables (+ tests below)


def missing_deliverables(root: Path, extra: list[str] | None = None) -> list[str]:
    """The task's deliverables (+ DESIGN_DECISIONS.md when the deviation switch is on)."""
    missing = [f for f in [*REQUIRED_FILES, *(extra or [])] if not (root / f).is_file()]
    if not list((root / "tests").glob("test_*.py")):
        missing.append("tests/test_*.py")
    return missing


def project_files(root: Path) -> list[tuple[str, int]]:
    return sorted((p.relative_to(root).as_posix(), p.stat().st_size) for p in root.rglob("*")
                  if p.is_file() and not SKIP_DIRS & set(p.relative_to(root).parts))


def write_report(root: Path, state: RunState, spec: dict[str, Any], cfg: AppConfig,
                 profile_name: str | None = None) -> Path:
    u = state.usage
    files = project_files(root)
    replay = state.provider.startswith("REPLAY")
    lines = [
        "# RUN_REPORT — Code Agent run",
        "",
        f"> **{'REPLAY of a recorded run (no API calls were made)' if replay else 'Live run'}**",
        "",
        "| Item | Value |", "|---|---|",
        f"| Generated (UTC) | {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} |",
        f"| Provider | {state.provider} |",
        f"| Model | `{state.model}` |",
        f"| Inputs | {', '.join(s.get('file', '?') for s in spec.get('sources', {}).values())} |",
        f"| Task profile | {profile_name or '(none — spec only)'} |",
        f"| Status | **{state.status}**{' — ' + state.stop_reason if state.stop_reason else ''} |",
        f"| Verification | {'PASSED' if state.verify_ok else 'FAILED' if state.verify_ok is False else 'not run'} |",
        f"| Fix rounds used | {state.fix_round} / {cfg.fix_rounds} |",
        f"| LLM requests | {state.requests} (limit {cfg.max_requests}) |",
        f"| Agent steps | {state.steps} |",
        f"| Context compactions | {state.compactions} |",
        f"| Prompt tokens | {u['prompt_tokens']:,} "
        f"(cache hit {u['cache_hit_tokens']:,} / miss {u['cache_miss_tokens']:,}) |",
        f"| Completion tokens | {u['completion_tokens']:,} |",
        f"| Estimated cost | ${state.cost_usd:.4f} (cap ${cfg.max_cost_usd:.2f}) |",
        f"| Duration | {state.elapsed_s:.0f} s |",
        "",
        "## Generated files", "",
        *[f"- `{name}` ({size:,} bytes)" for name, size in files if not name.startswith("agent_run/")],
        "",
        "## Todo list (final)", "",
        *([f"- [{'x' if t['status'] == 'completed' else ' '}] {t['content']}" for t in state.todos] or ["(none)"]),
        "",
        "## Input issues detected during preprocessing", "",
        *[f"- **{i['code']}** ({i['severity']}): {i['message']}" for i in spec.get("input_issues", [])],
        "",
        "## Verification output", "",
        "```text", (state.verify_report or "(not run)")[-6000:], "```",
        "",
        "## Agent run artefacts", "",
        "- `agent_run/spec.json` — structured input", "- `agent_run/transcript.jsonl` — full transcript",
        "- `agent_run/state.json` — resumable state", "- `agent_run/tool-results/` — full long tool outputs",
    ]
    path = root / "agent_run" / "RUN_REPORT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
