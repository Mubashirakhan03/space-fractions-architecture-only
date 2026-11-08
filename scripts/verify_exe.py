"""Verify dist/SpaceFractionsAgent.exe behaves correctly WITHOUT any Python on PATH.

    python scripts/verify_exe.py [path/to/SpaceFractionsAgent.exe]

The exe is started with a minimal environment (PATH = Windows system dirs only, no PYTHON* /
VIRTUAL_ENV variables, cwd = an empty temp dir) to simulate a PC with no Python installed.
Checks: --version, --doctor, --self-test (agent → child exe → pytest), --run-script, GUI window,
and launching the generated (mock demo) game window. No API calls are made.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sfagent import __version__  # noqa: E402

EXE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "SpaceFractionsArchOnly.exe"
WORK = Path(tempfile.mkdtemp(prefix="sfa_verify_"))
DEMO_TITLE = "Space Fractions — MOCK DEMO"  # window title of the mock demo app


def no_python_env() -> dict[str, str]:
    windir = os.environ.get("SYSTEMROOT", r"C:\Windows")
    keep = {k: v for k, v in os.environ.items()
            if not k.upper().startswith(("PYTHON", "VIRTUAL_ENV", "CONDA", "PATH"))
            and not any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET"))}
    keep["PATH"] = os.pathsep.join([rf"{windir}\System32", windir, rf"{windir}\System32\Wbem"])
    keep["APPDATA"] = str(WORK / "appdata")  # don't touch the developer's real config
    return keep


def run(args: list[str], cwd: Path = WORK, timeout: int = 300) -> tuple[int, str]:
    out = WORK / f"out_{int(time.time() * 1000)}.txt"
    env = no_python_env() | {"SFA_OUTPUT_FILE": str(out)}
    code = subprocess.run([str(EXE), *args], cwd=cwd, env=env, timeout=timeout).returncode
    return code, out.read_text(encoding="utf-8", errors="replace") if out.exists() else ""


def windows_titled(title: str) -> set[int]:
    """Handles of all top-level windows with exactly this title."""
    found: set[int] = set()
    user32 = ctypes.windll.user32

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if buf.value == title:
            found.add(hwnd)
        return True

    user32.EnumWindows(callback, 0)
    return found


def window_appears(args: list[str], title: str, cwd: Path = WORK, wait: float = 25) -> bool:
    """True if a NEW window with `title` appears (windows already open, e.g. the user's, are ignored)."""
    before = windows_titled(title)
    proc = subprocess.Popen([str(EXE), *args], cwd=cwd, env=no_python_env())
    window_pid = ctypes.c_ulong(0)
    try:
        end = time.time() + wait
        while time.time() < end:
            new = windows_titled(title) - before
            if new:
                ctypes.windll.user32.GetWindowThreadProcessId(next(iter(new)), ctypes.byref(window_pid))
                return True
            time.sleep(0.5)
        return False
    finally:
        # one-file exes run as bootloader + child; kill both trees so nothing is left running
        for pid in {proc.pid, window_pid.value} - {0}:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)


def main() -> int:
    if not EXE.is_file():
        print(f"exe not found: {EXE}")
        return 2
    print(f"exe: {EXE} ({EXE.stat().st_size / 1e6:.1f} MB)\nwork dir: {WORK}\nPATH: {no_python_env()['PATH']}\n")
    results: list[tuple[str, bool, str]] = []

    code, out = run(["--version"])
    results.append(("--version", code == 0 and out.strip() != "", out.strip()))

    code, out = run(["--doctor"])
    results.append(("--doctor", code == 0 and "RESULT: OK" in out, out.strip().splitlines()[-1] if out else ""))

    st_dir = WORK / "selftest_out"
    code, out = run(["--self-test", str(st_dir)])
    ok = code == 0 and "verify_ok=True" in out and (st_dir / "agent_run" / "RUN_REPORT.md").exists()
    results.append(("--self-test (agent + child exe + pytest)", ok, out.strip().splitlines()[-1] if out else ""))

    (WORK / "probe.py").write_text("import sys, sqlite3, tkinter, fractions\n"
                                   "print('frozen', getattr(sys, 'frozen', False), 'exe', sys.executable)\n",
                                   encoding="utf-8")
    code, out = run(["--run-script", "probe.py"])
    results.append(("--run-script uses bundled interpreter", code == 0 and "frozen True" in out, out.strip()))

    title = f"Space Fractions Code Agent — architecture only  v{__version__}"
    results.append(("GUI window opens", window_appears([], title), ""))
    results.append(("generated game window opens",
                    window_appears(["--run-script", "main.py"], DEMO_TITLE, cwd=st_dir), "mock demo main.py"))

    print("\n=== exe verification (no Python on PATH) ===")
    for name, ok, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail[:150]}")
    passed = all(ok for _, ok, _ in results)
    print("ALL PASSED" if passed else "SOME CHECKS FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
