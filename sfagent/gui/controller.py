"""UI-independent run controller: builds provider + agent, runs it in a worker thread, and hands
events to the UI through a queue (the Tk main loop polls it, so the window never freezes).
"""

from __future__ import annotations

import json
import queue
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sfagent import APP_NAME
from sfagent.agent.loop import Agent
from sfagent.agent.replay import ReplayProvider
from sfagent.config import AppConfig
from sfagent.llm.deepseek import DeepSeekProvider
from sfagent.llm.demo_script import demo_provider
from sfagent.llm.provider import LLMError, LLMProvider
from sfagent.parsers.spec import build_spec
from sfagent.tools.runner import base_command, clean_env

DOC_NAME = "Architecture_Documentation.md"
VIEW_NAME = "Architecture_View.md"


def build_provider(cfg: AppConfig, replay_transcript: Path | None = None) -> LLMProvider:
    if replay_transcript:
        return ReplayProvider(replay_transcript)
    if cfg.provider == "mock":
        return demo_provider()
    key = cfg.resolved_api_key()
    if not key:
        raise LLMError("No DeepSeek API key: enter it in the GUI or set DEEPSEEK_API_KEY.")
    return DeepSeekProvider(key, thinking=cfg.thinking)


APP_ROOT = Path(__file__).resolve().parent.parent.parent  # in a frozen exe this is the temp _MEI folder


def user_data_dir() -> Path:
    """Persistent, user-visible folder for samples and profiles (never the temp _MEI folder)."""
    return Path.home() / "Documents" / APP_NAME


def resource_dir(name: str) -> Path:
    """Folder with bundled `samples` or `profiles`.

    Dev mode: the repo folder. Frozen exe: copied once from the bundle to Documents/SpaceFractionsAgent/
    so paths shown in the GUI stay valid after the exe exits.
    """
    if not getattr(sys, "frozen", False):
        return APP_ROOT / name
    target = user_data_dir() / name
    bundled = APP_ROOT / name
    if bundled.is_dir() and not target.exists():
        shutil.copytree(bundled, target)
    return target


def find_default_inputs(extra_dirs: list[Path] | None = None) -> tuple[str, str]:
    """Pre-fill the two input files if they sit next to the exe, in the cwd, or in the samples folder."""
    exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None
    candidates = [*(extra_dirs or []), *(d for d in (exe_dir, exe_dir and exe_dir / "samples") if d),
                  Path.cwd(), Path.cwd() / "samples", resource_dir("samples")]
    for d in candidates:
        if (d / DOC_NAME).is_file() and (d / VIEW_NAME).is_file():
            return str(d / DOC_NAME), str(d / VIEW_NAME)
    return "", ""


@dataclass
class ApprovalRequest:
    path: str
    preview: str
    answered: threading.Event = field(default_factory=threading.Event)
    approved: bool = False


class RunController:
    def __init__(self) -> None:
        self.events: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.agent: Agent | None = None

    @property
    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def _emit(self, kind: str, data: dict[str, Any]) -> None:
        self.events.put((kind, data))

    def start(self, cfg: AppConfig, *, resume: bool = False, replay_transcript: Path | None = None,
              provider: LLMProvider | None = None, approval_timeout: float = 600) -> None:
        if self.running:
            raise RuntimeError("A run is already in progress.")
        self.stop_event = threading.Event()

        def approve(path: str, preview: str) -> bool:
            req = ApprovalRequest(path, preview)
            self._emit("approve", {"request": req})
            req.answered.wait(timeout=approval_timeout)
            return req.approved

        def work() -> None:
            try:
                prov = provider or build_provider(cfg, replay_transcript)
                spec = self._load_spec(cfg, replay_transcript)
                self.agent = Agent(prov, cfg, cfg.output_dir, spec, on_event=self._emit,
                                   approve_write=approve if cfg.ask_before_write else None,
                                   stop_event=self.stop_event)
                self._emit("log", {"text": f"Provider: {prov.name} | model: {prov.model} | architecture only | "
                                           f"record deviations: {'ON' if cfg.record_deviations else 'OFF'}"})
                self.agent.run(resume=resume)
            except Exception as exc:  # surface everything to the UI instead of dying silently
                self._emit("error", {"text": f"{type(exc).__name__}: {exc}"})
                self._emit("done", {"result": {"status": "error", "reason": str(exc)}})

        self.thread = threading.Thread(target=work, name="agent-run", daemon=True)
        self.thread.start()

    @staticmethod
    def _load_spec(cfg: AppConfig, replay_transcript: Path | None) -> dict[str, Any]:
        if replay_transcript:  # replay must use the exact spec of the recorded run
            recorded = Path(replay_transcript).parent / "spec.json"
            if recorded.exists():
                return json.loads(recorded.read_text(encoding="utf-8"))
        if not (cfg.doc_path and cfg.view_path):
            raise ValueError("Select both input files first.")
        if not cfg.output_dir:
            raise ValueError("Select an output folder first.")
        return build_spec(Path(cfg.doc_path), Path(cfg.view_path))

    def stop(self) -> None:
        self.stop_event.set()

    def drain(self, limit: int = 200) -> list[tuple[str, dict[str, Any]]]:
        out = []
        while len(out) < limit:
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                break
        return out


def launch_generated_game(output_dir: Path) -> subprocess.Popen:
    """Start the generated main.py with the bundled interpreter (no Python needed on the PC)."""
    main_py = Path(output_dir) / "main.py"
    if not main_py.is_file():
        raise FileNotFoundError(f"No main.py in {output_dir}")
    return subprocess.Popen([*base_command(), "--run-script", "main.py"], cwd=output_dir, env=clean_env(),
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------- output-folder helpers

GENERATED_EXTRA = ("DESIGN_DECISIONS.md", "AGENT_NOTES.md")


def read_run_state(folder: Path) -> dict[str, Any] | None:
    path = Path(folder) / "agent_run" / "state.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def run_succeeded(folder: Path | str) -> bool:
    """True if the folder holds a completed run whose verification passed and a main.py to launch."""
    if not folder:
        return False
    folder = Path(folder)
    state = read_run_state(folder)
    return bool(state and state.get("status") == "completed" and state.get("verify_ok")
                and (folder / "main.py").is_file())


def is_non_empty(folder: Path | str) -> bool:
    folder = Path(folder)
    return folder.is_dir() and any(folder.iterdir())


RUN_DIR_RE = re.compile(r"^run-\d{4}-\d{2}-\d{2}_\d{4}(-\d+)?$")


def run_folder_base(folder: Path | str) -> Path:
    """Where new run folders go. If `folder` is itself a run folder (it holds agent_run/ or has a run-… name),
    new runs become its siblings — otherwise every new run would be nested inside the previous one."""
    folder = Path(folder)
    if (folder / "agent_run").is_dir() or RUN_DIR_RE.match(folder.name):
        return folder.parent
    return folder


def new_run_subfolder(folder: Path | str, now: datetime | None = None) -> Path:
    """<base>/run-YYYY-MM-DD_HHMM (base = folder, or its parent if folder is a run folder), with -2, -3 … if taken."""
    base = run_folder_base(folder)
    stamp = (now or datetime.now()).strftime("run-%Y-%m-%d_%H%M")
    candidate = base / stamp
    n = 2
    while candidate.exists():
        candidate = base / f"{stamp}-{n}"
        n += 1
    return candidate


def clear_previous_run(folder: Path | str) -> list[str]:
    """Delete ONLY what a previous agent run generated (files it recorded + agent_run/); the user's own
    files are kept. Returns the removed relative paths. Raises if the folder has no recorded run."""
    folder = Path(folder).resolve()
    state = read_run_state(folder)
    if state is None:
        raise ValueError("No previous agent run is recorded in this folder; nothing was deleted.")
    removed = []
    for rel in sorted({*state.get("written", []), *GENERATED_EXTRA}):
        target = (folder / rel).resolve()
        if folder in target.parents and target.is_file():
            target.unlink()
            removed.append(rel)
    run_dir = folder / "agent_run"
    if run_dir.is_dir():
        shutil.rmtree(run_dir)
        removed.append("agent_run/")
    for d in sorted((p for p in folder.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if not any(d.iterdir()):  # tidy up empty package folders left behind
            d.rmdir()
    return removed
