"""The lattice: local registry of every twin, plus failover."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Iterable, List, Optional

from levi.twins.twin import Twin, counterpart_side, twin_id_for


def _home() -> str:
    return os.environ.get("LEVI_TWINS_HOME", os.path.expanduser("~/.levi/twins"))


class TwinLattice:
    """Owns the twin registry. Local JSONL, upsert by twin_id.

    Failover rule: a BG twin may be promoted only when its FG counterpart
    is stale past the threshold *and* the BG twin itself is fresh. Promotion
    swaps sides and is recorded; nothing promotes itself silently — the
    caller decides and the event is in the record.
    """

    def __init__(self, home: str | None = None) -> None:
        self.home = home or _home()
        os.makedirs(self.home, exist_ok=True)
        self._path = os.path.join(self.home, "twins.jsonl")
        self._twins: Dict[str, Twin] = {}
        self._load()

    # -- persistence ----------------------------------------------------
    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    tw = Twin.from_dict(data)
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    continue
                self._twins[tw.twin_id] = tw

    def _save(self) -> None:
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for tw in sorted(self._twins.values(), key=lambda t: t.twin_id):
                fh.write(json.dumps(tw.to_dict(), default=str) + "\n")
        os.replace(tmp, self._path)

    # -- registry -------------------------------------------------------
    def register(
        self,
        kind: str,
        subject: str,
        side: str,
        state: Optional[Dict[str, Any]] = None,
        notes: str = "",
        pair_id: Optional[str] = None,
    ) -> Twin:
        twin_id = twin_id_for(kind, subject, side)
        if pair_id is None:
            pair_id = twin_id_for(kind, subject, counterpart_side(side))
        existing = self._twins.get(twin_id)
        if existing is not None:
            if state:
                existing.state.update(state)
            if notes:
                existing.notes = notes
            self._save()
            return existing
        tw = Twin(
            twin_id=twin_id,
            kind=kind,
            subject=subject,
            side=side,
            pair_id=pair_id,
            state=dict(state or {}),
            notes=notes,
        )
        self._twins[twin_id] = tw
        self._save()
        return tw

    def ensure_pair(
        self,
        kind: str,
        subject: str,
        state: Optional[Dict[str, Any]] = None,
    ) -> List[Twin]:
        """Create the FG/BG pair if missing; idempotent."""
        return [
            self.register(kind, subject, "fg", state=state),
            self.register(kind, subject, "bg", state=state),
        ]

    def get(self, twin_id: str) -> Optional[Twin]:
        return self._twins.get(twin_id)

    def remove(self, twin_id: str) -> bool:
        """Delete a twin by id. Returns True if it existed."""
        if twin_id not in self._twins:
            return False
        del self._twins[twin_id]
        self._save()
        return True

    def list(
        self,
        kind: Optional[str] = None,
        subject: Optional[str] = None,
        side: Optional[str] = None,
    ) -> List[Twin]:
        out = list(self._twins.values())
        if kind is not None:
            out = [t for t in out if t.kind == kind]
        if subject is not None:
            out = [t for t in out if t.subject == subject]
        if side is not None:
            out = [t for t in out if t.side == side]
        return sorted(out, key=lambda t: t.twin_id)

    def heartbeat(
        self,
        twin_id: str,
        state_update: Optional[Dict[str, Any]] = None,
    ) -> Twin:
        tw = self._twins.get(twin_id)
        if tw is None:
            raise KeyError(f"unknown twin: {twin_id}")
        tw.heartbeat(state_update)
        self._save()
        return tw

    def stale(self, threshold_s: float) -> List[Twin]:
        now = time.time()
        return [t for t in self._twins.values() if t.is_stale(threshold_s, now)]

    # -- failover -------------------------------------------------------
    def promote(self, twin_id: str, threshold_s: float) -> Dict[str, Any]:
        """Promote a BG twin to FG, demoting its stale FG counterpart.

        Returns an event record. Refuses when the FG counterpart is still
        fresh, or when this twin itself is stale.
        """
        tw = self._twins.get(twin_id)
        if tw is None:
            raise KeyError(f"unknown twin: {twin_id}")
        if tw.side != "bg":
            raise ValueError("only a bg twin can be promoted")
        fg = self._twins.get(tw.pair_id)
        now = time.time()
        if fg is not None and not fg.is_stale(threshold_s, now):
            raise ValueError(f"refusing: fg counterpart {fg.twin_id} is still fresh")
        if tw.is_stale(threshold_s, now):
            raise ValueError(f"refusing: bg twin {twin_id} is itself stale")
        # swap sides: twin_ids encode side, so ids and pair pointers swap too
        fg_id, bg_id = fg.twin_id, tw.twin_id
        tw.side, fg.side = "fg", "bg"
        tw.twin_id, fg.twin_id = fg_id, bg_id
        tw.pair_id, fg.pair_id = bg_id, fg_id
        tw.promoted_at = now
        for stale_key in (twin_id, tw.pair_id):
            self._twins.pop(stale_key, None)
        self._twins[tw.twin_id] = tw
        self._twins[fg.twin_id] = fg
        self._save()
        return {
            "event": "promote",
            "promoted": tw.twin_id,
            "demoted": fg.twin_id,
            "at": now,
        }

    def rotate(self, twin_id: str) -> Dict[str, Any]:
        """Commanded FG/BG role swap — the shadow steps forward.

        Unlike :meth:`promote`, this is a drill, not a failover: no
        staleness checks. The transform operation of the evolution engine
        uses it to keep the lattice from ever standing still.
        """
        tw = self._twins.get(twin_id)
        if tw is None:
            raise KeyError(f"unknown twin: {twin_id}")
        other = self._twins.get(tw.pair_id)
        if other is None:
            raise ValueError(f"twin {twin_id} has no live counterpart")
        now = time.time()
        # swap sides: twin_ids encode side, so ids and pair pointers swap too
        a_id, b_id = tw.twin_id, other.twin_id
        tw.side, other.side = other.side, tw.side
        tw.twin_id, other.twin_id = b_id, a_id
        tw.pair_id, other.pair_id = a_id, b_id
        tw.rotated_at = now
        other.rotated_at = now
        for stale_key in (a_id, b_id):
            self._twins.pop(stale_key, None)
        self._twins[tw.twin_id] = tw
        self._twins[other.twin_id] = other
        self._save()
        return {
            "event": "rotate",
            "now_fg": tw.twin_id if tw.side == "fg" else other.twin_id,
            "now_bg": tw.twin_id if tw.side == "bg" else other.twin_id,
            "at": now,
        }

    def check_failover(
        self,
        kind: str,
        subject: str,
        threshold_s: float,
    ) -> Optional[Dict[str, Any]]:
        """If FG is stale and BG is fresh, promote. Returns event or None."""
        fg_id = twin_id_for(kind, subject, "fg")
        bg_id = twin_id_for(kind, subject, "bg")
        fg = self._twins.get(fg_id)
        bg = self._twins.get(bg_id)
        if fg is None or bg is None:
            return None
        now = time.time()
        if fg.is_stale(threshold_s, now) and not bg.is_stale(threshold_s, now):
            return self.promote(bg_id, threshold_s)
        return None

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for tw in self._twins.values():
            out[tw.kind] = out.get(tw.kind, 0) + 1
        return out

    def iter_all(self) -> Iterable[Twin]:
        return iter(sorted(self._twins.values(), key=lambda t: t.twin_id))
