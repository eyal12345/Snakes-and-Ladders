"""StartToss class: the dice toss that decides the player order."""

from dataclasses import dataclass
from typing import Optional

from exceptions import SnakesAndLaddersError
from player import Player


@dataclass(frozen=True)
class TossRoll:
    player: Player
    values: tuple                 # the value of each dice
    round: int                    # round this toss belonged to
    round_over: bool              # every contender of the round has tossed
    ties: tuple                   # after a round: groups still tied, as (total, players)
    winner: Optional[Player]      # set once the whole order is decided

    @property
    def total(self):
        return sum(self.values)


class StartToss:
    """Everyone tosses the dice (2 by default); the order is by current total, highest first.

    Each player's current total is the one from their latest toss. Players whose
    current totals are equal toss again in the next round (only they toss), and
    the new totals are compared with everyone's again. Rounds continue until all
    current totals are different; the highest starts the match.
    """

    DICE_COUNT = 2

    def __init__(self, players, dice, dice_count=DICE_COUNT):
        if len(players) < 2:
            raise SnakesAndLaddersError("The starting toss needs at least two players.")
        self._players = list(players)
        self._dice = dice
        self._dice_count = dice_count
        self._round = 1
        self._contenders = list(players)  # who tosses this round
        self._tossed = set()              # contenders who already tossed this round
        self._all_rolls = {player: [] for player in players}  # every total, round by round

    @property
    def dice_count(self):
        return self._dice_count

    @property
    def round(self):
        return self._round

    @property
    def contenders(self):
        """Players who toss in the current round."""
        return list(self._contenders)

    def current_total(self, player):
        """The player's latest total, or None before their first toss."""
        rolls = self._all_rolls[player]
        return rolls[-1] if rolls else None

    def tosses(self, player):
        """The totals this player tossed so far, one per round they played."""
        return list(self._all_rolls[player])

    @property
    def is_decided(self):
        return not self._contenders

    @property
    def ranking(self):
        """Players by current total, highest first, or None while undecided."""
        if not self.is_decided:
            return None
        return sorted(self._players, key=self.current_total, reverse=True)

    @property
    def winner(self):
        return self.ranking[0] if self.is_decided else None

    @property
    def next_player(self):
        """The contender who tosses next, or None once decided."""
        return next((p for p in self._contenders if p not in self._tossed), None)

    def _ties(self):
        """Groups of players sharing the same current total, highest total first."""
        by_total = {}
        for player in self._players:
            by_total.setdefault(self.current_total(player), []).append(player)
        return tuple(
            (total, tuple(group))
            for total, group in sorted(by_total.items(), reverse=True)
            if len(group) > 1
        )

    def roll(self):
        """Toss the dice for the next contender and return a TossRoll."""
        player = self.next_player
        if player is None:
            raise SnakesAndLaddersError("The toss is over: the player order is decided.")
        values = tuple(self._dice.roll() for _ in range(self._dice_count))
        self._all_rolls[player].append(sum(values))
        self._tossed.add(player)
        played_round = self._round
        if self.next_player is not None:
            return TossRoll(player, values, played_round, False, (), None)

        # Round over: everyone sharing a current total tosses again.
        ties = self._ties()
        self._contenders = [p for p in self._players if any(p in group for _, group in ties)]
        self._tossed = set()
        if ties:
            self._round += 1
        return TossRoll(player, values, played_round, True, ties, self.winner)
