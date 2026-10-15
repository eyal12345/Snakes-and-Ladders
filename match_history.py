"""MatchHistory class: saved board maps, one reservoir per difficulty level."""

import json
import os
import secrets
import string
from dataclasses import dataclass
from datetime import datetime

from board import Board
from difficulty import Difficulty
from exceptions import InvalidBoardError, MatchHistoryError


@dataclass(frozen=True)
class SavedMap:
    map_id: str
    board: Board
    created: str  # "YYYY-MM-DD HH:MM:SS"
    difficulty: Difficulty


class MatchHistory:
    """Stores every played board under a unique 6-character map ID.

    Each difficulty level has its own reservoir file (e.g. medium.json), so a
    map is only ever offered again for the level it was created on. IDs are
    unique across all reservoirs.
    """

    ID_LENGTH = 6
    ID_ALPHABET = string.ascii_uppercase + string.digits

    def __init__(self, directory=None):
        self._directory = directory or self.default_directory()

    @staticmethod
    def default_directory():
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "Snakes and Ladders", "maps")

    @property
    def directory(self):
        return self._directory

    # ------------------------------------------------------------------ ids
    def new_id(self):
        """Return a random map ID not used by any saved map."""
        used = self._all_ids()
        while True:
            map_id = "".join(secrets.choice(self.ID_ALPHABET) for _ in range(self.ID_LENGTH))
            if map_id not in used:
                return map_id

    def _all_ids(self):
        ids = set()
        for level in Difficulty:
            ids.update(self._read(level))
        return ids

    # ------------------------------------------------------------------ queries
    def maps(self, difficulty):
        """Return the saved maps of one difficulty level, newest first."""
        saved = []
        for map_id, entry in self._read(difficulty).items():
            try:
                board = Board(
                    entry["size"],
                    snakes={int(k): int(v) for k, v in entry["snakes"].items()},
                    ladders={int(k): int(v) for k, v in entry["ladders"].items()},
                )
            except (KeyError, TypeError, ValueError, AttributeError, InvalidBoardError):
                continue  # skip damaged entries instead of failing the whole list
            saved.append(SavedMap(map_id, board, str(entry.get("created", "")), difficulty))
        saved.sort(key=lambda m: m.created, reverse=True)
        return saved

    def all_maps(self):
        """Return the saved maps of every difficulty level together, newest first."""
        saved = [m for level in Difficulty for m in self.maps(level)]
        saved.sort(key=lambda m: m.created, reverse=True)
        return saved

    def contains(self, difficulty, map_id):
        return map_id in self._read(difficulty)

    # ------------------------------------------------------------------ saving
    def save(self, difficulty, map_id, board):
        """Add a board to its difficulty's reservoir (no-op if the ID is already there)."""
        entries = self._read(difficulty)
        if map_id in entries:
            return
        entries[map_id] = {
            "size": board.size,
            "snakes": {str(k): v for k, v in sorted(board.snakes.items())},
            "ladders": {str(k): v for k, v in sorted(board.ladders.items())},
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        path = self._path(difficulty)
        try:
            os.makedirs(self._directory, exist_ok=True)
            temp = path + ".tmp"
            with open(temp, "w", encoding="utf-8") as file:
                json.dump(entries, file, indent=2)
            os.replace(temp, path)  # atomic: a crash never leaves a half-written reservoir
        except OSError as error:
            raise MatchHistoryError(f"Could not save match {map_id}: {error}") from error

    # ------------------------------------------------------------------ files
    def _path(self, difficulty):
        return os.path.join(self._directory, f"{difficulty.label.lower()}.json")

    def _read(self, difficulty):
        try:
            with open(self._path(difficulty), encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}
