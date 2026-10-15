"""Custom exceptions used across the Snakes and Ladders game."""


class SnakesAndLaddersError(Exception):
    """Base class for every error raised by the game."""


class InvalidPlayerCountError(SnakesAndLaddersError):
    """Raised when the requested number of players is out of range."""

    def __init__(self, count, minimum, maximum):
        super().__init__(
            f"Number of players must be between {minimum} and {maximum}, got {count!r}."
        )
        self.count = count
        self.minimum = minimum
        self.maximum = maximum


class InvalidSquareError(SnakesAndLaddersError):
    """Raised when a square number is not on the board."""

    def __init__(self, square, size=None):
        valid = f" (valid range 1-{size})" if size is not None else ""
        super().__init__(f"Square {square!r} is not a valid board position{valid}.")
        self.square = square
        self.size = size


class InvalidBoardError(SnakesAndLaddersError):
    """Raised when the snakes/ladders layout is not valid."""


class InvalidColorError(SnakesAndLaddersError):
    """Raised when a player color is unknown or used by more than one player."""


class InvalidPlayerNameError(SnakesAndLaddersError):
    """Raised when a player name is empty, too long or used by more than one player."""


class InvalidDifficultyError(SnakesAndLaddersError):
    """Raised when an unknown difficulty level is requested."""


class InvalidDiceError(SnakesAndLaddersError):
    """Raised when a dice is configured with an invalid number of sides."""


class MatchHistoryError(SnakesAndLaddersError):
    """Raised when a map cannot be saved to the match history."""


class GameOverError(SnakesAndLaddersError):
    """Raised when trying to play a turn after the game has finished."""
