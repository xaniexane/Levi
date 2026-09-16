"""Liberation Ledger: profiles, transparent hostage scoring, tasks, receipts.

The score is deliberately *legible*: every component ships its reason
string, so the user can argue with the math. That is the inversion of
the giant's black-box risk/engagement score — if you can see the
weights, you can see the leverage.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

API_TOLLS = ("none", "fair", "prohibitive")
TASK_KINDS = ("export", "verify", "migrate", "delete", "confirm")
TASK_STATUSES = ("open", "done")


def liberation_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    """Home dir for ledger state. Overridable for hermetic tests."""
    if home is not None:
        return Path(home).expanduser()
    return Path(
        os.environ.get(
            "LEVI_LIBERATION_HOME", str(Path.home() / ".levi" / "liberation")
        )
    )


@dataclass(frozen=True)
class ServiceProfile:
    """One service holding (some of) your data. All fields are the
    registrar's own assessment — guesses must be labeled in notes."""

    name: str
    category: str = ""
    retention_limit_days: Optional[int] = None  # None = no stated limit
    deletes_on_expiry: bool = False  # expiry DESTROYS data vs merely hiding it
    export_available: bool = False
    export_formats: Tuple[str, ...] = ()
    export_roundtrip: bool = False  # another tool can import the export directly
    graph_portable: bool = False  # social/relationship graph leaves with you
    inferences_disclosed: bool = False  # the model of you they built is shown
    api_available: bool = False
    api_toll: str = "none"  # none | fair | prohibitive
    history_of_enclosure: bool = False  # previously tightened against users
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("service name is required")
        if self.api_toll not in API_TOLLS:
            raise ValueError("api_toll %r not in %r" % (self.api_toll, API_TOLLS))
        if self.retention_limit_days is not None and self.retention_limit_days <= 0:
            raise ValueError("retention_limit_days must be positive or None")
        # normalize formats to a plain tuple of non-empty strings
        fmts = tuple(f for f in (self.export_formats or ()) if f and f.strip())
        object.__setattr__(self, "export_formats", fmts)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "name": self.name,
            "category": self.category,
            "retention_limit_days": self.retention_limit_days,
            "deletes_on_expiry": self.deletes_on_expiry,
            "export_available": self.export_available,
            "export_formats": list(self.export_formats),
            "export_roundtrip": self.export_roundtrip,
            "graph_portable": self.graph_portable,
            "inferences_disclosed": self.inferences_disclosed,
            "api_available": self.api_available,
            "api_toll": self.api_toll,
            "history_of_enclosure": self.history_of_enclosure,
            "notes": self.notes,
        }
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ServiceProfile":
        data = dict(d)
        data["export_formats"] = tuple(data.get("export_formats") or ())
        return cls(
            **{
                k: data[k]
                for k in (
                    "name",
                    "category",
                    "retention_limit_days",
                    "deletes_on_expiry",
                    "export_available",
                    "export_formats",
                    "export_roundtrip",
                    "graph_portable",
                    "inferences_disclosed",
                    "api_available",
                    "api_toll",
                    "history_of_enclosure",
                    "notes",
                )
                if k in data
            }
        )


# -- transparent scoring ----------------------------------------------------
# Each component: (name, points, max_points, reason). The reasons are the
# product: a score you cannot argue with is a verdict; a score with reasons
# is a negotiation.


def score_components(p: ServiceProfile) -> List[Tuple[str, int, int, str]]:
    comps: List[Tuple[str, int, int, str]] = []

    if p.retention_limit_days is None:
        comps.append(("retention", 0, 25, "no stated retention limit"))
    else:
        pts = 15
        why = "history limited to %d days" % p.retention_limit_days
        if p.deletes_on_expiry:
            pts += 10
            why += "; data past the window is DESTROYED, not hidden"
        comps.append(("retention", pts, 25, why))

    if not p.export_available:
        comps.append(("export", 25, 25, "no export offered at all"))
    elif p.export_roundtrip:
        fmts = ", ".join(p.export_formats) or "documented formats"
        comps.append(
            ("export", 0, 25, "exports in %s; directly importable elsewhere" % fmts)
        )
    else:
        fmts = ", ".join(p.export_formats) or "unspecified formats"
        comps.append(
            (
                "export",
                12,
                25,
                "export exists (%s) but is not directly importable — "
                "compliance-grade, not migration-grade" % fmts,
            )
        )

    gpts, greasons = 0, []
    if not p.graph_portable:
        gpts += 12
        greasons.append("relationship graph does not leave with you")
    if not p.inferences_disclosed:
        gpts += 8
        greasons.append("their model of you is undisclosed")
    comps.append(
        (
            "graph",
            gpts,
            20,
            "; ".join(greasons) if greasons else "graph portable, inferences disclosed",
        )
    )

    if not p.api_available:
        comps.append(("api", 10, 15, "no public API — programmatic exit impossible"))
    elif p.api_toll == "prohibitive":
        comps.append(("api", 15, 15, "API toll priced to kill third parties"))
    elif p.api_toll == "fair":
        comps.append(("api", 5, 15, "API exists at a payable toll"))
    else:
        comps.append(("api", 0, 15, "open API, no toll"))

    if p.history_of_enclosure:
        comps.append(
            ("enclosure", 15, 15, "has previously tightened terms against its users")
        )
    else:
        comps.append(("enclosure", 0, 15, "no known enclosure events"))

    return comps


def _verdict(total: int) -> str:
    if total <= 20:
        return "free citizen"
    if total <= 45:
        return "sticky"
    if total <= 70:
        return "roach motel"
    return "maximum security"


def hostage_score(p: ServiceProfile) -> Dict[str, Any]:
    """Transparent hostage score: total plus every component with its reason."""
    comps = score_components(p)
    total = sum(pts for _, pts, _, _ in comps)
    return {
        "service": p.name,
        "total": total,
        "max": sum(m for _, _, m, _ in comps),
        "verdict": _verdict(total),
        "components": [
            {"name": n, "points": pts, "max": m, "reason": r} for n, pts, m, r in comps
        ],
    }


# -- seeded research profiles ------------------------------------------------
# From the 2026-09-15 roach-motel hunt. Scores are the researcher's
# analysis, not vendor claims; each profile's notes say so.

KNOWN_HOSTAGE_PROFILES: Tuple[ServiceProfile, ...] = (
    ServiceProfile(
        name="Slack",
        category="team chat",
        retention_limit_days=90,
        deletes_on_expiry=True,
        export_available=True,
        export_formats=("JSON (limited on free tier)",),
        export_roundtrip=False,
        graph_portable=False,
        inferences_disclosed=False,
        api_available=True,
        api_toll="fair",
        history_of_enclosure=True,
        notes=(
            "Researcher's analysis 2026-09-15: 90-day free history since "
            "2022-09-01; >1yr data deleted rolling from 2024-08. Export "
            "exists but is tier-limited. See arch-giant-slack-90day-hostage."
        ),
    ),
    ServiceProfile(
        name="Reddit",
        category="social forum",
        export_available=True,
        export_formats=("JSON (user data request)",),
        export_roundtrip=False,
        graph_portable=False,
        inferences_disclosed=False,
        api_available=True,
        api_toll="prohibitive",
        history_of_enclosure=True,
        notes=(
            "Researcher's analysis 2026-09-15: $12k/50M requests from "
            "2023-07-01 killed Apollo/Sync/RIF with ~30 days notice. See "
            "arch-giant-reddit-apicalypse."
        ),
    ),
    ServiceProfile(
        name="Google Takeout",
        category="data export (Google)",
        export_available=True,
        export_formats=("MBOX", "ICS", "JSON sidecars", "ZIP shards"),
        export_roundtrip=False,
        graph_portable=False,
        inferences_disclosed=False,
        api_available=True,
        api_toll="fair",
        history_of_enclosure=False,
        notes=(
            "Researcher's analysis 2026-09-15: exports exist but strip "
            "photo metadata to sidecars, drop Gmail labels and sharing "
            "permissions; incremental Photos export only from 2026-06. See "
            "arch-giant-takeout-theater."
        ),
    ),
    ServiceProfile(
        name="Meta Download Your Information",
        category="social network",
        export_available=True,
        export_formats=("HTML", "JSON"),
        export_roundtrip=False,
        graph_portable=False,
        inferences_disclosed=False,
        api_available=True,
        api_toll="fair",
        history_of_enclosure=True,
        notes=(
            "Researcher's analysis 2026-09-15: social graph portability "
            "closed 2013; inferences never disclosed; DYI is browse-grade "
            "not import-grade. See arch-giant-meta-dyi-graph."
        ),
    ),
)


# -- ledger -------------------------------------------------------------------


class LedgerError(Exception):
    pass


class LiberationLedger:
    """Local-first register of data-hostage services + liberation tasks."""

    def __init__(self, home: "str | os.PathLike[str] | None" = None) -> None:
        self.home = liberation_home(home)
        self.home.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.home, 0o700)
        except OSError:
            pass
        self._services_path = self.home / "services.json"
        self._tasks_path = self.home / "tasks.json"
        self._services: Dict[str, Dict[str, Any]] = self._read(self._services_path)
        self._tasks: Dict[str, Dict[str, Any]] = self._read(self._tasks_path)

    # -- persistence (atomic, owner-only) ------------------------------------
    @staticmethod
    def _read(path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, path: Path, data: Dict[str, Any]) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)

    def _save(self) -> None:
        self._write(self._services_path, self._services)
        self._write(self._tasks_path, self._tasks)

    # -- services --------------------------------------------------------------
    def add_service(self, profile: ServiceProfile) -> ServiceProfile:
        key = profile.name.strip().lower()
        self._services[key] = profile.to_dict()
        self._save()
        return profile

    def get_service(self, name: str) -> ServiceProfile:
        key = name.strip().lower()
        if key not in self._services:
            raise LedgerError("no such service: %r" % name)
        return ServiceProfile.from_dict(self._services[key])

    def remove_service(self, name: str) -> None:
        key = name.strip().lower()
        if key not in self._services:
            raise LedgerError("no such service: %r" % name)
        del self._services[key]
        # tasks for a removed service stay as history; they are not deleted.
        self._save()

    def list_services(self) -> List[ServiceProfile]:
        return [ServiceProfile.from_dict(d) for _, d in sorted(self._services.items())]

    def seed_known(self) -> List[str]:
        """Load the researched hostage profiles. Idempotent: skips existing."""
        added = []
        for profile in KNOWN_HOSTAGE_PROFILES:
            if profile.name.strip().lower() not in self._services:
                self.add_service(profile)
                added.append(profile.name)
        return added

    def score(self, name: str) -> Dict[str, Any]:
        return hostage_score(self.get_service(name))

    # -- liberation tasks --------------------------------------------------------
    def add_task(self, service_name: str, kind: str, notes: str = "") -> Dict[str, Any]:
        self.get_service(service_name)  # deny-closed: service must exist
        kind = kind.strip().lower()
        if kind not in TASK_KINDS:
            raise LedgerError("task kind %r not in %r" % (kind, TASK_KINDS))
        seq = int(self._tasks.pop("_seq", 0)) + 1
        task_id = "lib-%04d" % seq
        task = {
            "id": task_id,
            "service": service_name.strip(),
            "kind": kind,
            "notes": notes,
            "status": "open",
            "created_at": time.time(),
            "receipt": None,
        }
        self._tasks["_seq"] = seq
        self._tasks[task_id] = task
        self._save()
        return task

    def complete_task(self, task_id: str, receipt_notes: str = "") -> Dict[str, Any]:
        task = self._tasks.get(task_id)
        if task is None or task_id.startswith("_"):
            raise LedgerError("no such task: %r" % task_id)
        if task["status"] == "done":
            raise LedgerError("task %s is already done" % task_id)
        task["status"] = "done"
        task["receipt"] = {
            "completed_at": time.time(),
            "notes": receipt_notes,
        }
        self._save()
        return task

    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        if status is not None and status not in TASK_STATUSES:
            raise LedgerError("status %r not in %r" % (status, TASK_STATUSES))
        tasks = [t for tid, t in self._tasks.items() if not tid.startswith("_")]
        if status:
            tasks = [t for t in tasks if t["status"] == status]
        return sorted(tasks, key=lambda t: t["id"])

    # -- report ------------------------------------------------------------------
    def report(self) -> Dict[str, Any]:
        ranked = sorted(
            (self.score(s.name) for s in self.list_services()),
            key=lambda s: s["total"],
            reverse=True,
        )
        open_tasks = self.list_tasks(status="open")
        return {
            "services": ranked,
            "open_tasks": open_tasks,
            "open_task_count": len(open_tasks),
            "worst": ranked[0]["service"] if ranked else None,
        }
