"""
Continuity Shelf — LEVI-original resume engine.

Not a third-party agent “memory product.” Cross-organ pointers so the operator
never loses the thread: last ask, open HITL, active rail cars, L.W.P. scenes,
factory projects, monotropism tunnel, charter version.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone
import json


DEFAULT = Path.home() / ".levi" / "continuity_shelf.json"

#: Hard cap on snapshot text fields — continuity is pointers, not a dump.
_LAST_ASK_LIMIT = 500
_LAST_REPLY_LIMIT = 240
_HISTORY_LIMIT = 40


class ContinuityError(ValueError):
    """Invalid input to the continuity shelf."""


@dataclass
class ContinuityFrame:
    at: str
    last_ask: str = ""
    last_reply_head: str = ""
    open_hitl: int = 0
    active_rails: int = 0
    lwp_words: int = 0
    monotropism_depth: float = 0.0
    notes: List[str] = field(default_factory=list)
    pointers: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ContinuityShelf:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT
        self.history: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.history = []
            return
        history = raw.get("history") if isinstance(raw, dict) else []
        # One corrupt shelf must not poison resume: keep dict frames only.
        self.history = [h for h in history if isinstance(h, dict)][
            -_HISTORY_LIMIT:
        ] if isinstance(history, list) else []

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "history": self.history[-_HISTORY_LIMIT:],
            "updated": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            raise ContinuityError(
                f"cannot persist continuity shelf to {self.path}: {exc}"
            ) from exc

    def snapshot(self, last_ask: str = "", last_reply: str = "") -> ContinuityFrame:
        for field, value in (("last_ask", last_ask), ("last_reply", last_reply)):
            if not isinstance(value, str):
                raise ContinuityError(
                    f"snapshot: {field!r} must be a string, "
                    f"got {type(value).__name__}"
                )
        frame = ContinuityFrame(at=datetime.now(timezone.utc).isoformat())
        frame.last_ask = last_ask[:_LAST_ASK_LIMIT]
        frame.last_reply_head = last_reply[:_LAST_REPLY_LIMIT]
        try:
            from levi.project.hitl import HITLGate

            pend = [r for r in HITLGate().list_pending()]
            frame.open_hitl = len(pend)
            if pend:
                frame.pointers["hitl"] = getattr(pend[0], "id", "")
                frame.notes.append(f"HITL pending: {pend[0].what[:60]}")
        except Exception:
            pass
        try:
            from levi.lwp.opportunity_rail import OpportunityRail

            cars = list(OpportunityRail().cars.values())
            active = [c for c in cars if getattr(c, "status", "") == "active"]
            frame.active_rails = len(active)
            if active:
                frame.pointers["rail"] = active[0].id
                frame.notes.append(f"Rail {active[0].id} @ {active[0].gate}")
        except Exception:
            pass
        try:
            from levi.lwp.model_engine import LWPModelEngine

            eng = LWPModelEngine()
            frame.lwp_words = eng.state.words
            if eng.state.last_id:
                frame.pointers["lwp_scene"] = eng.state.last_id
        except Exception:
            pass
        try:
            # soft read
            from pathlib import Path as P
            import json as _j

            mp = P.home() / ".levi" / "monotropism.json"
            if mp.exists():
                data = _j.loads(mp.read_text())
                tunnels = data.get("tunnels") or data.get("active") or []
                if tunnels and isinstance(tunnels, list):
                    d = (
                        tunnels[0].get("depth", 0)
                        if isinstance(tunnels[0], dict)
                        else 0
                    )
                    frame.monotropism_depth = float(d)
        except Exception:
            pass
        try:
            from levi.identity.charter import Charter

            Charter()  # validate it loads; result unused
            frame.pointers["charter"] = "loaded"
        except Exception:
            pass
        self.history.append(frame.to_dict())
        self._persist()
        return frame

    def resume_card(self) -> str:
        frame = self.snapshot()
        lines = [
            "=== Continuity Shelf (LEVI-original) ===",
            f"Captured: {frame.at}",
            "",
            f"Open HITL: {frame.open_hitl}   Active rails: {frame.active_rails}   L.W.P. words: {frame.lwp_words}",
            f"Focus depth: {frame.monotropism_depth:.2f}",
            "",
        ]
        if frame.last_ask:
            lines.append(f"Last ask: {frame.last_ask[:160]}")
        if frame.notes:
            lines.append("Threads:")
            for n in frame.notes[:6]:
                lines.append(f"  · {n}")
        if frame.pointers:
            lines.append(
                "Pointers: " + ", ".join(f"{k}={v}" for k, v in frame.pointers.items())
            )
        lines.append("")
        lines.append(
            "Continue: levi ask | levi project --approve ID | levi rail --advance ID --approved"
        )
        lines.append("This is not a SaaS memory vault — local JSON shelf under ~/.levi")
        return "\n".join(lines)
