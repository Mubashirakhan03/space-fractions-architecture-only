import json
import os
import threading
import time

import pytest

from sfagent.agent.planner import TodoList
from sfagent.llm.provider import ToolCall
from sfagent.tools.builtin import ToolContext, build_registry
from sfagent.tools.registry import Tool, ToolRegistry
from sfagent.tools.runner import PythonRunner
from sfagent.tools.sandbox import ReadState, Sandbox, SandboxError


@pytest.fixture
def ctx(tmp_path):
    root = tmp_path / "proj"
    sb = Sandbox(root)
    return ToolContext(sandbox=sb, read_state=ReadState(), todos=TodoList(),
                       runner=PythonRunner(sb.root, sb.root / "agent_run", timeout=120))


@pytest.fixture
def reg(ctx):
    return build_registry(ctx)


def call(reg, name, mode="implement", **args):
    return reg.execute(ToolCall(id="c", name=name, arguments=json.dumps(args)), mode)


# ---------- sandbox ----------

@pytest.mark.parametrize("bad", ["../outside.txt", "a/../../x.py", "C:\\Windows\\x.txt", "/etc/passwd", "\\abs", ""])
def test_path_traversal_blocked(ctx, bad):
    with pytest.raises(SandboxError):
        ctx.sandbox.resolve(bad)


def test_write_outside_root_is_an_error_result(reg, tmp_path):
    r = call(reg, "write_file", path="../evil.py", content="x")
    assert r.is_error and "escapes" in r.content
    assert not (tmp_path / "evil.py").exists()


def test_harness_dir_and_scripts_not_writable(reg):
    assert call(reg, "write_file", path="agent_run/state.json", content="{}").is_error
    assert call(reg, "write_file", path="run.bat", content="del *").is_error


@pytest.mark.skipif(os.name == "nt", reason="symlinks need admin rights on Windows")
def test_symlink_escape_blocked(ctx, tmp_path):
    (tmp_path / "secret.txt").write_text("s")
    (ctx.sandbox.root / "link").symlink_to(tmp_path)
    with pytest.raises(SandboxError):
        ctx.sandbox.resolve("link/secret.txt")


# ---------- write / read / edit ----------

def test_write_read_roundtrip_and_batch(reg, ctx):
    r = call(reg, "write_files", files=[{"path": "pkg/a.py", "content": "A = 1\n"},
                                        {"path": "pkg/b.py", "content": "B = 2\n"}])
    assert not r.is_error and "pkg/a.py" in r.content
    r = call(reg, "read_file", path="pkg/a.py")
    assert "1\tA = 1" in r.content
    assert "pkg/b.py" in call(reg, "list_dir", path="pkg").content
    assert call(reg, "glob", pattern="**/*.py").content.splitlines() == ["pkg/a.py", "pkg/b.py"]
    assert "pkg/b.py:1: B = 2" in call(reg, "search_text", pattern=r"B\s=").content


def test_write_files_partial_failure_reports_each(reg):
    r = call(reg, "write_files", files=[{"path": "ok.py", "content": "x=1"}, {"path": "../bad.py", "content": ""}])
    assert not r.is_error and "FAILED ../bad.py" in r.content and "wrote ok.py" in r.content


def test_edit_requires_read_first(reg, ctx):
    (ctx.sandbox.root / "m.py").write_text("x = 1\n")
    r = call(reg, "edit_file", path="m.py", old_string="x = 1", new_string="x = 2")
    assert r.is_error and "read_file" in r.content
    call(reg, "read_file", path="m.py")
    assert not call(reg, "edit_file", path="m.py", old_string="x = 1", new_string="x = 2").is_error
    assert (ctx.sandbox.root / "m.py").read_text() == "x = 2\n"


def test_overwrite_existing_unread_file_refused(reg, ctx):
    (ctx.sandbox.root / "m.py").write_text("keep\n")
    assert call(reg, "write_file", path="m.py", content="new").is_error


def test_edit_uniqueness_and_replace_all(reg):
    call(reg, "write_file", path="d.py", content="a = 0\na = 0\n")
    r = call(reg, "edit_file", path="d.py", old_string="a = 0", new_string="a = 1")
    assert r.is_error and "2 matches" in r.content
    r = call(reg, "edit_file", path="d.py", old_string="a = 0", new_string="a = 1", replace_all=True)
    assert "replaced 2" in r.content
    assert call(reg, "edit_file", path="d.py", old_string="zzz", new_string="y").is_error


def test_edit_detects_external_change(reg, ctx):
    call(reg, "write_file", path="e.py", content="v = 1\n")
    p = ctx.sandbox.root / "e.py"
    time.sleep(0.01)
    p.write_text("v = 99\n")
    os.utime(p, ns=(time.time_ns(), time.time_ns() + 10_000_000))
    r = call(reg, "edit_file", path="e.py", old_string="v = 99", new_string="v = 2")
    assert r.is_error and "changed since" in r.content


def test_ask_before_write_denied(ctx):
    ctx.approve_write = lambda path, preview: False
    reg = build_registry(ctx)
    r = call(reg, "write_file", path="x.py", content="1")
    assert r.is_error and "denied" in r.content
    assert not (ctx.sandbox.root / "x.py").exists()


# ---------- registry behaviour ----------

def test_plan_mode_blocks_write_tools(reg):
    r = call(reg, "write_file", mode="plan", path="a.py", content="x")
    assert r.is_error and "plan mode" in r.content
    assert not call(reg, "list_dir", mode="plan").is_error
    assert call(reg, "finish", mode="plan", summary="x").is_error
    assert call(reg, "submit_plan", mode="implement", plan="x", file_tree=["a"]).is_error


def test_submit_plan_needs_no_ui_brief_and_checks_deviations_only_when_switched_on(reg, ctx):
    call(reg, "update_todos", mode="plan", todos=[{"content": "a", "status": "in_progress"}])
    assert call(reg, "submit_plan", mode="plan", plan="", file_tree=["main.py"]).is_error
    assert not call(reg, "submit_plan", mode="plan", plan="short plan", file_tree=["main.py"]).is_error
    ctx.record_deviations = True
    refused = call(reg, "submit_plan", mode="plan", plan="short plan", file_tree=["main.py"])
    assert refused.is_error and "deviation table" in refused.content
    table = "## Deviations\n| a | b | c |"
    assert not call(reg, "submit_plan", mode="plan", plan=table, file_tree=["main.py"]).is_error


def test_invalid_json_unknown_tool_missing_args(reg):
    r = reg.execute(ToolCall(id="1", name="read_file", arguments="{bad"), "implement")
    assert r.is_error and "Invalid JSON" in r.content
    assert "Unknown tool" in call(reg, "rm_rf").content
    assert "Missing required" in call(reg, "read_file").content


def test_schemas_have_stable_order(reg):
    names = [s["function"]["name"] for s in reg.schemas()]
    assert names == [s["function"]["name"] for s in build_registry(reg.context).schemas()]
    assert names[0] == "list_dir" and names[-1] == "finish"


def test_read_only_calls_run_in_parallel_writes_serial():
    active, peak, lock = [0], [0], threading.Lock()

    def slow(ctx, a):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.05)
        with lock:
            active[0] -= 1
        return a["i"]

    reg = ToolRegistry()
    reg.register(Tool("r", "", {"type": "object", "properties": {}}, slow, read_only=True))
    reg.register(Tool("w", "", {"type": "object", "properties": {}}, lambda c, a: "w"))
    calls = [ToolCall(str(i), "r", json.dumps({"i": str(i)})) for i in range(4)] + [ToolCall("w", "w", "{}")]
    results = reg.execute_batch(calls, "implement")
    assert [r.content for r in results] == ["0", "1", "2", "3", "w"]
    assert peak[0] > 1


def test_todos_validation(reg, ctx):
    seen = []
    ctx.on_todos = seen.append
    ok = call(reg, "update_todos", todos=[{"content": "a", "status": "in_progress"},
                                          {"content": "b", "status": "pending"}])
    assert "(0/2 completed)" in ok.content and seen
    two = call(reg, "update_todos", todos=[{"content": "a", "status": "in_progress"},
                                           {"content": "b", "status": "in_progress"}])
    assert two.is_error
    assert call(reg, "update_todos", todos=[{"content": "a", "status": "done"}]).is_error


# ---------- runner (real subprocess, bundled-interpreter path) ----------

def test_runner_compile_and_pytest(reg, ctx):
    call(reg, "write_files", files=[
        {"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"},
        {"path": "tests/test_calc.py",
         "content": "from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"},
    ])
    assert call(reg, "run_python", action="compile").content.startswith("PASSED")
    r = call(reg, "run_python", action="test")
    assert r.content.startswith("PASSED") and "1 passed" in r.content


def test_runner_reports_failures_and_syntax_errors(reg):
    call(reg, "write_files", files=[{"path": "tests/test_x.py", "content": "def test_x():\n    assert 1 == 2\n"}])
    r = call(reg, "run_python", action="test")
    assert r.content.startswith("FAILED") and "1 failed" in r.content
    call(reg, "write_file", path="broken.py", content="def f(:\n")
    r = call(reg, "run_python", action="compile")
    assert r.content.startswith("FAILED") and "broken.py" in r.content


def test_runner_script_timeout_and_no_secrets(reg, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-secret-value")
    call(reg, "write_files", files=[
        {"path": "env_check.py", "content": "import os\nprint('KEY' , os.environ.get('DEEPSEEK_API_KEY'))\n"},
        {"path": "hang.py", "content": "import time\ntime.sleep(30)\n"},
    ])
    r = call(reg, "run_python", action="script", target="env_check.py")
    assert "KEY None" in r.content
    r = call(reg, "run_python", action="script", target="hang.py", timeout=2)
    assert r.content.startswith("FAILED") and "timed out" in r.content


def test_delete_file_is_sandboxed(reg, ctx):
    call(reg, "write_files", files=[{"path": "diag.py", "content": "print(1)\n"}, {"path": "pkg/a.py", "content": ""}])
    assert call(reg, "delete_file", path="diag.py").content == "deleted diag.py"
    assert not (ctx.sandbox.root / "diag.py").exists() and "diag.py" not in ctx.written
    assert call(reg, "delete_file", path="diag.py").is_error            # already gone
    assert call(reg, "delete_file", path="pkg").is_error                # directories are never deleted
    assert call(reg, "delete_file", path="../outside.txt").is_error     # path traversal
    assert call(reg, "delete_file", path="agent_run/state.json").is_error
    assert call(reg, "delete_file", mode="plan", path="pkg/a.py").is_error  # not in plan mode
    ctx.approve_write = lambda path, preview: False
    denied = build_registry(ctx)
    assert "denied" in call(denied, "delete_file", path="pkg/a.py").content
    assert (ctx.sandbox.root / "pkg" / "a.py").exists()


def test_write_files_explains_missing_path(reg, ctx):
    """Legacy list form still works; a dropped path names the object form as the way out."""
    r = call(reg, "write_files", files=[{"path": "ok.py", "content": "x = 1\n"}, {"content": "lost path"}])
    assert not r.is_error and "wrote ok.py" in r.content
    assert "FAILED entry #2: missing path" in r.content and "object keyed by path" in r.content


def test_write_files_accepts_path_keyed_object(reg, ctx):
    """Regression (GUI run 2026-10-19 23:20): 6 of 12 list-form calls lost "path" because the model wrote
    "content" first. With the path as the JSON key it cannot be dropped."""
    r = call(reg, "write_files", files={"pkg/a.py": "A = 1\n", "pkg/b.py": "B = 2\n", "README.md": "# x\n"})
    assert not r.is_error
    for rel in ("pkg/a.py", "pkg/b.py", "README.md"):
        assert f"wrote {rel}" in r.content
    assert (ctx.sandbox.root / "pkg" / "b.py").read_text(encoding="utf-8") == "B = 2\n"


def test_write_files_object_form_partial_failure_and_single_entry(reg, ctx):
    r = call(reg, "write_files", files={"ok.py": "x=1", "../escape.py": "y=2", "bad.py": 3})
    assert not r.is_error and "wrote ok.py" in r.content
    assert "FAILED ../escape.py" in r.content and "FAILED entry #3: missing content" in r.content
    # a single {"path", "content"} entry sent without the surrounding list
    r = call(reg, "write_files", files={"path": "solo.py", "content": "z = 3\n"})
    assert not r.is_error and "wrote solo.py" in r.content
    assert call(reg, "write_files", files={}).is_error


def test_write_files_schema_uses_path_keys(reg):
    schema = next(s for s in reg.schemas() if s["function"]["name"] == "write_files")
    files = schema["function"]["parameters"]["properties"]["files"]
    assert files["type"] == "object" and files["additionalProperties"] == {"type": "string"}


def test_generated_project_may_have_its_own_app_package(reg, ctx):
    """Regression (real run 6): a generated `app/` package used to shadow the agent's own package, so every
    run_python script/test failed with "No module named app.main"."""
    call(reg, "write_files", files=[
        {"path": "app/__init__.py", "content": ""},
        {"path": "app/controller.py", "content": "def answer():\n    return 42\n"},
        {"path": "check.py", "content": "from app.controller import answer\nprint('ANSWER', answer())\n"},
        {"path": "tests/test_app.py",
         "content": "from app.controller import answer\n\n\ndef test_answer():\n    assert answer() == 42\n"},
    ])
    r = call(reg, "run_python", action="script", target="check.py")
    assert r.content.startswith("PASSED") and "ANSWER 42" in r.content
    r = call(reg, "run_python", action="test")
    assert r.content.startswith("PASSED") and "1 passed" in r.content
