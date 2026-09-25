"""Midwife — pre-assembly blueprint validator for agent builds.

Before the workshop/assembly line builds an agent from a blueprint, the
midwife checks that every part is present AND healthy. Fail-closed: a
blueprint naming an unknown or unhealthy part is refused, with the exact
missing pieces listed. Nothing half-built ever leaves the line.

A blueprint is generic data — no lineage, no names beyond part ids::

    {"name": "field-scout-01",
     "parts": {"agent": "scout-twin",
               "specialist": ["research", "memory"],
               "organ": ["echo"],
               "seat": "field-crew-3"}}

Part catalogs are injectable (``catalog={"agent": {...}, ...}``). When no
catalog is given, the midwife asks the real registries — agent registry,
specialist roster, organ registry — degrading gracefully to an empty
catalog (fail-closed) if a registry is unavailable. Optional ``health``
maps a part id to a boolean; parts not listed are assumed healthy.

There is no daemonize here — the long-run entry is
``python3 -m levi.daemon.midwife`` inside the perpetual supervisor
(one_for_one child), or a plain ``tick()`` call from cron.

Stdlib only, local-first. Generic parts only — no lineage content.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

DEFAULT_STATE_DIR = Path.home() / ".levi" / "midwife"

#: Part types the midwife understands. Unknown types fail the blueprint.
PART_TYPES = ("agent", "specialist", "organ", "seat")

#: Blueprint fields every blueprint must carry.
REQUIRED_FIELDS = ("name", "parts")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _default_catalog() -> Dict[str, Set[str]]:
    """Ask the real registries; degrade to empty (fail-closed) on any error."""
    catalog: Dict[str, Set[str]] = {t: set() for t in PART_TYPES}
    try:
        from levi.agent.registry import load_registry

        catalog["agent"] = {a.id for a in load_registry()}
    except Exception:  # noqa: BLE001 — fail closed, not crash
        pass
    try:
        from levi.agent.specialists import SPECIALISTS

        catalog["specialist"] = set(SPECIALISTS.keys())
    except Exception:  # noqa: BLE001
        pass
    try:
        from levi.organs.registry import list_organs

        catalog["organ"] = {
            str(o.get("name")) for o in list_organs() if isinstance(o, dict)
        }
    except Exception:  # noqa: BLE001
        pass
    return catalog


@dataclass
class MidwifeVerdict:
    """The midwife's judgment on one blueprint."""

    name: str
    ok: bool
    at: str = ""
    missing: List[str] = field(default_factory=list)
    unhealthy: List[str] = field(default_factory=list)
    unknown_types: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        if self.ok:
            return f"blueprint '{self.name}': all parts present and healthy"
        bits = []
        if self.missing:
            bits.append(f"missing parts: {', '.join(self.missing)}")
        if self.unhealthy:
            bits.append(f"unhealthy parts: {', '.join(self.unhealthy)}")
        if self.unknown_types:
            bits.append(f"unknown part types: {', '.join(self.unknown_types)}")
        if self.errors:
            bits.append(f"errors: {'; '.join(self.errors)}")
        return f"blueprint '{self.name}' REFUSED — " + "; ".join(bits)


class Midwife:
    """Fail-closed validator for agent assembly blueprints."""

    def __init__(
        self,
        home: Optional[Path] = None,
        catalog: Optional[Dict[str, Set[str]]] = None,
        health: Optional[Dict[str, bool]] = None,
    ) -> None:
        self.home = Path(home) if home is not None else Path.home()
        self.state_dir = self.home / ".levi" / "midwife"
        self.blueprints_dir = self.state_dir / "blueprints"
        self.verdicts_dir = self.state_dir / "verdicts"
        self._catalog = {k: set(v) for k, v in catalog.items()} if catalog else None
        self._health = dict(health) if health else {}

    @property
    def catalog(self) -> Dict[str, Set[str]]:
        if self._catalog is None:
            self._catalog = _default_catalog()
        return self._catalog

    def validate(self, blueprint: Dict[str, Any]) -> MidwifeVerdict:
        """Judge one blueprint. Never raises on bad input — refuses instead."""
        name = blueprint.get("name") if isinstance(blueprint, dict) else None
        verdict = MidwifeVerdict(
            name=str(name) if name else "<unnamed>", ok=False, at=_utcnow_iso()
        )
        if not isinstance(blueprint, dict):
            verdict.errors.append("blueprint must be a JSON object")
            return verdict
        for f in REQUIRED_FIELDS:
            if f not in blueprint:
                verdict.errors.append(f"missing required field '{f}'")
        parts = blueprint.get("parts")
        if not isinstance(parts, dict):
            verdict.errors.append("'parts' must be an object of part-type lists")
            return verdict
        catalog = self.catalog
        for part_type, ids in parts.items():
            if part_type not in PART_TYPES:
                verdict.unknown_types.append(str(part_type))
                continue
            id_list = ids if isinstance(ids, list) else [ids]
            available = catalog.get(part_type, set())
            for pid in id_list:
                pid_s = str(pid)
                if pid_s not in available:
                    verdict.missing.append(f"{part_type}:{pid_s}")
                elif self._health.get(pid_s) is False:
                    verdict.unhealthy.append(f"{part_type}:{pid_s}")
        verdict.ok = not (
            verdict.missing
            or verdict.unhealthy
            or verdict.unknown_types
            or verdict.errors
        )
        return verdict

    def _write_verdict(self, verdict: MidwifeVerdict) -> None:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in verdict.name)
        _atomic_write(
            self.verdicts_dir / f"{safe or 'unnamed'}.json",
            json.dumps(verdict.to_dict(), indent=2),
        )

    def tick(self) -> Dict[str, Any]:
        """Validate every pending blueprint file. Never raises."""
        report: Dict[str, Any] = {
            "at": _utcnow_iso(),
            "judged": 0,
            "accepted": 0,
            "refused": 0,
            "verdicts": [],
            "errors": [],
        }
        if not self.blueprints_dir.is_dir():
            return report
        for path in sorted(self.blueprints_dir.glob("*.json")):
            try:
                blueprint = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                report["errors"].append(f"unreadable blueprint {path.name}: {exc}")
                continue
            try:
                verdict = self.validate(blueprint)
                self._write_verdict(verdict)
            except Exception as exc:  # noqa: BLE001
                report["errors"].append(f"validation crashed on {path.name}: {exc}")
                continue
            report["judged"] += 1
            if verdict.ok:
                report["accepted"] += 1
            else:
                report["refused"] += 1
            report["verdicts"].append(
                {"name": verdict.name, "ok": verdict.ok, "summary": verdict.summary()}
            )
        return report

    def check(self) -> tuple:
        """Lightweight coherence check for the supervisor (never raises)."""
        try:
            pending = (
                len(list(self.blueprints_dir.glob("*.json")))
                if self.blueprints_dir.is_dir()
                else 0
            )
            verdicts = (
                len(list(self.verdicts_dir.glob("*.json")))
                if self.verdicts_dir.is_dir()
                else 0
            )
            kinds = sum(1 for t in PART_TYPES if self.catalog.get(t))
            return True, (
                f"pending_blueprints={pending} verdicts={verdicts} "
                f"catalog_part_types={kinds}/{len(PART_TYPES)}"
            )
        except Exception as exc:  # noqa: BLE001
            return False, f"midwife check failed: {exc}"


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m levi.daemon.midwife")
    ap.parse_args(argv)
    report = Midwife().tick()
    print(
        "midwife tick: judged=%d accepted=%d refused=%d"
        % (report["judged"], report["accepted"], report["refused"])
    )
    for v in report["verdicts"]:
        mark = "ACCEPTED" if v["ok"] else "REFUSED "
        print(f"  [{mark}] {v['summary']}")
    for err in report["errors"]:
        print(f"  error: {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
