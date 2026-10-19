"""MatchHistory class: saved board maps, one reservoir per difficulty level."""

import json
import os
import secrets
import string
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from board import Board
from difficulty import Difficulty
from exceptions import InvalidBoardError, MatchHistoryError


@dataclass(frozen=True)
class Record:
    steps: int        # fewest steps a winner needed on the map
    holder: str = ""  # multiplayer only: "You" (the first player), "Rival" or "You/Rival"


@dataclass(frozen=True)
class SavedMap:
    map_id: str
    board: Board
    created: str  # "YYYY-MM-DD HH:MM:SS"
    difficulty: Difficulty
    single_record: Optional[Record] = None  # None while undetermined
    multi_record: Optional[Record] = None


class MatchHistory:
    """Stores every played board under a unique 6-character map ID.

    Each difficulty level has its own reservoir file (e.g. medium.json), so a
    map is only ever offered again for the level it was created on. IDs are
    unique across all reservoirs.
    """

    # Record kinds: singleplayer and multiplayer matches keep separate records.
    SINGLE = "single"
    MULTI = "multi"
    YOU = "You"
    RIVAL = "Rival"
    SHARED = "You/Rival"  # both reached the same record
    HOLDERS = (YOU, RIVAL, SHARED)
    # Records live under RECORDS_KEY. Older versions kept a single record under the other
    # keys; those are ignored (and dropped on the next write), so every map starts over
    # as Undetermined.
    RECORDS_KEY = "records"
    OLD_RECORD_KEYS = ("record", "best_steps")

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
            saved.append(SavedMap(map_id, board, str(entry.get("created", "")), difficulty,
                                  self._record_of(entry, self.SINGLE),
                                  self._record_of(entry, self.MULTI)))
        saved.sort(key=lambda m: m.created, reverse=True)
        return saved

    def all_maps(self):
        """Return the saved maps of every difficulty level, grouped by level (easiest first),
        newest first within each level."""
        return [m for level in Difficulty for m in self.maps(level)]

    def contains(self, difficulty, map_id):
        return map_id in self._read(difficulty)

    def record(self, difficulty, map_id, kind):
        """Return the map's Record of the given kind, or None if undetermined or not saved."""
        entry = self._read(difficulty).get(map_id)
        return self._record_of(entry, kind) if isinstance(entry, dict) else None

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
        self._write(difficulty, entries, map_id)

    def update_record(self, difficulty, map_id, kind, steps, holder=""):
        """Store a winner's step count if it beats the map's record of that kind.

        With a holder (multiplayer), equaling the record set by the other side makes it
        shared ("You/Rival"). Returns True when the record changed.
        """
        entries = self._read(difficulty)
        entry = entries.get(map_id)
        if not isinstance(entry, dict):
            return False
        record = self._record_of(entry, kind)
        tied = record is not None and record.steps == steps
        if tied and holder and record.holder not in (holder, self.SHARED):
            holder = self.SHARED
        elif record is not None and record.steps <= steps:
            return False
        records = entry.get(self.RECORDS_KEY)
        if not isinstance(records, dict):
            records = entry[self.RECORDS_KEY] = {}
        records[kind] = {"steps": steps, "holder": holder} if holder else {"steps": steps}
        self._write(difficulty, entries, map_id)
        return True

    def clear_record(self, difficulty, map_id, kind):
        """Reset the map's record of that kind to undetermined. Returns True if there was one."""
        entries = self._read(difficulty)
        entry = entries.get(map_id)
        if not isinstance(entry, dict) or self._record_of(entry, kind) is None:
            return False
        del entry[self.RECORDS_KEY][kind]
        self._write(difficulty, entries, map_id)
        return True

    @classmethod
    def _record_of(cls, entry, kind):
        """The entry's Record of that kind, or None if it is undetermined."""
        records = entry.get(cls.RECORDS_KEY)
        record = records.get(kind) if isinstance(records, dict) else None
        if not isinstance(record, dict):
            return None
        steps, holder = record.get("steps"), record.get("holder", "")
        if not isinstance(steps, int) or isinstance(steps, bool):
            return None
        return Record(steps, holder if holder in cls.HOLDERS else "")

    # ------------------------------------------------------------------ files
    def _path(self, difficulty):
        return os.path.join(self._directory, f"{difficulty.label.lower()}.json")

    def _write(self, difficulty, entries, map_id):
        for entry in entries.values():
            if isinstance(entry, dict):
                for key in self.OLD_RECORD_KEYS:
                    entry.pop(key, None)
        path = self._path(difficulty)
        try:
            os.makedirs(self._directory, exist_ok=True)
            temp = path + ".tmp"
            with open(temp, "w", encoding="utf-8") as file:
                json.dump(entries, file, indent=2)
            os.replace(temp, path)  # atomic: a crash never leaves a half-written reservoir
        except OSError as error:
            raise MatchHistoryError(f"Could not save match {map_id}: {error}") from error

    def _read(self, difficulty):
        try:
            with open(self._path(difficulty), encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}
