# ruff: noqa: I001, SIM105  (style only; evidence tools are frozen as used for the study)
"""Run Agent B through its own GUI and record everything (research evidence; not part of the agent).

    python scripts/evidence/record_agent_run.py --out runs/b1 --evidence evidence/b1 --max-cost 0.22 [--mock]

The GUI is filled in and "Generate" is pressed by this script (the paid-run confirmation is answered "yes" and
logged). The API key is NOT typed into the GUI: it comes from .env, so it never appears on screen.
Writes to --evidence: agent_gui.mp4, agent_gui_*.png (every 30 s, at every phase change, at the end),
agent_events.jsonl (every GUI event with a timestamp), agent_gui_log.txt / _todos.txt / _report.txt.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import winrec  # noqa: E402

from sfagent.gui import app as gui  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--max-cost", type=float, default=0.22)
    ap.add_argument("--max-requests", type=int, default=80)
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    out, ev = Path(a.out).resolve(), Path(a.evidence).resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty — every study run needs a new empty folder")
    ev.mkdir(parents=True, exist_ok=True)
    events = (ev / "agent_events.jsonl").open("a", encoding="utf-8")
    t0 = time.time()

    def note(kind: str, data) -> None:
        events.write(json.dumps({"t": round(time.time() - t0, 2), "kind": kind, "data": data}, default=str,
                                ensure_ascii=False) + "\n")
        events.flush()

    def auto_yes(title, message, **_):
        note("dialog_auto_answer", {"title": title, "message": message, "answer": "yes"})
        return True

    gui.messagebox.askyesno = auto_yes  # only the paid-run confirmation is asked in an empty folder
    app = gui.create_window()
    hwnd = {"main": int(app.wm_frame(), 16)}
    rec = winrec.Recorder(lambda: hwnd["main"], ev / "agent_gui.mp4", fps=2, fixed=True).start()
    shots = {"n": 0}

    def shot(label: str, widget=None) -> None:
        shots["n"] += 1
        h = int(widget.wm_frame(), 16) if widget is not None else hwnd["main"]
        winrec.save_png(winrec.capture(h), ev / f"agent_gui_{shots['n']:03d}_{label}.png")

    original_handle = app._handle

    def handle(kind, d):
        if kind != "approve":
            note(kind, d)
        original_handle(kind, d)
        if kind == "phase":
            app.after(1500, lambda p=d["phase"]: shot(f"phase_{p}"))
        if kind == "done":
            app.after(4000, finish)

    app._handle = handle

    def periodic():
        if app.controller.running:
            shot("progress")
            app.after(30000, periodic)

    def start():
        v = app.vars
        v["mock"].set(a.mock)
        v["output_dir"].set(str(out))
        v["max_cost_usd"].set(f"{a.max_cost:.2f}")
        v["max_requests"].set(str(a.max_requests))
        v["record_deviations"].set(False)  # study protocol: never ask for reasons
        v["api_key"].set("")
        app._refresh_badge()
        app.update_idletasks()
        shot("settings_before_start")
        note("start", {"out": str(out), "max_cost": a.max_cost, "max_requests": a.max_requests, "mock": a.mock,
                       "record_deviations": False})
        app._generate()
        app.after(30000, periodic)

    def finish():
        shot("end_main_window")
        for w in app.winfo_children():
            if w.winfo_class() == "Toplevel" or isinstance(w, gui.ctk.CTkToplevel):
                try:
                    shot("end_result_dialog", w)
                except Exception:  # noqa: BLE001
                    pass
        for tab in ("Log", "Todos", "Report"):
            (ev / f"agent_gui_{tab.lower()}.txt").write_text(app.text[tab].get("1.0", "end"), encoding="utf-8")
        note("evidence_saved", {"seconds": round(time.time() - t0, 1)})
        app.after(1500, close)

    def close():
        rec.stop()
        app.destroy()

    app.after(2500, start)
    app.mainloop()
    events.close()
    print(f"evidence in {ev} ({rec.frames} video frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
