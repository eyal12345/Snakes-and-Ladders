"""Player class."""

from exceptions import InvalidPlayerNameError, InvalidSquareError


class Player:
    """A human player with a name, a token color and a position on the board.

    Position 0 means the player has not entered the board yet.
    """

    START_POSITION = 0

    def __init__(self, name, color):
        self.name = name
        self.color = color
        self._position = self.START_POSITION

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if not isinstance(value, str) or not value.strip():
            raise InvalidPlayerNameError("Player name must be a non-empty string.")
        self._name = value.strip()

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Player color must be a non-empty string.")
        self._color = value

    @property
    def position(self):
        return self._position

    @property
    def is_computer(self):
        return False

    def move_to(self, square):
        """Place the player on the given square."""
        if not isinstance(square, int) or isinstance(square, bool) or square < self.START_POSITION:
            raise InvalidSquareError(square)
        self._position = square

    def reset(self):
        self._position = self.START_POSITION

    def __repr__(self):
        return (
            f"{type(self).__name__}(name={self._name!r}, color={self._color!r}, "
            f"position={self._position})"
        )
