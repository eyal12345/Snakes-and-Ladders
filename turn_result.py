"""TurnResult class: the outcome of a single turn."""

from dataclasses import dataclass
from typing import Optional

from player import Player


@dataclass(frozen=True)
class TurnResult:
    player: Player
    roll: int
    start: int          # square before the roll
    landed: int         # square reached by the dice (before snake/ladder)
    end: int            # final square after snake/ladder
    event: Optional[str]  # Board.SNAKE, Board.LADDER or None
    overshoot: bool     # roll would pass the last square
    is_winner: bool
    bounced: bool = False  # overshoot steps were walked back from the last square (Hard)

    @property
    def steps(self):
        """Squares walked by the dice this turn (snake/ladder jumps not counted)."""
        if self.bounced:
            return self.roll  # up to the last square and back down
        return self.landed - self.start  # 0 when an inexact roll leaves the token in place
