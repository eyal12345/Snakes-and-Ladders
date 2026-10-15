"""Difficulty class: the game's difficulty levels."""

from enum import Enum

from exceptions import InvalidDifficultyError

# How a roll that would pass the last square is handled.
FINISH_ANY = "any"        # reaching or passing the last square wins
FINISH_EXACT = "exact"    # exact roll needed; otherwise the player stays put
FINISH_BOUNCE = "bounce"  # exact roll needed; extra steps bounce back from the last square


class Difficulty(Enum):
    """Each level sets how many snakes/ladders the board gets and the finishing rule."""

    EASY = ("Easy", 5, 10, FINISH_ANY)
    MEDIUM = ("Medium", 8, 8, FINISH_EXACT)
    HARD = ("Hard", 12, 5, FINISH_BOUNCE)

    def __init__(self, label, snakes, ladders, finish_rule):
        self.label = label
        self.snakes = snakes
        self.ladders = ladders
        self.finish_rule = finish_rule

    @property
    def description(self):
        finish = {
            FINISH_ANY: "any roll reaching 100 wins",
            FINISH_EXACT: "exact roll to 100, else stay",
            FINISH_BOUNCE: "exact roll to 100, else bounce back",
        }[self.finish_rule]
        return f"{self.snakes} snakes, {self.ladders} ladders, {finish}"

    @classmethod
    def from_label(cls, label):
        """Return the level with the given label (case-insensitive)."""
        for level in cls:
            if isinstance(label, str) and level.label.casefold() == label.strip().casefold():
                return level
        raise InvalidDifficultyError(
            f"Unknown difficulty {label!r}; choose from {', '.join(level.label for level in cls)}."
        )
