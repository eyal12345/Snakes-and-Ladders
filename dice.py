"""Dice class."""

import random

from exceptions import InvalidDiceError


class Dice:
    """A single fair dice."""

    def __init__(self, sides=6, rng=None):
        if not isinstance(sides, int) or isinstance(sides, bool) or sides < 2:
            raise InvalidDiceError(f"A dice needs an integer number of sides >= 2, got {sides!r}.")
        self._sides = sides
        self._rng = rng or random.Random()
        self._last_value = None

    @property
    def sides(self):
        return self._sides

    @property
    def last_value(self):
        """The value of the most recent roll, or None if never rolled."""
        return self._last_value

    def roll(self):
        """Roll the dice and return a value between 1 and the number of sides."""
        self._last_value = self._rng.randint(1, self._sides)
        return self._last_value
