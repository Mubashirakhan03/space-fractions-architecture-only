"""Tkinter desktop UI for Space Fractions.

Scenes (the spec's implied features):
    1. Introductory movie (animated welcome)
    2. Main menu (Play / View Score / Help / Admin)
    3. Game scene (series of fraction questions, pause/resume)
    4. Ending scene (feedback + final score)
"""

from __future__ import annotations

import random
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import List, Optional

from . import APP_NAME
from .models import Game, Question, User
from .question_component import QuestionComponent, seed_questions
from .user_component import UserComponent
from .game_component import GameComponent


class SpaceFractionsApp:
    """Root application that swaps between scene frames."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("760x520")
        self.root.minsize(560, 420)

        self.questions_component = QuestionComponent()
        seed_questions(self.questions_component)
        self.users_component = UserComponent()
        self.game_component = GameComponent()

        self.current_user: Optional[User] = None
        self.game: Optional[Game] = None

        self.container = tk.Frame(self.root)
        self.container.pack(fill="both", expand=True)

        self.frames: dict = {}
        self.show_scene("movie")

    def show_scene(self, name: str, **kwargs) -> None:
        for widget in self.container.winfo_children():
            widget.destroy()
        if name == "movie":
            self.frames[name] = MovieScene(self.container, self, self._after_movie)
        elif name == "menu":
            self.frames[name] = MenuScene(self.container, self)
        elif name == "game":
            self.frames[name] = GameScene(self.container, self)
        elif name == "ending":
            self.frames[name] = EndingScene(self.container, self, kwargs.get("feedback"))
        elif name == "help":
            self.frames[name] = HelpScene(self.container, self)
        elif name == "admin":
            self.frames[name] = AdminScene(self.container, self)
        else:
            raise ValueError(f"Unknown scene: {name!r}")
        self.frames[name].pack(fill="both", expand=True)

    def _after_movie(self) -> None:
        self.show_scene("menu")

    def start(self) -> None:
        self.root.mainloop()


class BaseScene(tk.Frame):
    def __init__(self, parent, app: SpaceFractionsApp):
        super().__init__(parent)
        self.app = app


class MovieScene(BaseScene):
    """Introductory movie — animated starfield welcome."""

    def __init__(self, parent, app, on_done):
        super().__init__(parent, app)
        self.on_done = on_done
        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.stars: List[tuple] = []
        self._spawn_stars(120)
        self.title_id = self.canvas.create_text(
            380, 220, text="SPACE FRACTIONS", fill="white", font=("Arial", 36, "bold")
        )
        self.sub_id = self.canvas.create_text(
            380, 280,
            text="An intergalactic fraction adventure",
            fill="#aaddff", font=("Arial", 16),
        )
        self.frame = 0
        self._animate()

    def _spawn_stars(self, count: int) -> None:
        for _ in range(count):
            x = random.randint(0, 760)
            y = random.randint(0, 520)
            speed = random.randint(1, 5)
            oval = self.canvas.create_oval(x, y, x + 2, y + 2, fill="white")
            self.stars.append((oval, speed))

    def _animate(self) -> None:
        self.frame += 1
        for oval, speed in self.stars:
            self.canvas.move(oval, 0, speed)
            x0, y0, x1, y1 = self.canvas.coords(oval)
            if y0 > 520:
                self.canvas.coords(oval, x0, -2, x0 + 2, 0)
        pulse = 0.5 + 0.5 * abs(1 - (self.frame % 40) / 20)
        color = "#%02x%02x%02x" % (
            int(255 * pulse), int(255 * pulse), 255
        )
        self.canvas.itemconfig(self.title_id, fill=color)
        if self.frame < 180:  # ~3 seconds
            self.after(30, self._animate)
        else:
            self.after(200, self._finish)

    def _finish(self) -> None:
        self.on_done()


class MenuScene(BaseScene):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        tk.Label(
            self, text=APP_NAME, font=("Arial", 28, "bold")
        ).pack(pady=30)
        tk.Label(self, text="— Main Menu —", font=("Arial", 14)).pack(pady=5)

        if app.current_user is not None:
            tk.Label(
                self, text=f"Signed in as: {app.current_user.username}",
                font=("Arial", 12, "italic"),
            ).pack(pady=5)

        ttk.Button(
            self, text="Play Game", command=self.play_game, width=24
        ).pack(pady=8)
        ttk.Button(
            self, text="View Score", command=self.view_score, width=24
        ).pack(pady=8)
        ttk.Button(
            self, text="Help", command=lambda: app.show_scene("help"), width=24
        ).pack(pady=8)
        ttk.Button(
            self, text="Admin (Update Questions)",
            command=lambda: app.show_scene("admin"), width=24,
        ).pack(pady=8)
        ttk.Button(
            self, text="Quit", command=app.root.destroy, width=24
        ).pack(pady=20)

    def play_game(self) -> None:
        questions = self.app.questions_component.list_questions()
        if not questions:
            messagebox.showwarning(APP_NAME, "No questions available.")
            return
        sample = random.sample(questions, min(len(questions), 5))
        self.app.game = self.app.game_component.new_game(
            self.app.current_user, sample
        )
        self.app.show_scene("game")

    def view_score(self) -> None:
        if self.app.game is not None:
            messagebox.showinfo(
                APP_NAME,
                f"Last game score: {self.app.game.viewScore()}",
            )
        else:
            messagebox.showinfo(APP_NAME, "No game played yet.")


class GameScene(BaseScene):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.game = app.game
        self.sm = None  # state machine not strictly required here; reuse game.state

        self.prompt_label = tk.Label(
            self, text="", font=("Arial", 18), wraplength=600, justify="center"
        )
        self.prompt_label.pack(pady=40)

        self.options_var = tk.StringVar(value="")
        self.option_buttons: List[ttk.Radiobutton] = []
        self.options_frame = tk.Frame(self)
        self.options_frame.pack(pady=10)

        self.entry = tk.Entry(self, font=("Arial", 14), justify="center")
        self.entry.pack(pady=10)
        self.entry.bind("<Return>", lambda e: self.submit())

        self.feedback_label = tk.Label(
            self, text="", font=("Arial", 14, "bold")
        )
        self.feedback_label.pack(pady=10)

        self.score_label = tk.Label(self, text="", font=("Arial", 12))
        self.score_label.pack(pady=5)

        controls = tk.Frame(self)
        controls.pack(pady=20)
        ttk.Button(controls, text="Submit", command=self.submit).pack(
            side="left", padx=10
        )
        ttk.Button(controls, text="Pause", command=self.pause).pack(
            side="left", padx=10
        )
        ttk.Button(
            controls, text="Back to Menu", command=self._to_menu
        ).pack(side="left", padx=10)

        self.render()

    def render(self) -> None:
        if self.game is None:
            return
        if self.game.state == "GameOver" or self.game.current_index >= len(
            self.game.questions
        ):
            self._finish()
            return
        question = self.game.questions[self.game.current_index]
        self.prompt_label.config(
            text=f"Question {self.game.current_index + 1} of "
            f"{len(self.game.questions)}:\n{question.getPrompt()}"
        )
        for b in self.option_buttons:
            b.destroy()
        self.option_buttons.clear()
        self.options_var.set("")
        for idx, opt in enumerate(question.getOptions()):
            rb = ttk.Radiobutton(
                self.options_frame, text=opt, variable=self.options_var, value=opt
            )
            rb.pack(anchor="w")
            self.option_buttons.append(rb)
        self.entry.delete(0, tk.END)
        self.feedback_label.config(text="")
        self.score_label.config(text=f"Score: {self.game.viewScore()}")

    def submit(self) -> None:
        if self.game is None or self.game.state == "Paused":
            return
        answer = self.options_var.get() or self.entry.get().strip()
        if not answer:
            return
        correct = self.app.game_component.answer(self.game, answer)
        self.feedback_label.config(
            text="Correct! ✨" if correct else "Incorrect 🚀",
            fg="green" if correct else "red",
        )
        self.score_label.config(text=f"Score: {self.game.viewScore()}")
        if self.game.state == "GameOver":
            self.after(900, self._finish)
        else:
            self.after(900, self.render)

    def pause(self) -> None:
        if self.game is None:
            return
        if self.game.state == "Playing":
            self.game.state = "Paused"
            self.prompt_label.config(text="Paused — press Resume to continue")
        elif self.game.state == "Paused":
            self.game.state = "Playing"
            self.render()

    def _finish(self) -> None:
        score = self.game.viewScore() if self.game else 0
        total = len(self.game.questions) if self.game else 0
        if score == total:
            feedback = "Out of this world! Perfect score! 🌟"
        elif score >= total * 0.6:
            feedback = "Great job, cadet! Almost home! 🛸"
        else:
            feedback = "Keep practicing — you will blast off soon! 🚀"
        self.app.game_component.save(self.game, self.app.current_user)
        self.app.show_scene("ending", feedback=feedback)

    def _to_menu(self) -> None:
        self.app.show_scene("menu")


class EndingScene(BaseScene):
    def __init__(self, parent, app, feedback: str = ""):
        super().__init__(parent, app)
        game = app.game
        score = game.viewScore() if game else 0
        total = len(game.questions) if game else 0
        self.canvas = tk.Canvas(self, bg="#050510", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(
            380, 120, text=feedback, fill="#ffd700",
            font=("Arial", 18, "bold"), justify="center", width=600,
        )
        self.canvas.create_text(
            380, 220, text=f"Final Score: {score} / {total}",
            fill="white", font=("Arial", 28, "bold"),
        )
        pct = (score / total * 100) if total else 0
        self.canvas.create_text(
            380, 280, text=f"{pct:.0f}% accuracy",
            fill="#aaddff", font=("Arial", 16),
        )
        ttk.Button(
            self, text="Back to Menu", command=lambda: app.show_scene("menu")
        ).place(relx=0.5, rely=0.75, anchor="center")


class HelpScene(BaseScene):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        tk.Label(
            self, text="How to Play", font=("Arial", 22, "bold")
        ).pack(pady=20)
        text = (
            "1. Select Play Game from the menu.\n"
            "2. Each question shows a fraction problem.\n"
            "3. Choose an option, or type your answer as a fraction\n"
            "   (e.g. 3/4), a decimal (0.75), or '3 4'.\n"
            "4. Correct answers earn points.\n"
            "5. Reach the end to see your score and feedback.\n\n"
            "You can Pause at any time, then Resume."
        )
        tk.Label(
            self, text=text, font=("Arial", 13), justify="left"
        ).pack(pady=10)
        ttk.Button(
            self, text="Back", command=lambda: app.show_scene("menu")
        ).pack(pady=20)


class AdminScene(BaseScene):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        tk.Label(
            self, text="Admin — Update Questions", font=("Arial", 20, "bold")
        ).pack(pady=20)

        tk.Label(self, text="Prompt:").pack()
        self.prompt_var = tk.StringVar()
        tk.Entry(self, textvariable=self.prompt_var, width=50).pack(pady=5)

        tk.Label(self, text="Options (comma-separated):").pack()
        self.options_var = tk.StringVar()
        tk.Entry(self, textvariable=self.options_var, width=50).pack(pady=5)

        tk.Label(self, text="Answer:").pack()
        self.answer_var = tk.StringVar()
        tk.Entry(self, textvariable=self.answer_var, width=50).pack(pady=5)

        ttk.Button(
            self, text="Add Question", command=self.add_question
        ).pack(pady=15)

        self.listbox = tk.Listbox(self, width=60, height=8)
        self.listbox.pack(pady=10)
        self.refresh()

        ttk.Button(
            self, text="Delete Selected", command=self.delete_selected
        ).pack(pady=5)
        ttk.Button(
            self, text="Back", command=lambda: app.show_scene("menu")
        ).pack(pady=10)

    def add_question(self) -> None:
        prompt = self.prompt_var.get().strip()
        options = [
            o.strip() for o in self.options_var.get().split(",") if o.strip()
        ]
        answer = self.answer_var.get().strip()
        if not prompt or not answer:
            messagebox.showwarning(APP_NAME, "Prompt and answer are required.")
            return
        self.app.questions_component.add_question(prompt, options, answer)
        self.prompt_var.set("")
        self.options_var.set("")
        self.answer_var.set("")
        self.refresh()

    def delete_selected(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        qid = self.listbox.get(selection[0]).split("|")[0].strip()
        self.app.questions_component.delete_question(qid)
        self.refresh()

    def refresh(self) -> None:
        self.listbox.delete(0, tk.END)
        for q in self.app.questions_component.list_questions():
            self.listbox.insert(tk.END, f"{q.id} | {q.prompt} | ans={q.answer}")
