"""The agent loop (two layers, like Claude Code's QueryEngine + query loop).

Outer layer — `Agent.run()`: owns the session (messages, usage, cost, state file) and drives the
pipeline  plan → implement → verify ⇄ fix → report, saving state after every step so a run can be
resumed.
Inner layer — `Agent._run_phase()`: send messages + tool schemas → model returns tool calls →
execute (read-only in parallel, writes serially) → append `role:"tool"` results → repeat until the
phase-ending tool (`submit_plan` / `finish`) succeeds or a limit is hit.
"""

from __future__ import annotations

import contextlib
import json
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sfagent.agent import prompts
from sfagent.agent.context import ContextManager
from sfagent.agent.import_check import run_import_check
from sfagent.agent.launch_check import run_launch_check
from sfagent.agent.planner import TodoList
from sfagent.agent.profile import TaskProfile
from sfagent.agent.report import REQUIRED_FILES, missing_deliverables, write_report
from sfagent.agent.state import RunState
from sfagent.agent.transcript import Transcript
from sfagent.config import AppConfig
from sfagent.llm.pricing import estimate_cost
from sfagent.llm.provider import LLMError, LLMProvider, LLMResponse
from sfagent.parsers.spec import save_spec
from sfagent.tools.builtin import ApproveWrite, ToolContext, build_registry
from sfagent.tools.registry import ToolResult
from sfagent.tools.runner import PythonRunner
from sfagent.tools.sandbox import ReadState, Sandbox

EventCallback = Callable[[str, dict[str, Any]], None]
MAX_CONTINUES = 3
MAX_NUDGES = 2


class StopRun(Exception):
    """Graceful stop: budget/limit reached, user pressed Stop, or the model gave up."""


@dataclass
class RunResult:
    status: str  # "completed" | "stopped" | "error"
    reason: str
    verify_ok: bool | None
    requests: int
    cost_usd: float
    report_path: Path


class Agent:
    def __init__(self, provider: LLMProvider, cfg: AppConfig, output_dir: Path | str, spec: dict[str, Any], *,
                 on_event: EventCallback | None = None, approve_write: ApproveWrite | None = None,
                 stop_event: threading.Event | None = None, profile: TaskProfile | None = None):
        self.provider = provider
        self.cfg = cfg
        self.spec = spec
        self.profile = profile
        self.root = Path(output_dir).resolve()
        self.run_dir = self.root / "agent_run"
        self.state_path = self.run_dir / "state.json"
        self.on_event = on_event or (lambda kind, data: None)
        self.stop_event = stop_event or threading.Event()

        self.sandbox = Sandbox(self.root)
        self.todos = TodoList()
        self.runner = PythonRunner(self.root, self.run_dir)
        self.ctx = ToolContext(sandbox=self.sandbox, read_state=ReadState(), todos=self.todos, runner=self.runner,
                               approve_write=approve_write, on_todos=lambda t: self.emit("todos", todos=t),
                               record_deviations=cfg.record_deviations)
        self.registry = build_registry(self.ctx)
        self.context = ContextManager(self.run_dir)
        self.transcript = Transcript(self.run_dir / "transcript.jsonl")
        self.state = RunState()
        self._instructions: str | None = None

    # ------------------------------------------------------------------ helpers
    def emit(self, kind: str, **data: Any) -> None:
        with contextlib.suppress(Exception):  # a broken UI callback must never kill the run
            self.on_event(kind, data)

    def _user(self, text: str) -> None:
        self.state.messages.append({"role": "user", "content": text})

    def log(self, text: str) -> None:
        self.emit("log", text=text)

    def _save(self) -> None:
        self.state.todos = self.todos.to_list()
        self.state.written = sorted(self.ctx.written)
        self.state.save(self.state_path)

    # ------------------------------------------------------------------ outer layer
    def run(self, resume: bool = False) -> RunResult:
        started = time.time()
        if resume and self.state_path.exists():
            self.state = RunState.load(self.state_path)
            if self.state.todos:
                self.todos.update(self.state.todos)
            self.ctx.written = set(self.state.written)
            self.ctx.plan = self.state.plan
            self.state.status, self.state.stop_reason = "running", ""
            self.log(f"Resuming run at phase '{self.state.phase}' ({self.state.requests} requests so far).")
            self.emit("resume", phase=self.state.phase, fix_round=self.state.fix_round)
        else:
            save_spec(prompts.architecture_only(self.spec), self.run_dir / "spec.json")
            self._copy_inputs()
            self.state = RunState(messages=prompts.initial_messages(self.spec, None, self.cfg.record_deviations))
        self.state.provider, self.state.model = self.provider.name, self.provider.model
        self.transcript.append("run_start", provider=self.provider.name, model=self.provider.model, resume=resume,
                               profile=self.profile.name if self.profile else None,
                               config={k: v for k, v in asdict(self.cfg).items() if k != "api_key"})
        prior_elapsed = self.state.elapsed_s
        try:
            self._pipeline()
            self.state.status = "completed"
        except StopRun as exc:
            self.state.status, self.state.stop_reason = "stopped", str(exc)
            self.log(f"Run stopped: {exc}")
        except LLMError as exc:
            self.state.status, self.state.stop_reason = "error", str(exc)
            self.emit("error", text=str(exc))
        finally:
            self.state.elapsed_s = prior_elapsed + (time.time() - started)
            self._save()
            report = write_report(self.root, self.state, self.spec, self.cfg,
                                  self.profile.name if self.profile else None)
            self.transcript.append("run_end", status=self.state.status, reason=self.state.stop_reason,
                                   requests=self.state.requests, cost_usd=round(self.state.cost_usd, 6),
                                   usage=self.state.usage, verify_ok=self.state.verify_ok)
        result = RunResult(self.state.status, self.state.stop_reason, self.state.verify_ok, self.state.requests,
                           self.state.cost_usd, report)
        self.emit("done", result=asdict(result) | {"report_path": str(report)})
        return result

    def _copy_inputs(self) -> None:
        """The original architecture documents, read-only for the model in agent_run/inputs/."""
        dest = self.run_dir / "inputs"
        for src in (self.cfg.doc_path, self.cfg.view_path):
            if src and Path(src).is_file():
                dest.mkdir(parents=True, exist_ok=True)
                (dest / Path(src).name).write_bytes(Path(src).read_bytes())

    def _pipeline(self) -> None:
        s = self.state
        if s.phase == "plan":
            self._phase_event("plan")
            self._run_phase("plan", prompts.plan_instructions(self.cfg.record_deviations))
            self._apply_plan()
            s.phase = "implement"
            self._save()
        if s.phase == "implement":
            self._phase_event("implement")
            self._run_phase("implement", prompts.IMPLEMENT_INSTRUCTIONS + prompts.notes_block(self._notes()))
            s.phase = "verify"
            self._save()
        while s.phase == "verify":
            self._phase_event("verify")
            ok, report = self.verify()
            if ok or s.fix_round >= self.cfg.fix_rounds:
                s.phase = "report"
                self._save()
                break
            s.fix_round += 1
            self._phase_event("fix")
            self._run_phase("fix", prompts.fix_instructions(report, s.fix_round, self.cfg.fix_rounds)
                            + prompts.notes_block(self._notes()))
            self._save()
        if s.phase == "report":
            self._phase_event("report")
            s.phase = "done"

    def _phase_event(self, name: str) -> None:
        self.emit("phase", phase=name)
        self.transcript.append("phase", phase=name)
        self.log(f"=== Phase: {name} ===")

    def _apply_plan(self) -> None:
        """Like ExitPlanMode: the harness persists the approved plan as files."""
        plan = self.ctx.plan or {}
        self.state.plan = plan
        plan_rel = "DESIGN_DECISIONS.md" if self.cfg.record_deviations else "agent_run/plan.md"
        for rel, text in ((plan_rel, plan.get("plan", "")),
                          ("AGENT_NOTES.md", "# AGENT_NOTES.md — agent memory\n\n" + (plan.get("notes") or ""))):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            self.ctx.read_state.mark(path)
            self.ctx.written.add(rel)
        self.transcript.append("plan", file_tree=plan.get("file_tree", []))
        self.log(f"Plan accepted: {len(plan.get('file_tree', []))} files planned.")

    def _notes(self) -> str | None:
        p = self.root / "AGENT_NOTES.md"
        return p.read_text(encoding="utf-8") if p.exists() else None

    # ------------------------------------------------------------------ inner layer
    def _run_phase(self, mode: str, instructions: str) -> None:
        self._instructions = instructions
        if not self.state.phase_started:
            self._user(instructions)
            self.state.phase_started = True
        else:
            self._user("The run was interrupted and has been resumed. Continue the current phase from where "
                       "you left off.")
        self._save()
        end_tool = "submit_plan" if mode == "plan" else "finish"
        continues = nudges = 0
        while True:
            self._check_limits()
            self._manage_context()
            resp = self._call_llm(mode)
            self.state.messages.append(resp.to_message())
            self.state.steps += 1
            if resp.content and resp.content.strip():
                self.log(f"model: {resp.content.strip()[:500]}")
            if resp.tool_calls:
                results = self._execute(resp, mode)
                self._save()
                if any(r.ends_phase and not r.is_error for r in results):
                    self.state.phase_started = False
                    return
                continue
            if resp.finish_reason == "length" and continues < MAX_CONTINUES:
                continues += 1
                self._user("Your reply was cut off by the output limit. Continue exactly where you stopped, "
                           "using tool calls.")
            elif nudges < MAX_NUDGES:
                nudges += 1
                self._user(f"No tool was called. Continue the task with the tools and call `{end_tool}` when "
                           "this phase is complete.")
            else:
                raise StopRun(f"model stopped calling tools during the {mode} phase")
            self._save()

    def _execute(self, resp: LLMResponse, mode: str) -> list[ToolResult]:
        for tc in resp.tool_calls:
            self.emit("tool_call", name=tc.name, summary=_summarise_call(tc.name, tc.arguments))
        results = self.registry.execute_batch(resp.tool_calls, mode)
        for r in results:
            content = self.context.cap_tool_output(r.name, r.content)
            self.state.messages.append({"role": "tool", "tool_call_id": r.call_id, "content": content})
            self.transcript.append("tool_result", phase=mode, name=r.name, call_id=r.call_id, is_error=r.is_error,
                                   content=r.content[:4000])
            self.emit("tool_result", name=r.name, ok=not r.is_error, preview=r.content[:300])
        return results

    def _call_llm(self, phase: str, purpose: str = "agent", messages: list | None = None,
                  tools: bool = True) -> LLMResponse:
        self.state.requests += 1
        resp = self.provider.complete(messages or self.state.messages,
                                      tools=self.registry.schemas() if tools else None,
                                      max_tokens=self.cfg.max_output_tokens)
        self._account(resp, phase, purpose)
        return resp

    def _account(self, resp: LLMResponse, phase: str, purpose: str) -> None:
        cost = estimate_cost(resp.usage, self.provider.model)
        self.state.add_usage(resp.usage)
        self.state.cost_usd += cost
        self.transcript.log_response(phase, resp, purpose)
        self.emit("usage", usage=self.state.usage, cost_usd=self.state.cost_usd, requests=self.state.requests)

    def _check_limits(self) -> None:
        s, c = self.state, self.cfg
        if self.stop_event.is_set():
            raise StopRun("stopped by user")
        if s.requests >= c.max_requests:
            raise StopRun(f"max LLM requests per run reached ({c.max_requests})")
        if s.cost_usd >= c.max_cost_usd:
            raise StopRun(f"cost cap reached (${s.cost_usd:.4f} ≥ ${c.max_cost_usd:.2f})")
        if s.usage_obj.total_tokens >= c.max_total_tokens:
            raise StopRun(f"token cap reached ({s.usage_obj.total_tokens} tokens)")
        if s.steps >= c.max_steps:
            raise StopRun(f"max agent steps reached ({c.max_steps})")

    def _manage_context(self) -> None:
        msgs = self.state.messages
        cleared = self.context.microcompact(msgs)
        if cleared:
            self.log(f"context: cleared {cleared} old tool results (microcompact)")
        if self.context.needs_compaction(msgs) and self.context.split_point(msgs):
            before = self.context.growing_tokens(msgs)
            self._check_limits()
            self.state.requests += 1
            new_msgs, resp = self.context.compact(msgs, self.provider, restate=self._instructions)
            self._account(resp, self.state.phase, "compaction")
            self.state.messages = new_msgs
            self.state.compactions += 1
            after = self.context.growing_tokens(new_msgs)
            self.log(f"context: auto-compacted {before} → {after} estimated tokens")

    # ------------------------------------------------------------------ verification
    def verify(self) -> tuple[bool, str]:
        """Harness-side check that the program RUNS (deliverables, compile, own tests, imports, start-up) —
        nothing about features, layout or style."""
        parts, ok = [], True
        missing = missing_deliverables(self.root, ["DESIGN_DECISIONS.md"] if self.cfg.record_deviations else None)
        if missing:
            ok = False
            parts.append("Missing required deliverables: " + ", ".join(missing))
        c_ok, c_out = self.runner.compile_all()
        parts.append(("COMPILE OK: " if c_ok else "COMPILE FAILED:\n") + c_out)
        ok &= c_ok
        if (self.root / "tests").is_dir():
            t_ok, t_out = self.runner.run_pytest("tests")
            parts.append(("TESTS PASSED:\n" if t_ok else "TESTS FAILED:\n") + _tail(t_out, 6000))
            ok &= t_ok
        if c_ok:
            i_ok, i_out = run_import_check(self.runner)
            parts.append(i_out)
            ok &= i_ok
            u_ok, u_out = run_launch_check(self.runner)
            parts.append(u_out)
            ok &= u_ok
        report = "\n\n".join(parts)
        self.state.verify_ok, self.state.verify_report = ok, report
        self.transcript.append("verify", ok=ok, report=report[:8000])
        self.emit("verify", ok=ok, report=report)
        self.log(f"verify: {'PASSED' if ok else 'FAILED'}")
        return ok, report


def _tail(text: str, limit: int) -> str:
    return text if len(text) <= limit else "… (truncated)\n" + text[-limit:]


def _summarise_call(name: str, arguments: str) -> str:
    """Short log line such as `write_files game/engine.py, ui/menu.py`."""
    try:
        a = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return f"{name} (invalid JSON)"
    if name == "write_files" and isinstance(a.get("files"), dict):
        return f"{name} " + ", ".join(map(str, a["files"]))
    if name == "write_files" and isinstance(a.get("files"), list):
        return f"{name} " + ", ".join(str(f.get("path")) for f in a["files"] if isinstance(f, dict))
    if name == "update_todos":
        return f"{name} ({len(a.get('todos') or [])} items)"
    if name == "run_python":
        return f"{name} {a.get('action')} {a.get('target') or ''}".strip()
    for key in ("path", "pattern"):
        if key in a:
            return f"{name} {a[key]}"
    return name


__all__ = ["Agent", "RunResult", "StopRun", "REQUIRED_FILES"]
