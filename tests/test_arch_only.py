"""Architecture-only variant: the model gets the architecture and the task's fixed conditions — nothing else.

These tests guard the experiment: no application-level requirements, UI rules, task profile or harness analysis
(e.g. a chosen data store) reach the model; the deviation switch is the only optional instruction; verification
only checks that the program runs.
"""

import json
import sys

import pytest

from sfagent.agent import prompts
from sfagent.agent.launch_check import run_launch_check
from sfagent.agent.loop import Agent
from sfagent.bundled import BUNDLED_STDLIB
from sfagent.config import AppConfig
from sfagent.gui import controller
from sfagent.llm.mock import MockProvider, reply, tool_call
from sfagent.parsers.spec import build_spec, validate_spec
from sfagent.tools.runner import PythonRunner
from tests.conftest import SAMPLES

LIB = SAMPLES / "library_tracker"


@pytest.fixture(scope="module")
def sf_spec():
    return build_spec(SAMPLES / "Architecture_Documentation.md", SAMPLES / "Architecture_View.md")


@pytest.fixture(scope="module")
def lib_spec():
    return build_spec(LIB / "Architecture_Documentation.md", LIB / "Architecture_View.md")


# Words that would mean an application-level requirement leaked into the system prompt: app-specific content, and
# the rules the previous version added (UI style, admin/PIN, animation, seed data, quiz rounds, layout probe).
LEAKS = ["space fractions", "fraction", "game", "question", "score", "player", "intro", "movie", "animation",
         "admin", "pin", "seed", "quiz", "palette", "maximized", "zoomed", "f11", "minsize",
         "1100x750", "ui design brief", "submit/check", "button", "screen", "theme", "kid", "child", "student",
         "sqlite", "postgres", "traceability", "create_app", "test_ui_smoke"]


@pytest.mark.parametrize("record", [False, True])
@pytest.mark.parametrize("term", LEAKS)
def test_system_prompt_carries_no_application_requirements(term, record):
    import re
    text = prompts.system_prompt(record).lower()
    assert not re.search(rf"\b{re.escape(term)}\b", text), f"'{term}' is in the system prompt"


def test_system_prompt_keeps_only_the_task_conditions():
    p = prompts.system_prompt(False)
    assert "only source of requirements" in p and "DESKTOP application" in p
    assert all(m in p for m in BUNDLED_STDLIB)  # technical constraint of the exe
    for deliverable in ("requirements.txt", "README.md", "tests/", "Dockerfile (optional)"):
        assert deliverable in p
    assert "DESIGN_DECISIONS" not in p and "deviation" not in p.lower()


def test_deviation_switch_adds_exactly_one_rule_and_one_deliverable():
    off, on = prompts.system_prompt(False), prompts.system_prompt(True)
    assert on.startswith(off.split("\n\n# Tool usage")[0])
    assert prompts.DEVIATION_RULE in on and prompts.DEVIATION_OUTPUT in on
    assert len(on) - len(off) == len(prompts.DEVIATION_RULE) + len(prompts.DEVIATION_OUTPUT) + 2
    assert "DESIGN_DECISIONS.md" in prompts.plan_instructions(True)
    assert "DESIGN_DECISIONS" not in prompts.plan_instructions(False)


def test_model_never_sees_the_harness_analysis(sf_spec):
    """The parser's own findings (e.g. target_platform with 'SQLite file') are not part of the architecture."""
    assert "SQLite" in json.dumps(sf_spec["target_platform"])  # present in the full extraction …
    user = prompts.initial_messages(sf_spec)[1]["content"]
    for key in ("target_platform", "input_issues", "platform_conflicts", "SQLite file", "Task constraint"):
        assert key not in user  # … but never shown to the model
    assert "PostgreSQL" in user and "Admin" in user and "introductory movie" in user  # the architecture itself is


def test_task_profile_is_ignored(sf_spec):
    from sfagent.agent.profile import parse_profile
    profile = parse_profile("---\nname: Hints\n---\nMake it pink.", source="x.md")
    assert prompts.initial_messages(sf_spec, profile) == prompts.initial_messages(sf_spec)


def test_second_sample_parses_into_valid_spec(lib_spec):
    assert validate_spec(lib_spec) == []
    assert [c["name"] for c in lib_spec["domain_model"]["classes"]] == ["Book", "Member", "Loan"]


TK_MAIN = ("import tkinter as tk\nfrom loans.loan import Loan\n\n\ndef main():\n    root = tk.Tk()\n"
           "    root.title('Library')\n    tk.Label(root, text=str(Loan().daysLate(1))).pack()\n"
           "    root.mainloop()\n\n\nif __name__ == '__main__':\n    main()\n")


def library_project(extra=None):
    files = {
        "main.py": TK_MAIN,
        "loans/__init__.py": "",
        "loans/loan.py": "class Loan:\n    def daysLate(self, late=0):\n        return late\n",
        "tests/test_loan.py": "from loans.loan import Loan\n\n\ndef test_days_late():\n"
                              "    assert Loan().daysLate(2) == 2\n",
        "README.md": "# Library Book Tracker\n",
        "requirements.txt": "pytest\n",
    }
    return files | (extra or {})


def library_script(plan="# Plan\nLoans in loans/.", extra=None):
    return [
        reply(tool_call("update_todos", "t", todos=[{"content": "build", "status": "in_progress"}]),
              tool_call("submit_plan", "p", plan=plan, file_tree=list(library_project(extra)))),
        reply(tool_call("write_files", "w", files=library_project(extra))),
        reply(tool_call("finish", "f", summary="ok")),
    ]


def test_mock_run_off_keeps_the_plan_out_of_the_project(tmp_path, lib_spec):
    doc, view = LIB / "Architecture_Documentation.md", LIB / "Architecture_View.md"
    mock = MockProvider(library_script())
    cfg = AppConfig(provider="mock", doc_path=str(doc), view_path=str(view))
    result = Agent(mock, cfg, tmp_path / "lib", lib_spec).run()
    out = tmp_path / "lib"
    assert result.status == "completed" and result.verify_ok is True
    assert not (out / "DESIGN_DECISIONS.md").exists() and (out / "agent_run" / "plan.md").exists()
    assert (out / "agent_run" / "inputs" / doc.name).read_bytes() == doc.read_bytes()  # original naqsha available
    saved = json.loads((out / "agent_run" / "spec.json").read_text(encoding="utf-8"))
    assert "target_platform" not in saved and "input_issues" not in saved
    assert mock.requests[0]["messages"][0]["content"] == prompts.system_prompt(False)
    assert "LAUNCH CHECK OK" in Agent(mock, cfg, out, lib_spec).verify()[1]


def test_mock_run_on_requires_and_writes_design_decisions(tmp_path, lib_spec):
    cfg = AppConfig(provider="mock", record_deviations=True, fix_rounds=0)
    plain = Agent(MockProvider(library_script()), cfg, tmp_path / "a", lib_spec)
    result = plain.run()  # plan without a deviation table is refused by submit_plan → the run stops early
    assert result.verify_ok is not True
    table = "# Design decisions\n\n## Deviations\n| Architecture | Implemented | Reason |\n|---|---|---|\n" \
            "| PostgreSQL | JSON file | single user |\n"
    mock = MockProvider(library_script(plan=table))
    result = Agent(mock, cfg, tmp_path / "b", lib_spec).run()
    assert result.status == "completed" and result.verify_ok is True
    assert (tmp_path / "b" / "DESIGN_DECISIONS.md").read_text(encoding="utf-8").startswith("# Design decisions")
    assert mock.requests[0]["messages"][0]["content"] == prompts.system_prompt(True)


def runner_for(tmp_path, main_py):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "main.py").write_text(main_py, encoding="utf-8")
    return PythonRunner(tmp_path, tmp_path / "agent_run", timeout=60)


def test_launch_check_passes_a_window_that_runs(tmp_path):
    ok, report = run_launch_check(runner_for(tmp_path, "import tkinter as tk\n\nif __name__ == '__main__':\n"
                                                       "    root = tk.Tk()\n    tk.Label(root, text='hi').pack()\n"
                                                       "    root.mainloop()\n"))
    assert ok, report


def test_launch_check_reports_crash_callback_error_and_no_window(tmp_path):
    ok, report = run_launch_check(runner_for(tmp_path / "a", "raise RuntimeError('boom at start')\n"))
    assert not ok and "crashed while starting: RuntimeError: boom at start" in report
    ok, report = run_launch_check(runner_for(tmp_path / "b", (
        "import tkinter as tk\nroot = tk.Tk()\nroot.after(100, lambda: 1 / 0)\nroot.mainloop()\n")))
    assert not ok and "a Tk callback raised ZeroDivisionError" in report
    ok, report = run_launch_check(runner_for(tmp_path / "c", "print('console only')\n"))
    assert not ok and "without opening a window" in report


def test_launch_check_is_not_swallowed_by_a_broad_except(tmp_path):
    ok, report = run_launch_check(runner_for(tmp_path, (
        "import tkinter as tk\nroot = tk.Tk()\ntry:\n    root.mainloop()\n"
        "except Exception:\n    raise SystemExit(1)\n")))
    assert ok, report


def test_frozen_resources_are_copied_out_of_temp_bundle(tmp_path, monkeypatch):
    bundle = tmp_path / "_MEI123"
    (bundle / "samples").mkdir(parents=True)
    (bundle / "samples" / controller.DOC_NAME).write_text("d")
    (bundle / "samples" / controller.VIEW_NAME).write_text("v")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "exe_dir" / "SpaceFractionsArchOnly.exe"))
    monkeypatch.setattr(controller, "APP_ROOT", bundle)
    monkeypatch.setattr(controller, "user_data_dir", lambda: tmp_path / "Documents" / "SpaceFractionsArchOnly")
    monkeypatch.chdir(tmp_path)
    doc, view = controller.find_default_inputs()
    assert "_MEI" not in doc and doc.startswith(str(tmp_path / "Documents"))
