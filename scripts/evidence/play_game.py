# ruff: noqa: I001, SIM105  (style only; evidence tools are frozen as used for the study)
"""Play a generated Tkinter app with a generic bot and record it (research evidence; not part of the agent).

    python scripts/evidence/play_game.py --project runs/b1 --evidence evidence/b1 [--steps 70] [--seconds 300]

The bot knows nothing about the app. Every step it looks at the widgets on screen and does one thing a user could
do: type an answer into an empty entry, pick a radio button, or click a button / clickable label / clickable
canvas item, preferring ones it has not tried on this screen and words like Start, Play, Next, Submit, Check.
For simple fraction expressions it finds on screen (``3/4 + 1/8``, ``simplify 6/8`` …) it types the correct
answer, otherwise it cycles a few answers. It plays on a COPY of the project, so the generated project stays as it
was. Message boxes are logged and answered "OK"/"Yes"; a PIN / text prompt gets a fixed value. Writes to --evidence:
game_play.mp4 (+ game_play.srt subtitles with every action), game_step_NNN.png, game_play_log.jsonl,
game_play_summary.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOOD = ["start", "play", "begin", "skip", "continue", "next", "submit", "check", "answer", "ok", "go", "enter",
        "new game", "launch", "fire", "yes"]
LAST = ["quit", "exit", "close", "logout", "log out"]
RISKY = ["delete", "remove", "reset", "clear"]
FALLBACK_ANSWERS = ["1/2", "3/4", "2/3", "1", "5/8"]
PROMPT_VALUE = "1234"
CLICK_SEQS = ("<Button-1>", "<ButtonPress-1>", "<ButtonRelease-1>", "<Button>")


# ----------------------------------------------------------------------------------------------- answer guessing
FR = r"(\d+)\s*/\s*(\d+)"


def solve(texts: list[str]) -> list[str]:
    """Correct answers for simple fraction tasks visible on screen (most specific first)."""
    out: list[str] = []
    blob = "  ".join(texts)
    for m in re.finditer(FR + r"\s*([+\-−×x*÷:])\s*" + FR, blob):
        a, op, b = Fraction(int(m[1]), int(m[2]) or 1), m[3], Fraction(int(m[4]), int(m[5]) or 1)
        r = {"+": a + b, "-": a - b, "−": a - b, "×": a * b, "x": a * b, "*": a * b}.get(op)
        if r is None and b:
            r = a / b
        if r is not None:
            out.append(f"{r.numerator}/{r.denominator}" if r.denominator != 1 else str(r.numerator))
    for m in re.finditer(r"(?:simplif\w*|reduce\w*|lowest terms)[^0-9]{0,20}" + FR, blob, re.I):
        r = Fraction(int(m[1]), int(m[2]) or 1)
        out.append(f"{r.numerator}/{r.denominator}")
    return out


# ----------------------------------------------------------------------------------------------- child process
def child(main_py: Path, ev: Path, steps: int, seconds: int) -> None:
    import tkinter as tk
    from tkinter import messagebox, simpledialog

    sys.path.insert(0, str(HERE))
    import winrec

    import faulthandler
    stacks = (ev / "game_play_stacks.txt").open("w", encoding="utf-8")
    faulthandler.dump_traceback_later(40, repeat=True, file=stacks)  # shows where a stuck app hangs

    t0 = time.time()
    log = (ev / "game_play_log.jsonl").open("w", encoding="utf-8")
    subs: list[tuple[float, str]] = []
    state = {"root": None, "step": 0, "tried": {}, "answer_i": 0, "errors": [], "dialogs": [], "screens": set(),
             "done": False, "rec": None, "tops": [], "global": {}, "hwnd": 0, "lists": []}

    def note(kind: str, **data) -> None:
        t = round(time.time() - t0, 2)
        log.write(json.dumps({"t": t, "step": state["step"], "kind": kind, **data}, ensure_ascii=False) + "\n")
        log.flush()
        if kind in ("action", "dialog", "callback_error", "crash", "end"):
            subs.append((t, data.get("text") or data.get("summary") or kind))

    # --- dialogs: log and answer like a user who reads and confirms
    def dialog(kind, default):
        def f(title=None, message=None, **_):
            state["dialogs"].append(kind)
            note("dialog", text=f"[{kind}] {title or ''}: {message or ''}"[:300])
            return default
        return f

    for name, value in {"showinfo": "ok", "showwarning": "ok", "showerror": "ok", "askyesno": True,
                        "askokcancel": True, "askquestion": "yes", "askretrycancel": False,
                        "askyesnocancel": True}.items():
        setattr(messagebox, name, dialog(name, value))
    creds = json.loads(os.environ.get("SFBOT_CREDS", "{}"))

    given: list[str] = []  # values typed into the current series of content prompts

    def askstring(title, prompt, **kw):
        low = f"{title} {prompt}".lower()
        field = str(prompt or "").lower()
        secret = kw.get("show") or any(k in field for k in ("pass", "pin", "code"))
        login = any(k in low for k in ("user", "login", "log in", "sign in"))
        if secret:
            value = creds.get("password") or PROMPT_VALUE
        elif login:
            value = creds.get("username") or PROMPT_VALUE
        elif any(k in field for k in ("correct", "answer", "solution")):
            value = given[0] if given else "1/2"
            given.clear()
        elif any(k in field for k in ("question", "prompt", "text")):
            given.clear()
            value = "What is 1/2 + 1/4?"
        else:  # an option / numerator / any other field
            value = ["3/4", "1/2", "2/3", "1/4", "5/8"][len(given) % 5]
            given.append(value)
        note("dialog", text=f"[askstring] {title}: {prompt} → {value}")
        return value

    simpledialog.askstring = askstring
    simpledialog.askinteger = lambda title, prompt, **_: (note("dialog", text=f"[askinteger] {title}: {prompt}"), 1)[1]
    simpledialog.askfloat = lambda title, prompt, **_: (note("dialog", text=f"[askfloat] {title}: {prompt}"), 1.0)[1]

    def report_error(self, exc, val, tb):
        import traceback
        text = "".join(traceback.format_exception_only(exc, val)).strip()
        state["errors"].append(text)
        note("callback_error", text=f"Tk callback error: {text}",
             traceback="".join(traceback.format_exception(exc, val, tb))[-2000:])

    tk.Tk.report_callback_exception = report_error
    orig_init = tk.Tk.__init__

    def init(self, *a, **k):
        orig_init(self, *a, **k)
        if state["root"] is None:
            state["root"] = self
            self.after(2500, lambda: begin(self))

    tk.Tk.__init__ = init

    # --- widget helpers
    def walk(w):
        yield w
        for c in w.winfo_children():
            yield from walk(c)

    def viewable(w) -> bool:
        try:
            return bool(w.winfo_viewable())
        except tk.TclError:
            return False

    def text_of(w) -> str:
        for opt in ("text",):
            try:
                v = str(w.cget(opt)).strip()
                if v:
                    return v
            except tk.TclError:
                pass
        return ""

    def toplevels(root):
        tops = [root] + [w for w in walk(root) if isinstance(w, tk.Toplevel)]
        return [t for t in tops if viewable(t)]

    def active_top(root):
        tops = toplevels(root)
        return tops[-1] if tops else root

    def canvas_texts(c) -> list[str]:
        out = []
        for item in c.find_all():
            if c.type(item) == "text" and "hidden" not in str(c.itemcget(item, "state")):
                t = str(c.itemcget(item, "text")).strip()
                if t:
                    out.append(t)
        return out

    def clickable_canvas_items(c):
        items = []
        for item in c.find_all():
            if "hidden" in str(c.itemcget(item, "state")):
                continue
            keys = [item, *c.gettags(item)]
            if any(c.tag_bind(k, seq) for k in keys for seq in CLICK_SEQS):
                x1, y1, x2, y2 = c.bbox(item) or (0, 0, 0, 0)
                label = ""
                for other in c.find_overlapping(x1, y1, x2, y2):
                    if c.type(other) == "text":
                        label = str(c.itemcget(other, "text")).strip() or label
                items.append((item, (x1 + x2) // 2, (y1 + y2) // 2, label or f"canvas item {item}"))
        return items

    def screen(root):
        top = active_top(root)
        texts, buttons, entries, radios, canvases = [], [], [], [], []
        lists = state["lists"] = []
        for w in walk(top):
            if w is not top and isinstance(w, tk.Toplevel):
                continue
            if not viewable(w):
                continue
            cls = w.winfo_class()
            t = text_of(w)
            if cls in ("Label", "TLabel", "Message") and t:
                texts.append(t)
                if any(w.bind(seq) for seq in CLICK_SEQS):
                    buttons.append((w, t, "label"))
            elif cls in ("Button", "TButton"):
                texts.append(t)
                if str(w.cget("state")) != "disabled":
                    buttons.append((w, t or "(unnamed button)", "button"))
            elif cls in ("Entry", "TEntry", "Spinbox", "TSpinbox", "TCombobox"):
                if str(w.cget("state")) not in ("disabled", "readonly"):
                    entries.append(w)
            elif cls in ("Radiobutton", "TRadiobutton"):
                texts.append(t)
                radios.append((w, t))
            elif cls == "Canvas":
                texts.extend(canvas_texts(w))
                canvases.append(w)
            elif cls == "Listbox":
                texts.extend(str(x) for x in w.get(0, "end")[:10])
                lists.append(w)
            elif cls == "Treeview":
                rows = w.get_children()
                texts.extend(" ".join(map(str, w.item(r, "values")))[:80] for r in rows[:10])
                lists.append(w)
        for c in canvases:
            for item, x, y, label in clickable_canvas_items(c):
                buttons.append(((c, item, x, y), label, "canvas"))
            if any(c.bind(seq) for seq in CLICK_SEQS):  # the whole canvas reacts to a click
                buttons.append(((c, None, c.winfo_width() // 2, c.winfo_height() // 2), "click on the screen",
                                "canvas"))
        return top, texts, buttons, entries, radios

    def key_bound(top) -> bool:
        return any(w.bind(seq) for w in (top, *walk(top)) for seq in ("<Key>", "<KeyPress>", "<space>", "<Return>"))

    def shot(label: str) -> None:
        top = active_top(state["root"])
        try:
            winrec.save_png(winrec.capture(int(top.wm_frame(), 16)), ev / f"game_step_{state['step']:03d}_{label}.png")
        except tk.TclError:
            pass

    def is_last(text: str) -> bool:
        low = re.sub(r"[^a-z ]", " ", text.lower()).split()
        return bool(low) and (low[0] in ("quit", "close", "logout") or low == ["exit"]
                              or " ".join(low[:2]) in ("exit game", "exit app", "log out"))

    def score(text: str, kind: str, tried: int, answers=()) -> float:
        low = text.lower()
        s = 10.0 - 4 * tried - 1.5 * state["global"].get(text, 0)  # explore: new buttons first
        if any(k in low for k in GOOD):
            s += 5
        if text.strip() in answers:
            s += 8  # the correct answer of a fraction task on screen
        if any(k in low for k in RISKY):
            s -= 6
        if is_last(text):
            s -= 100
        if kind == "canvas":
            s += 1
        return s

    def act(root) -> None:
        if state["done"]:
            return
        try:
            top, texts, buttons, entries, radios = screen(root)
        except tk.TclError:
            return
        sig = " | ".join(t.replace("\n", " ")[:60] for t in texts[:25])
        state["screens"].add(sig)
        state["step"] += 1
        note("screen", texts=texts[:40], buttons=[b[1] for b in buttons], entries=len(entries),
             radios=[r[1] for r in radios])
        shot("screen")
        tried = state["tried"].setdefault(sig, {})
        answers = solve(texts)
        done = []
        screen_low = " ".join(texts).lower()
        for e in entries:
            try:
                if not e.get().strip():
                    secret = str(e.cget("show")) or any(k in screen_low for k in ("password", "pin"))
                    if secret and creds.get("password"):
                        ans = creds["password"]
                    elif "user" in screen_low and creds.get("username") and not secret:
                        ans = creds["username"]
                    else:
                        ans = (answers[0] if answers
                               else FALLBACK_ANSWERS[state["answer_i"] % len(FALLBACK_ANSWERS)])
                    state["answer_i"] += 1
                    e.delete(0, "end")
                    e.insert(0, ans)
                    done.append(f"typed '{ans}'")
            except tk.TclError:
                pass
        for lst in state["lists"]:  # a list with rows and nothing selected: select the first row, like a user
            try:
                if lst.winfo_class() == "Treeview":
                    rows = lst.get_children()
                    if rows and not lst.selection():
                        lst.selection_set(rows[0])
                        lst.event_generate("<<TreeviewSelect>>")
                        done.append("selected the first row of the list")
                elif lst.size() and not lst.curselection():
                    lst.selection_set(0)
                    lst.event_generate("<<ListboxSelect>>")
                    done.append("selected the first row of the list")
            except tk.TclError:
                pass
        if radios:
            pick = next((r for r in radios if any(a == r[1].strip() for a in answers)), None)
            pick = pick or radios[state["step"] % len(radios)]
            try:
                pick[0].invoke()
                done.append(f"picked '{pick[1]}'")
            except tk.TclError:
                pass
        def sc(b):
            return score(b[1], b[2], tried.get(b[1], 0), answers)

        candidates = sorted(buttons, key=lambda b: -sc(b))
        if candidates and sc(candidates[0]) > -50:
            w, label, kind = candidates[0]
            tried[label] = tried.get(label, 0) + 1
            state["global"][label] = state["global"].get(label, 0) + 1
            done.append(f"clicked '{label}'")
            note("action", summary=f"step {state['step']}: " + ", ".join(done), answers_seen=answers)
            click(w, kind)
        elif done:
            note("action", summary=f"step {state['step']}: " + ", ".join(done) + ", pressed Enter",
                 answers_seen=answers)
            top.event_generate("<Return>")
        elif key_bound(top) and tried.get("<key>", 0) < 2:
            tried["<key>"] = tried.get("<key>", 0) + 1
            note("action", summary=f"step {state['step']}: pressed Space (the screen listens for keys)")
            target = top.focus_lastfor() or top  # like a real key press: it goes to the window's focus widget
            target.focus_force()
            target.event_generate("<KeyPress>", keysym="space")
            if target.winfo_exists():
                target.event_generate("<KeyRelease>", keysym="space")
        else:
            note("action", summary=f"step {state['step']}: nothing to do on this screen (waiting)")

    def click(w, kind) -> None:
        try:
            if kind == "button":
                w.invoke()
            elif kind == "label":
                w.event_generate("<Button-1>", x=2, y=2)
                if w.winfo_exists():
                    w.event_generate("<ButtonRelease-1>", x=2, y=2)
            else:
                c, _item, x, y = w
                c.event_generate("<Button-1>", x=x, y=y)
                if c.winfo_exists():
                    c.event_generate("<ButtonRelease-1>", x=x, y=y)
        except tk.TclError as exc:
            note("action", summary=f"click failed: {exc}")

    def loop(root) -> None:
        if state["done"]:
            return
        if state["step"] >= steps or time.time() - t0 > seconds:
            return end(root)
        try:
            act(root)
        except Exception as exc:  # noqa: BLE001 - the bot's own problem, not an error of the app
            note("bot_error", text=f"bot error (not the app): {exc!r}")
        try:
            root.after(1800, lambda: loop(root))
        except tk.TclError:
            pass

    def end(root) -> None:
        state["done"] = True
        top, texts, buttons, *_ = screen(root)
        quit_btn = next((b for b in buttons if is_last(b[1])), None)
        note("end", text="end of play: " + (f"clicking '{quit_btn[1]}'" if quit_btn else "closing the window"))
        shot("final")
        state["rec"].stop()
        summary = {"steps": state["step"], "distinct_screens": len(state["screens"]),
                   "callback_errors": state["errors"], "dialogs": len(state["dialogs"]),
                   "seconds": round(time.time() - t0, 1)}
        (ev / "game_play_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), "utf-8")
        write_srt(ev / "game_play.srt", subs, time.time() - t0)
        try:
            if quit_btn:
                click(quit_btn[0], quit_btn[2])
            root.after(1500, lambda: root.winfo_exists() and root.destroy())
        except tk.TclError:
            pass

    def track(root) -> None:  # Tk may only be used from its own thread; the recorder just reads this number
        if state["done"]:
            return
        try:
            state["hwnd"] = int(active_top(root).wm_frame(), 16)
            root.after(250, lambda: track(root))
        except tk.TclError:
            pass

    def begin(root) -> None:
        track(root)
        state["rec"] = winrec.Recorder(lambda: state["hwnd"], ev / "game_play.mp4", fps=4).start()
        note("start", text=f"window '{root.title()}' opened")
        root.after(1500, lambda: loop(root))

    import runpy
    sys.argv = [str(main_py)]
    sys.path.insert(0, str(main_py.parent))
    try:
        runpy.run_path(str(main_py), run_name="__main__")
    except SystemExit:
        pass
    except BaseException as exc:  # noqa: BLE001
        import traceback
        note("crash", text=f"main.py crashed: {exc!r}", traceback=traceback.format_exc()[-2000:])
    if state["rec"] and not state["done"]:
        state["rec"].stop()
        write_srt(ev / "game_play.srt", subs, time.time() - t0)
    log.close()


def write_srt(path: Path, subs: list[tuple[float, str]], total: float) -> None:
    def ts(s: float) -> str:
        ms = int(round(s * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"

    t_start = subs[0][0] if subs else 0.0
    lines = []
    for i, (t, text) in enumerate(subs):
        start = max(0.0, t - t_start - 2.5)  # the video starts when the window has opened
        nxt = subs[i + 1][0] - t_start - 2.5 if i + 1 < len(subs) else total - t_start
        lines.append(f"{i + 1}\n{ts(start)} --> {ts(max(start + 0.5, nxt))}\n{text}\n")
    path.write_text("\n".join(lines), encoding="utf-8")


# ----------------------------------------------------------------------------------------------- parent
def ffmpeg_path() -> str:
    sys.path.insert(0, str(HERE))
    import winrec
    return winrec.ffmpeg_exe()


def readme_credentials(readme: Path) -> dict:
    """Login data a tester would find in the generated README (e.g. "username `admin`, password `admin123`")."""
    if not readme.exists():
        return {}
    text = readme.read_text(encoding="utf-8", errors="replace")
    found = {}
    for key, pattern in (("username", r"user(?:name)?\W{0,4}[`'\"]([^`'\"\s]+)[`'\"]"),
                         ("password", r"(?:password|passcode|pin)\W{0,4}[`'\"]([^`'\"\s]+)[`'\"]")):
        m = re.search(pattern, text, re.I)
        if m:
            found[key] = m[1]
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--steps", type=int, default=70)
    ap.add_argument("--seconds", type=int, default=300)
    ap.add_argument("--child-main")
    a = ap.parse_args()
    ev = Path(a.evidence).resolve()
    ev.mkdir(parents=True, exist_ok=True)
    if a.child_main:
        child(Path(a.child_main), ev, a.steps, a.seconds)
        return 0
    src = Path(a.project).resolve()
    play = Path(tempfile.mkdtemp(prefix="sf_play_"))
    shutil.copytree(src, play / "app", ignore=shutil.ignore_patterns("agent_run", "__pycache__", ".pytest_cache"))
    (play / "home").mkdir()
    creds = readme_credentials(src / "README.md")
    env = os.environ | {"USERPROFILE": str(play / "home"), "HOME": str(play / "home"),  # app data stays in the copy
                        "APPDATA": str(play / "home"), "LOCALAPPDATA": str(play / "home"),
                        "SFBOT_CREDS": json.dumps(creds), "SFBOT_FFMPEG": ffmpeg_path()}
    (ev / "game_play_setup.json").write_text(json.dumps({"project": str(src), "credentials_from_readme": creds,
                                                         "steps": a.steps, "seconds": a.seconds}, indent=2),
                                             encoding="utf-8")
    proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--evidence", str(ev), "--steps",
                           str(a.steps), "--seconds", str(a.seconds), "--child-main", str(play / "app" / "main.py")],
                          cwd=play / "app", capture_output=True, text=True, timeout=a.seconds + 120, env=env)
    (ev / "game_play_stdout.txt").write_text(proc.stdout + "\n--- stderr ---\n" + proc.stderr, encoding="utf-8")
    print((ev / "game_play_summary.json").read_text(encoding="utf-8") if (ev / "game_play_summary.json").exists()
          else f"no summary; exit {proc.returncode}\n{proc.stderr[-1500:]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
