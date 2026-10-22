"""Game class: rules and turn management."""

import heapq

from board import Board
from computer_player import ComputerPlayer
from dice import Dice
from difficulty import FINISH_ANY, FINISH_EXACT, Difficulty
from exceptions import (
    GameOverError,
    InvalidColorError,
    InvalidDifficultyError,
    InvalidPlayerCountError,
    InvalidPlayerNameError,
    SnakesAndLaddersError,
)
from player import Player
from turn_result import TurnResult


class Game:
    """A Snakes and Ladders match for 2-4 participants (humans and/or computers) with one dice.

    Rules: players start off the board (square 0), move by the dice value,
    slide down snakes and climb ladders. The difficulty level decides how many
    snakes/ladders a random board gets and what happens when a roll would pass
    the last square (see difficulty.py).
    """

    MIN_PLAYERS = 2
    MAX_PLAYERS = 4
    MAX_NAME_LENGTH = 15
    # Available token colors: display name -> drawing color.
    COLORS = {
        "Red": "#e53935",
        "Blue": "#1e88e5",
        "Green": "#43a047",
        "Yellow": "#fdd835",
        "Purple": "#8e24aa",
        "Orange": "#fb8c00",
        "Pink": "#f06292",
        "Sky": "#4fc3f7",
        "Black": "#212121",
        "White": "#fafafa",
        "Brown": "#6d4c41",
        "Gray": "#9e9e9e",
    }
    # Colors dark enough to need light text drawn over them.
    DARK_COLORS = {"Black", "Brown", "Purple", "Blue"}

    def __init__(self, num_players, board=None, dice=None, player_names=None,
                 player_colors=None, computer_players=None, difficulty=Difficulty.MEDIUM):
        """
        num_players      -- total participants (2-4), computers included
        board            -- optional board; by default a random one sized by the difficulty
        player_names     -- optional list of names
        player_colors    -- optional list of color names from Game.COLORS, all different
        computer_players -- optional list of booleans: True marks a computer-controlled player
        difficulty       -- a Difficulty level (default Medium)
        """
        if not isinstance(difficulty, Difficulty):
            raise InvalidDifficultyError(f"Difficulty must be a Difficulty level, got {difficulty!r}.")
        if (
            not isinstance(num_players, int)
            or isinstance(num_players, bool)
            or not self.MIN_PLAYERS <= num_players <= self.MAX_PLAYERS
        ):
            raise InvalidPlayerCountError(num_players, self.MIN_PLAYERS, self.MAX_PLAYERS)

        names = list(player_names or [f"Player {i + 1}" for i in range(num_players)])
        colors = list(player_colors or list(self.COLORS)[:num_players])
        computers = list(computer_players or [False] * num_players)
        for label, values in (("names", names), ("colors", colors), ("computer flags", computers)):
            if len(values) != num_players:
                raise ValueError(f"Expected {num_players} player {label}, got {len(values)}.")
        self.validate_names(names)
        self.validate_colors(colors)

        self._difficulty = difficulty
        self._board = board or self.random_board(difficulty)
        self._dice = dice or Dice()
        self._players = [
            ComputerPlayer(color, name) if is_computer else Player(name, color)
            for name, color, is_computer in zip(names, colors, computers)
        ]
        self._turn_order = list(self._players)  # who plays when; `players` keeps its order
        self._current_index = 0
        self._winner = None
        self._history = []

    @staticmethod
    def random_board(difficulty, size=100):
        """Create a random board with the number of snakes/ladders of the given level."""
        return Board.random(size=size, num_snakes=difficulty.snakes, num_ladders=difficulty.ladders)

    @staticmethod
    def min_steps(board, difficulty, sides=6):
        """Fewest dice steps (as counted by TurnResult.steps) that can win on this board.

        Snake/ladder jumps are free; the finish rule of the level decides what an
        overshooting roll costs and where it leaves the token.
        """
        size = board.size
        best = {0: 0}
        queue = [(0, 0)]
        while queue:
            cost, square = heapq.heappop(queue)
            if square == size:
                return cost
            if cost > best.get(square, cost):
                continue
            for roll in range(1, sides + 1):
                target = square + roll
                if target > size:
                    if difficulty.finish_rule == FINISH_EXACT:
                        continue  # the token stays put: no progress
                    if difficulty.finish_rule == FINISH_ANY:
                        landed, steps = size, size - square
                    else:  # bounce back the extra steps
                        landed, steps = 2 * size - target, roll
                else:
                    landed, steps = target, roll
                end = board.destination(landed)[0]
                if cost + steps < best.get(end, float("inf")):
                    best[end] = cost + steps
                    heapq.heappush(queue, (cost + steps, end))
        return None  # unreachable (cannot happen on a valid board)

    @staticmethod
    def min_tosses(board, difficulty, sides=6):
        """Fewest dice tosses (turns) that can win on this board, under the level's finish rule."""
        size = board.size
        seen = {0}
        frontier = [0]
        tosses = 0
        while frontier:
            tosses += 1
            reached = []
            for square in frontier:
                for roll in range(1, sides + 1):
                    target = square + roll
                    if target > size:
                        if difficulty.finish_rule == FINISH_EXACT:
                            continue  # the token stays put: no progress
                        target = size if difficulty.finish_rule == FINISH_ANY else 2 * size - target
                    end = board.destination(target)[0]
                    if end == size:
                        return tosses
                    if end not in seen:
                        seen.add(end)
                        reached.append(end)
            frontier = reached
        return None  # unreachable (cannot happen on a valid board)

    # ------------------------------------------------------------------ names
    @classmethod
    def validate_names(cls, names):
        """Raise InvalidPlayerNameError if a name is empty, too long or used twice."""
        seen = set()
        for index, name in enumerate(names, start=1):
            if not isinstance(name, str) or not name.strip():
                raise InvalidPlayerNameError(f"Player {index} needs a name.")
            name = name.strip()
            if len(name) > cls.MAX_NAME_LENGTH:
                raise InvalidPlayerNameError(
                    f"Name {name!r} is too long (max {cls.MAX_NAME_LENGTH} characters)."
                )
            if name.casefold() in seen:
                raise InvalidPlayerNameError(f"Each player needs a different name: {name!r} used twice.")
            seen.add(name.casefold())

    def set_player_names(self, names):
        """Rename all players at once (allowed at any time during the game)."""
        names = list(names)
        if len(names) != len(self._players):
            raise InvalidPlayerNameError(f"Expected {len(self._players)} names, got {len(names)}.")
        self.validate_names(names)
        for player, name in zip(self._players, names):
            player.name = name

    # ------------------------------------------------------------------ colors
    @classmethod
    def validate_colors(cls, colors):
        """Raise InvalidColorError if a color is unknown or chosen twice."""
        for color in colors:
            if color not in cls.COLORS:
                raise InvalidColorError(
                    f"Unknown color {color!r}; choose from {', '.join(cls.COLORS)}."
                )
        duplicates = sorted({c for c in colors if colors.count(c) > 1})
        if duplicates:
            raise InvalidColorError(f"Each player needs a different color: {', '.join(duplicates)} used twice.")

    @classmethod
    def color_code(cls, color):
        """Return the drawing color for a color name."""
        try:
            return cls.COLORS[color]
        except KeyError:
            raise InvalidColorError(f"Unknown color {color!r}.") from None

    def set_player_colors(self, colors):
        """Change all players' colors at once (allowed at any time during the game)."""
        colors = list(colors)
        if len(colors) != len(self._players):
            raise InvalidColorError(f"Expected {len(self._players)} colors, got {len(colors)}.")
        self.validate_colors(colors)
        for player, color in zip(self._players, colors):
            player.color = color

    # ------------------------------------------------------------------ properties
    @property
    def board(self):
        return self._board

    @property
    def difficulty(self):
        return self._difficulty

    @property
    def dice(self):
        return self._dice

    @property
    def players(self):
        return list(self._players)

    @property
    def current_player(self):
        return self._turn_order[self._current_index]

    @property
    def winner(self):
        return self._winner

    @property
    def is_over(self):
        return self._winner is not None

    @property
    def has_started(self):
        """True once at least one turn has been played."""
        return bool(self._history)

    @property
    def in_progress(self):
        """True between the first roll and the end of the match."""
        return self.has_started and not self.is_over

    def reset(self):
        """Restart the match on the same board: everyone back to start, players' own order."""
        for player in self._players:
            player.reset()
        self._turn_order = list(self._players)
        self._current_index = 0
        self._winner = None
        self._history = []

    def set_turn_order(self, players):
        """Set who plays when (e.g. by the starting toss); only before the first roll.

        The first player in the new order plays the first turn. The `players`
        list itself keeps its original order.
        """
        players = list(players)
        if self.has_started:
            raise SnakesAndLaddersError("The turn order can only change before the first roll.")
        if len(players) != len(self._players) or set(players) != set(self._players):
            raise SnakesAndLaddersError("The turn order must contain exactly this match's players.")
        self._turn_order = players
        self._current_index = 0

    @property
    def turn_order(self):
        return list(self._turn_order)

    @property
    def history(self):
        return list(self._history)

    # ------------------------------------------------------------------ gameplay
    def play_turn(self):
        """Roll the dice for the current player, move them and return a TurnResult."""
        if self.is_over:
            raise GameOverError(f"The game is over, {self._winner.name} already won.")

        player = self.current_player
        roll = self._dice.roll()
        start = player.position
        target = start + roll
        size = self._board.size
        overshoot = target > size
        bounced = False

        if overshoot and self._difficulty.finish_rule == FINISH_EXACT:
            landed = end = start  # needs an exact roll: stay put
            event = None
        else:
            if overshoot and self._difficulty.finish_rule == FINISH_ANY:
                target = size  # passing the last square still wins
            elif overshoot:
                target = 2 * size - target  # bounce back the extra steps
                bounced = True
            landed = target
            end, event = self._board.destination(target)

        player.move_to(end)
        is_winner = end == size
        if is_winner:
            self._winner = player
        else:
            self._current_index = (self._current_index + 1) % len(self._turn_order)

        result = TurnResult(player, roll, start, landed, end, event, overshoot, is_winner, bounced)
        self._history.append(result)
        return result
