"""Space Fractions Tkinter application.

UI flow:
    intro -> main menu (Play / View Score / Help / Admin)
    game screen (series of fraction questions) -> ending scene (score + feedback)
"""

import random
import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import List, Optional

from ..game.game import Game
from ..game.state import GameState
from ..game.question import Question
from ..game.fractions import make_fraction_question, check_fraction_answer
from ..persistence.repository import Repository


class SpaceFractionsApp:
    """Root Tk application orchestrating all screens."""

    def __init__(self, repository: Optional[Repository] = None):
        self.repository = repository or Repository()
        self.root = tk.Tk()
        self.root.title("Space Fractions")
        self.root.geometry("760x560")
        self.root.resizable(False, False)

        self.current_user = None  # User object once logged in
        self.current_game: Optional[Game] = None
        self.game_frame_vars = {}

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._show_intro()

    # ---- screen helpers ---------------------------------------------------

    def _clear(self) -> None:
        for child in self.root.winfo_children():
            child.destroy()

    def _frame(self) -> tk.Frame:
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(fill="both", expand=True)
        return frame

    def _show_intro(self) -> None:
        """Introductory movie substitute: an animated welcome frame."""
        self._clear()
        frame = self._frame()

        title = tk.Label(
            frame,
            text="Space Fractions",
            font=("Helvetica", 42, "bold"),
            fg="#4a4ae0",
        )
        title.pack(pady=(60, 10))

        subtitle = tk.Label(
            frame,
            text="Blast through the fraction galaxy!",
            font=("Helvetica", 16),
        )
        subtitle.pack(pady=(0, 40))

        banner = tk.Label(
            frame,
            text="\u2726  \u2b50  \u2726  \u2b50  \u2726",
            font=("Helvetica", 28),
        )
        banner.pack()

        countdown = {"n": 3}
        self._flash_counter(frame, countdown)

    def _flash_counter(self, parent: tk.Widget, counter: dict) -> None:
        """Simple frame-based 'movie' animation before the main menu."""
        label = None

        def tick():
            nonlocal label
            if counter["n"] <= 0:
                self._show_menu()
                return
            if label is not None:
                label.destroy()
            label = tk.Label(
                parent,
                text=f"Loading... {counter['n']}",
                font=("Helvetica", 14),
            )
            label.pack(pady=10)
            counter["n"] -= 1
            self.root.after(700, tick)

        tick()

    def _show_menu(self) -> None:
        self._clear()
        frame = self._frame()

        tk.Label(
            frame,
            text="Main Menu",
            font=("Helvetica", 28, "bold"),
        ).pack(pady=(20, 30))

        buttons = [
            ("Play Game", self._show_login_for_game),
            ("View Score", self._show_login_for_score),
            ("View Help", self._show_help),
            ("Admin", self._show_admin),
        ]
        for text, command in buttons:
            tk.Button(
                frame,
                text=text,
                width=24,
                font=("Helvetica", 13),
                command=command,
            ).pack(pady=6)

        tk.Button(
            frame,
            text="Quit",
            width=24,
            command=self._on_close,
        ).pack(pady=(24, 0))

    # ---- authentication ---------------------------------------------------

    def _prompt_username(self) -> Optional[str]:
        return simpledialog.askstring(
            "Login", "Enter your username:", parent=self.root
        )

    def _prompt_password(self) -> Optional[str]:
        return simpledialog.askstring(
            "Login", "Enter your password:", parent=self.root, show="*"
        )

    def _login(self) -> bool:
        username = self._prompt_username()
        if not username:
            return False
        user = self.repository.get_user(username.strip())
        if user is None:
            # First-time user: register
            password = simpledialog.askstring(
                "Register",
                f"New user '{username}'. Set a password:",
                parent=self.root,
                show="*",
            )
            if not password:
                return False
            user = self.repository.create_user(username.strip(), password)
            messagebox.showinfo("Welcome", f"Account created for {user.username}.")
            self.current_user = user
            return True
        password = self._prompt_password()
        if password and user.verify_password(password):
            self.current_user = user
            return True
        if password:
            messagebox.showerror("Login Failed", "Incorrect password.")
        return False

    def _show_login_for_game(self) -> None:
        if self._login():
            self._start_game()

    def _show_login_for_score(self) -> None:
        if self._login():
            self._show_score_screen()

    # ---- game screen ------------------------------------------------------

    def _start_game(self) -> None:
        self._clear()
        frame = self._frame()
        questions = self._pick_questions()
        game = Game(id=f"g-{random.randint(1, 10**9)}", questions=questions)
        game.start()
        self.current_game = game
        self._build_game_frame(frame)
        self._render_question()

    def _pick_questions(self) -> List[Question]:
        all_questions = self.repository.get_questions()
        if not all_questions:
            return [make_fraction_question(i) for i in range(1, 6)]
        random.shuffle(all_questions)
        return all_questions[:5]

    def _build_game_frame(self, frame: tk.Frame) -> None:
        top = tk.Frame(frame)
        top.pack(fill="x")

        self.game_frame_vars["score_label"] = tk.Label(
            top, text="Score: 0", font=("Helvetica", 14, "bold")
        )
        self.game_frame_vars["score_label"].pack(side="left")

        self.game_frame_vars["progress_label"] = tk.Label(
            top, text="", font=("Helvetica", 12)
        )
        self.game_frame_vars["progress_label"].pack(side="right")

        self.game_frame_vars["prompt_label"] = tk.Label(
            frame, text="", font=("Helvetica", 20, "bold"), wraplength=600
        )
        self.game_frame_vars["prompt_label"].pack(pady=(40, 20))

        self.game_frame_vars["options_frame"] = tk.Frame(frame)
        self.game_frame_vars["options_frame"].pack()

        self.game_frame_vars["answer_var"] = tk.StringVar(value="")

        bottom = tk.Frame(frame)
        bottom.pack(side="bottom", pady=20)

        self.game_frame_vars["pause_button"] = tk.Button(
            bottom, text="Pause", width=10, command=self._toggle_pause
        )
        self.game_frame_vars["pause_button"].pack(side="left", padx=10)

        self.game_frame_vars["feedback_label"] = tk.Label(
            frame, text="", font=("Helvetica", 13), fg="#338833"
        )
        self.game_frame_vars["feedback_label"].pack(pady=10)

    def _render_question(self) -> None:
        game = self.current_game
        question = game.current_question()

        if self.game_frame_vars.get("options_frame") is None:
            return

        self.game_frame_vars["score_label"].config(text=f"Score: {game.score}")
        self.game_frame_vars["progress_label"].config(
            text=f"Question {game.current_index + 1} of {game.total_questions}"
        )

        if question is None or game.is_finished:
            self._finish_game()
            return

        self.game_frame_vars["prompt_label"].config(text=question.getPrompt())

        options_frame = self.game_frame_vars["options_frame"]
        for child in options_frame.winfo_children():
            child.destroy()

        for option in question.getOptions():
            tk.Radiobutton(
                options_frame,
                text=option,
                variable=self.game_frame_vars["answer_var"],
                value=option,
                font=("Helvetica", 14),
                anchor="w",
                width=24,
            ).pack(anchor="w", pady=2)

        self.game_frame_vars["submit_button"] = tk.Button(
            options_frame,
            text="Submit",
            width=14,
            command=self._submit_answer,
        )
        self.game_frame_vars["submit_button"].pack(pady=12)

        self.game_frame_vars["feedback_label"].config(text="")

    def _submit_answer(self) -> None:
        game = self.current_game
        question = game.current_question()
        if question is None:
            return
        answer = self.game_frame_vars["answer_var"].get()
        if not answer:
            messagebox.showinfo("No answer", "Please select an answer.")
            return

        correct = check_fraction_answer(question, answer)
        if correct:
            self.game_frame_vars["feedback_label"].config(
                text="Correct!", fg="#228822"
            )
        else:
            self.game_frame_vars["feedback_label"].config(
                text=f"Not quite. Correct answer: {question.correct_answer}",
                fg="#aa2222",
            )
        game.submit_answer(answer)
        self.game_frame_vars["answer_var"].set("")
        self.root.after(900, self._render_question)

    def _toggle_pause(self) -> None:
        game = self.current_game
        if game.state is GameState.PLAYING:
            game.pause()
            self.game_frame_vars["pause_button"].config(text="Resume")
            self.game_frame_vars["prompt_label"].config(text="Game Paused")
            for child in self.game_frame_vars["options_frame"].winfo_children():
                child.destroy()
        elif game.state is GameState.PAUSED:
            game.resume()
            self.game_frame_vars["pause_button"].config(text="Pause")
            self._render_question()

    def _finish_game(self) -> None:
        """Ending scene showing the final score and feedback."""
        self._clear()
        frame = self._frame()
        game = self.current_game

        tk.Label(
            frame, text="Game Over", font=("Helvetica", 30, "bold"), fg="#4a4ae0"
        ).pack(pady=(40, 10))

        score = game.viewScore()
        total = game.total_questions
        tk.Label(
            frame,
            text=f"Your score: {score} / {total}",
            font=("Helvetica", 22),
        ).pack(pady=10)

        feedback = self._score_feedback(score, total)
        tk.Label(
            frame, text=feedback, font=("Helvetica", 14), wraplength=500
        ).pack(pady=10)

        # Persist the result for durability (ASR-1).
        user_id = self.current_user.id if self.current_user else "guest"
        self.repository.save_game_result(
            game.id, user_id, score, total, game.state
        )

        tk.Button(
            frame, text="Back to Menu", width=18, command=self._show_menu
        ).pack(pady=30)

    def _score_feedback(self, score: int, total: int) -> str:
        if total == 0:
            return "No questions were answered."
        ratio = score / total
        if ratio == 1.0:
            return "Perfect score! You're a fraction champion! \u2b50"
        if ratio >= 0.8:
            return "Great job! Nearly perfect. \U0001f680"
        if ratio >= 0.6:
            return "Good work! Keep practicing to reach the stars."
        if ratio >= 0.4:
            return "Not bad. A bit more practice will boost your score."
        return "Keep trying! Every explorer starts somewhere."

    # ---- score screen -----------------------------------------------------

    def _show_score_screen(self) -> None:
        self._clear()
        frame = self._frame()
        user = self.current_user

        tk.Label(
            frame, text="Your Score", font=("Helvetica", 26, "bold")
        ).pack(pady=(30, 20))

        best = self.repository.get_best_score(user.id)
        tk.Label(
            frame,
            text=f"Best score: {best}",
            font=("Helvetica", 18),
        ).pack(pady=10)

        tk.Button(
            frame, text="Back to Menu", width=18, command=self._show_menu
        ).pack(pady=30)

    # ---- help screen ------------------------------------------------------

    def _show_help(self) -> None:
        self._clear()
        frame = self._frame()
        tk.Label(
            frame, text="Help", font=("Helvetica", 26, "bold")
        ).pack(pady=(30, 20))

        help_text = (
            "Space Fractions is a game where you add fractions together.\n\n"
            "- Read the fraction question shown on screen.\n"
            "- Select one of the answer options.\n"
            "- Click Submit to check your answer.\n"
            "- Use Pause/Resume to take a break.\n"
            "- After all questions, you'll see your score and feedback.\n\n"
            "Tip: 1/2 + 1/4 = 3/4, and 1/2 + 1/2 = 1."
        )
        tk.Label(
            frame, text=help_text, font=("Helvetica", 13), justify="left"
        ).pack(anchor="w", pady=10)

        tk.Button(
            frame, text="Back to Menu", width=18, command=self._show_menu
        ).pack(pady=20)

    # ---- admin screen -----------------------------------------------------

    def _show_admin(self) -> None:
        self._clear()
        frame = self._frame()
        tk.Label(
            frame, text="Admin - Manage Questions", font=("Helvetica", 20, "bold")
        ).pack(pady=(20, 15))

        self.game_frame_vars["admin_list"] = tk.Listbox(
            frame, height=10, width=70, font=("Helvetica", 12)
        )
        self.game_frame_vars["admin_list"].pack(pady=10)
        self._refresh_admin_list()

        btn_frame = tk.Frame(frame)
        btn_frame.pack(pady=6)

        tk.Button(btn_frame, text="Add", width=10, command=self._admin_add).pack(
            side="left", padx=5
        )
        tk.Button(btn_frame, text="Delete", width=10, command=self._admin_delete).pack(
            side="left", padx=5
        )
        tk.Button(
            btn_frame, text="Back to Menu", width=14, command=self._show_menu
        ).pack(side="left", padx=5)

    def _refresh_admin_list(self) -> None:
        listbox = self.game_frame_vars.get("admin_list")
        if listbox is None:
            return
        listbox.delete(0, tk.END)
        for q in self.repository.get_questions():
            listbox.insert(tk.END, f"{q.id}: {q.prompt}  (ans: {q.correct_answer})")

    def _admin_add(self) -> None:
        prompt = simpledialog.askstring(
            "Add Question", "Enter the fraction question prompt:", parent=self.root
        )
        if not prompt:
            return
        correct = simpledialog.askstring(
            "Add Question", "Enter the correct answer (e.g. 3/4):", parent=self.root
        )
        if not correct:
            return
        options = [correct]
        options_str = simpledialog.askstring(
            "Add Question",
            "Enter extra options separated by commas (optional):",
            parent=self.root,
            initialvalue="1/2,1/3,1/4",
        )
        if options_str:
            for opt in options_str.split(","):
                opt = opt.strip()
                if opt and opt not in options:
                    options.append(opt)
        question = Question(
            id=f"q-{random.randint(1, 10**9)}",
            prompt=prompt.strip(),
            options=options,
            correct_answer=correct.strip(),
        )
        self.repository.save_question(question)
        self._refresh_admin_list()
        messagebox.showinfo("Saved", "Question saved.")

    def _admin_delete(self) -> None:
        listbox = self.game_frame_vars.get("admin_list")
        if listbox is None:
            return
        selection = listbox.curselection()
        if not selection:
            messagebox.showinfo("Delete", "Select a question to delete.")
            return
        questions = self.repository.get_questions()
        question = questions[selection[0]]
        self.repository.delete_question(question.id)
        self._refresh_admin_list()
        messagebox.showinfo("Deleted", f"Deleted {question.id}.")

    # ---- lifecycle --------------------------------------------------------

    def run(self) -> None:
        self.root.mainloop()

    def _on_close(self) -> None:
        self.repository.close()
        self.root.destroy()
