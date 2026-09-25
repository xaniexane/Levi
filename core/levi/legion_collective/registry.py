"""Workstream registry — the "1 is all, all is one" record.

One shared JSON store (local file, stdlib-only, no network) listing every
KFX² workstream, its lifecycle status, its capability manifest, and its
twin. Sibling workstreams read and write the same format — no silo
formats, no private protocols.

Paired-mind doctrine: promoting a workstream from planned to active takes
a PAIR — a proposer and a distinct verifier. One identity cannot promote
alone. Retiring is explicit (confirm=True); nothing retires by default.

Register only what exists. Everything not yet built stays "planned".
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from levi.legion_collective import conventions as C

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")

_ENTRY_FIELDS = (
    "slug",
    "title",
    "plan_doc",
    "status",
    "surface",
    "twin",
    "capabilities",
    "registered_by",
    "registered_at",
    "history",
)


class RegistryError(ValueError):
    """Anything wrong with a registry read or write."""


def default_store_path() -> Path:
    override = os.environ.get(C.STORE_ENV_VAR)
    if override:
        return Path(override)
    return Path.home() / C.DEFAULT_STORE_DIRNAME / C.REGISTRY_FILENAME


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _blank_store() -> dict:
    return {
        "schema_version": C.SCHEMA_VERSION,
        "workstreams": {},
    }


def _validate_entry(entry: dict) -> dict:
    if not isinstance(entry, dict):
        raise RegistryError("entry must be a dict")
    unknown = set(entry) - set(_ENTRY_FIELDS)
    if unknown:
        raise RegistryError(f"unknown entry fields: {sorted(unknown)}")
    slug = entry.get("slug")
    if not isinstance(slug, str) or not _SLUG_RE.match(slug):
        raise RegistryError(f"bad slug: {slug!r}")
    title = entry.get("title")
    if not isinstance(title, str) or not title.strip():
        raise RegistryError("title must be a non-empty string")
    status = entry.get("status", C.STATUS_PLANNED)
    if status not in C.STATUSES:
        raise RegistryError(f"bad status: {status!r}")
    surface = entry.get("surface", C.SURFACE_GENERAL)
    if surface not in C.SURFACES:
        raise RegistryError(f"bad surface: {surface!r}")
    twin = entry.get("twin")
    if twin is not None and (not isinstance(twin, str) or not _SLUG_RE.match(twin)):
        raise RegistryError(f"bad twin slug: {twin!r}")
    caps = entry.get("capabilities", [])
    if not isinstance(caps, list):
        raise RegistryError("capabilities must be a list")
    return {
        "slug": slug,
        "title": title.strip(),
        "plan_doc": entry.get("plan_doc"),
        "status": status,
        "surface": surface,
        "twin": twin,
        "capabilities": caps,
        "registered_by": entry.get("registered_by"),
        "registered_at": entry.get("registered_at"),
        "history": list(entry.get("history") or []),
    }


class WorkstreamRegistry:
    """Local JSON registry of the fourteen KFX² workstreams."""

    def __init__(self, store_path: Path | str | None = None) -> None:
        self.store_path = Path(store_path) if store_path else default_store_path()
        self._data = _blank_store()
        self._load()

    # -- persistence ----------------------------------------------------
    def _load(self) -> None:
        if self.store_path.exists():
            raw = json.loads(self.store_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or "workstreams" not in raw:
                raise RegistryError(f"corrupt store: {self.store_path}")
            self._data = raw

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.store_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, self.store_path)  # atomic on POSIX

    # -- reads (the shared format every sibling can parse) --------------
    def dump(self) -> dict:
        """The whole store as plain JSON-serializable dicts. No private protocol."""
        return json.loads(json.dumps(self._data))

    def get(self, slug: str) -> dict | None:
        entry = self._data["workstreams"].get(slug)
        return json.loads(json.dumps(entry)) if entry else None

    def list(self, status: str | None = None) -> list[dict]:
        entries = list(self._data["workstreams"].values())
        if status is not None:
            if status not in C.STATUSES:
                raise RegistryError(f"bad status: {status!r}")
            entries = [e for e in entries if e["status"] == status]
        return sorted(entries, key=lambda e: e["slug"])

    # -- writes (opt-in; nothing auto-registers) -------------------------
    def register(self, entry: dict, actor: str) -> dict:
        clean = _validate_entry(entry)
        slug = clean["slug"]
        if slug in self._data["workstreams"]:
            raise RegistryError(f"already registered: {slug}")
        twin = clean["twin"]
        if twin and twin not in self._data["workstreams"]:
            raise RegistryError(f"twin not registered: {twin}")
        clean["registered_by"] = actor
        clean["registered_at"] = _utcnow()
        clean["history"].append(
            {"at": clean["registered_at"], "by": actor, "event": "registered"}
        )
        self._data["workstreams"][slug] = clean
        self._save()
        return self.get(slug)

    def _record(self, slug: str, actor: str, event: str) -> dict:
        entry = self._data["workstreams"].get(slug)
        if entry is None:
            raise RegistryError(f"unknown workstream: {slug}")
        entry["history"].append({"at": _utcnow(), "by": actor, "event": event})
        self._save()
        return self.get(slug)

    def set_capabilities(self, slug: str, capabilities: list, actor: str) -> dict:
        """Replace a workstream's capability list (owner declares, registry records)."""
        entry = self._data["workstreams"].get(slug)
        if entry is None:
            raise RegistryError(f"unknown workstream: {slug}")
        if not isinstance(capabilities, list):
            raise RegistryError("capabilities must be a list")
        entry["capabilities"] = capabilities
        self._save()
        return self._record(
            slug, actor, f"manifest attached ({len(capabilities)} capabilities)"
        )

    # -- paired promotion: proposer + distinct verifier ------------------
    def propose(self, slug: str, actor: str) -> dict:
        entry = self._data["workstreams"].get(slug)
        if entry is None:
            raise RegistryError(f"unknown workstream: {slug}")
        if entry["status"] != C.STATUS_PLANNED:
            raise RegistryError(f"only planned workstreams can be proposed: {slug}")
        entry["proposed_by"] = actor
        return self._record(slug, actor, "proposed")

    def verify(self, slug: str, actor: str) -> dict:
        entry = self._data["workstreams"].get(slug)
        if entry is None:
            raise RegistryError(f"unknown workstream: {slug}")
        proposer = entry.pop("proposed_by", None)
        if proposer is None:
            raise RegistryError(f"no open proposal for: {slug}")
        if actor == proposer:
            raise RegistryError(
                "paired mind: proposer and verifier must be different identities"
            )
        entry["status"] = C.STATUS_ACTIVE
        self._save()
        return self._record(slug, actor, f"verified (proposed by {proposer})")

    def retire(self, slug: str, actor: str, confirm: bool = False) -> dict:
        if not confirm:
            raise RegistryError("retire() requires explicit confirm=True")
        entry = self._data["workstreams"].get(slug)
        if entry is None:
            raise RegistryError(f"unknown workstream: {slug}")
        entry["status"] = C.STATUS_RETIRED
        entry.pop("proposed_by", None)
        self._save()
        return self._record(slug, actor, "retired")

    # -- KFX² seed: the fourteen workstreams, only what exists -----------
    def seed_kfx2(self, actor: str = "legion-collective") -> list[str]:
        """Register the fourteen KFX² workstreams.

        Titles come from the plan docs; capabilities are left empty for each
        owning workstream to declare. Only LEGION is active (this build);
        everything else is planned until its own milestone-1 lands.
        Idempotent: already-registered slugs are skipped.
        """
        seeds = [
            (
                "legion",
                "KFX2 on Legion — the intelligence-universe launch",
                "LEGION_KFX2_PRODUCTION.md",
                C.STATUS_ACTIVE,
                C.SURFACE_GENERAL,
            ),
            (
                "brainux",
                "KFX2 on the model-runners — Ollama, LM Studio, Jan",
                "BRAINUX_KFX2_PRODUCTION.md",
                C.STATUS_PLANNED,
                C.SURFACE_GENERAL,
            ),
            (
                "builders",
                "KFX2 — AI app-builder brands",
                "BUILDERS_KFX2_PRODUCTION.md",
                C.STATUS_PLANNED,
                C.SURFACE_GENERAL,
            ),
            (
                "demandpulse",
                "DemandPulse KFX2 — trend/demand sensing engine",
                "DEMANDPULSE_KFX2_PRODUCTION.md",
                C.STATUS_PLANNED,
                C.SURFACE_GENERAL,
            ),
            (
                "dispatch",
                "KFX2 on the transportation/dispatch lane",
                "DISPATCH_KFX2_PRODUCTION.md",
                C.STATUS_PLANNED,
                C.SURFACE_GENERAL,
            ),
            (
                "dynasty",
                "KFX2 — Dynasty wave orchestration (capability-level, eyes-only)",
                "DYNASTY_KFX2_PRODUCTION.md",
                C.STATUS_PLANNED,
                C.SURFACE_GENERAL,
            ),
            (
                "echoverse",
                "Echoverse KFX2 — the SFW companion track",
                "ECHOVERSE_KFX2_PRODUCTION.md",
                C.STATUS_PLANNED,
                C.SURFACE_GENERAL,
            ),
            (
                "hicomb",
                "HICOMB — KFX2 teardown + production-phase plan",
                "HICOMB_KFX2_PRODUCTION.md",
                C.STATUS_PLANNED,
                C.SURFACE_GENERAL,
            ),
            (
                "hub",
                "HUB KFX2 — teardown, synthesis & production plan",
                "HUB_KFX2_PRODUCTION.md",
                C.STATUS_PLANNED,
                C.SURFACE_GENERAL,
            ),
            (
                "legal",
                "KFX2 on the legal AI giants — Harvey, CoCounsel",
                "LEGAL_KFX2_PRODUCTION.md",
                C.STATUS_PLANNED,
                C.SURFACE_GENERAL,
            ),
            (
                "lwp",
                "KFX2 on the AI writing editors — Sudowrite, NovelAI",
                "LWP_KFX2_PRODUCTION.md",
                C.STATUS_PLANNED,
                C.SURFACE_GENERAL,
            ),
            (
                "mesh",
                "KFX2 — Off-Grid Mesh Tower Hardware",
                "MESH_KFX2_PRODUCTION.md",
                C.STATUS_PLANNED,
                C.SURFACE_GENERAL,
            ),
            (
                "pl05",
                "PL-05 KFX2 — Veil Messenger + Creator Services",
                "PL05_KFX2_PRODUCTION.md",
                C.STATUS_PLANNED,
                C.SURFACE_GENERAL,
            ),
            (
                "plaiground",
                "Plaiground KFX2 — the adult/NSFW track",
                "PLAIGROUND_CRUSHON_KFX2.md+PLAIGROUND_GIANTS_KFX2.md",
                C.STATUS_PLANNED,
                C.SURFACE_ADULT,
            ),
        ]
        added = []
        for slug, title, plan_doc, status, surface in seeds:
            if slug in self._data["workstreams"]:
                continue
            self.register(
                {
                    "slug": slug,
                    "title": title,
                    "plan_doc": plan_doc,
                    "status": status,
                    "surface": surface,
                },
                actor=actor,
            )
            added.append(slug)
        return added
