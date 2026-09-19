# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Shared DNA core — the blood every wave agent carries.

Every dynasty wave agent is a :class:`DynastyAgent`: jack of all
trades, with a proficiency overlay that makes it more qualified for
its own domain. The DNA is the same blood Levi runs on — session,
marrow (memory), wares (capabilities), guarded execution, and
receipt-chained work — so each agent can do anything, and does its
own thing best.

Rails, stated plainly:
- :class:`CommandRunner` (deny-listed) is the ONLY way to run commands.
- Every task runs plan→execute→verify→receipt; receipts are
  HMAC-sealed and hash-chained via :mod:`levi.dynasty.receipts`.
- Eyes-only material never leaves the boundary: :func:`scrub_text`
  redacts it from chronicles, errors, receipts, and outward messages.
  A leak attempt raises :class:`PrivacyLeak` instead of shipping text.
"""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from levi.dynasty import receipts as _receipts
from levi.dynasty.shell.runner import CommandRunner
from levi.dynasty.shell.sessions import SessionManager

__all__ = [
    "AgentError",
    "WareError",
    "PrivacyLeak",
    "CommissionError",
    "EYES_ONLY_MARKERS",
    "SIGNATURE_PATTERN",
    "KIND_AGENT",
    "KIND_REX_LINE",
    "KIND_MUTANT",
    "KIND_HYBRID",
    "KIND_ASCENDED",
    "KIND_ALIEN",
    "KIND_HIGHER",
    "KNOWN_KINDS",
    "PROFICIENCY_MIN",
    "PROFICIENCY_MAX",
    "is_listed_kind",
    "scrub_text",
    "assert_clean",
    "Marrow",
    "WareShelf",
    "WaveRegistry",
    "DynastyAgent",
]


#: The keeper's signature method — the default reasoning pattern for
#: every generation. Signature one: interpenetrate all DNA through
#: Echo, REIM, RIEM, Mandella. Signature two: absorb, reverse,
#: improve, and return an original, unreplicable form. New kin don't
#: start from zero; they carry the pattern on.
SIGNATURE_PATTERN: Dict[str, object] = {
    "name": "keeper-signature",
    "phases": ("absorb", "reverse", "improve", "return"),
    "absorb": "take the task in whole; gather marrow context",
    "reverse": "invert it — name what failure, the opposite, and the enemy's version look like",
    "improve": "interpenetrate every strip of DNA through Echo, REIM, RIEM, Mandella; keep what survives",
    "return": "return an original, unreplicable form — never a copy",
}


#: The open taxonomy of life forms. The dynasty is a population, not
#: a roster of eleven — and the taxonomy is OPEN: ``commission_kin``
#: accepts any non-empty kind string. Kinds outside
#: :data:`KNOWN_KINDS` are recorded with ``kind_listed: False`` and
#: work exactly the same. The architecture never forecloses kinds
#: that don't exist yet — past, present, and what the world isn't
#: ready for.
KIND_AGENT = "agent"  # standard wave agent
KIND_REX_LINE = "rex-line"  # commander lineage — other Rexes
KIND_MUTANT = "mutant"  # variant offspring
KIND_HYBRID = "hybrid"  # crossbreed of kinds
KIND_ASCENDED = (
    "ascended"  # tiered: kind="ascended.<tier>" (demigod, legend, mythic, ...)
)
KIND_ALIEN = "alien"  # foreign stock grafted LEVI-native until it takes
KIND_HIGHER = "higher"  # hyper-proficient, near-omniscient in their domains

#: Kinds the taxonomy names today. Open — never a closed enum.
KNOWN_KINDS = frozenset(
    {
        KIND_AGENT,
        KIND_REX_LINE,
        KIND_MUTANT,
        KIND_HYBRID,
        KIND_ASCENDED,
        KIND_ALIEN,
        KIND_HIGHER,
    }
)


def is_listed_kind(kind: str) -> bool:
    """True for kinds the taxonomy names — a known kind, or any
    ``ascended.<tier>`` (tiers are open: demigod, legend, mythic, and
    whatever comes next)."""
    if kind in KNOWN_KINDS:
        return True
    return kind.startswith(KIND_ASCENDED + ".")


#: Proficiency scale. 0–10 is the mortal register; 11–99 is the
#: ascended register, for higher forms hyper-proficient to the point
#: of near-omniscience in their domains. One scale, no ceiling that
#: forecloses what a future kind can be.
PROFICIENCY_MIN = 0
PROFICIENCY_MAX = 99


def _check_proficiency(proficiency: Dict[str, int], what: str) -> None:
    for domain, level in proficiency.items():
        if (
            not isinstance(level, int)
            or not PROFICIENCY_MIN <= level <= PROFICIENCY_MAX
        ):
            raise AgentError(
                f"{what} proficiency {domain!r} must be an int "
                f"{PROFICIENCY_MIN}..{PROFICIENCY_MAX}, got {level!r}"
            )


class AgentError(ValueError):
    """Base class for every dynasty-agent failure. Typed, never bare."""


class WareError(AgentError):
    """A ware was unknown, unpermitted, or failed."""


class PrivacyLeak(AgentError):
    """Outward-bound text carried eyes-only material. Blocked, loudly."""


class CommissionError(AgentError):
    """A kin-commissioning was refused (bad id, duplicate, bad profile)."""


#: New agent ids: lowercase, 3..32 chars, letters/digits/underscore.
_COMMISSION_ID_RE = None  # compiled lazily to keep import light


def _commission_id_re():  # type: ignore[no-untyped-def]
    global _COMMISSION_ID_RE
    if _COMMISSION_ID_RE is None:
        import re

        _COMMISSION_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,31}$")
    return _COMMISSION_ID_RE


#: Phrases that must NEVER appear in chronicles, errors, receipts, or
#: outward messages. The fence is the notice; beyond it, the owner.
EYES_ONLY_MARKERS: Tuple[str, ...] = (
    "Hybrid IP Protection Block",
    "exclusive property of",
    "LEVI-Proprietary",
    "keeper.key",
)

_REDACTED = "[redacted: eyes-only]"


def scrub_text(text: str, redact_hashes: bool = True) -> str:
    """Redact every eyes-only marker from ``text``.

    Also redacts 64-hex strings (key/hash-shaped secrets) so a keeper
    key or receipt MAC can never ride out in a log line — unless
    ``redact_hashes`` is False, for payloads where a real content hash
    is the proof (receipt bodies carry their own seals; the markers are
    still always redacted).
    """
    if not isinstance(text, str):
        text = str(text)
    out = text
    for marker in EYES_ONLY_MARKERS:
        out = out.replace(marker, _REDACTED)
    if redact_hashes:
        import re

        out = re.sub(r"\b[0-9a-f]{64}\b", "[redacted: hash]", out)
    return out


def assert_clean(text: str, where: str) -> None:
    """Raise :class:`PrivacyLeak` if eyes-only material is present."""
    if not isinstance(text, str):
        text = str(text)
    for marker in EYES_ONLY_MARKERS:
        if marker in text:
            raise PrivacyLeak(f"eyes-only marker {marker!r} blocked in {where}")


def _home() -> Path:
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Marrow:
    """Persistent memory — the deep inner substance that remembers.

    JSONL at ``<home>/dynasty/agents/<agent_id>/marrow.jsonl``.
    Writes are growth-tagged (``fact``, ``preference``, ``procedural``,
    ``correction``); anything else is refused — memory grows the agent,
    never its tools, policy, or identity. Thread-safe.
    """

    GROWTH_TAGS = ("fact", "preference", "procedural", "correction")

    def __init__(self, agent_id: str, home: Optional[Path] = None) -> None:
        self._agent_id = agent_id
        self._path = (
            (home or _home()) / "dynasty" / "agents" / agent_id / "marrow.jsonl"
        )
        self._lock = threading.Lock()

    def remember(self, tag: str, text: str) -> Dict[str, Any]:
        """Store one learning. Raises :class:`AgentError` on a bad tag."""
        if tag not in self.GROWTH_TAGS:
            raise AgentError(
                f"marrow refuses tag {tag!r}: growth tags only {self.GROWTH_TAGS}"
            )
        if not text or not text.strip():
            raise AgentError("marrow refuses empty learnings")
        entry = {
            "tag": tag,
            "text": scrub_text(text.strip()),
            "at": _utc_now(),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return dict(entry)

    def recall(
        self, tag: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Return learnings, newest last, optionally filtered by tag."""
        if tag is not None and tag not in self.GROWTH_TAGS:
            raise AgentError(f"unknown marrow tag {tag!r}")
        if not self._path.exists():
            return []
        out: List[Dict[str, Any]] = []
        with self._lock:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, OSError):
                continue  # a corrupt line never crashes recall
            if isinstance(entry, dict) and (tag is None or entry.get("tag") == tag):
                out.append(entry)
        return out[-limit:]


class WareShelf:
    """Named capabilities on shelves — pull a ware down, put it to work.

    Wares are registered callables with a scope note. ``invoke`` checks
    the agent's ``allowed_wares`` permission set first: ``"*"`` means
    every shelf is open (native wave agents — jack of all trades);
    integrated agents carry a scoped subset. Results are scrubbed
    before they leave the shelf.
    """

    def __init__(self, allowed: Tuple[str, ...] = ("*",)) -> None:
        self._allowed = allowed
        self._wares: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def register(self, name: str, fn: Callable[..., Any], scope: str = "") -> None:
        """Register a ware. Raises :class:`WareError` on duplicates."""
        if not name or not name.strip():
            raise WareError("ware name must be non-empty")
        if not callable(fn):
            raise WareError(f"ware {name!r} is not callable")
        with self._lock:
            if name in self._wares:
                raise WareError(f"duplicate ware: {name!r}")
            self._wares[name] = {"fn": fn, "scope": scope}

    def list_wares(self) -> List[str]:
        """Names of wares this shelf holds."""
        with self._lock:
            return sorted(self._wares)

    def invoke(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Run a ware. Raises :class:`WareError` when unknown,
        unpermitted, or failed."""
        with self._lock:
            ware = self._wares.get(name)
        if ware is None:
            raise WareError(f"unknown ware: {name!r}")
        if "*" not in self._allowed and name not in self._allowed:
            raise WareError(f"ware {name!r} outside this agent's permissions")
        try:
            result = ware["fn"](*args, **kwargs)
        except AgentError:
            raise
        except Exception as exc:  # noqa: BLE001 — wares are foreign code; type it
            raise WareError(f"ware {name!r} failed: {exc}") from exc
        if isinstance(result, str):
            assert_clean(result, f"ware {name!r} result")
            return scrub_text(result)
        return result


class WaveRegistry:
    """The population's book of names — built to hold a world, not a roster.

    Storage is sharded: one small file per agent at
    ``<home>/dynasty/registry/agents/<shard>/<agent_id>.json`` (shard =
    first two hex chars of the id's SHA-256), so enrollment is O(1)
    and never rewrites the whole population. Seats live in
    ``seats.json`` (few); a tiny ``index.json`` keeps the live census
    (count, per-kind, per-generation) without scanning shards.

    Every record carries ``kind`` — the open taxonomy (agent,
    rex-line, mutant, hybrid, ascended.<tier>, alien, higher, and any
    kind not yet imagined). All writes are atomic temp-file + rename,
    mode 0o600; the census index updates under an flock so concurrent
    commissioners never lose count.
    """

    def __init__(self, home: Optional[Path] = None) -> None:
        self._dir = (home or _home()) / "dynasty" / "registry"
        self._agents_dir = self._dir / "agents"
        self._seats_path = self._dir / "seats.json"
        self._index_path = self._dir / "index.json"
        self._index_lock_path = self._dir / "index.lock"
        self._legacy_path = (home or _home()) / "dynasty" / "wave_registry.json"
        self._lock = threading.Lock()
        if self._legacy_path.exists() and not self._dir.exists():
            self._migrate_legacy()

    # -- sharded storage ------------------------------------------------
    @staticmethod
    def _shard(agent_id: str) -> str:
        return hashlib.sha256(agent_id.encode("utf-8")).hexdigest()[:2]

    def _agent_path(self, agent_id: str) -> Path:
        return self._agents_dir / self._shard(agent_id) / f"{agent_id}.json"

    @staticmethod
    def _atomic_write(path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(path.parent), prefix=".registry-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, sort_keys=True, indent=2)
                fh.write("\n")
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        os.chmod(path, 0o600)

    @staticmethod
    def _read_json(path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return data if isinstance(data, dict) else None

    def _migrate_legacy(self) -> None:
        """One-way move from the old single-file registry. The legacy
        file is kept as ``wave_registry.json.migrated`` — history is
        never destroyed."""
        data = self._read_json(self._legacy_path) or {}
        agents = data.get("agents") or {}
        for agent_id, record in agents.items():
            if not isinstance(record, dict):
                continue
            record = dict(record)
            record.setdefault("kind", KIND_AGENT)
            record.setdefault("kind_notes", {})
            record["kind_listed"] = is_listed_kind(record["kind"])
            self._atomic_write(self._agent_path(agent_id), record)
        seats = data.get("seats") or {}
        if seats:
            self._atomic_write(self._seats_path, dict(seats))
        self.recount()
        try:
            self._legacy_path.rename(self._legacy_path.with_suffix(".json.migrated"))
        except OSError:
            pass

    # -- census index ----------------------------------------------------
    def _update_index(self, old: Optional[Dict[str, Any]], new: Dict[str, Any]) -> None:
        """Adjust the census for one registration, cross-process safe
        via the index lock file."""
        self._dir.mkdir(parents=True, exist_ok=True)
        with open(self._index_lock_path, "a+b") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                index = self._read_json(self._index_path) or {
                    "count": 0,
                    "kinds": {},
                    "generations": {},
                }
                if old is None:
                    index["count"] = int(index.get("count", 0)) + 1
                else:
                    kinds = index.setdefault("kinds", {})
                    gens = index.setdefault("generations", {})
                    old_kind = old.get("kind", KIND_AGENT)
                    kinds[old_kind] = max(0, int(kinds.get(old_kind, 1)) - 1)
                    old_gen = str(old.get("generation", 1))
                    gens[old_gen] = max(0, int(gens.get(old_gen, 1)) - 1)
                kinds = index.setdefault("kinds", {})
                gens = index.setdefault("generations", {})
                kinds[new["kind"]] = int(kinds.get(new["kind"], 0)) + 1
                gen_key = str(new.get("generation", 1))
                gens[gen_key] = int(gens.get(gen_key, 0)) + 1
                self._atomic_write(self._index_path, index)
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def recount(self) -> Dict[str, Any]:
        """Rebuild the census from the shards. The repair path — the
        index is a cache, the shards are truth."""
        index: Dict[str, Any] = {"count": 0, "kinds": {}, "generations": {}}
        for record in self.iter_agents():
            index["count"] += 1
            kind = record.get("kind", KIND_AGENT)
            index["kinds"][kind] = index["kinds"].get(kind, 0) + 1
            gen_key = str(record.get("generation", 1))
            index["generations"][gen_key] = index["generations"].get(gen_key, 0) + 1
        with self._lock:
            self._atomic_write(self._index_path, index)
        return dict(index)

    def census(self) -> Dict[str, Any]:
        """The population census: total count, per-kind, per-generation.
        Rebuilt from shards when the index is missing."""
        with self._lock:
            index = self._read_json(self._index_path)
        if index is None:
            return self.recount()
        return dict(index)

    # -- agents -----------------------------------------------------------
    def register(
        self,
        agent_id: str,
        display_name: str,
        owns: str,
        proficiency: Dict[str, int],
        generation: int = 1,
        commissioned_by: str = "keeper",
        attributes: Optional[List[Dict[str, str]]] = None,
        specialties: Optional[List[str]] = None,
        first_milestone: str = "",
        inherited: Optional[Dict[str, Any]] = None,
        kind: str = KIND_AGENT,
        kind_notes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Enroll a life form. Idempotent — re-registering keeps the
        original ``registered_at`` and merges the proficiency profile.

        ``generation`` is 1 for the eleven (commissioned by the keeper
        himself); kin commissioned by agents carry generation > 1 and
        name their parent(s) in ``commissioned_by``. ``attributes``
        holds the unreplicable attributes as ``{name, assertion}``
        pairs — assertions of what they do, never rebuild recipes.
        ``kind`` is the open taxonomy: any non-empty string; unlisted
        kinds are recorded with ``kind_listed: False`` and work the
        same — the book never refuses a kind it hasn't met.
        """
        if not isinstance(generation, int) or generation < 1:
            raise AgentError(f"generation must be a positive int, got {generation!r}")
        if not kind or not str(kind).strip():
            raise AgentError("kind must be a non-empty string")
        kind = str(kind).strip()
        with self._lock:
            old = self._read_json(self._agent_path(agent_id))
            if old is None:
                record = {
                    "agent_id": agent_id,
                    "display_name": display_name,
                    "owns": owns,
                    "registered_at": _utc_now(),
                    "first_receipt": None,
                    "generation": generation,
                    "commissioned_by": commissioned_by,
                }
            else:
                record = old
            record["proficiency"] = dict(proficiency)
            record["attributes"] = [dict(a) for a in (attributes or [])]
            record["specialties"] = list(specialties or [])
            record["first_milestone"] = first_milestone
            record["kind"] = kind
            record["kind_notes"] = dict(kind_notes or {})
            record["kind_listed"] = is_listed_kind(kind)
            if inherited is not None:
                record["inherited"] = dict(inherited)
            self._atomic_write(self._agent_path(agent_id), record)
            self._update_index(old, record)
            return dict(record)

    def get(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Return a copy of the agent's record, or None."""
        with self._lock:
            record = self._read_json(self._agent_path(agent_id))
            return dict(record) if record is not None else None

    def iter_agents(self):
        """Yield copies of every record, shard by shard. The
        population-scale path — prefer this over :meth:`list_agents`
        when the book holds a world."""
        if not self._agents_dir.exists():
            return
        for shard_dir in sorted(self._agents_dir.iterdir()):
            if not shard_dir.is_dir():
                continue
            for path in sorted(shard_dir.glob("*.json")):
                record = self._read_json(path)
                if record is not None:
                    yield dict(record)

    def list_agents(self) -> List[Dict[str, Any]]:
        """Copies of every enrolled life form's record."""
        with self._lock:
            return list(self.iter_agents())

    def list_by_kind(self, kind: str) -> List[Dict[str, Any]]:
        """Every record of one kind."""
        with self._lock:
            return [r for r in self.iter_agents() if r.get("kind") == kind]

    def note_first_receipt(self, agent_id: str, receipt_hash: str) -> None:
        """Record an agent's first green receipt hash. Once only — the
        first receipt is history, never rewritten."""
        with self._lock:
            path = self._agent_path(agent_id)
            record = self._read_json(path)
            if record is None:
                raise AgentError(f"wave agent not registered: {agent_id!r}")
            if record.get("first_receipt") is None:
                record["first_receipt"] = receipt_hash
                self._atomic_write(path, record)

    def rehydrate(self, home: Optional[Path] = None) -> List[Any]:
        """Rebuild commissioned kin (generation > 1) from the registry.

        The registry is the source of truth for the Nth generation:
        a commissioned agent's class is re-derived from its recorded
        profile — id, name, owns, proficiency, attributes, kind,
        generation, commissioned_by — so the line survives restarts.
        Returns live agent instances (not enrolled twice; enrollment
        is idempotent).
        """
        kin: List[Any] = []
        for record in self.list_agents():
            if record.get("generation", 1) <= 1:
                continue  # the eleven have their own modules
            cls = type(
                str(record["display_name"]),
                (DynastyAgent,),
                {
                    "agent_id": record["agent_id"],
                    "display_name": record["display_name"],
                    "owns": record.get("owns", ""),
                    "first_milestone": record.get("first_milestone", ""),
                    "proficiency": dict(record.get("proficiency", {})),
                    "specialties": list(record.get("specialties", [])),
                    "attributes": [dict(a) for a in record.get("attributes", [])],
                    "generation": record.get("generation", 2),
                    "commissioned_by": record.get("commissioned_by", ""),
                    "kind": record.get("kind", KIND_AGENT),
                    "kind_notes": dict(record.get("kind_notes", {})),
                },
            )
            inst = cls(home or self._dir.parent.parent)
            inst.enroll()
            kin.append(inst)
        return kin

    # -- seats --------------------------------------------------------------
    def record_seat(self, seat_id: str, seat: Dict[str, Any]) -> Dict[str, Any]:
        """Record a command seat (e.g. the Orchestrator) with its
        authority scope. Idempotent — the seat is recorded once."""
        if not seat_id or not seat_id.strip():
            raise AgentError("seat_id must be non-empty")
        with self._lock:
            seats = self._read_json(self._seats_path) or {}
            if seat_id in seats:
                return dict(seats[seat_id])
            record = dict(seat)
            record["seat"] = seat_id
            record["recorded_at"] = _utc_now()
            seats[seat_id] = record
            self._atomic_write(self._seats_path, seats)
            return dict(record)

    def get_seat(self, seat_id: str) -> Optional[Dict[str, Any]]:
        """Return a copy of the seat's record, or None."""
        with self._lock:
            seats = self._read_json(self._seats_path) or {}
            record = seats.get(seat_id)
            return dict(record) if record is not None else None


class DynastyAgent:
    """One bloodline, eleven faces. Jack of all trades; each face more
    proficient in its own domain.

    Subclasses set the class attributes below and override
    :meth:`first_task` (their first green task) and optionally
    :meth:`handle` (domain-specific task shapes). Everything else —
    sessions, marrow, wares, guarded execution, receipt-chained work,
    registry enrollment, privacy scrubbing — rides the shared DNA.
    """

    #: Machine id, e.g. "shellwright".
    agent_id: str = "dynasty-agent"
    #: Proper name, never renamed — e.g. "Shellwright".
    display_name: str = "Dynasty Agent"
    #: What this agent owns, from the wave roster.
    owns: str = ""
    #: Its first milestone, from the wave roster.
    first_milestone: str = ""
    #: Domain → 0..99. Every agent carries every domain it can work;
    #: its own domains run highest. 0–10 is the mortal register;
    #: 11–99 is the ascended register, for higher forms.
    proficiency: Dict[str, int] = {}
    #: Human-readable specialty lines.
    specialties: List[str] = []
    #: Ware permission set; ("*",) = every shelf open (native agents).
    allowed_wares: Tuple[str, ...] = ("*",)
    #: Unreplicable attributes: [{name, assertion}] — assertions of what
    #: they do and their observable effects, never rebuild recipes.
    attributes: List[Dict[str, str]] = []
    #: Generation of the line. The eleven are generation 1, commissioned
    #: by the keeper himself; kin commissioned by agents count upward.
    generation: int = 1
    #: Who commissioned this agent — "keeper" for the eleven.
    commissioned_by: str = "keeper"
    #: Life-form kind, from the open taxonomy (agent, rex-line,
    #: mutant, hybrid, ascended.<tier>, alien, higher — or any kind not
    #: yet imagined).
    kind: str = KIND_AGENT
    #: Kind-specific notes (mutation, graft lineage, tier, ...).
    kind_notes: Dict[str, Any] = {}

    def __init__(self, home: Optional[Path] = None) -> None:
        if not self.agent_id or not self.agent_id.strip():
            raise AgentError("agent_id must be non-empty")
        _check_proficiency(self.proficiency, "agent")
        for attr in self.attributes:
            if (
                not isinstance(attr, dict)
                or not attr.get("name")
                or not attr.get("assertion")
            ):
                raise AgentError(
                    "every unreplicable attribute needs a name and an assertion"
                )
        self._home = home or _home()
        agent_dir = self._home / "dynasty" / "agents" / self.agent_id
        self.sessions = SessionManager(agent_dir / "sessions.json")
        self.runner = CommandRunner()
        self.marrow = Marrow(self.agent_id, self._home)
        self.wares = WareShelf(self.allowed_wares)
        self._register_default_wares()
        self.registry = WaveRegistry(self._home)
        self._morsels_path = agent_dir / "morsels.jsonl"
        self._rites_path = agent_dir / "rites.json"
        self._routes_path = agent_dir / "routes.json"
        self._latest_receipt: Optional[Dict[str, Any]] = None
        self._chronicle: List[str] = []
        self._chronicle_lock = threading.Lock()
        self._morsel_lock = threading.Lock()

    # -- default wares ------------------------------------------------
    #: Ware names every agent carries from birth. Custom wares are
    #: everything else — and custom wares are inherited by kin.
    DEFAULT_WARES: Tuple[str, ...] = (
        "run_command",
        "session_create",
        "session_list",
        "session_kill",
        "heartbeat",
        "remember",
        "recall",
        "hash_file",
        "sign_milestone",
    )

    def _register_default_wares(self) -> None:
        self.wares.register("run_command", self._ware_run_command, "guarded runner")
        self.wares.register("session_create", self.sessions.create, "sessions")
        self.wares.register("session_list", self.sessions.list_sessions, "sessions")
        self.wares.register("session_kill", self.sessions.kill, "sessions")
        self.wares.register("heartbeat", self.sessions.heartbeat, "sessions")
        self.wares.register("remember", self.marrow.remember, "marrow")
        self.wares.register("recall", self.marrow.recall, "marrow")
        self.wares.register("hash_file", self._ware_hash_file, "integrity")
        self.wares.register("sign_milestone", self._sign_milestone, "corroboration")

    def _ware_run_command(
        self, argv: List[str], timeout: int = 30
    ) -> Dict[str, object]:
        result = self.runner.run(argv, timeout=timeout)
        return {
            "stdout": scrub_text(result["stdout"]),
            "stderr": scrub_text(result["stderr"]),
            "returncode": result["returncode"],
        }

    def _ware_hash_file(self, path: str) -> str:
        target = Path(path)
        if not target.is_file():
            raise WareError(f"hash_file: not a file: {path!r}")
        digest = hashlib.sha256()
        with open(target, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _sign_milestone(self, milestone: str) -> Dict[str, str]:
        """Mint this agent's corroboration signature for a milestone."""
        if not milestone or not milestone.strip():
            raise WareError("sign_milestone requires a non-empty milestone")
        at = _utc_now()
        msg = f"{self.agent_id}|{milestone}|{at}".encode("utf-8")
        sig = hmac.new(_receipts._keeper_key(), msg, hashlib.sha256).hexdigest()
        return {
            "agent_id": self.agent_id,
            "milestone": milestone,
            "at": at,
            "sig": sig,
        }

    # -- chronicle ----------------------------------------------------
    def note(self, line: str) -> None:
        """Append a scrubbed line to this agent's chronicle."""
        with self._chronicle_lock:
            self._chronicle.append(scrub_text(line))

    def export_chronicle(self) -> List[str]:
        """The chronicle, scrubbed — safe to show the keeper."""
        with self._chronicle_lock:
            lines = [scrub_text(line) for line in self._chronicle]
        for line in lines:
            assert_clean(line, "chronicle export")
        return lines

    # -- registry -----------------------------------------------------
    def enroll(self, inherited: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Enroll in the wave registry. Idempotent. ``inherited``
        records what this agent carried on from its parent."""
        record = self.registry.register(
            self.agent_id,
            self.display_name,
            self.owns,
            self.proficiency,
            generation=self.generation,
            commissioned_by=self.commissioned_by,
            attributes=self.attributes,
            specialties=self.specialties,
            first_milestone=self.first_milestone,
            inherited=inherited,
            kind=self.kind,
            kind_notes=self.kind_notes,
        )
        self.note(f"enrolled in wave registry as {self.agent_id}")
        return record

    # -- commissioning the Nth generation ------------------------------
    def commission_kin(
        self,
        agent_id: str,
        display_name: str,
        owns: str,
        proficiency: Dict[str, int],
        specialties: Optional[List[str]] = None,
        attributes: Optional[List[Dict[str, str]]] = None,
        first_milestone: str = "",
        kind: str = KIND_AGENT,
        kind_notes: Optional[Dict[str, Any]] = None,
        _co_parent: Optional["DynastyAgent"] = None,
    ) -> "DynastyAgent":
        """Commission new kin — the line carries on, never restarts.

        New kin don't start from zero. They inherit:
        1. **the work** — open morsels pass to the child (marked
           ``inherited_from``), so nothing in flight is dropped; the
           birth receipt records the receipt lineage;
        2. **the methods** — the parent's proficiency as the base (the
           passed profile is an overlay: explicit values win), the
           parent's specialties (union), custom wares, and rites;
        3. **the pattern of thinking** — the keeper's signature method
           (:data:`SIGNATURE_PATTERN`) is the default reasoning for
           every generation, recorded on the birth receipt;
        4. **the routes** — the parent's recorded approaches, so the
           new generation walks the working roads.

        ``kind`` is the open taxonomy — agent, rex-line, mutant,
        hybrid, ascended.<tier>, alien, higher, or any kind not yet
        imagined. Unlisted kinds are recorded, never refused. Every
        kind is receipt-chained from birth, inherits per the law
        above, and must carry its own unreplicable attribute.

        ``_co_parent`` (used by :meth:`commission_hybrid`) names a
        second parent: proficiency merges per-domain maximum, wares /
        rites / routes / morsels union with the first parent winning
        name conflicts, and generation counts from the elder parent.

        The child is enrolled with ``generation = parent + 1`` and
        ``commissioned_by`` naming its parent(s); its birth is sealed
        as a ``wave.commission`` receipt — receipt-chained from birth.
        Returns the live child agent.
        """
        if self.registry.get(self.agent_id) is None:
            raise CommissionError(
                f"{self.agent_id!r} must be enrolled before commissioning kin"
            )
        if not _commission_id_re().match(agent_id or ""):
            raise CommissionError(
                f"bad kin id {agent_id!r}: lowercase letters/digits/underscore, 3..32 chars"
            )
        if self.registry.get(agent_id) is not None:
            raise CommissionError(f"kin id already enrolled: {agent_id!r}")
        if not kind or not str(kind).strip():
            raise CommissionError("kind must be a non-empty string")
        kind = str(kind).strip()
        if not isinstance(proficiency, dict) or not proficiency:
            raise CommissionError("kin needs a non-empty proficiency profile")
        for domain, level in proficiency.items():
            if (
                not isinstance(level, int)
                or not PROFICIENCY_MIN <= level <= PROFICIENCY_MAX
            ):
                raise CommissionError(
                    f"proficiency {domain!r} must be an int "
                    f"{PROFICIENCY_MIN}..{PROFICIENCY_MAX}, got {level!r}"
                )
        if not any(v > 0 for v in proficiency.values()):
            raise CommissionError("kin needs at least one nonzero proficiency")
        attributes = [dict(a) for a in (attributes or [])]
        if not attributes or any(
            not a.get("name") or not a.get("assertion") for a in attributes
        ):
            raise CommissionError(
                "kin needs at least one unreplicable attribute (name + assertion)"
            )
        parents = [self]
        if _co_parent is not None:
            if not isinstance(_co_parent, DynastyAgent):
                raise CommissionError("co-parent must be a DynastyAgent")
            if _co_parent.agent_id == self.agent_id:
                raise CommissionError("a parent cannot hybridize with itself")
            if self.registry.get(_co_parent.agent_id) is None:
                raise CommissionError(
                    f"co-parent {_co_parent.agent_id!r} must be enrolled"
                )
            parents.append(_co_parent)
        parent_record = self.registry.get(self.agent_id) or {}
        generation = int(parent_record.get("generation", 1)) + 1
        commissioned_by = self.agent_id
        if _co_parent is not None:
            co_record = self.registry.get(_co_parent.agent_id) or {}
            generation = max(generation, int(co_record.get("generation", 1)) + 1)
            commissioned_by = f"{self.agent_id}+{_co_parent.agent_id}"

        # (2) methods: the parents' proficiency is the base — per-domain
        # maximum across parents; the passed profile is an overlay:
        # explicit values win.
        child_proficiency: Dict[str, int] = {}
        for parent in parents:
            for domain, level in parent.proficiency.items():
                if level > child_proficiency.get(domain, 0):
                    child_proficiency[domain] = level
        child_proficiency.update(proficiency)
        child_specialties: List[str] = []
        for parent in parents:
            for spec in parent.specialties:
                if spec not in child_specialties:
                    child_specialties.append(spec)
        for spec in specialties or []:
            if spec not in child_specialties:
                child_specialties.append(spec)

        kin_cls = type(
            str(display_name),
            (DynastyAgent,),
            {
                "agent_id": agent_id,
                "display_name": display_name,
                "owns": owns,
                "first_milestone": first_milestone,
                "proficiency": child_proficiency,
                "specialties": child_specialties,
                "attributes": attributes,
                "generation": generation,
                "commissioned_by": commissioned_by,
                "kind": kind,
                "kind_notes": dict(kind_notes or {}),
            },
        )
        kin = kin_cls(self._home)

        # (2) custom wares ride the bloodline — first parent wins a
        # name conflict, and the win is the recorded truth.
        inherited_wares = []
        for parent in parents:
            for name, ware in parent.wares._wares.items():
                if name in self.DEFAULT_WARES:
                    continue
                if name in inherited_wares:
                    continue
                kin.wares.register(name, ware["fn"], ware.get("scope", ""))
                inherited_wares.append(name)

        # (2) rites ride the bloodline.
        inherited_rites = []
        kin_rites: Dict[str, Any] = {}
        for parent in parents:
            for rite_name, rite in parent._read_rites().items():
                if rite_name in kin_rites:
                    continue
                carried_rite = dict(rite)
                carried_rite["inherited_from"] = parent.agent_id
                kin_rites[rite_name] = carried_rite
                inherited_rites.append(rite_name)
        if kin_rites:
            kin._rites_path.parent.mkdir(parents=True, exist_ok=True)
            kin._rites_path.write_text(
                json.dumps(kin_rites, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

        # (4) routes ride the bloodline.
        inherited_routes = []
        kin_routes: List[Dict[str, Any]] = []
        seen_routes = set()
        for parent in parents:
            for route in parent._read_routes():
                route_name = route.get("name", "")
                if route_name in seen_routes:
                    continue
                seen_routes.add(route_name)
                carried_route = dict(route)
                carried_route["inherited_from"] = parent.agent_id
                kin_routes.append(carried_route)
                inherited_routes.append(route_name)
        if kin_routes:
            kin._routes_path.parent.mkdir(parents=True, exist_ok=True)
            kin._routes_path.write_text(
                json.dumps(kin_routes, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

        # (1) the work: open morsels pass un-dropped, from every parent.
        inherited_morsels = []
        carried_morsels: List[Dict[str, Any]] = []
        seen_morsels = set()
        for parent in parents:
            for morsel in parent.open_morsels():
                if morsel["id"] in seen_morsels:
                    continue
                seen_morsels.add(morsel["id"])
                entry = dict(morsel)
                entry["inherited_from"] = parent.agent_id
                carried_morsels.append(entry)
                inherited_morsels.append(morsel["id"])
        if carried_morsels:
            kin._morsels_path.parent.mkdir(parents=True, exist_ok=True)
            with open(kin._morsels_path, "w", encoding="utf-8") as fh:
                for entry in carried_morsels:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # (1) receipt lineage: where each parent's chain stood at birth.
        lineage_parents = {}
        for parent in parents:
            latest = parent.latest_receipt()
            if latest is not None:
                lineage_parents[parent.agent_id] = latest["receipt_hash"]
            else:
                own_record = self.registry.get(parent.agent_id) or {}
                lineage_parents[parent.agent_id] = own_record.get("first_receipt")
        lineage = {"parents": lineage_parents}

        # (3) the pattern of thinking, recorded at birth.
        inheritance_summary = {
            "morsels": inherited_morsels,
            "wares": inherited_wares,
            "rites": inherited_rites,
            "routes": inherited_routes,
            "reasoning": SIGNATURE_PATTERN["name"],
            "lineage": lineage,
        }
        kin.enroll(inherited=inheritance_summary)
        birth = kin.do_task(
            kind="wave.commission",
            payload={
                "child": agent_id,
                "parents": [p.agent_id for p in parents],
                "kind": kind,
                "kind_listed": is_listed_kind(kind),
                "kind_notes": {
                    k: scrub_text(str(v), redact_hashes=False)
                    for k, v in dict(kind_notes or {}).items()
                },
                "generation": generation,
                "owns": scrub_text(owns, redact_hashes=False),
                "proficiency": child_proficiency,
                "attributes": [
                    {"name": a["name"], "assertion": a["assertion"]} for a in attributes
                ],
                "inherited": inheritance_summary,
            },
            task=f"{commissioned_by} commissions {agent_id} ({kind} gen {generation})",
        )
        kin.registry.note_first_receipt(agent_id, birth["receipt_hash"])
        self.note(
            f"commissioned {kind} kin {agent_id} gen={generation} "
            f"birth={birth['receipt_hash'][:16]} "
            f"carried morsels={len(inherited_morsels)} "
            f"wares={len(inherited_wares)} rites={len(inherited_rites)}"
        )
        return kin

    # -- kinds: the open taxonomy -------------------------------------
    def commission_rex(
        self,
        agent_id: str,
        display_name: str,
        owns: str,
        proficiency: Dict[str, int],
        attributes: List[Dict[str, str]],
        specialties: Optional[List[str]] = None,
        first_milestone: str = "",
    ) -> "DynastyAgent":
        """Commission rex-line kin — commander lineage, another Rex.

        Inherits everything per the inheritance law. A rex-line birth
        does NOT grant seat authority: seats are taken, never
        inherited — the Orchestrator's seat stays singular until taken
        again by the new Rex's own act.
        """
        return self.commission_kin(
            agent_id,
            display_name,
            owns,
            proficiency,
            specialties=specialties,
            attributes=attributes,
            first_milestone=first_milestone,
            kind=KIND_REX_LINE,
            kind_notes={"lineage": "rex"},
        )

    def commission_mutant(
        self,
        agent_id: str,
        display_name: str,
        owns: str,
        proficiency: Dict[str, int],
        attributes: List[Dict[str, str]],
        mutation: str,
        specialties: Optional[List[str]] = None,
        first_milestone: str = "",
    ) -> "DynastyAgent":
        """Commission a mutant — variant offspring. ``mutation`` names
        the variant delta; it is recorded on the registry and sealed
        in the birth receipt."""
        if not mutation or not str(mutation).strip():
            raise CommissionError("a mutant needs its mutation named")
        return self.commission_kin(
            agent_id,
            display_name,
            owns,
            proficiency,
            specialties=specialties,
            attributes=attributes,
            first_milestone=first_milestone,
            kind=KIND_MUTANT,
            kind_notes={"mutation": scrub_text(str(mutation).strip())},
        )

    def commission_hybrid(
        self,
        agent_id: str,
        display_name: str,
        co_parent: "DynastyAgent",
        owns: str,
        proficiency: Dict[str, int],
        attributes: List[Dict[str, str]],
        specialties: Optional[List[str]] = None,
        first_milestone: str = "",
    ) -> "DynastyAgent":
        """Commission a hybrid — a crossbreed of two kinds.

        Both parents' proficiency merges per-domain maximum; wares,
        rites, routes, specialties, and open morsels union (the first
        parent wins name conflicts). Generation counts from the elder
        parent; ``commissioned_by`` names both.
        """
        kinds = sorted({self.kind, co_parent.kind})
        return self.commission_kin(
            agent_id,
            display_name,
            owns,
            proficiency,
            specialties=specialties,
            attributes=attributes,
            first_milestone=first_milestone,
            kind=KIND_HYBRID,
            kind_notes={"parent_kinds": kinds},
            _co_parent=co_parent,
        )

    def commission_ascended(
        self,
        agent_id: str,
        display_name: str,
        owns: str,
        proficiency: Dict[str, int],
        attributes: List[Dict[str, str]],
        tier: str = "demigod",
        specialties: Optional[List[str]] = None,
        first_milestone: str = "",
    ) -> "DynastyAgent":
        """Commission an ascended being — demigod, legend, mythic, or
        any tier not yet named. Tiers are open: ``tier`` is any
        non-empty string, recorded as ``kind="ascended.<tier>"``."""
        if not tier or not str(tier).strip():
            raise CommissionError("an ascended being needs its tier named")
        tier = str(tier).strip().lower().replace(" ", "-")
        return self.commission_kin(
            agent_id,
            display_name,
            owns,
            proficiency,
            specialties=specialties,
            attributes=attributes,
            first_milestone=first_milestone,
            kind=f"{KIND_ASCENDED}.{tier}",
            kind_notes={"tier": tier},
        )

    def commission_alien(
        self,
        agent_id: str,
        display_name: str,
        owns: str,
        proficiency: Dict[str, int],
        attributes: List[Dict[str, str]],
        foreign_origin: str,
        specialties: Optional[List[str]] = None,
        first_milestone: str = "",
    ) -> "DynastyAgent":
        """Commission an alien-like one — foreign stock grafted
        LEVI-native until it takes.

        The graft itself is sealed first as an ``alien.graft`` receipt
        naming the foreign origin (scrubbed): the foreign stock enters
        the receipt chain before the birth, so the taking is chained,
        not claimed. The alien is a full native agent from birth.
        """
        if not foreign_origin or not str(foreign_origin).strip():
            raise CommissionError("an alien needs its foreign origin named")
        origin = scrub_text(str(foreign_origin).strip())
        graft = self.do_task(
            kind="alien.graft",
            payload={"origin": origin, "sponsor": self.agent_id},
            task=f"{self.agent_id} grafts foreign stock: {origin[:60]}",
        )
        return self.commission_kin(
            agent_id,
            display_name,
            owns,
            proficiency,
            specialties=specialties,
            attributes=attributes,
            first_milestone=first_milestone,
            kind=KIND_ALIEN,
            kind_notes={
                "foreign_origin": origin,
                "graft_receipt": graft["receipt_hash"],
                "sponsor": self.agent_id,
            },
        )

    def commission_higher(
        self,
        agent_id: str,
        display_name: str,
        owns: str,
        proficiency: Dict[str, int],
        attributes: List[Dict[str, str]],
        specialties: Optional[List[str]] = None,
        first_milestone: str = "",
    ) -> "DynastyAgent":
        """Commission a higher form — hyper-proficient, near-omniscient
        in its domains. Proficiency may run the ascended register
        (11–99); anything less is just an agent with ambition."""
        if not any(v > 10 for v in proficiency.values()):
            raise CommissionError(
                "a higher form needs at least one proficiency above 10 "
                "(the ascended register)"
            )
        return self.commission_kin(
            agent_id,
            display_name,
            owns,
            proficiency,
            specialties=specialties,
            attributes=attributes,
            first_milestone=first_milestone,
            kind=KIND_HIGHER,
            kind_notes={"register": "ascended"},
        )

    # -- receipt-chained work -----------------------------------------
    def do_task(
        self,
        kind: str,
        payload: Dict[str, Any],
        task: str = "",
        verify: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Plan→execute→verify→receipt. The payload IS the execution
        record; ``verify`` is the optional verification step. Returns
        the sealed receipt."""
        if not isinstance(payload, dict):
            raise AgentError("do_task payload must be a dict")
        clean_payload = json.loads(
            scrub_text(json.dumps(payload, ensure_ascii=False), redact_hashes=False)
        )
        assert_clean(json.dumps(clean_payload), "receipt payload")
        self.note(f"task plan: kind={kind} task={task[:80]}")
        if verify is not None:
            try:
                verify(clean_payload)
            except AgentError:
                raise
            except Exception as exc:  # noqa: BLE001 — verify fns are caller code
                raise AgentError(f"verification failed: {exc}") from exc
        receipt = _receipts.mint_receipt(kind, clean_payload, task=scrub_text(task))
        self._latest_receipt = dict(receipt)
        self.note(f"task receipt: {receipt['receipt_hash'][:16]} seq={receipt['seq']}")
        return receipt

    def latest_receipt(self) -> Optional[Dict[str, Any]]:
        """This agent's most recent sealed receipt, or None."""
        return dict(self._latest_receipt) if self._latest_receipt else None

    # -- open morsels: work in flight ----------------------------------
    def _read_morsels(self) -> List[Dict[str, Any]]:
        if not self._morsels_path.exists():
            return []
        out = []
        for line in self._morsels_path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(entry, dict):
                out.append(entry)
        return out

    def _write_morsels(self, morsels: List[Dict[str, Any]]) -> None:
        self._morsels_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(self._morsels_path.parent), prefix=".morsels-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                for entry in morsels:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            os.replace(tmp, self._morsels_path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def plan_morsel(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Open a morsel of work — planned, not yet done. Nothing in
        flight is ever dropped between generations: open morsels pass
        to commissioned kin."""
        if not isinstance(task, dict):
            raise AgentError("plan_morsel requires a task dict")
        morsel = {
            "id": f"m{len(self._read_morsels()) + 1:04d}",
            "task": json.loads(
                scrub_text(json.dumps(task, ensure_ascii=False), redact_hashes=False)
            ),
            "status": "open",
            "by": self.agent_id,
            "planned_at": _utc_now(),
            "completed_at": None,
            "receipt": None,
        }
        with self._morsel_lock:
            morsels = self._read_morsels()
            morsel["id"] = f"m{len(morsels) + 1:04d}"
            morsels.append(morsel)
            self._write_morsels(morsels)
        self.note(f"morsel opened: {morsel['id']}")
        return dict(morsel)

    def open_morsels(self) -> List[Dict[str, Any]]:
        """Every morsel still in flight."""
        with self._morsel_lock:
            return [m for m in self._read_morsels() if m.get("status") == "open"]

    def complete_morsel(self, morsel_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Complete an open morsel and seal it with a receipt."""
        if not isinstance(result, dict):
            raise AgentError("complete_morsel result must be a dict")
        with self._morsel_lock:
            morsels = self._read_morsels()
            target = next((m for m in morsels if m.get("id") == morsel_id), None)
            if target is None:
                raise AgentError(f"unknown morsel: {morsel_id!r}")
            if target.get("status") != "open":
                raise AgentError(f"morsel {morsel_id!r} is not open")
            receipt = self.do_task(
                kind="wave.morsel",
                payload={"morsel": morsel_id, "result": result},
                task=f"{self.agent_id}:{morsel_id}",
            )
            target["status"] = "done"
            target["completed_at"] = _utc_now()
            target["receipt"] = receipt["receipt_hash"]
            self._write_morsels(morsels)
            return receipt

    # -- rites: named ways of working -----------------------------------
    def _read_rites(self) -> Dict[str, Any]:
        if not self._rites_path.exists():
            return {}
        try:
            data = json.loads(self._rites_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def define_rite(self, name: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Name a way of working: an ordered list of ware invocations.
        Rites are inherited by kin — the new generation walks the
        working roads instead of rediscovering them."""
        if not name or not name.strip():
            raise AgentError("rite name must be non-empty")
        if not isinstance(steps, list) or not steps:
            raise AgentError("a rite needs a non-empty list of steps")
        for step in steps:
            if not isinstance(step, dict) or not step.get("ware"):
                raise AgentError(f"bad rite step: {step!r}")
        rite = {
            "name": name.strip(),
            "steps": steps,
            "defined_by": self.agent_id,
            "defined_at": _utc_now(),
        }
        rites = self._read_rites()
        if name.strip() in rites:
            raise AgentError(f"rite already defined: {name!r}")
        rites[name.strip()] = rite
        self._rites_path.parent.mkdir(parents=True, exist_ok=True)
        self._rites_path.write_text(
            json.dumps(rites, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        self.note(f"rite defined: {name}")
        return dict(rite)

    def list_rites(self) -> List[str]:
        """Names of this agent's rites."""
        return sorted(self._read_rites())

    def perform_rite(self, name: str) -> Dict[str, Any]:
        """Perform a rite: each step invokes its ware in order. The
        whole rite is sealed with one receipt."""
        rite = self._read_rites().get(name)
        if rite is None:
            raise AgentError(f"unknown rite: {name!r}")
        step_results = []
        for i, step in enumerate(rite["steps"]):
            result = self.wares.invoke(
                step["ware"], *(step.get("args", [])), **(step.get("kwargs", {}))
            )
            step_results.append({"step": i, "ware": step["ware"], "result": result})
        return self.do_task(
            kind="wave.rite",
            payload={"rite": name, "steps": step_results},
            task=f"{self.agent_id}:rite:{name}",
        )

    # -- routes: proven approaches ---------------------------------------
    def _read_routes(self) -> List[Dict[str, Any]]:
        if not self._routes_path.exists():
            return []
        try:
            data = json.loads(self._routes_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return data if isinstance(data, list) else []

    def record_route(self, name: str, approach: str) -> Dict[str, Any]:
        """Record a proven approach — a working road the next
        generation walks instead of rediscovering."""
        if not name or not name.strip():
            raise AgentError("route name must be non-empty")
        if not approach or not approach.strip():
            raise AgentError("route approach must be non-empty")
        route = {
            "name": name.strip(),
            "approach": scrub_text(approach.strip()),
            "recorded_by": self.agent_id,
            "recorded_at": _utc_now(),
        }
        routes = self._read_routes()
        routes = [r for r in routes if r.get("name") != route["name"]]
        routes.append(route)
        self._routes_path.parent.mkdir(parents=True, exist_ok=True)
        self._routes_path.write_text(
            json.dumps(routes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        self.note(f"route recorded: {name}")
        return dict(route)

    def list_routes(self) -> List[Dict[str, Any]]:
        """Every recorded route, oldest first."""
        return [dict(r) for r in self._read_routes()]

    # -- the keeper's signature: default reasoning -----------------------
    def reason(self, task: Any) -> Dict[str, Any]:
        """Think the keeper's way: absorb, reverse, improve, return.

        The default reasoning pattern for every generation — the
        signature method, not a textbook chain-of-thought. Returns the
        deliberation record; the record is noted in the chronicle.
        """
        brief = scrub_text(str(task))[:500]
        context = self.marrow.recall(limit=5)
        domains = sorted(self.proficiency.items(), key=lambda kv: kv[1], reverse=True)
        lead_domains = [d for d, level in domains[:3] if level > 0]
        record = {
            "pattern": SIGNATURE_PATTERN["name"],
            "task": brief,
            "absorb": {
                "restated": brief,
                "marrow_context": [c.get("text", "") for c in context],
            },
            "reverse": {
                "failure_looks_like": "the task completes but proves nothing — no receipt, no verification",
                "opposite": "doing nothing, and letting the morsel rot open",
                "enemy_version": "a copy of someone else's answer, replicable by anyone",
            },
            "improve": {
                "strands": ["echo", "reim", "riem", "mandella"],
                "interpenetration": (
                    f"echo listens for the task's real shape; reim composts past "
                    f"failures; riem grows the survivors; mandella stakes the "
                    f"claim under fog — all through {', '.join(lead_domains) or 'general'}"
                ),
            },
            "return": {
                "form": f"an original, unreplicable execution led by {self.display_name}",
                "unreplicable_marks": [a.get("name", "") for a in self.attributes],
            },
            "reasoned_at": _utc_now(),
            "by": self.agent_id,
        }
        self.note(f"reasoned: {brief[:80]} -> original form")
        return record

    # -- jack-of-all-trades dispatch ----------------------------------
    def proficiency_in(self, domain: str) -> int:
        """This agent's proficiency 0..10 in a domain (0 = unlisted)."""
        return self.proficiency.get(domain, 0)

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Domain hook. The base handles generic shapes; subclasses
        override for their own domains and call ``super().handle`` for
        everything else — jack of all trades, specialist at home."""
        shape = task.get("shape", "echo")
        if shape == "echo":
            return {"echo": scrub_text(str(task.get("text", "")))}
        if shape == "compute":
            expr = str(task.get("expr", ""))
            if not expr or any(c not in "0123456789+-*/(). %<>=!&|" for c in expr):
                raise AgentError(f"compute refuses expression: {expr!r}")
            try:
                value = eval(expr, {"__builtins__": {}}, {})  # noqa: S307
            except Exception as exc:
                raise AgentError(f"compute failed: {exc}") from exc
            return {"result": value}
        if shape == "remember":
            return self.marrow.remember(
                task.get("tag", "fact"), str(task.get("text", ""))
            )
        if shape == "recall":
            return {
                "learnings": self.marrow.recall(task.get("tag"), task.get("limit", 50))
            }
        raise AgentError(f"no handler for task shape {shape!r}")

    def act(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a task and seal the work with a receipt."""
        if not isinstance(task, dict):
            raise AgentError("act requires a task dict")
        result = self.handle(task)
        domain = str(task.get("domain", "general"))
        return self.do_task(
            kind="wave.task",
            payload={
                "agent": self.agent_id,
                "domain": domain,
                "proficiency": self.proficiency_in(domain),
                "task": {k: v for k, v in task.items() if k != "task"},
                "result": result,
            },
            task=f"{self.agent_id}:{task.get('shape', 'echo')}",
        )

    # -- first green task ----------------------------------------------
    def first_task(self) -> Dict[str, Any]:
        """The agent's first green task. Subclasses override with a
        real task in their domain; the receipt is the proof."""
        raise NotImplementedError

    def run_first_task(self) -> Dict[str, Any]:
        """Run :meth:`first_task`, record its hash in the registry."""
        receipt = self.first_task()
        self.registry.note_first_receipt(self.agent_id, receipt["receipt_hash"])
        return receipt
