"""Player-owned saves: portable JSON the player keeps forever.

The Stadia lesson (arch-games-stadia-vanishing-library), encoded: progress
is never held hostage on a server. Every save is a plain JSON file under
``~/.levi/games/saves/<game_id>/`` that the player can export, copy,
inspect, or re-import. No account, no network, no revocation path.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

SAVE_FORMAT = 1


class SaveError(Exception):
    """Save/export/import failures."""


def _default_root() -> Path:
    home = os.environ.get("LEVI_HOME") or os.path.expanduser("~/.levi")
    return Path(home) / "games" / "saves"


class SaveStore:
    """Owner-only save files, portable by design."""

    def __init__(self, root: "str | os.PathLike[str] | None" = None):
        self.root = Path(root) if root else _default_root()

    # -- paths -----------------------------------------------------------
    def _slot_path(self, game_id: str, slot: str) -> Path:
        safe_game = "".join(c for c in game_id if c.isalnum() or c in "-_")
        safe_slot = "".join(c for c in slot if c.isalnum() or c in "-_")
        if not safe_game or not safe_slot:
            raise SaveError("bad game_id or slot name")
        return self.root / safe_game / (safe_slot + ".json")

    # -- CRUD ------------------------------------------------------------
    def save(self, game_id: str, slot: str, state: Dict[str, Any]) -> Path:
        path = self._slot_path(game_id, slot)
        path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            "levi_game_save": SAVE_FORMAT,
            "game_id": game_id,
            "slot": slot,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "state": dict(state),
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        os.chmod(path, 0o600)
        return path

    def load(self, game_id: str, slot: str) -> Dict[str, Any]:
        path = self._slot_path(game_id, slot)
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SaveError("no save in slot %r for game %r" % (slot, game_id)) from exc
        except ValueError as exc:
            raise SaveError("corrupt save file: %s" % exc) from exc
        if envelope.get("levi_game_save") != SAVE_FORMAT:
            raise SaveError("unrecognized save format")
        if envelope.get("game_id") != game_id:
            raise SaveError("save belongs to a different game")
        return dict(envelope.get("state") or {})

    def list_slots(self, game_id: str) -> List[str]:
        game_dir = self._slot_path(game_id, "x").parent
        if not game_dir.is_dir():
            return []
        return sorted(p.stem for p in game_dir.glob("*.json"))

    def delete(self, game_id: str, slot: str) -> bool:
        path = self._slot_path(game_id, slot)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True

    # -- portability ------------------------------------------------------
    def export(self, game_id: str, slot: str, dest: "str | os.PathLike[str]") -> Path:
        """Copy a save out as a portable file the player owns."""
        state = self.load(game_id, slot)  # validates first
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            "levi_game_save": SAVE_FORMAT,
            "game_id": game_id,
            "slot": slot,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "state": state,
        }
        dest.write_text(
            json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return dest

    def import_save(
        self, path: "str | os.PathLike[str]", slot: "str | None" = None
    ) -> Tuple[str, str]:
        """Import a portable save file. Refuses foreign envelopes."""
        path = Path(path)
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SaveError("cannot import save: %s" % exc) from exc
        if envelope.get("levi_game_save") != SAVE_FORMAT:
            raise SaveError("not a LEVI game save")
        game_id = str(envelope.get("game_id") or "")
        if not game_id:
            raise SaveError("save envelope has no game_id")
        slot = slot or str(envelope.get("slot") or "imported")
        self.save(game_id, slot, dict(envelope.get("state") or {}))
        return game_id, slot
