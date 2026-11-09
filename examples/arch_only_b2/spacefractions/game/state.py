"""Game state machine: Playing / Paused / GameOver."""

from enum import Enum, auto


class GameState(Enum):
    """Lifecycle states of a Game.

    Transitions:
        [*] -> Playing            (start)
        Playing -> Paused         (pause)
        Paused -> Playing         (resume)
        Playing -> GameOver       (gameOver)
    """

    PLAYING = auto()
    PAUSED = auto()
    GAMEOVER = auto()

    def __str__(self) -> str:
        return self.name
