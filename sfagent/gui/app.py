"""Main window (customtkinter, light theme).

Header: app name, subtitle, provider/model badge.
Left: cards (DeepSeek API, Inputs, Output, Run limits) + a fixed action bar that never scrolls away.
Right: phase bar (pending / running / done / failed / skipped), mode banner, tabs (Log, Todos,
Spec preview, Report) and a status bar with requests, tokens and cost.
The agent runs in a worker thread; this window polls the controller's queue every 100 ms.
"""

from __future__ import annotations

import json
import os
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

import customtkinter as ctk

from sfagent import APP_NAME, __version__
from sfagent.agent.replay import REPLAY_LABEL
from sfagent.config import AppConfig, load_config, mask_key, save_config
from sfagent.gui import theme as T
from sfagent.gui.controller import (
    RunController,
    build_provider,
    clear_previous_run,
    find_default_inputs,
    is_non_empty,
    launch_generated_game,
    new_run_subfolder,
    read_run_state,
    run_succeeded,
)
from sfagent.llm.deepseek import DEEPSEEK_MODEL
from sfagent.llm.pricing import PRICES_PER_M
from sfagent.parsers.spec import build_spec

TITLE = "Space Fractions Code Agent — architecture only"
SUBTITLE = "A simplified Claude-Code-style agent powered by DeepSeek"
PHASES = ["plan", "implement", "verify", "fix", "report"]
PHASE_NAMES = {"plan": "1  Plan", "implement": "2  Implement", "verify": "3  Verify", "fix": "4  Fix",
               "report": "5  Report"}
POLL_MS = 100
TODO_ICON = {"pending": "○", "in_progress": "◐", "completed": "●"}


def friendly_key_problem(key: str) -> str | None:
    if not key:
        return "No API key — paste your DeepSeek key (it starts with sk-) or enable mock mode."
    if not key.startswith("sk-"):
        return "Invalid API key — DeepSeek keys start with sk-. Copy it again from platform.deepseek.com → API keys."
    return None


class AgentApp(ctk.CTk):
    def __init__(self) -> None:
        ctk.set_appearance_mode("light")
        super().__init__(fg_color=T.BG)
        self.title(f"{TITLE}  v{__version__}")
        self.minsize(900, 560)
        self._fit_to_screen(1400, 850)
        icon = Path(__file__).resolve().parent.parent.parent / "assets" / "icon.ico"
        if icon.exists():
            self.iconbitmap(str(icon))
        self.cfg = load_config()
        self.controller = RunController()
        self.vars: dict[str, tk.Variable] = {}
        self.phase_status: dict[str, str] = {}
        self._run_kind = "live"
        self._started_at = 0.0
        self._max = (AppConfig.max_requests, AppConfig.max_cost_usd)
        self._last_usage: dict[str, Any] | None = None
        self._pulsing = False
        self._build()
        self._load_into_form()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(POLL_MS, self._poll)

    def _fit_to_screen(self, width: int, height: int) -> None:
        """Open at width×height (logical px) but never larger than the screen, centred.
        With Windows display scaling (e.g. 150%) a fixed 1400×850 would run off the bottom."""
        scale = ctk.ScalingTracker.get_window_scaling(self)
        screen_w, screen_h = self.winfo_screenwidth() / scale, self.winfo_screenheight() / scale
        w, h = min(width, int(screen_w * 0.95)), min(height, int(screen_h * 0.88))
        x, y = max(int((screen_w - w) / 2), 0), max(int((screen_h - h) / 3), 0)
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------ small widget helpers
    def font(self, size: int = 13, weight: str = "normal", mono: bool = False) -> ctk.CTkFont:
        return ctk.CTkFont(family=T.MONO_FONT if mono else T.UI_FONT, size=size, weight=weight)

    def _var(self, name: str, kind=tk.StringVar, value: Any = "") -> tk.Variable:
        self.vars[name] = kind(value=value)
        return self.vars[name]

    def _card(self, parent, title: str, hint: str | None = None) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=T.CARD, border_color=T.BORDER, border_width=1, corner_radius=10)
        card.pack(fill="x", padx=4, pady=6)
        ctk.CTkLabel(card, text=title, font=self.font(15, "bold"), text_color=T.TEXT, anchor="w").pack(
            fill="x", padx=14, pady=(10, 0))
        if hint:
            ctk.CTkLabel(card, text=hint, font=self.font(12), text_color=T.MUTED, anchor="w", justify="left",
                         wraplength=370).pack(fill="x", padx=14)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=(6, 12))
        return body

    def _label(self, parent, text: str) -> None:
        ctk.CTkLabel(parent, text=text, font=self.font(12, "bold"), text_color=T.TEXT, anchor="w").pack(
            fill="x", pady=(6, 2))

    def _entry(self, parent, var: str, placeholder: str = "", show: str | None = None) -> ctk.CTkEntry:
        e = ctk.CTkEntry(parent, textvariable=self._var(var), placeholder_text=placeholder, height=34,
                         font=self.font(13), border_color=T.BORDER, fg_color="#F9FAFB", text_color=T.TEXT)
        if show:
            e.configure(show=show)
        return e

    def _button(self, parent, text: str, command, primary: bool = False, **kw) -> ctk.CTkButton:
        style = ({"fg_color": T.ACCENT, "hover_color": T.ACCENT_HOVER, "text_color": "#FFFFFF"} if primary else
                 {"fg_color": T.NEUTRAL_BTN, "hover_color": T.NEUTRAL_BTN_HOVER, "text_color": T.TEXT})
        opts = {"height": 36, "corner_radius": 8, "font": self.font(13, "bold" if primary else "normal")}
        return ctk.CTkButton(parent, text=text, command=command, **(opts | style | kw))

    def _path_row(self, parent, label: str, var: str, placeholder: str, picker) -> None:
        self._label(parent, label)
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x")
        entry = self._entry(row, var, placeholder)
        entry.pack(side="left", fill="x", expand=True)
        self._button(row, "Browse", lambda: picker(var, label), width=80).pack(side="left", padx=(6, 0))
        # show the end of long paths (the file name), not the drive letter
        self.vars[var].trace_add("write", lambda *_: entry.after_idle(lambda: entry.xview("end")))

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(16, 8), pady=(0, 16))
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)
        scroll = ctk.CTkScrollableFrame(left, width=420, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        self._build_settings(scroll)
        actions = ctk.CTkFrame(left, fg_color=T.CARD, border_color=T.BORDER, border_width=1, corner_radius=10)
        actions.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self._build_actions(actions)
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 16), pady=(0, 16))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)
        self._build_right(right)

    def _build_header(self) -> None:
        head = ctk.CTkFrame(self, fg_color=T.CARD, corner_radius=0, border_color=T.BORDER, border_width=1)
        head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(head, text="🚀", font=self.font(30)).grid(row=0, column=0, rowspan=2, padx=(20, 10), pady=12)
        ctk.CTkLabel(head, text=TITLE, font=self.font(22, "bold"), text_color=T.TEXT, anchor="w").grid(
            row=0, column=1, sticky="sw", pady=(12, 0))
        ctk.CTkLabel(head, text=SUBTITLE, font=self.font(13), text_color=T.MUTED, anchor="w").grid(
            row=1, column=1, sticky="nw", pady=(0, 12))
        self.provider_badge = ctk.CTkLabel(head, text="", font=self.font(13, "bold"), corner_radius=14,
                                           fg_color="#EFF6FF", text_color=T.ACCENT, height=30)
        self.provider_badge.grid(row=0, column=2, rowspan=2, padx=20, ipadx=12)

    def _build_settings(self, f) -> None:
        api = self._card(f, "DeepSeek API", f"Provider: DeepSeek (official) · Model: {DEEPSEEK_MODEL}")
        self._label(api, "API key")
        row = ctk.CTkFrame(api, fg_color="transparent")
        row.pack(fill="x")
        self.key_entry = self._entry(row, "api_key", "sk-…", show="•")
        self.key_entry.pack(side="left", fill="x", expand=True)
        self.show_key_btn = self._button(row, "👁  Show", self._toggle_key, width=84)
        self.show_key_btn.pack(side="left", padx=(6, 0))
        row2 = ctk.CTkFrame(api, fg_color="transparent")
        row2.pack(fill="x", pady=(8, 0))
        ctk.CTkCheckBox(row2, text="Remember key on this PC", font=self.font(12), fg_color=T.ACCENT,
                        variable=self._var("remember_key", tk.BooleanVar, False)).pack(side="left")
        self.test_btn = self._button(row2, "Test connection", self._test_connection, width=140)
        self.test_btn.pack(side="right")
        self.conn_label = ctk.CTkLabel(api, text="Test connection sends one tiny request (≈ $0.0001).",
                                       font=self.font(12), text_color=T.MUTED, anchor="w", wraplength=370,
                                       justify="left")
        self.conn_label.pack(fill="x", pady=(4, 0))
        opts = ctk.CTkFrame(api, fg_color="transparent")
        opts.pack(fill="x", pady=(6, 0))
        ctk.CTkCheckBox(opts, text="Thinking mode (slower, more tokens)", font=self.font(12), fg_color=T.ACCENT,
                        variable=self._var("thinking", tk.BooleanVar, False)).pack(anchor="w", pady=2)
        ctk.CTkCheckBox(opts, text="Developer: mock mode (no API calls, scripted demo)", font=self.font(12),
                        fg_color=T.ACCENT, variable=self._var("mock", tk.BooleanVar, False),
                        command=self._refresh_badge).pack(anchor="w", pady=2)

        inputs = self._card(f, "Inputs", "Any architecture document + PlantUML views; they are parsed to spec.json.")
        self._path_row(inputs, "Architecture documentation (.md)", "doc_path", "Architecture_Documentation.md",
                       self._pick_file)
        self._path_row(inputs, "Architecture views — PlantUML (.md)", "view_path", "Architecture_View.md",
                       self._pick_file)
        self._label(inputs, "Experiment (architecture only — no task profile, no extra requirements)")
        ctk.CTkCheckBox(inputs, text="Ask the agent to record every deviation from the architecture (and why)",
                        font=self.font(12), fg_color=T.ACCENT,
                        variable=self._var("record_deviations", tk.BooleanVar, False)).pack(anchor="w")
        self._button(inputs, "Preview spec.json", self._preview_spec).pack(fill="x", pady=(10, 0))

        out = self._card(f, "Output")
        self._path_row(out, "Output folder (must be empty for a new run)", "output_dir", "Choose a folder",
                       self._pick_dir)

        lim = self._card(f, "Run limits", "Hard caps: the run stops gracefully and saves its state.")
        grid = ctk.CTkFrame(lim, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure(0, weight=1)
        fields = [("max_cost_usd", "Max cost per run (USD)"), ("max_requests", "Max LLM requests per run"),
                  ("max_steps", "Max agent steps"), ("fix_rounds", "Auto-fix rounds")]
        for i, (name, label) in enumerate(fields):
            ctk.CTkLabel(grid, text=label, font=self.font(13), text_color=T.TEXT, anchor="w").grid(
                row=i, column=0, sticky="w", pady=3)
            e = self._entry(grid, name)
            e.configure(width=90, justify="right")
            e.grid(row=i, column=1, sticky="e", pady=3)
        ctk.CTkCheckBox(lim, text="Ask me before every file write", font=self.font(12), fg_color=T.ACCENT,
                        variable=self._var("ask_before_write", tk.BooleanVar, False)).pack(anchor="w", pady=(8, 0))

    def _build_actions(self, f) -> None:
        inner = ctk.CTkFrame(f, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=12)
        self.generate_btn = self._button(inner, "▶   Generate project", self._generate, primary=True, height=44)
        self.generate_btn.configure(font=self.font(15, "bold"))
        self.generate_btn.pack(fill="x")
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))
        row.grid_columnconfigure((0, 1, 2), weight=1, uniform="a")
        self.stop_btn = self._button(row, "■  Stop", self._stop, state="disabled")
        self.stop_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.resume_btn = self._button(row, "⟳  Resume", self._resume)
        self.resume_btn.grid(row=0, column=1, sticky="ew", padx=4)
        self.replay_btn = self._button(row, "⏵  Replay", self._replay)
        self.replay_btn.grid(row=0, column=2, sticky="ew", padx=(4, 0))
        row2 = ctk.CTkFrame(inner, fg_color="transparent")
        row2.pack(fill="x", pady=(8, 0))
        row2.grid_columnconfigure((0, 1), weight=1, uniform="b")
        self._button(row2, "📂  Open output folder", self._open_output).grid(row=0, column=0, sticky="ew",
                                                                           padx=(0, 4))
        self.run_game_btn = self._button(row2, "▶  Run generated app", self._run_game, fg_color=T.OK,
                                         hover_color="#15803D", text_color="#FFFFFF")
        self.run_game_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

    def _build_right(self, f) -> None:
        bar = ctk.CTkFrame(f, fg_color=T.CARD, border_color=T.BORDER, border_width=1, corner_radius=10)
        bar.grid(row=0, column=0, sticky="ew")
        self.phase_widgets: dict[str, tuple[ctk.CTkFrame, ctk.CTkLabel, ctk.CTkLabel]] = {}
        for i, p in enumerate(PHASES):
            bar.grid_columnconfigure(i, weight=1, uniform="p")
            box = ctk.CTkFrame(bar, corner_radius=8, height=56)
            box.grid(row=0, column=i, sticky="ew", padx=6, pady=10)
            name = ctk.CTkLabel(box, text=PHASE_NAMES[p], font=self.font(14, "bold"))
            name.pack(pady=(6, 0))
            caption = ctk.CTkLabel(box, text="", font=self.font(11))
            caption.pack(pady=(0, 6))
            self.phase_widgets[p] = (box, name, caption)
        self.mode_banner = ctk.CTkLabel(f, text="", font=self.font(13, "bold"), text_color=T.WARN, height=28)
        self.mode_banner.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        self.tabs = ctk.CTkTabview(f, fg_color=T.CARD, border_color=T.BORDER, border_width=1, corner_radius=10,
                                   segmented_button_selected_color=T.ACCENT,
                                   segmented_button_selected_hover_color=T.ACCENT_HOVER,
                                   segmented_button_unselected_color="#F3F4F6", text_color=T.TEXT)
        self.tabs.grid(row=2, column=0, sticky="nsew")
        self.text: dict[str, ctk.CTkTextbox] = {}
        for name in ("Log", "Todos", "Spec preview", "Report"):
            tab = self.tabs.add(name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)
            box = ctk.CTkTextbox(tab, font=self.font(14 if name == "Todos" else 13, mono=name != "Todos"),
                                 wrap="word", fg_color="#FAFAFA", text_color=T.TEXT, border_spacing=8)
            box.grid(row=0, column=0, sticky="nsew")
            for tag, color in T.LOG_COLORS.items():
                box.tag_config(tag, foreground=color)
            box.configure(state="disabled")
            self.text[name] = box

        self.status = ctk.CTkLabel(f, text="", font=self.font(13, mono=True), text_color=T.TEXT, anchor="w",
                                   fg_color=T.CARD, corner_radius=8, height=34)
        self.status.grid(row=3, column=0, sticky="ew", pady=(8, 0), ipadx=12)
        self._reset_phases()
        self._update_status()

    # ------------------------------------------------------------------ form <-> config
    def _load_into_form(self) -> None:
        c = self.cfg
        doc, view = find_default_inputs()
        values = {"api_key": c.api_key, "remember_key": bool(c.api_key), "thinking": c.thinking,
                  "mock": c.provider == "mock", "doc_path": c.doc_path or doc, "view_path": c.view_path or view,
                  "output_dir": c.output_dir or str(Path.home() / "Documents" / "SpaceFractionsGenerated"),
                  "max_steps": c.max_steps, "max_requests": c.max_requests, "max_cost_usd": c.max_cost_usd,
                  "fix_rounds": c.fix_rounds, "ask_before_write": c.ask_before_write,
                  "record_deviations": c.record_deviations}
        for k, v in values.items():
            self.vars[k].set(v)
        self._refresh_badge()
        self.vars["output_dir"].trace_add("write", lambda *_: self._refresh_run_button(self.controller.running))
        self._refresh_run_button()

    def _form_config(self) -> AppConfig:
        v = {k: var.get() for k, var in self.vars.items()}
        try:
            return AppConfig(api_key=v["api_key"].strip(), provider="mock" if v["mock"] else "deepseek",
                             thinking=v["thinking"], max_steps=int(v["max_steps"]),
                             max_requests=int(v["max_requests"]), max_cost_usd=float(v["max_cost_usd"]),
                             fix_rounds=int(v["fix_rounds"]), ask_before_write=v["ask_before_write"],
                             doc_path=v["doc_path"].strip(), view_path=v["view_path"].strip(),
                             output_dir=v["output_dir"].strip(), record_deviations=v["record_deviations"])
        except ValueError as exc:
            raise ValueError("Run limits must be numbers (e.g. 1.00 for cost, 40 for requests).") from exc

    def _persist(self, cfg: AppConfig) -> None:
        stored = AppConfig(**{**cfg.__dict__, "api_key": cfg.api_key if self.vars["remember_key"].get() else ""})
        save_config(stored)

    # ------------------------------------------------------------------ actions
    def _refresh_badge(self) -> None:
        if self._run_kind == "replay" and self.controller.running:
            text = f"⏵ {REPLAY_LABEL}"
        elif self.vars["mock"].get():
            text = "Provider: Mock (scripted demo) · no API calls"
        else:
            text = f"Provider: DeepSeek (official) · Model: {DEEPSEEK_MODEL}"
        self.provider_badge.configure(text=f"  {text}  ")

    def _toggle_key(self) -> None:
        hidden = bool(self.key_entry.cget("show"))
        self.key_entry.configure(show="" if hidden else "•")
        self.show_key_btn.configure(text="🙈  Hide" if hidden else "👁  Show")

    def _pick_file(self, var: str, title: str) -> None:
        path = filedialog.askopenfilename(title=f"Select {title}", filetypes=[("Markdown", "*.md"), ("All", "*.*")])
        if path:
            self.vars[var].set(path)

    def _pick_dir(self, var: str, title: str) -> None:
        path = filedialog.askdirectory(title=f"Select {title}")
        if path:
            self.vars[var].set(path)

    def _test_connection(self) -> None:
        try:
            cfg = self._form_config()
            problem = None if cfg.provider == "mock" else friendly_key_problem(cfg.resolved_api_key())
            if problem:
                raise ValueError(problem)
            provider = build_provider(cfg)
        except Exception as exc:
            self.conn_label.configure(text=f"✗ {exc}", text_color=T.ERR)
            return
        self.conn_label.configure(text=f"Testing key {mask_key(cfg.resolved_api_key())} …", text_color=T.MUTED)
        self.test_btn.configure(state="disabled")

        def work():
            try:
                msg, color = "✓ " + provider.test_connection(), T.OK
            except Exception as exc:
                msg, color = f"✗ {exc}", T.ERR
            self.after(0, lambda: (self.conn_label.configure(text=msg, text_color=color),
                                   self.test_btn.configure(state="normal")))

        threading.Thread(target=work, daemon=True).start()

    def _preview_spec(self) -> None:
        try:
            cfg = self._form_config()
            spec = build_spec(Path(cfg.doc_path), Path(cfg.view_path))
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not build spec.json:\n{exc}")
            return
        summary = {"domain_model": spec["domain_model"], "input_issues": spec["input_issues"],
                   "requirements": spec["requirements"]}
        self._set_text("Spec preview", json.dumps(summary, indent=2, ensure_ascii=False))
        self.tabs.set("Spec preview")

    def _generate(self, resume: bool = False, replay: Path | None = None) -> None:
        try:
            cfg = self._form_config()
        except ValueError as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return
        out = Path(cfg.output_dir) if cfg.output_dir else None
        if not resume and out and is_non_empty(out):
            choice = self._folder_dialog(out)
            if choice == "new":
                sub = new_run_subfolder(out)
                self.vars["output_dir"].set(str(sub))
                cfg.output_dir = str(sub)
                self._log(f"Using a new subfolder: {sub}", "info")
            elif choice == "overwrite":
                if not messagebox.askyesno(APP_NAME, f"Delete the files generated by the previous run in\n{out}\n\n"
                                                     "Only files the agent created are removed; your own files stay."):
                    return
                try:
                    removed = clear_previous_run(out)
                except (OSError, ValueError) as exc:
                    messagebox.showerror(APP_NAME, str(exc))
                    return
                self._log(f"Removed {len(removed)} files from the previous run.", "warn")
            elif choice == "resume":
                self._generate(resume=True)
                return
            else:
                return
        if replay is None and cfg.provider == "deepseek" and not self._confirm_paid_run(cfg):
            return
        self._persist(cfg)
        self._run_kind = "replay" if replay else ("mock" if cfg.provider == "mock" else "live")
        self._max = (cfg.max_requests, cfg.max_cost_usd)
        self._reset_view()
        self.controller.start(cfg, resume=resume, replay_transcript=replay)
        self._started_at = time.time()
        self._set_running(True)

    def _confirm_paid_run(self, cfg: AppConfig) -> bool:
        problem = friendly_key_problem(cfg.resolved_api_key())
        if problem:
            messagebox.showerror(APP_NAME, problem)
            return False
        p = PRICES_PER_M[DEEPSEEK_MODEL]
        return messagebox.askyesno(APP_NAME, (
            f"This run calls the paid DeepSeek API ({DEEPSEEK_MODEL}).\n\n"
            f"Price per 1M tokens: input ${p['cache_miss']} (cache hit ${p['cache_hit']}), output ${p['output']} "
            f"(2× in peak hours).\nTypical full run: about $0.20–0.45.\n\n"
            f"Hard limits for this run: ${cfg.max_cost_usd:.2f} and {cfg.max_requests} requests.\n\nStart?"))

    def _resume(self) -> None:
        out = Path(self.vars["output_dir"].get())
        if not (out / "agent_run" / "state.json").exists():
            messagebox.showinfo(APP_NAME, "No saved run in this output folder.")
            return
        self._generate(resume=True)

    def _replay(self) -> None:
        path = filedialog.askopenfilename(title="Select a recorded transcript.jsonl",
                                          filetypes=[("Transcript", "transcript.jsonl"), ("JSONL", "*.jsonl")])
        if path:
            self._generate(replay=Path(path))

    def _stop(self) -> None:
        self.controller.stop()
        self._log("Stop requested — finishing the current step…", "warn")

    def _open_output(self) -> None:
        out = Path(self.vars["output_dir"].get())
        if out.is_dir():
            os.startfile(out)  # noqa: S606 - Windows desktop app
        else:
            messagebox.showinfo(APP_NAME, "The output folder does not exist yet.")

    def _run_game(self) -> None:
        try:
            launch_generated_game(Path(self.vars["output_dir"].get()))
            self._log("Launched the generated app (main.py) with the bundled interpreter.", "ok")
        except FileNotFoundError:
            messagebox.showinfo(APP_NAME, "No generated main.py in the output folder yet — run Generate first.")
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def _on_close(self) -> None:
        if self.controller.running:
            if not messagebox.askyesno(APP_NAME, "A run is in progress. Stop it and quit? (Its state is saved.)"):
                return
            self.controller.stop()
            self.controller.thread.join(timeout=5)
        self.destroy()

    # ------------------------------------------------------------------ events from the worker
    def _poll(self) -> None:
        for kind, data in self.controller.drain():
            self._handle(kind, data)
        if self.controller.running:
            self._update_status()
        self.after(POLL_MS, self._poll)

    def _handle(self, kind: str, d: dict[str, Any]) -> None:
        if kind == "log":
            text = d["text"]
            tag = "phase" if text.startswith("===") else "model" if text.startswith("model:") else "info"
            if text.startswith("verify:"):
                tag = "ok" if "PASSED" in text else "err"
            self._log(text, tag)
        elif kind == "phase":
            self._on_phase(d["phase"])
        elif kind == "resume":
            self._on_resume(d["phase"], d.get("fix_round", 0))
        elif kind == "tool_call":
            self._log(f"→ {d['summary']}", "tool")
        elif kind == "tool_result":
            first = d["preview"].splitlines()[0][:160] if d["preview"] else ""
            self._log(f"    {'✓' if d['ok'] else '✗'} {first}", "ok" if d["ok"] else "err")
        elif kind == "todos":
            self._set_text("Todos", "\n".join(f"{TODO_ICON[t['status']]}  {t['content']}" for t in d["todos"]))
        elif kind == "usage":
            self._update_status(d)
        elif kind == "verify":
            self._set_phase("verify", "done" if d["ok"] else "failed")
            self._log(("✓ VERIFY PASSED\n" if d["ok"] else "✗ VERIFY FAILED\n") + d["report"][-1500:],
                      "ok" if d["ok"] else "err")
        elif kind == "error":
            self._log(f"ERROR: {d['text']}", "err")  # the end-of-run dialog shows the reason
        elif kind == "approve":
            req = d["request"]
            req.approved = messagebox.askyesno(APP_NAME, f"Allow the agent to write:\n\n{req.path}\n\n"
                                                         f"{req.preview[:600]}")
            req.answered.set()
        elif kind == "done":
            self._finish(d["result"])

    def _on_resume(self, phase: str, fix_round: int) -> None:
        """A resumed run starts mid-pipeline: show the phases it already completed as done."""
        order = {"plan": 0, "implement": 1, "verify": 2, "report": 4, "done": 5}
        current = order.get(phase, 0)
        for p in PHASES:
            idx = PHASES.index(p)
            if p == "fix":
                if fix_round > 0 and current >= 2:
                    self._set_phase("fix", "done")
            elif idx < current:
                self._set_phase(p, "done")
        self._log(f"Resumed at phase '{phase}' — earlier phases were completed in the previous session.", "info")

    def _on_phase(self, phase: str) -> None:
        for p, s in self.phase_status.items():
            if s == "running" and p != phase:
                self._set_phase(p, "done")
        if phase == "report" and self.phase_status.get("fix") == "pending":
            self._set_phase("fix", "skipped")
        self._set_phase(phase, "running")

    def _finish(self, result: dict[str, Any]) -> None:
        self._set_running(False)
        status = result.get("status")
        end_state = {"completed": "done", "stopped": "stopped"}.get(status, "failed")
        for p, s in self.phase_status.items():
            if s == "running":
                self._set_phase(p, end_state)
        reason = f": {result['reason']}" if result.get("reason") else ""
        self._log(f"=== Run {status}{reason} ===", "ok" if status == "completed" else "err")
        report = result.get("report_path")
        if report and Path(report).exists():
            self._set_text("Report", Path(report).read_text(encoding="utf-8"))
        self._update_status(final=True)
        self._refresh_badge()
        self._show_result(result)

    # ------------------------------------------------------------------ result feedback & dialogs
    def _show_result(self, result: dict[str, Any]) -> None:
        """Clear end-of-run feedback: green banner + dialog on success, red on failure/stop."""
        out = self.vars["output_dir"].get()
        status = result.get("status")
        if status == "completed" and result.get("verify_ok"):
            self.mode_banner.configure(text="✅ Project generated successfully!  Tests: PASSED", text_color=T.OK)
            self._result_dialog(True, "Project generated successfully!",
                                f"Files saved in:\n{out}\n\nTests: PASSED")
            return
        if status == "completed":
            reason = "the generated project still fails its checks — see the Report tab"
        else:
            reason = result.get("reason") or status or "unknown error"
        title = {"stopped": "Run stopped"}.get(status, "Run did not succeed")
        self.mode_banner.configure(text=f"✗ {title}: {reason}", text_color=T.ERR)
        self._result_dialog(False, title, f"Reason: {reason}\n\nFiles so far: {out}")

    def _result_dialog(self, success: bool, title: str, message: str) -> None:
        dlg = ctk.CTkToplevel(self, fg_color=T.CARD)
        dlg.title(APP_NAME)
        dlg.transient(self)
        dlg.resizable(False, False)
        color = T.OK if success else T.ERR
        ctk.CTkLabel(dlg, text="✅" if success else "✗", font=self.font(40), text_color=color).pack(pady=(22, 4))
        ctk.CTkLabel(dlg, text=title, font=self.font(20, "bold"), text_color=color).pack(padx=30)
        ctk.CTkLabel(dlg, text=message, font=self.font(13), text_color=T.TEXT, justify="center",
                     wraplength=520).pack(padx=30, pady=(8, 18))
        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(pady=(0, 22))

        def then(action):
            return lambda: (dlg.destroy(), action())

        if success:
            self._button(row, "▶  Run generated app", then(self._run_game), fg_color=T.OK, hover_color="#15803D",
                         text_color="#FFFFFF", width=200).pack(side="left", padx=6)
        else:
            self._button(row, "View report", then(lambda: self.tabs.set("Report")), width=140).pack(side="left",
                                                                                                    padx=6)
        self._button(row, "📂  Open folder", then(self._open_output), width=150).pack(side="left", padx=6)
        self._button(row, "Close", dlg.destroy, width=100).pack(side="left", padx=6)
        self._place_dialog(dlg)

    def _folder_dialog(self, out: Path) -> str | None:
        """Output folder is not empty: new subfolder / overwrite previous run / resume / cancel."""
        has_run = read_run_state(out) is not None
        dlg = ctk.CTkToplevel(self, fg_color=T.CARD)
        dlg.title(APP_NAME)
        dlg.transient(self)
        dlg.resizable(False, False)
        choice: dict[str, str | None] = {"value": None}
        ctk.CTkLabel(dlg, text="The output folder already contains files", font=self.font(18, "bold"),
                     text_color=T.TEXT).pack(padx=30, pady=(22, 4))
        ctk.CTkLabel(dlg, text=str(out), font=self.font(12), text_color=T.MUTED, wraplength=520).pack(padx=30)
        ctk.CTkLabel(dlg, text=f"A new run folder would be:  {new_run_subfolder(out)}", font=self.font(12),
                     wraplength=520, text_color=T.MUTED).pack(padx=30, pady=(6, 14))

        def pick(value):
            return lambda: (choice.update(value=value), dlg.destroy())

        self._button(dlg, "📁  Create a new run folder (recommended)", pick("new"), primary=True,
                     width=380).pack(pady=4)
        self._button(dlg, "♻  Overwrite this folder (removes the previous run's files only)", pick("overwrite"),
                     width=380, state="normal" if has_run else "disabled").pack(pady=4)
        self._button(dlg, "⟳  Resume previous run", pick("resume"), width=380,
                     state="normal" if has_run else "disabled").pack(pady=4)
        self._button(dlg, "Cancel", dlg.destroy, width=380).pack(pady=(4, 22))
        if not has_run:
            ctk.CTkLabel(dlg, text="(No previous agent run here, so only a new subfolder is offered.)",
                         font=self.font(11), text_color=T.MUTED).pack(pady=(0, 14))
        self._place_dialog(dlg)
        dlg.grab_set()
        self.wait_window(dlg)
        return choice["value"]

    def _place_dialog(self, dlg) -> None:
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - dlg.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dlg.winfo_height()) // 3
        dlg.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        dlg.lift()
        dlg.focus_force()

    def _refresh_run_button(self, force_disabled: bool = False) -> None:
        """'Run generated app' is only enabled (and pulses) when the selected folder holds a successful run."""
        ready = not force_disabled and run_succeeded(self.vars["output_dir"].get())
        self.run_game_btn.configure(state="normal" if ready else "disabled",
                                    fg_color=T.OK if ready else T.NEUTRAL_BTN,
                                    text_color="#FFFFFF" if ready else T.MUTED,
                                    font=self.font(14 if ready else 13, "bold" if ready else "normal"))
        if ready and not self._pulsing:
            self._pulsing = True
            self._pulse(0)
        elif not ready:
            self._pulsing = False

    def _pulse(self, step: int) -> None:
        if not self._pulsing:
            return
        self.run_game_btn.configure(fg_color=T.OK if step % 2 == 0 else "#22C55E",
                                    border_width=2 if step % 2 == 0 else 0, border_color="#86EFAC")
        self.after(650, lambda: self._pulse(step + 1))

    # ------------------------------------------------------------------ view helpers
    def phase_state(self, phase: str) -> str:
        return self.phase_status.get(phase, "pending")

    def _set_phase(self, phase: str, status: str) -> None:
        if phase not in self.phase_widgets:
            return
        self.phase_status[phase] = status
        box, name, caption = self.phase_widgets[phase]
        bg, fg = T.PHASE_COLORS[status]
        box.configure(fg_color=bg)
        name.configure(text_color=fg)
        caption.configure(text=T.PHASE_CAPTION[status], text_color=fg)

    def _reset_phases(self) -> None:
        for p in PHASES:
            self._set_phase(p, "pending")

    def _reset_view(self) -> None:
        for name in ("Log", "Todos", "Report"):
            self._set_text(name, "")
        self._reset_phases()
        self._last_usage = None
        banners = {"replay": f"⏵ {REPLAY_LABEL} — no API calls are made",
                   "mock": "MOCK MODE — scripted demo, no API calls"}
        self.mode_banner.configure(text=banners.get(self._run_kind, ""))
        self._refresh_badge()
        self.tabs.set("Log")

    def _set_running(self, running: bool) -> None:
        for b in (self.generate_btn, self.resume_btn, self.replay_btn, self.test_btn):
            b.configure(state="disabled" if running else "normal")
        self._refresh_run_button(force_disabled=running)
        self.stop_btn.configure(state="normal" if running else "disabled",
                                fg_color=T.ERR if running else T.NEUTRAL_BTN,
                                text_color="#FFFFFF" if running else T.TEXT)

    def _update_status(self, d: dict[str, Any] | None = None, final: bool = False) -> None:
        if d:
            self._last_usage = d
        d = self._last_usage
        max_req, max_cost = self._max
        elapsed = int(time.time() - self._started_at) if self._started_at else 0
        if not d:
            text = f"Requests 0 / {max_req}   ·   Tokens 0   ·   Cost $0.0000 / ${max_cost:.2f}"
        else:
            u = d["usage"]
            total = u["prompt_tokens"] + u["completion_tokens"]
            hit = 100 * u["cache_hit_tokens"] / u["prompt_tokens"] if u["prompt_tokens"] else 0
            text = (f"Requests {d['requests']} / {max_req}   ·   Tokens {total:,} (cache hit {hit:.0f}%)   ·   "
                    f"Cost ${d['cost_usd']:.4f} / ${max_cost:.2f}")
        if elapsed:
            text += f"   ·   {elapsed // 60}:{elapsed % 60:02d}"
        self.status.configure(text=text)
        if final:
            self._started_at = 0.0

    def _log(self, text: str, tag: str = "info") -> None:
        box = self.text["Log"]
        box.configure(state="normal")
        box.insert("end", text + "\n", tag)
        box.see("end")
        box.configure(state="disabled")

    def _set_text(self, tab: str, text: str) -> None:
        box = self.text[tab]
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")


def create_window(retries: int = 3) -> AgentApp:
    """Tk initialisation occasionally fails transiently on Windows ("Can't find a usable init.tcl"
    while the file is being scanned); retry a few times before giving up."""
    for attempt in range(retries):
        try:
            return AgentApp()
        except tk.TclError:
            if attempt == retries - 1:
                raise
            time.sleep(0.5)
    raise RuntimeError("unreachable")


def launch() -> int:
    app = create_window()
    app.mainloop()
    return 0
