"""ComputerPlayer class."""

from player import Player


class ComputerPlayer(Player):
    """A player whose turns are played automatically by the application.

    Computers are named "AI Rival" when there is one, "AI Rival 1",
    "AI Rival 2", ... when there are several, but can be renamed like any player.
    """

    NAME = "AI Rival"

    def __init__(self, color="Blue", name=NAME):
        super().__init__(name, color)

    @classmethod
    def names(cls, count):
        """The default names of `count` computer players in one match."""
        if count == 1:
            return [cls.NAME]
        return [f"{cls.NAME} {i + 1}" for i in range(count)]

    @property
    def is_computer(self):
        return True
