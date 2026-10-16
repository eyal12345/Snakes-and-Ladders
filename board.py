"""Board class: squares, snakes and ladders."""

import random

from exceptions import InvalidBoardError, InvalidSquareError


class Board:
    """A board of squares 1..size with snakes (head -> tail) and ladders (bottom -> top)."""

    FIRST_SQUARE = 1
    SNAKE = "snake"
    LADDER = "ladder"

    def __init__(self, size=100, snakes=None, ladders=None):
        if not isinstance(size, int) or isinstance(size, bool) or size < 2:
            raise InvalidBoardError(f"Board size must be an integer >= 2, got {size!r}.")
        self._size = size
        self._snakes = dict(snakes or {})
        self._ladders = dict(ladders or {})
        self._validate()

    # ------------------------------------------------------------------ properties
    @property
    def size(self):
        return self._size

    @property
    def snakes(self):
        """A copy of the snakes mapping {head: tail}."""
        return dict(self._snakes)

    @property
    def ladders(self):
        """A copy of the ladders mapping {bottom: top}."""
        return dict(self._ladders)

    # ------------------------------------------------------------------ queries
    def check_square(self, square):
        """Raise InvalidSquareError if the square is not on the board."""
        if not isinstance(square, int) or isinstance(square, bool) or not (
            self.FIRST_SQUARE <= square <= self._size
        ):
            raise InvalidSquareError(square, self._size)

    def destination(self, square):
        """Return (final_square, event) after applying any snake or ladder on `square`.

        `event` is Board.SNAKE, Board.LADDER or None.
        """
        self.check_square(square)
        if square in self._snakes:
            return self._snakes[square], self.SNAKE
        if square in self._ladders:
            return self._ladders[square], self.LADDER
        return square, None

    # ------------------------------------------------------------------ validation
    def _validate(self):
        for head, tail in self._snakes.items():
            self.check_square(head)
            self.check_square(tail)
            if tail >= head:
                raise InvalidBoardError(f"Snake {head}->{tail} must go down.")
            if tail == self.FIRST_SQUARE:
                raise InvalidBoardError(f"Snake {head}->{tail} cannot slide down to the first square.")

        for bottom, top in self._ladders.items():
            self.check_square(bottom)
            self.check_square(top)
            if top <= bottom:
                raise InvalidBoardError(f"Ladder {bottom}->{top} must go up.")

        starts = set(self._snakes) | set(self._ladders)
        if set(self._snakes) & set(self._ladders):
            raise InvalidBoardError("A square cannot hold both a snake head and a ladder bottom.")
        if self.FIRST_SQUARE in starts or self._size in starts:
            raise InvalidBoardError("The first and last squares cannot start a snake or ladder.")

        ends = set(self._snakes.values()) | set(self._ladders.values())
        chained = starts & ends
        if chained:
            raise InvalidBoardError(f"Snakes/ladders cannot chain on squares {sorted(chained)}.")

    # ------------------------------------------------------------------ factory
    @classmethod
    def random(cls, size=100, num_snakes=8, num_ladders=8, rng=None, max_attempts=200):
        """Create a board with randomly placed snakes and ladders.

        Every snake/ladder spans at least one row (size // 10 squares) and no
        two of them share a square.
        """
        if num_snakes < 0 or num_ladders < 0:
            raise InvalidBoardError("Number of snakes and ladders cannot be negative.")
        rng = rng or random.Random()
        min_span = max(1, size // 10)

        for _ in range(max_attempts):
            try:
                snakes, ladders = cls._random_layout(size, num_snakes, num_ladders, min_span, rng)
                return cls(size, snakes, ladders)
            except InvalidBoardError:
                continue
        raise InvalidBoardError(
            f"Could not place {num_snakes} snakes and {num_ladders} ladders on a {size}-square board."
        )

    @staticmethod
    def _random_layout(size, num_snakes, num_ladders, min_span, rng):
        used = set()

        def pick(low, high):
            candidates = [n for n in range(low, high + 1) if n not in used]
            if not candidates:
                raise InvalidBoardError("No free square available.")
            choice = rng.choice(candidates)
            used.add(choice)
            return choice

        ladders = {}
        for _ in range(num_ladders):
            bottom = pick(2, size - 1 - min_span)
            ladders[bottom] = pick(bottom + min_span, size - 1)

        snakes = {}
        for _ in range(num_snakes):
            head = pick(2 + min_span, size - 1)
            snakes[head] = pick(2, head - min_span)

        return snakes, ladders
