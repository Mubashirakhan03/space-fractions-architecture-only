
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
