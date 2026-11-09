"""Explicit finite state machine for the game.

States: Playing, Paused, GameOver.
Transitions (from the architecture spec):
    [*]   -> Playing   (start)
    Playing -> Paused  (pause)
    Paused  -> Playing (resume)
    Playing -> GameOver (gameOver)
    Paused  -> GameOver (gameOver)  -- allowed so pause doesn't deadlock
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Set, Tuple


@dataclass(frozen=True)
class Transition:
    from_state: str
    to_state: str
    trigger: str


class GameStateMachine:
    """Tracks the current state and validates transitions."""

    STATES: Tuple[str, ...] = ("Playing", "Paused", "GameOver")
    TRANSITIONS: Tuple[Transition, ...] = (
        Transition("*", "Playing", "start"),
        Transition("Playing", "Paused", "pause"),
        Transition("Paused", "Playing", "resume"),
        Transition("Playing", "GameOver", "gameOver"),
        Transition("Paused", "GameOver", "gameOver"),
    )

    def __init__(self, initial_state: str = "Playing") -> None:
        if initial_state not in self.STATES:
            raise ValueError(f"Unknown state: {initial_state!r}")
        self._state: str = initial_state

    @property
    def state(self) -> str:
        return self._state

    def can(self, trigger: str) -> bool:
        """Return True if `trigger` is legal from the current state."""
        for t in self.TRANSITIONS:
            if t.trigger == trigger and t.from_state in (self._state, "*"):
                return True
        return False

    def trigger(self, trigger: str) -> str:
        """Apply a trigger, returning the new state (raises on illegal calls)."""
        for t in self.TRANSITIONS:
            if t.trigger == trigger and t.from_state in (self._state, "*"):
                self._state = t.to_state
                return self._state
        raise ValueError(
            f"Illegal transition {trigger!r} from state {self._state!r}"
        )

    def pause(self) -> str:
        return self.trigger("pause")

    def resume(self) -> str:
        return self.trigger("resume")

    def game_over(self) -> str:
        return self.trigger("gameOver")
