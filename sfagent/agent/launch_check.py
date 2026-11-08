"""Harness-side launch check (part of Verify) — "does the delivered program start?".

Runs `main.py` exactly as `python main.py` would (run_name="__main__"), in a child process of the bundled
interpreter, with Tk's mainloop replaced by a few seconds of real event processing. It reports a crash during
start-up, an exception raised inside a Tk callback (timers, events) while the window runs, and main.py not opening
a window at all (the task asks for a desktop application). It needs no contract from the generated code and
checks nothing about layout, style or features.
"""

from __future__ import annotations

import json

from sfagent.tools.runner import PythonRunner

CHECK_REL = "agent_run/launch_check.py"

CHECK_SOURCE = r'''
import json, runpy, sys, time, traceback
from pathlib import Path
import tkinter as tk
sys.path.insert(0, ".")
SECONDS = 3.0
roots, errors = [], []
_orig_init = tk.Tk.__init__


def _where(tb):
    frames = traceback.extract_tb(tb) if tb else []
    return f"{Path(frames[-1].filename).name}:{frames[-1].lineno}" if frames else "?"


def _init(self, *args, **kwargs):
    _orig_init(self, *args, **kwargs)
    roots.append(self)
    self.report_callback_exception = lambda et, ev, tb: errors.append(f"{et.__name__}: {ev} (at {_where(tb)})")


class _Done(BaseException):  # BaseException: an app's `except Exception` around mainloop must not swallow it
    pass


def _mainloop(*_args, **_kwargs):
    end = time.time() + SECONDS
    while roots and time.time() < end:
        try:
            roots[-1].update()
        except tk.TclError:
            break  # the application closed its own window
        time.sleep(0.02)
    raise _Done()


tk.Tk.__init__ = _init
tk.Misc.mainloop = _mainloop
tk.mainloop = _mainloop
result = {"window": False, "errors": errors, "crash": None}
try:
    runpy.run_path("main.py", run_name="__main__")
except (_Done, SystemExit):
    pass
except BaseException as exc:
    result["crash"] = f"{type(exc).__name__}: {exc} (at {_where(exc.__traceback__)})"
result["window"] = bool(roots)
print("LAUNCH_CHECK_RESULT " + json.dumps(result), flush=True)
for root in roots:
    try:
        root.destroy()
    except tk.TclError:
        pass
'''


def run_launch_check(runner: PythonRunner, timeout: int = 60) -> tuple[bool, str]:
    """Start main.py for a few seconds. Returns (ok, report text)."""
    if not (runner.root / "main.py").is_file():
        return False, "LAUNCH CHECK FAILED: main.py not found (the application must start with `python main.py`)."
    target = runner.root / CHECK_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(CHECK_SOURCE, encoding="utf-8")
    ok, out = runner.run_script(CHECK_REL, timeout=timeout)
    line = next((ln for ln in reversed(out.splitlines()) if ln.startswith("LAUNCH_CHECK_RESULT ")), None)
    if line is None:
        return False, ("LAUNCH CHECK FAILED: `python main.py` did not get through start-up (it hung, exited the "
                       "process, or crashed hard):\n" + out[-2000:])
    data = json.loads(line[len("LAUNCH_CHECK_RESULT "):])
    problems = []
    if data["crash"]:
        problems.append(f"main.py crashed while starting: {data['crash']}")
    problems += [f"a Tk callback raised {e} while the window was running" for e in data["errors"][:5]]
    if not data["crash"] and not data["window"]:
        problems.append("main.py ran without opening a window (tk.Tk()); the task asks for a desktop application")
    if problems:
        return False, f"LAUNCH CHECK FAILED ({len(problems)}):\n- " + "\n- ".join(problems)
    return True, "LAUNCH CHECK OK: main.py opened its window and ran for 3 s without errors"
