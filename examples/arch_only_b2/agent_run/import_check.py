
import importlib, json, runpy, sys, traceback
from pathlib import Path
sys.path.insert(0, ".")
SKIP = {"agent_run", "tests", "__pycache__", ".venv", "venv", ".git"}
problems, checked = [], []
for path in sorted(Path(".").rglob("*.py")):
    parts = path.parts
    if SKIP & set(parts) or path.name.startswith(("test_", "conftest")):
        continue
    rel = path.as_posix()
    try:
        if rel == "main.py":
            runpy.run_path(rel, run_name="__import_check__")  # top-level imports only, main() is not called
        else:
            mod = ".".join(parts[:-1] + (() if path.stem == "__init__" else (path.stem,)))
            if mod:
                importlib.import_module(mod)
        checked.append(rel)
    except SystemExit:
        checked.append(rel)
    except BaseException as exc:  # ImportError, AttributeError, NameError, … at import time
        last = traceback.extract_tb(exc.__traceback__)[-1]
        problems.append(f"{rel}: {type(exc).__name__}: {exc} (at {Path(last.filename).name}:{last.lineno})")
print("IMPORT_CHECK_RESULT " + json.dumps({"checked": checked, "problems": problems}), flush=True)
