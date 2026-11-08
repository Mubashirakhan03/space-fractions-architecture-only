"""Built-in tools given to the model.

Read-only: list_dir, read_file, glob, search_text.
Write (serial, sandboxed, optional user approval): write_file, write_files, edit_file.
Execution: run_python (compile / pytest / script, bundled interpreter, timeout).
Control: update_todos, submit_plan (ends plan phase), finish (ends implement/fix phase).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sfagent.agent.planner import TodoList
from sfagent.tools.registry import Tool, ToolError, ToolRegistry
from sfagent.tools.runner import SKIP_DIRS, PythonRunner
from sfagent.tools.sandbox import ReadState, Sandbox

MAX_LIST = 200
MAX_READ_LINES = 2000
MAX_MATCHES = 100
WORK_MODES = frozenset({"implement", "fix"})

ApproveWrite = Callable[[str, str], bool]


@dataclass
class ToolContext:
    sandbox: Sandbox
    read_state: ReadState
    todos: TodoList
    runner: PythonRunner
    approve_write: ApproveWrite | None = None
    on_todos: Callable[[list[dict[str, str]]], None] | None = None
    plan: dict[str, Any] | None = None
    finish_summary: str | None = None
    written: set[str] = field(default_factory=set)
    record_deviations: bool = False  # experiment switch (see prompts.DEVIATION_RULE)


# ---------- read-only ----------

def list_dir(ctx: ToolContext, a: dict) -> str:
    base = ctx.sandbox.resolve(a.get("path") or ".")
    if not base.is_dir():
        raise ToolError(f"Not a directory: {a.get('path')}")
    entries = []
    for p in sorted(base.rglob("*") if a.get("recursive") else base.iterdir()):
        rel_parts = p.relative_to(ctx.sandbox.root).parts
        if SKIP_DIRS & set(rel_parts):
            continue
        entries.append(ctx.sandbox.rel(p) + ("/" if p.is_dir() else f"  ({p.stat().st_size} bytes)"))
        if len(entries) >= MAX_LIST:
            entries.append(f"... (truncated at {MAX_LIST} entries)")
            break
    return "\n".join(entries) or "(empty directory)"


def read_file(ctx: ToolContext, a: dict) -> str:
    full = ctx.sandbox.resolve(a["path"])
    if not full.is_file():
        raise ToolError(f"File not found: {a['path']}")
    lines = full.read_text(encoding="utf-8", errors="replace").splitlines()
    offset = max(int(a.get("offset") or 1), 1)
    limit = int(a.get("limit") or MAX_READ_LINES)
    chunk = lines[offset - 1: offset - 1 + limit]
    if offset == 1 and len(chunk) == len(lines):
        ctx.read_state.mark(full)  # whole file seen → editing allowed
    body = "\n".join(f"{n:>5}\t{ln}" for n, ln in enumerate(chunk, start=offset))
    more = len(lines) - (offset - 1 + len(chunk))
    tail = f"\n... ({more} more lines; use offset/limit)" if more > 0 else ""
    return (body or "(empty file)") + tail


def glob_files(ctx: ToolContext, a: dict) -> str:
    pattern = a["pattern"]
    if ".." in pattern or pattern.startswith(("/", "\\")) or ":" in pattern:
        raise ToolError("Glob pattern must be relative to the project root.")
    hits = [ctx.sandbox.rel(p) for p in sorted(ctx.sandbox.root.glob(pattern))
            if not SKIP_DIRS & set(p.relative_to(ctx.sandbox.root).parts)]
    return "\n".join(hits[:MAX_LIST]) or "(no matches)"


def search_text(ctx: ToolContext, a: dict) -> str:
    try:
        rx = re.compile(a["pattern"])
    except re.error as exc:
        raise ToolError(f"Invalid regex: {exc}") from exc
    base = ctx.sandbox.resolve(a.get("path") or ".")
    files = [base] if base.is_file() else sorted(base.rglob(a.get("glob") or "*"))
    out = []
    for f in files:
        if not f.is_file() or SKIP_DIRS & set(f.relative_to(ctx.sandbox.root).parts):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                out.append(f"{ctx.sandbox.rel(f)}:{n}: {line.strip()[:200]}")
                if len(out) >= MAX_MATCHES:
                    return "\n".join(out) + f"\n... (stopped at {MAX_MATCHES} matches)"
    return "\n".join(out) or "(no matches)"


# ---------- write ----------

def _write(ctx: ToolContext, path: str, content: str) -> str:
    full = ctx.sandbox.resolve(path)
    ctx.sandbox.check_writable(full)
    rel = ctx.sandbox.rel(full)
    if full.exists() and not ctx.read_state.has_read(full) and rel not in ctx.written:
        raise ToolError(f"'{rel}' already exists. read_file it first, or use edit_file for a small change.")
    if not isinstance(content, str):
        raise ToolError("content must be a string.")
    if ctx.approve_write and not ctx.approve_write(rel, content[:2000]):
        raise ToolError(f"The user denied writing '{rel}'.")
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8", newline="\n")
    ctx.read_state.mark(full)  # the model knows the exact content it just wrote
    ctx.written.add(rel)
    return f"wrote {rel} ({content.count(chr(10)) + 1} lines)"


def write_file(ctx: ToolContext, a: dict) -> str:
    return _write(ctx, a["path"], a["content"])


def _file_entries(files: Any) -> list[tuple[int, str | None, Any]]:
    """Normalise write_files input to (index, path, content).

    Preferred form is a mapping {"path": "content", ...}: the path is the JSON key, so it cannot be dropped.
    Real runs with the older list form [{"path", "content"}] lost "path" in about half of the calls, because
    the model wrote "content" first and never came back to "path"; the list form is still accepted."""
    if isinstance(files, dict):
        if set(files) == {"path", "content"} and isinstance(files.get("path"), str):
            return [(1, files["path"], files["content"])]  # a single entry sent without the list around it
        return [(i, p, c) for i, (p, c) in enumerate(files.items(), start=1)]
    if isinstance(files, list):
        out = []
        for i, f in enumerate(files, start=1):
            f = f if isinstance(f, dict) else {}
            out.append((i, f.get("path"), f.get("content")))
        return out
    return []


def write_files(ctx: ToolContext, a: dict) -> str:
    entries = _file_entries(a["files"])
    if not entries:
        raise ToolError('files must be a non-empty object {"relative/path.py": "full file content", ...}.')
    report, failed = [], 0
    for i, path, content in entries:
        if not isinstance(path, str) or not path or not isinstance(content, str):
            failed += 1
            what = "path" if not isinstance(path, str) or not path else "content (must be a string)"
            report.append(f"FAILED entry #{i}: missing {what}. Send files as an object keyed by path, "
                          '{"pkg/mod.py": "<full content>"}, and re-send only this file.')
            continue
        try:
            report.append(_write(ctx, path, content))
        except Exception as exc:  # one bad file must not block the rest
            failed += 1
            report.append(f"FAILED {path}: {exc}")
    if failed == len(entries):
        raise ToolError("\n".join(report))
    return "\n".join(report)


def edit_file(ctx: ToolContext, a: dict) -> str:
    full = ctx.sandbox.resolve(a["path"])
    ctx.sandbox.check_writable(full)
    rel = ctx.sandbox.rel(full)
    if not full.is_file():
        raise ToolError(f"File not found: {rel}. Use write_file to create it.")
    ctx.read_state.check_editable(full, rel)
    old, new = a["old_string"], a["new_string"]
    if old == new:
        raise ToolError("old_string and new_string are identical.")
    if not old:
        raise ToolError("old_string must not be empty.")
    text = full.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 0:
        raise ToolError(f"old_string not found in {rel}. Check whitespace/indentation and do not include the "
                        "line-number prefix from read_file.")
    if count > 1 and not a.get("replace_all"):
        raise ToolError(f"Found {count} matches of old_string in {rel}. Add surrounding context to make it "
                        "unique, or set replace_all=true.")
    if ctx.approve_write and not ctx.approve_write(rel, f"--- replace ---\n{old[:800]}\n--- with ---\n{new[:800]}"):
        raise ToolError(f"The user denied editing '{rel}'.")
    full.write_text(text.replace(old, new) if a.get("replace_all") else text.replace(old, new, 1),
                    encoding="utf-8", newline="\n")
    ctx.read_state.mark(full)
    ctx.written.add(rel)
    return f"edited {rel}: replaced {count if a.get('replace_all') else 1} occurrence(s)"


def delete_file(ctx: ToolContext, a: dict) -> str:
    """Delete one file inside the sandbox (e.g. a temporary diagnostic script). Directories are never deleted."""
    full = ctx.sandbox.resolve(a["path"])
    ctx.sandbox.check_writable(full)
    rel = ctx.sandbox.rel(full)
    if not full.is_file():
        raise ToolError(f"File not found: {rel}")
    if ctx.approve_write and not ctx.approve_write(rel, "--- delete this file ---"):
        raise ToolError(f"The user denied deleting '{rel}'.")
    full.unlink()
    ctx.read_state.forget(full)
    ctx.written.discard(rel)
    return f"deleted {rel}"


# ---------- execution ----------

def run_python(ctx: ToolContext, a: dict) -> str:
    action = a["action"]
    if action == "compile":
        ok, out = ctx.runner.compile_all()
    elif action == "test":
        target = a.get("target") or "tests"
        ctx.sandbox.resolve(target)
        ok, out = ctx.runner.run_pytest(target)
    elif action == "script":
        if not a.get("target"):
            raise ToolError("action 'script' needs target (a .py file).")
        full = ctx.sandbox.resolve(a["target"])
        if full.suffix != ".py" or not full.is_file():
            raise ToolError("target must be an existing .py file.")
        ok, out = ctx.runner.run_script(ctx.sandbox.rel(full), timeout=int(a.get("timeout") or 30))
    else:
        raise ToolError("action must be 'compile', 'test' or 'script'.")
    return ("PASSED\n" if ok else "FAILED\n") + out


# ---------- control ----------

def update_todos(ctx: ToolContext, a: dict) -> str:
    try:
        ctx.todos.update(a["todos"])
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    if ctx.on_todos:
        ctx.on_todos(ctx.todos.to_list())
    return ctx.todos.render()


def submit_plan(ctx: ToolContext, a: dict) -> str:
    tree = a["file_tree"]
    if not isinstance(tree, list) or not tree:
        raise ToolError("file_tree must be a non-empty list of relative file paths.")
    plan = str(a["plan"]).strip()
    if not plan:
        raise ToolError("plan must not be empty.")
    if ctx.record_deviations and "deviation" not in plan.lower():
        raise ToolError("plan is the content of DESIGN_DECISIONS.md and must contain the deviation table (rule 9).")
    if not ctx.todos.items:
        raise ToolError("Call update_todos with the implementation plan before submit_plan.")
    ctx.plan = {"plan": plan, "file_tree": tree, "notes": a.get("notes", "")}
    return "Plan accepted. Implementation phase will start."


def finish(ctx: ToolContext, a: dict) -> str:
    ctx.finish_summary = a["summary"]
    return "Phase finished; the harness will now verify the project."


# ---------- schemas ----------

def _obj(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required}


S = {"type": "string"}


def build_registry(ctx: ToolContext) -> ToolRegistry:
    reg = ToolRegistry(ctx)
    file_entry = _obj({"path": S, "content": S}, ["path", "content"])
    todo_entry = _obj({"content": S, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}},
                      ["content", "status"])
    tools = [
        Tool("list_dir", "List files in a project directory (relative path). Set recursive=true for a tree.",
             _obj({"path": S, "recursive": {"type": "boolean"}}, []), list_dir, read_only=True),
        Tool("read_file", "Read a text file with line numbers (prefix is not part of the file). Read the whole "
             "file before edit_file.", _obj({"path": S, "offset": {"type": "integer"}, "limit": {"type": "integer"}},
                                            ["path"]), read_file, read_only=True),
        Tool("glob", "Find files by glob pattern relative to the project root, e.g. '**/*.py'.",
             _obj({"pattern": S}, ["pattern"]), glob_files, read_only=True),
        Tool("search_text", "Regex search in project files; returns path:line: text.",
             _obj({"pattern": S, "path": S, "glob": S}, ["pattern"]), search_text, read_only=True),
        Tool("write_file", "Create a new file (or fully rewrite a file you have read). Paths are relative.",
             file_entry, write_file, modes=WORK_MODES),
        Tool("write_files", "Create several files in ONE call (preferred: saves requests). `files` is an object "
             "that maps each relative path to its full content: {\"pkg/a.py\": \"…\", \"pkg/b.py\": \"…\"}.",
             _obj({"files": {"type": "object", "description": "relative file path -> complete file content",
                             "additionalProperties": S}}, ["files"]), write_files, modes=WORK_MODES),
        Tool("edit_file", "Replace an exact, unique string in a file you have read. Prefer this over rewriting.",
             _obj({"path": S, "old_string": S, "new_string": S, "replace_all": {"type": "boolean"}},
                  ["path", "old_string", "new_string"]), edit_file, modes=WORK_MODES),
        Tool("delete_file", "Delete one project file (e.g. a temporary diagnostic script). Never a directory.",
             _obj({"path": S}, ["path"]), delete_file, modes=WORK_MODES),
        Tool("run_python", "Run checks with the bundled Python: action='compile' (syntax-check all files), "
             "'test' (pytest, target default 'tests'), or 'script' (run a .py file that terminates; never main.py).",
             _obj({"action": {"type": "string", "enum": ["compile", "test", "script"]}, "target": S,
                   "timeout": {"type": "integer"}}, ["action"]), run_python, modes=WORK_MODES),
        Tool("update_todos", "Replace the todo list (TodoWrite). Exactly one item in_progress while working.",
             _obj({"todos": {"type": "array", "items": todo_entry}}, ["todos"]), update_todos),
        Tool("submit_plan", "PLAN phase only: submit the plan, the target file tree and notes for AGENT_NOTES.md. "
             "Ends the plan phase.",
             _obj({"plan": S, "file_tree": {"type": "array", "items": S}, "notes": S},
                  ["plan", "file_tree"]), submit_plan, modes=frozenset({"plan"}), ends_phase=True),
        Tool("finish", "Call when the current implement/fix phase is complete. The harness then compiles and "
             "runs the tests.", _obj({"summary": S}, ["summary"]), finish, modes=WORK_MODES, ends_phase=True),
    ]
    for t in tools:
        reg.register(t)
    return reg
