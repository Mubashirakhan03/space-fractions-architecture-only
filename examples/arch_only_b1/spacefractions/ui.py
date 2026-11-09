"""Tkinter user interface for Space Fractions.

Views:
    IntroMovieView  — animated space-themed introduction (skippable)
    MainMenuView    — Play / View Score / Help / Admin / Quit
    GameView        — series of fraction questions
    EndingView      — ending scene with score & feedback
    AdminView       — manage the question bank (admin only)

The UI layer is intentionally thin: all logic lives in service/repository.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable, Optional

from .repository import GameRepository, QuestionRepository
from .service import GameService, GameState


class App(tk.Tk):
    """Top-level application window."""

    def __init__(self, db, repository, auth):
        super().__init__()
        self.db = db
        self.question_repo: QuestionRepository = repository
        self.auth = auth
        self.title("Space Fractions")
        self.geometry("900x600")
        self.minsize(720, 480)
        self._user: Optional[dict] = None
        self._frame: Optional[tk.Frame] = None
        self.show_intro()

    def _swap(self, frame: tk.Frame) -> None:
        if self._frame is not None:
            self._frame.destroy()
        self._frame = frame
        frame.pack(fill="both", expand=True)

    def show_intro(self) -> None:
        self._swap(IntroMovieView(self, on_done=self.show_menu))

    def show_menu(self) -> None:
        self._swap(
            MainMenuView(
                self,
                username=(self._user or {}).get("username"),
                on_play=self.start_game,
                on_score=self.show_scores,
                on_help=self.show_help,
                on_admin=self.show_admin,
                on_admin_login=self.admin_login,
                on_quit=self.destroy,
            )
        )

    def start_game(self) -> None:
        questions = self.question_repo.all()
        service = GameService(
            questions, username=(self._user or {}).get("username", "guest")
        )
        self._game_service = service
        self._swap(GameView(self, service, on_done=self.finish_game))

    def finish_game(self, service: GameService) -> None:
        GameRepository(self.db).record_score(
            (self._user or {}).get("username", "guest"),
            service.game.id,
            service.viewScore(),
            service.totalQuestions(),
        )
        self._swap(
            EndingView(
                self, service, on_menu=self.show_menu, on_replay=self.start_game
            )
        )

    def show_scores(self) -> None:
        history = GameRepository(self.db).history(
            (self._user or {}).get("username")
            if self._user
            else None
        )
        self._swap(ScoreView(self, history, on_back=self.show_menu))

    def show_help(self) -> None:
        self._swap(HelpView(self, on_back=self.show_menu))

    def show_admin(self) -> None:
        if not self._user or self._user.get("role") != "admin":
            messagebox.showinfo("Admin", "You must sign in as an admin first.")
            self.admin_login()
            return
        self._swap(AdminView(self, on_back=self.show_menu))

    def admin_login(self) -> None:
        username = simpledialog.askstring("Admin login", "Username:", parent=self)
        if username is None:
            return
        password = simpledialog.askstring(
            "Admin login", "Password:", show="*", parent=self
        )
        if password is None:
            return
        result = self.auth.authenticate(username, password)
        if result and result.get("role") == "admin":
            self._user = result
            messagebox.showinfo("Admin", "Signed in as admin.")
            self.show_admin()
        else:
            messagebox.showerror("Admin", "Invalid admin credentials.")


class IntroMovieView(tk.Frame):
    """Animated introduction; press any key or click to skip."""

    def __init__(self, master, on_done: Callable[[], None]):
        super().__init__(master, bg="#050510")
        self.on_done = on_done
        self._steps = 0
        self._canvas = tk.Canvas(self, bg="#050510", highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._title = self._canvas.create_text(
            450, 200, text="SPACE FRACTIONS", fill="#7fd4ff",
            font=("Segoe UI", 40, "bold")
        )
        self._sub = self._canvas.create_text(
            450, 260, text="An adventure among the numbers",
            fill="#cceeff", font=("Segoe UI", 16)
        )
        self._ship = self._canvas.create_oval(
            420, 400, 480, 440, fill="#ffffff"
        )
        self._stars = [
            self._canvas.create_oval(x, y, x + 2, y + 2, fill="white")
            for x, y in self._random_stars()
        ]
        self._hint = self._canvas.create_text(
            450, 540, text="— press any key or click to continue —",
            fill="#8899aa", font=("Segoe UI", 12)
        )
        self.bind("<Button-1>", self._skip)
        self.bind("<Key>", self._skip)
        self.focus_set()
        self._animate()

    @staticmethod
    def _random_stars():
        import random

        return [(random.randint(0, 900), random.randint(0, 560)) for _ in range(60)]

    def _animate(self):
        if not self.winfo_exists():
            return
        self._steps += 1
        self._canvas.move(self._ship, 0, -2 if self._steps % 4 == 0 else 0)
        color = "#7fd4ff" if self._steps % 20 < 10 else "#ffffff"
        self._canvas.itemconfig(self._title, fill=color)
        self._after = self.after(30, self._animate)

    def _skip(self, _event=None):
        if hasattr(self, "_after"):
            self.after_cancel(self._after)
        self.on_done()


class MainMenuView(tk.Frame):
    def __init__(
        self,
        master,
        username: Optional[str],
        on_play,
        on_score,
        on_help,
        on_admin,
        on_admin_login,
        on_quit,
    ):
        super().__init__(master, bg="#101428")
        label = tk.Label(
            self, text="Space Fractions", bg="#101428", fg="#7fd4ff",
            font=("Segoe UI", 32, "bold")
        )
        label.pack(pady=30)
        if username:
            tk.Label(
                self, text=f"Player: {username}", bg="#101428", fg="#cceeff",
                font=("Segoe UI", 12)
            ).pack()
        buttons = [
            ("Play Game", on_play),
            ("View Score", on_score),
            ("View Help", on_help),
            ("Admin (Update Questions)", on_admin),
            ("Admin Login", on_admin_login),
            ("Quit", on_quit),
        ]
        for text, cmd in buttons:
            ttk.Button(self, text=text, command=cmd).pack(pady=6, ipadx=20)


class GameView(tk.Frame):
    def __init__(self, master, service: GameService, on_done):
        super().__init__(master, bg="#101428")
        self.service = service
        self.on_done = on_done
        self._render()

    def _render(self):
        q = self.service.currentQuestion
        self.info = tk.Label(
            self,
            text=f"Question {self.service.game.current_index + 1} of "
            f"{self.service.totalQuestions()}   |   Score: "
            f"{self.service.viewScore()}",
            bg="#101428", fg="#cceeff", font=("Segoe UI", 12),
        )
        self.info.pack(pady=10)
        self.qlabel = tk.Label(
            self, text=q.prompt if q else "", bg="#101428", fg="white",
            font=("Segoe UI", 20)
        )
        self.qlabel.pack(pady=30)
        self.buttons = []
        for opt in q.options if q else []:
            b = ttk.Button(
                self, text=opt, command=lambda o=opt: self._answer(o)
            )
            b.pack(pady=4, ipadx=20, fill="x", padx=200)
            self.buttons.append(b)
        bar = tk.Frame(self, bg="#101428")
        bar.pack(pady=20)
        ttk.Button(bar, text="Pause", command=self._pause).pack(
            side="left", padx=10
        )
        ttk.Button(bar, text="Quit to Menu", command=self._quit).pack(
            side="left", padx=10
        )
        self._feedback = tk.Label(
            self, text="", bg="#101428", fg="#7fd4ff", font=("Segoe UI", 14)
        )
        self._feedback.pack(pady=10)

    def _answer(self, opt: str):
        correct = self.service.submitAnswer(opt)
        self._feedback.config(
            text="Correct! +1" if correct else "Not quite.",
            fg="#8f8" if correct else "#f88",
        )
        if self.service.is_over:
            self.after(600, lambda: self.on_done(self.service))
        else:
            self.after(600, self._rerender)

    def _rerender(self):
        for w in self.winfo_children():
            w.destroy()
        self._render()

    def _pause(self):
        self.service.pause()
        paused = tk.Toplevel(self)
        paused.title("Paused")
        tk.Label(paused, text="Game paused.", font=("Segoe UI", 14)).pack(padx=40, pady=20)
        ttk.Button(paused, text="Resume", command=lambda: (self.service.resume(), paused.destroy())).pack(pady=6)

    def _quit(self):
        self.service.gameOver()
        self.on_done(self.service)


class EndingView(tk.Frame):
    def __init__(self, master, service: GameService, on_menu, on_replay):
        super().__init__(master, bg="#050510")
        score = service.viewScore()
        total = service.totalQuestions()
        pct = score / total * 100 if total else 0
        if pct == 100:
            message = "Perfect! You mastered the fractions! 🚀"
        elif pct >= 70:
            message = "Great job, astronaut! Keep exploring!"
        elif pct >= 40:
            message = "Good effort — the cosmos awaits more practice!"
        else:
            message = "Don't give up — every fraction gets you closer!"
        tk.Label(
            self, text="Mission Report", bg="#050510", fg="#7fd4ff",
            font=("Segoe UI", 30, "bold")
        ).pack(pady=40)
        tk.Label(
            self, text=f"Score: {score} / {total} ({pct:.0f}%)",
            bg="#050510", fg="white", font=("Segoe UI", 22)
        ).pack(pady=10)
        tk.Label(
            self, text=message, bg="#050510", fg="#cceeff",
            font=("Segoe UI", 14)
        ).pack(pady=20)
        bar = tk.Frame(self, bg="#050510")
        bar.pack(pady=30)
        ttk.Button(bar, text="Play Again", command=on_replay).pack(
            side="left", padx=10
        )
        ttk.Button(bar, text="Main Menu", command=on_menu).pack(
            side="left", padx=10
        )


class ScoreView(tk.Frame):
    def __init__(self, master, history, on_back):
        super().__init__(master, bg="#101428")
        tk.Label(
            self, text="Score History", bg="#101428", fg="#7fd4ff",
            font=("Segoe UI", 24, "bold")
        ).pack(pady=20)
        tree = ttk.Treeview(
            self, columns=("score", "total", "date"), show="headings"
        )
        tree.heading("score", text="Player")
        tree.heading("total", text="Score")
        tree.heading("date", text="Date")
        tree.column("score", anchor="center", width=180)
        tree.column("total", anchor="center", width=140)
        tree.column("date", anchor="center", width=220)
        tree.pack(fill="both", expand=True, padx=30, pady=10)
        for row in history:
            tree.insert(
                "", "end",
                values=(row["username"], f"{row['score']}/{row['total']}",
                        row["played_at"]),
            )
        ttk.Button(self, text="Back", command=on_back).pack(pady=16)


class HelpView(tk.Frame):
    def __init__(self, master, on_back):
        super().__init__(master, bg="#101428")
        tk.Label(
            self, text="How to Play", bg="#101428", fg="#7fd4ff",
            font=("Segoe UI", 24, "bold")
        ).pack(pady=20)
        help_text = (
            "Space Fractions presents a series of fraction questions.\n\n"
            "• Read the question and choose one of the four options.\n"
            "• Each correct answer earns 1 point.\n"
            "• You can Pause at any time and Resume later.\n"
            "• Your final score is shown in the ending scene.\n\n"
            "Admins can sign in to add, edit or remove questions."
        )
        tk.Label(
            self, text=help_text, bg="#101428", fg="#cceeff",
            font=("Segoe UI", 13), justify="left"
        ).pack(padx=60, pady=10)
        ttk.Button(self, text="Back", command=on_back).pack(pady=16)


class AdminView(tk.Frame):
    """Manage questions: add / edit / delete."""

    def __init__(self, master: App, on_back):
        super().__init__(master, bg="#101428")
        self.app = master
        self.repo = master.question_repo
        tk.Label(
            self, text="Question Bank (Admin)", bg="#101428", fg="#7fd4ff",
            font=("Segoe UI", 22, "bold")
        ).pack(pady=16)
        self.tree = ttk.Treeview(
            self, columns=("prompt", "correct"), show="headings"
        )
        self.tree.heading("prompt", text="Prompt")
        self.tree.heading("correct", text="Answer")
        self.tree.column("prompt", width=520)
        self.tree.column("correct", width=120, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=30, pady=10)
        self._reload()
        bar = tk.Frame(self, bg="#101428")
        bar.pack(pady=14)
        ttk.Button(bar, text="Add", command=self._add).pack(side="left", padx=8)
        ttk.Button(bar, text="Edit", command=self._edit).pack(side="left", padx=8)
        ttk.Button(bar, text="Delete", command=self._delete).pack(
            side="left", padx=8
        )
        ttk.Button(bar, text="Back", command=on_back).pack(side="left", padx=8)

    def _reload(self):
        self.tree.delete(*self.tree.get_children())
        self._questions = self.repo.all()
        for q in self._questions:
            self.tree.insert("", "end", iid=q.id, values=(q.prompt, q.options[q.correct_index]))

    def _selected(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _add(self):
        prompt = simpledialog.askstring("Add question", "Prompt:", parent=self)
        if not prompt:
            return
        options = []
        for i in range(4):
            opt = simpledialog.askstring(
                "Add question", f"Option {i + 1}:", parent=self
            )
            if opt is None:
                return
            options.append(opt)
        correct = simpledialog.askstring(
            "Add question", "Correct answer (must match an option):", parent=self
        )
        if correct is None:
            return
        if correct not in options:
            messagebox.showerror("Error", "Correct answer must match an option.")
            return
        from .models import Question

        self.repo.add(Question(prompt, options, options.index(correct)))
        self._reload()

    def _edit(self):
        qid = self._selected()
        if not qid:
            messagebox.showinfo("Edit", "Select a question first.")
            return
        q = self.repo.get(qid)
        prompt = simpledialog.askstring(
            "Edit question", "Prompt:", initialvalue=q.prompt, parent=self
        )
        if prompt is None:
            return
        options = []
        for i, old in enumerate(q.options):
            opt = simpledialog.askstring(
                "Edit question", f"Option {i + 1}:", initialvalue=old, parent=self
            )
            if opt is None:
                return
            options.append(opt)
        correct = simpledialog.askstring(
            "Edit question", "Correct answer:",
            initialvalue=q.options[q.correct_index], parent=self
        )
        if correct not in options:
            messagebox.showerror("Error", "Correct answer must match an option.")
            return
        q.prompt = prompt
        q.options = options
        q.correct_index = options.index(correct)
        self.repo.update(q)
        self._reload()

    def _delete(self):
        qid = self._selected()
        if not qid:
            messagebox.showinfo("Delete", "Select a question first.")
            return
        if messagebox.askyesno("Delete", "Delete this question?"):
            self.repo.delete(qid)
            self._reload()
