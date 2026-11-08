"""End-to-end agent runs with the scripted MockProvider (deterministic, zero API cost).

Scenarios mirror claw-code's mock parity harness: happy path, fix round, plan-mode write denied,
request/cost limits, resume, nudges, output-length continue, auto-compaction, replay, user stop,
large tool output, malformed tool-call JSON.
"""

import json
import threading

import pytest

from sfagent.agent.context import COMPACT_PROMPT, ContextManager
from sfagent.agent.loop import Agent
from sfagent.agent.replay import ReplayProvider
from sfagent.agent.state import RunState
from sfagent.agent.transcript import read_events
from sfagent.config import AppConfig
from sfagent.llm.mock import MockProvider, reply, tool_call
from sfagent.llm.provider import LLMResponse, ToolCall, Usage
from sfagent.parsers.spec import build_spec

DESIGN = "# Design decisions\n\nPlan: logic in game/, a Tk window in main.py.\n"


def project_files(failing: bool = False):
    assertion = "assert add(1, 1) == 3" if failing else "assert add(1, 1) == 2"
    return [
        {"path": "main.py",
         "content": "import tkinter as tk\n\nfrom game.logic import add\n\nif __name__ == '__main__':\n"
                    "    root = tk.Tk()\n    tk.Label(root, text=str(add(1, 2))).pack()\n    root.mainloop()\n"},
        {"path": "game/__init__.py", "content": ""},
        {"path": "game/logic.py", "content": "def add(a, b):\n    return a + b\n"},
        {"path": "tests/test_logic.py",
         "content": f"from game.logic import add\n\n\ndef test_add():\n    {assertion}\n"},
        {"path": "README.md", "content": "# Mini\n"},
        {"path": "requirements.txt", "content": "# standard library only\npytest\n"},
        {"path": "sql/schema.sql", "content": "CREATE TABLE scores (id INTEGER PRIMARY KEY);\n"},
        {"path": "data/questions.json", "content": "[]\n"},
    ]


def plan_turn():
    return reply(
        tool_call("update_todos", "t1", todos=[{"content": "write code", "status": "in_progress"},
                                               {"content": "write tests", "status": "pending"}]),
        tool_call("submit_plan", "p1", plan=DESIGN, file_tree=[f["path"] for f in project_files()],
                  notes="Logic in game/, tests headless."),
    )


def implement_turns(failing: bool = False):
    return [reply(tool_call("write_files", "w1", files=project_files(failing))),
            reply(tool_call("finish", "f1", summary="done"))]


@pytest.fixture(scope="module")
def spec():
    from tests.conftest import SAMPLES
    return build_spec(SAMPLES / "Architecture_Documentation.md", SAMPLES / "Architecture_View.md")


def make_agent(tmp_path, provider, spec, events=None, **cfg):
    config = AppConfig(provider="mock", **cfg)
    on_event = (lambda k, d: events.append((k, d))) if events is not None else None
    return Agent(provider, config, tmp_path / "out", spec, on_event=on_event)


def test_happy_path_end_to_end(tmp_path, spec):
    events = []
    mock = MockProvider([plan_turn(), *implement_turns()])
    result = make_agent(tmp_path, mock, spec, events).run()
    out = tmp_path / "out"

    assert result.status == "completed" and result.verify_ok is True
    assert result.requests == 3
    assert (out / "game/logic.py").exists() and not (out / "DESIGN_DECISIONS.md").exists()
    assert (out / "agent_run/plan.md").read_text().startswith("# Design")  # the plan stays out of the project
    assert "tests headless" in (out / "AGENT_NOTES.md").read_text()
    report = (out / "agent_run/RUN_REPORT.md").read_text(encoding="utf-8")
    assert "Verification | PASSED" in report and "Mock" in report
    assert json.loads((out / "agent_run/spec.json").read_text(encoding="utf-8"))["spec_version"] == "1.0"
    kinds = [k for k, _ in events]
    assert {"phase", "tool_call", "tool_result", "todos", "usage", "verify", "done"} <= set(kinds)
    phases = [d["phase"] for k, d in events if k == "phase"]
    assert phases == ["plan", "implement", "verify", "report"]
    ev = [e["event"] for e in read_events(out / "agent_run/transcript.jsonl")]
    assert ev[0] == "run_start" and ev[-1] == "run_end" and ev.count("llm_response") == 3
    assert RunState.load(out / "agent_run/state.json").phase == "done"


def test_prompt_prefix_is_stable_across_requests(tmp_path, spec):
    mock = MockProvider([plan_turn(), *implement_turns()])
    make_agent(tmp_path, mock, spec).run()
    first = mock.requests[0]
    for req in mock.requests[1:]:
        assert req["messages"][:2] == first["messages"][:2]  # system + spec unchanged → cache hits
        assert req["tools"] == first["tools"]


def test_failing_tests_trigger_fix_round(tmp_path, spec):
    def read_then_edit(messages, tools):
        assert "TESTS FAILED" in messages[-1]["content"]
        return reply(tool_call("read_file", "r1", path="tests/test_logic.py"))

    mock = MockProvider([plan_turn(), *implement_turns(failing=True), read_then_edit,
                         reply(tool_call("edit_file", "e1", path="tests/test_logic.py",
                                         old_string="add(1, 1) == 3", new_string="add(1, 1) == 2")),
                         reply(tool_call("finish", "f2", summary="fixed"))])
    result = make_agent(tmp_path, mock, spec, fix_rounds=2).run()
    state = RunState.load(tmp_path / "out/agent_run/state.json")
    assert result.verify_ok is True and state.fix_round == 1


def test_fix_rounds_are_bounded(tmp_path, spec):
    mock = MockProvider([plan_turn(), *implement_turns(failing=True)])
    result = make_agent(tmp_path, mock, spec, fix_rounds=0).run()
    assert result.status == "completed" and result.verify_ok is False


def test_plan_mode_denies_writes(tmp_path, spec):
    def check_denied(messages, tools):
        assert "not available in plan mode" in messages[-1]["content"]
        return plan_turn()

    mock = MockProvider([reply(tool_call("write_file", "x", path="a.py", content="1")), check_denied,
                         *implement_turns()])
    assert make_agent(tmp_path, mock, spec).run().verify_ok
    assert not (tmp_path / "out/a.py").exists()


def test_max_requests_stops_gracefully(tmp_path, spec):
    mock = MockProvider([plan_turn(), *implement_turns()])
    result = make_agent(tmp_path, mock, spec, max_requests=1).run()
    assert result.status == "stopped" and "max LLM requests" in result.reason
    assert (tmp_path / "out/agent_run/RUN_REPORT.md").exists()


def test_cost_cap_stops(tmp_path, spec):
    expensive = plan_turn()
    expensive.usage = Usage(prompt_tokens=1_000_000, completion_tokens=1_000_000, cache_miss_tokens=1_000_000)
    mock = MockProvider([expensive, *implement_turns()], model="deepseek-v4-pro")
    result = make_agent(tmp_path, mock, spec, max_cost_usd=0.5).run()
    assert result.status == "stopped" and "cost cap" in result.reason and result.cost_usd > 0.5


def test_resume_after_interruption(tmp_path, spec):
    first = make_agent(tmp_path, MockProvider([plan_turn(), *implement_turns()]), spec, max_requests=2).run()
    assert first.status == "stopped"
    state = RunState.load(tmp_path / "out/agent_run/state.json")
    assert state.phase == "implement" and state.phase_started

    events = []
    second = make_agent(tmp_path, MockProvider([reply(tool_call("finish", "f9", summary="resumed"))]), spec,
                        events).run(resume=True)
    assert ("resume", {"phase": "implement", "fix_round": 0}) in events
    assert second.status == "completed" and second.verify_ok is True
    assert second.requests == 3


def test_nudges_then_stop_when_model_never_calls_tools(tmp_path, spec):
    talk = [LLMResponse(content="I think...") for _ in range(3)]
    result = make_agent(tmp_path, MockProvider(talk), spec).run()
    assert result.status == "stopped" and "stopped calling tools" in result.reason


def test_length_cutoff_asks_to_continue(tmp_path, spec):
    def check_continue(messages, tools):
        assert "cut off" in messages[-1]["content"]
        return plan_turn()

    mock = MockProvider([LLMResponse(content="partial", finish_reason="length"), check_continue, *implement_turns()])
    assert make_agent(tmp_path, mock, spec).run().verify_ok


class CompactingMock(MockProvider):
    """Answers summary requests itself so the script only contains agent turns."""

    summaries = 0

    def complete(self, messages, tools=None, max_tokens=8192):
        if messages[0]["content"] == COMPACT_PROMPT:
            self.summaries += 1
            return LLMResponse(content="SUMMARY of work so far")
        return super().complete(messages, tools, max_tokens)


def test_auto_compaction(tmp_path, spec):
    agent = make_agent(tmp_path, None, spec)
    agent.context = ContextManager(agent.run_dir, budget_tokens=1000, keep_recent=2)
    reads = [reply(tool_call("read_file", f"r{i}", path="agent_run/spec.json")) for i in range(3)]
    agent.provider = CompactingMock([*reads, plan_turn(), *implement_turns()])
    result = agent.run()
    assert result.verify_ok
    assert agent.state.compactions == agent.provider.summaries >= 1
    events = read_events(agent.run_dir / "transcript.jsonl")
    assert "compaction" in [e.get("purpose") for e in events if e["event"] == "llm_response"]
    assert agent.state.messages[:2] == agent.provider.requests[0]["messages"][:2]  # cached prefix untouched
    summary = next(m for m in agent.state.messages if "auto-compacted" in str(m.get("content")))
    assert "Current phase instructions (restated)" in summary["content"]


def test_compaction_needs_enough_middle_messages(tmp_path):
    cm = ContextManager(tmp_path, budget_tokens=10, keep_recent=2)
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "spec"},
            {"role": "user", "content": "x" * 400}, {"role": "assistant", "content": "a"}]
    assert cm.needs_compaction(msgs) and cm.split_point(msgs) is None


def test_replay_reproduces_run_without_cost(tmp_path, spec):
    make_agent(tmp_path / "a", MockProvider([plan_turn(), *implement_turns()]), spec).run()
    replay = ReplayProvider(tmp_path / "a/out/agent_run/transcript.jsonl")
    assert replay.remaining == 3
    result = make_agent(tmp_path / "b", replay, spec).run()
    assert result.verify_ok and result.cost_usd == 0
    assert (tmp_path / "b/out/game/logic.py").read_text() == (tmp_path / "a/out/game/logic.py").read_text()
    assert "REPLAY of a recorded run" in (tmp_path / "b/out/agent_run/RUN_REPORT.md").read_text(encoding="utf-8")


def test_user_stop(tmp_path, spec):
    stop = threading.Event()
    stop.set()
    agent = Agent(MockProvider([plan_turn()]), AppConfig(), tmp_path / "out", spec, stop_event=stop)
    result = agent.run()
    assert result.status == "stopped" and "user" in result.reason and result.requests == 0


def test_large_tool_output_is_saved_and_truncated(tmp_path, spec):
    def check(messages, tools):
        content = messages[-1]["content"]
        assert "truncated" in content and "tool-results/" in content and len(content) < 9000
        return plan_turn()

    agent = make_agent(tmp_path, None, spec)
    agent.provider = MockProvider([reply(tool_call("read_file", "big", path="agent_run/spec.json")), check,
                                   *implement_turns()])
    assert agent.run().verify_ok
    assert list((agent.run_dir / "tool-results").glob("*_read_file.txt"))


def test_malformed_tool_json_is_recoverable(tmp_path, spec):
    def check(messages, tools):
        assert "Invalid JSON" in messages[-1]["content"]
        return plan_turn()

    bad = LLMResponse(tool_calls=[ToolCall("b1", "update_todos", "{not json")], finish_reason="tool_calls")
    assert make_agent(tmp_path, MockProvider([bad, check, *implement_turns()]), spec).run().verify_ok
