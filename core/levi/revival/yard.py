"""yard — the revival yard's raising pipeline.

The Forge canon (docs/LEXICON.md, commit f011bb0): "things begun and left
to die get raised again." This module is the yard itself — the procedure by
which a hunt find becomes a LEVI-native recreation:

    intake   hunt build_queue.jsonl items -> YardCandidate (adapted, never rewritten)
    study    the warden records what died, what it taught, and the LEVI-native name
    scaffold a module skeleton honoring the revival pattern is written
    prove    revival laws checked (stdlib-only, original never copied/masked,
             LEVI-native identity), module importable
    shelve   green raisings are marked ready-for-review (never claimed reviewed)

The stone ledger (``stone.jsonl``) records EVERY raising — what died, what it
taught, what rose — with provenance on everything. It is append-only:
nothing is ever deleted. Failed raisings are composted through REIM
(``levi.organs.reim.compost_failure``), never erased.

Revival laws enforced here:
  1. Original recreations with LEVI's twist — the LEVI name is never the dead
     software's name, and the module never claims the original's identity.
  2. Never copies, never masks, never reverse-engineered: studied from
     research notes, rebuilt stdlib-only, local-first.
  3. The stone never forgets: append-only ledger; compost, don't delete.

Safety contract (binding):
  - Intake adapts the hunt output format (``levi.perpetual.hunt``) without
    touching it; a missing/foreign hunt module degrades to a direct read of
    ``<home>/perpetual/build_queue.jsonl``.
  - Scaffolding writes only under an explicit ``target_dir`` — there is no
    default that resolves to the real repo. Roots ``/`` and the real $HOME
    are refused outright.
  - ``prove`` executes the candidate module file to import it; only run it
    on raisings the yard itself scaffolded or that the keeper trusts.

stdlib-only. Local filesystem only; no network, no daemons.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "Yard",
    "YardCandidate",
    "Raising",
    "RevivalLawsError",
    "YardRefusedError",
    "intake_candidates",
    "check_revival_laws",
    "compost_raising",
    "main",
]


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class YardRefusedError(RuntimeError):
    """Raised when the yard refuses a target, a transition, or bad input."""


class RevivalLawsError(RuntimeError):
    """Raised when a module violates the revival laws at prove time."""


# --------------------------------------------------------------------------
# Home / paths
# --------------------------------------------------------------------------


def yard_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    """Resolve the yard's working home.

    Explicit ``home`` wins, then ``LEVI_YARD_HOME``, then the durable
    ``~/.levi/revival/yard``. The stone ledger lives here — outside the repo
    so raisings survive repo surgery.
    """
    if home is not None:
        return Path(home).expanduser()
    env = os.environ.get("LEVI_YARD_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".levi" / "revival" / "yard"


_STONE = "stone.jsonl"
_STATE = "state.json"
_RAISED = "raised.jsonl"

# --------------------------------------------------------------------------
# Stages
# --------------------------------------------------------------------------

STAGE_QUEUED = "queued"
STAGE_STUDIED = "studied"
STAGE_RECREATING = "recreating"
STAGE_GREEN = "green"
STAGE_SHELVED = "shelved"
STAGE_COMPOSTED = "composted"

_STAGES = (
    STAGE_QUEUED,
    STAGE_STUDIED,
    STAGE_RECREATING,
    STAGE_GREEN,
    STAGE_SHELVED,
    STAGE_COMPOSTED,
)

_BUILDABLE = ("load-bearing", "useful-pattern")

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


# --------------------------------------------------------------------------
# Candidates + raisings
# --------------------------------------------------------------------------


@dataclass
class YardCandidate:
    """One hunt find admitted to the yard.

    Adapted from the hunt output format (``levi.perpetual.hunt`` build queue
    items), never a rewrite of it: ``wave_id``, ``record_id``, ``title``,
    ``kind``, ``rating`` come straight from the queue; ``decline``,
    ``mechanism``, ``sources`` are enriched from the wave's pending archive
    records when available.
    """

    wave_id: str
    record_id: str
    title: str
    kind: str
    rating: str
    hard_route: bool = False
    decline: str = ""
    mechanism: str = ""
    sources: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "YardCandidate":
        return cls(
            wave_id=str(data.get("wave_id", "")),
            record_id=str(data.get("record_id", "")),
            title=str(data.get("title", "")),
            kind=str(data.get("kind", "")),
            rating=str(data.get("rating", "")),
            hard_route=bool(data.get("hard_route", False)),
            decline=str(data.get("decline", "")),
            mechanism=str(data.get("mechanism", "")),
            sources=list(data.get("sources", [])),
            provenance=dict(data.get("provenance", {})),
        )


@dataclass
class Raising:
    """One raising in flight: a candidate being reborn LEVI-native."""

    id: str
    candidate: YardCandidate
    stage: str = STAGE_QUEUED
    levi_name: str = ""
    module: str = ""  # dotted path, e.g. "levi.revival.foomancy"
    title: str = ""  # LEVI-native capability title
    flair: str = ""
    what_died: str = ""
    decline: str = ""
    what_it_taught: str = ""
    evidence: str = ""  # green evidence, e.g. "pytest ...: 12 passed"
    compost: Optional[Dict[str, Any]] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["candidate"] = self.candidate.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Raising":
        cand = data.get("candidate", {})
        return cls(
            id=str(data.get("id", "")),
            candidate=YardCandidate.from_dict(cand),
            stage=str(data.get("stage", STAGE_QUEUED)),
            levi_name=str(data.get("levi_name", "")),
            module=str(data.get("module", "")),
            title=str(data.get("title", "")),
            flair=str(data.get("flair", "")),
            what_died=str(data.get("what_died", "")),
            decline=str(data.get("decline", "")),
            what_it_taught=str(data.get("what_it_taught", "")),
            evidence=str(data.get("evidence", "")),
            compost=data.get("compost"),
            events=list(data.get("events", [])),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
        )


# --------------------------------------------------------------------------
# Intake — adapt the hunt output format, never rewrite it
# --------------------------------------------------------------------------


def _hunt_build_queue(
    home: "str | os.PathLike[str] | None" = None,
) -> List[Dict[str, Any]]:
    """Read build queue items via the hunt module, or by direct file read.

    The hunt module (``levi.perpetual.hunt``) is adapted, not rewritten: we
    call its ``read_build_queue`` when importable, and fall back to reading
    ``<home>/perpetual/build_queue.jsonl`` directly when it isn't.
    """
    try:
        from levi.perpetual.hunt import read_build_queue

        return read_build_queue(home)
    except Exception:
        pass
    base = (
        Path(home).expanduser() / ".levi"
        if home is not None
        else (Path.home() / ".levi")
    )
    path = base / "perpetual" / "build_queue.jsonl"
    items: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except ValueError:
            continue
    return items


def _hunt_pending_records(
    home: "str | os.PathLike[str] | None" = None,
) -> Dict[str, Dict[str, Any]]:
    """Map record_id -> pending archive record dict (enrichment for intake).

    Reads ``<home>/perpetual/pending/<wave>.jsonl`` — the validated
    ``ArchiveRecord`` payloads the hunts wrote. Best-effort: a missing pending
    dir simply yields no enrichment.
    """
    base = (
        Path(home).expanduser() / ".levi"
        if home is not None
        else (Path.home() / ".levi")
    )
    pending = base / "perpetual" / "pending"
    out: Dict[str, Dict[str, Any]] = {}
    if not pending.is_dir():
        return out
    for p in sorted(pending.glob("*.jsonl")):
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            rid = rec.get("id")
            if rid and rid not in out:
                out[rid] = rec
    return out


def intake_candidates(
    home: "str | os.PathLike[str] | None" = None,
    only_buildable: bool = True,
    known_record_ids: Optional[set] = None,
) -> List[YardCandidate]:
    """Admit hunt finds as yard candidates.

    Reads the hunt build queue (adapting its format) and enriches with the
    pending archive records. Only buildable ratings (``load-bearing``,
    ``useful-pattern``) are admitted by default — inspirational finds stay in
    the Archive as inspiration, not build orders. Items whose ``record_id``
    is in ``known_record_ids`` are skipped so intake stays idempotent.
    """
    known = known_record_ids or set()
    pending = _hunt_pending_records(home)
    out: List[YardCandidate] = []
    for item in _hunt_build_queue(home):
        if not isinstance(item, dict):
            continue
        rid = str(item.get("record_id", ""))
        if not rid:
            continue
        key = "%s:%s" % (item.get("wave_id", ""), rid)
        if key in known or rid in known:
            continue
        if only_buildable and str(item.get("rating", "")) not in _BUILDABLE:
            continue
        rec = pending.get(rid, {})
        prov = rec.get("provenance", {}) if isinstance(rec, dict) else {}
        out.append(
            YardCandidate(
                wave_id=str(item.get("wave_id", "")),
                record_id=rid,
                title=str(item.get("title", "")),
                kind=str(item.get("kind", "")),
                rating=str(item.get("rating", "")),
                hard_route=bool(item.get("hard_route", False)),
                decline=str(rec.get("decline", "")),
                mechanism=str(rec.get("mechanism", "")),
                sources=list(rec.get("sources", []))
                if isinstance(rec.get("sources"), list)
                else [],
                provenance={
                    "wave_id": str(item.get("wave_id", "")),
                    "record_id": rid,
                    "found_date": str(prov.get("found_date", ""))
                    if isinstance(prov, dict)
                    else "",
                    "research_slug": str(prov.get("research_slug", ""))
                    if isinstance(prov, dict)
                    else "",
                },
            )
        )
    return out


# --------------------------------------------------------------------------
# Revival laws — checked at prove time
# --------------------------------------------------------------------------

_MANIFEST_KEYS = ("module", "levi_name", "title", "flair", "origin")


def _stdlib_names() -> set:
    return set(getattr(sys, "stdlib_module_names", ())) | {"builtins", "__future__"}


def check_revival_laws(
    module_path: "str | os.PathLike[str]",
    candidate: YardCandidate,
    manifest: Dict[str, Any],
) -> List[str]:
    """Check a raising's module against the revival laws.

    Returns a list of violations (empty means lawful):
      1. identity law — the LEVI name is never the dead software's name and
         the module never claims the original's identity;
      2. purity law — stdlib-only imports (``levi.*`` allowed as LEVI-native
         dependencies; third-party imports are a mask, not a recreation);
      3. manifest law — a ``__revival_manifest__`` dict names the module,
         its LEVI name, title, flair, and studied origin.
    """
    violations: List[str] = []
    src = Path(module_path).read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return ["module does not parse: %s" % exc]

    # --- manifest law ---
    missing = [k for k in _MANIFEST_KEYS if not manifest.get(k)]
    if missing:
        violations.append("manifest missing keys: %s" % ", ".join(missing))

    # --- identity law: never the original's name, never its mask ---
    levi_name = str(manifest.get("levi_name", "")).strip()
    dead_title = (candidate.title or "").strip()
    if levi_name and dead_title and levi_name.lower() == dead_title.lower():
        violations.append(
            "identity law: LEVI name %r is the dead software's own name — a mask, not a recreation"
            % levi_name
        )
    doc = ast.get_docstring(tree) or ""
    dead_key = dead_title.lower().replace(" ", "")
    if (
        dead_key
        and dead_key in levi_name.lower().replace(" ", "")
        and dead_title.lower() in levi_name.lower()
    ):
        pass  # substring overlap alone is not identity theft; exact-match rule above governs
    if dead_title and ("i am %s" % dead_title.lower()) in doc.lower():
        violations.append("identity law: module claims to BE the original")

    # --- purity law: stdlib-only ---
    stdlib = _stdlib_names()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            tops = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import inside the package — allowed
                continue
            tops = [(node.module or "").split(".")[0]]
        else:
            continue
        for top in tops:
            if not top:
                continue
            if top == "levi" or top in stdlib:
                continue
            violations.append(
                "purity law: non-stdlib import %r — recreations are stdlib-only" % top
            )
    return violations


def _load_manifest(module_path: Path) -> Tuple[Dict[str, Any], Any]:
    """Import a module file and return (manifest, module object)."""
    spec = importlib.util.spec_from_file_location(
        "levi_revival_yard_probe", str(module_path)
    )
    if spec is None or spec.loader is None:
        raise RevivalLawsError("cannot load module file: %s" % module_path)
    mod = importlib.util.module_from_spec(spec)
    # dataclasses (and friends) resolve their module through sys.modules —
    # register during exec, then drop it so probes never leak.
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(spec.name, None)
    manifest = getattr(mod, "__revival_manifest__", None)
    if not isinstance(manifest, dict):
        raise RevivalLawsError(
            "module %s exposes no __revival_manifest__ dict" % module_path
        )
    return manifest, mod


# --------------------------------------------------------------------------
# Scaffold — the revival pattern as a starting shape
# --------------------------------------------------------------------------

_SCAFFOLD = '''"""{title} — a LEVI-native recreation.

Studied from: {dead_title} ({dead_kind}).
What it taught: {taught}

This is an ORIGINAL LEVI work: the capability was studied from research
notes and rebuilt from scratch in LEVI's own voice — never a copy, never a
mask, never reverse-engineered. stdlib-only, local-first.

Raised in the revival yard ({raising_id}) from hunt find
{record_id} (wave {wave_id}).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


__revival_manifest__ = {{
    "module": "{module}",
    "levi_name": "{levi_name}",
    "title": "{title}",
    "flair": "{flair}",
    "origin": "levi-revival/{slug}",
    "status": "raised",
}}


@dataclass
class {classname}:
    """The recreated capability. Fill in as the raising matures."""

    name: str = "{levi_name}"
    notes: List[str] = field(default_factory=list)

    def describe(self) -> Dict[str, Any]:
        """One-paragraph account of what this module does, in LEVI's voice."""
        return {{
            "levi_name": self.name,
            "capability": {title!r},
            "studied_from": {dead_title!r},
            "status": "raised — maturing under the warden",
        }}
'''


def _refuse_root(target: Path) -> None:
    resolved = target.resolve()
    home = Path.home().resolve()
    if resolved == Path("/").resolve():
        raise YardRefusedError("refusing to scaffold at filesystem root")
    if resolved == home:
        raise YardRefusedError("refusing to scaffold at the real HOME")


def scaffold_module(
    raising: Raising,
    target_dir: "str | os.PathLike[str]",
    overwrite: bool = False,
) -> Path:
    """Write the raising's module skeleton honoring the revival pattern.

    ``target_dir`` is REQUIRED and explicit — there is no default that
    resolves to the real repo; ``/`` and the real ``$HOME`` are refused.
    The skeleton is a starting shape, not the recreation: the warden (or the
    keeper's crew) fills in the capability, then ``prove`` checks the laws.
    """
    if not raising.module:
        raise YardRefusedError("raising %s has no module path yet" % raising.id)
    if not raising.levi_name:
        raise YardRefusedError(
            "raising %s has no LEVI name yet — study first" % raising.id
        )
    target = Path(target_dir).expanduser()
    _refuse_root(target)
    stem = raising.module.split(".")[-1]
    if not _ID_RE.match(stem):
        raise YardRefusedError("bad module stem: %r" % stem)
    target.mkdir(parents=True, exist_ok=True)
    path = target / ("%s.py" % stem)
    if path.exists() and not overwrite:
        raise YardRefusedError("module file already exists: %s" % path)
    words = re.findall(r"[A-Za-z0-9]+", raising.levi_name)
    classname = "".join(w[:1].upper() + w[1:] for w in words) or "Raised"
    text = _SCAFFOLD.format(
        title=raising.title or raising.levi_name,
        dead_title=raising.candidate.title or "the dead find",
        dead_kind=raising.candidate.kind or "software",
        taught=(raising.what_it_taught or raising.candidate.mechanism or "—"),
        raising_id=raising.id,
        record_id=raising.candidate.record_id,
        wave_id=raising.candidate.wave_id,
        module=raising.module,
        levi_name=raising.levi_name,
        flair=raising.flair or "A dead shape, reborn in LEVI's own voice.",
        slug=re.sub(r"[^a-z0-9]+", "-", raising.levi_name.lower()).strip("-")
        or "raised",
        classname=classname,
    )
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# Compost — failed raisings via REIM, never erased
# --------------------------------------------------------------------------


def compost_raising(
    raising: Raising, reason: str, severity: str = "medium"
) -> Dict[str, Any]:
    """Compost a failed raising through REIM.

    The compost record is returned for the stone ledger. Nothing about the
    raising is deleted — the failure, its lesson, and its reusable inverse
    all stay on the stone.
    """
    try:
        from levi.organs.reim import compost_failure
    except Exception as exc:  # REIM unavailable: record the failure plainly
        return {
            "organ": "reim",
            "source": "revival-yard",
            "what": "raising %s failed: %s" % (raising.id, reason),
            "context": "REIM unavailable (%s); failure recorded raw on the stone" % exc,
            "ts": _now(),
            "severity": severity,
            "compost_class": "unknown",
            "lesson": "the yard must survive even its organs' absence",
            "reusable": False,
            "provenance": {"source": "revival-yard", "raising": raising.id},
        }
    record = {
        "source": "revival-yard",
        "what": "raising %s (%s) failed: %s"
        % (raising.id, raising.candidate.record_id, reason),
        "context": "candidate %r from wave %s; stage was %s"
        % (raising.candidate.title, raising.candidate.wave_id, raising.stage),
        "ts": _now(),
        "severity": severity,
    }
    return compost_failure(record)


# --------------------------------------------------------------------------
# The Yard
# --------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Yard:
    """The revival yard: intake -> raising -> stone ledger.

    State (``state.json``) is the working record of in-flight raisings; the
    stone ledger (``stone.jsonl``) is the append-only history. The ledger has
    NO delete path — every method here only appends.
    """

    def __init__(self, home: "str | os.PathLike[str] | None" = None):
        self.home = yard_home(home)
        self.home.mkdir(parents=True, exist_ok=True)
        self._state_path = self.home / _STATE
        self._stone_path = self.home / _STONE
        self._raised_path = self.home / _RAISED
        self._state = self._load_state()

    # -- persistence ------------------------------------------------------

    def _load_state(self) -> Dict[str, Any]:
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            data = {}
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("raisings", {})
        data.setdefault("counter", 0)
        data.setdefault("seen_record_ids", [])
        return data

    def _save_state(self) -> None:
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._state, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(tmp, self._state_path)

    # -- the stone: append-only -------------------------------------------

    def _stone_append(
        self, event: str, raising: Raising, detail: Dict[str, Any]
    ) -> None:
        entry = {
            "ts": _now(),
            "event": event,
            "raising": raising.id,
            "stage": raising.stage,
            "what_died": raising.what_died or raising.candidate.title,
            "what_it_taught": raising.what_it_taught or raising.candidate.mechanism,
            "what_rose": {
                "levi_name": raising.levi_name,
                "module": raising.module,
                "title": raising.title,
            },
            "detail": detail,
            "provenance": {
                "wave_id": raising.candidate.wave_id,
                "record_id": raising.candidate.record_id,
                "sources": raising.candidate.sources,
                **raising.candidate.provenance,
            },
        }
        with open(self._stone_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        raising.events.append({"ts": entry["ts"], "event": event, "detail": detail})
        raising.updated_at = entry["ts"]

    def ledger(self) -> List[Dict[str, Any]]:
        """Read the whole stone, oldest first. There is no delete path."""
        try:
            lines = self._stone_path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        out = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out

    # -- raisings ----------------------------------------------------------

    def _next_id(self) -> str:
        self._state["counter"] += 1
        self._save_state()
        return "yard-%04d" % self._state["counter"]

    def get(self, raising_id: str) -> Raising:
        try:
            return Raising.from_dict(self._state["raisings"][raising_id])
        except KeyError:
            raise YardRefusedError("no such raising: %s" % raising_id) from None

    def _put(self, raising: Raising) -> None:
        self._state["raisings"][raising.id] = raising.to_dict()
        self._save_state()

    def list_raisings(self, stage: Optional[str] = None) -> List[Raising]:
        out = [Raising.from_dict(d) for d in self._state["raisings"].values()]
        if stage:
            out = [r for r in out if r.stage == stage]
        return sorted(out, key=lambda r: r.id)

    # -- intake ------------------------------------------------------------

    def intake(
        self,
        hunt_home: "str | os.PathLike[str] | None" = None,
        only_buildable: bool = True,
    ) -> List[Raising]:
        """Admit new hunt finds. Idempotent: known record_ids are skipped."""
        seen = set(self._state["seen_record_ids"])
        candidates = intake_candidates(
            hunt_home, only_buildable=only_buildable, known_record_ids=seen
        )
        admitted: List[Raising] = []
        now = _now()
        for cand in candidates:
            rid = "%s:%s" % (cand.wave_id, cand.record_id)
            raising = Raising(
                id=self._next_id(),
                candidate=cand,
                created_at=now,
                updated_at=now,
            )
            self._put(raising)
            self._stone_append("intake", raising, {"candidate": cand.to_dict()})
            self._state["seen_record_ids"].append(rid)
            admitted.append(raising)
        self._save_state()
        return admitted

    # -- study --------------------------------------------------------------

    def study(
        self,
        raising_id: str,
        *,
        levi_name: str,
        title: str,
        flair: str,
        module: str,
        what_died: str,
        decline: str,
        what_it_taught: str,
    ) -> Raising:
        """Record the study: what died, what it taught, what it will be.

        ``module`` is the dotted path the recreation will live at
        (``levi.revival.<stem>``). The LEVI name must already differ from the
        dead software's name — the identity law starts at study time.
        """
        raising = self.get(raising_id)
        if raising.stage != STAGE_QUEUED:
            raise YardRefusedError(
                "raising %s is at stage %r; study applies to %r only"
                % (raising_id, raising.stage, STAGE_QUEUED)
            )
        for label, value in (
            ("levi_name", levi_name),
            ("title", title),
            ("flair", flair),
            ("module", module),
            ("what_died", what_died),
            ("decline", decline),
            ("what_it_taught", what_it_taught),
        ):
            if not value or not value.strip():
                raise YardRefusedError("study requires %r" % label)
        dead = (raising.candidate.title or "").strip().lower()
        if levi_name.strip().lower() == dead and dead:
            raise YardRefusedError(
                "identity law: the LEVI name %r is the dead software's own name"
                % levi_name
            )
        if not module.startswith("levi.revival."):
            raise YardRefusedError(
                "module %r must live under levi.revival.* — the yard raises revivals"
                % module
            )
        raising.levi_name = levi_name.strip()
        raising.title = title.strip()
        raising.flair = flair.strip()
        raising.module = module.strip()
        raising.what_died = what_died.strip()
        raising.decline = decline.strip()
        raising.what_it_taught = what_it_taught.strip()
        raising.stage = STAGE_STUDIED
        self._put(raising)
        self._stone_append(
            "studied",
            raising,
            {"levi_name": raising.levi_name, "module": raising.module},
        )
        return raising

    # -- scaffold -----------------------------------------------------------

    def scaffold(
        self,
        raising_id: str,
        target_dir: "str | os.PathLike[str]",
        overwrite: bool = False,
    ) -> Path:
        """Write the module skeleton honoring the revival pattern."""
        raising = self.get(raising_id)
        if raising.stage != STAGE_STUDIED:
            raise YardRefusedError(
                "raising %s is at stage %r; scaffold applies to %r only"
                % (raising_id, raising.stage, STAGE_STUDIED)
            )
        path = scaffold_module(raising, target_dir, overwrite=overwrite)
        raising.stage = STAGE_RECREATING
        self._put(raising)
        self._stone_append("recreating", raising, {"module_file": str(path)})
        return path

    # -- prove --------------------------------------------------------------

    def prove(
        self,
        raising_id: str,
        module_file: "str | os.PathLike[str]",
        evidence: str = "",
    ) -> Raising:
        """Prove a raising against the revival laws.

        Checks the module's manifest and imports (stdlib-only, identity law)
        and imports the module to confirm it loads. On success the raising
        goes green and ``evidence`` (e.g. a pytest result line) is recorded.
        On failure the raising is COMPOSTED through REIM — the stone keeps
        the failure and its lesson; nothing is deleted.
        """
        raising = self.get(raising_id)
        if raising.stage != STAGE_RECREATING:
            raise YardRefusedError(
                "raising %s is at stage %r; prove applies to %r only"
                % (raising_id, raising.stage, STAGE_RECREATING)
            )
        path = Path(module_file)
        if not path.is_file():
            return self._fail(raising, "module file missing: %s" % path)
        try:
            manifest, _mod = _load_manifest(path)
        except Exception as exc:
            return self._fail(raising, "module would not load: %s" % exc)
        violations = check_revival_laws(path, raising.candidate, manifest)
        if violations:
            return self._fail(
                raising, "revival laws violated: " + "; ".join(violations)
            )
        # The manifest must agree with the raising's studied identity.
        for key in ("levi_name", "title", "module"):
            got = str(manifest.get(key, "")).strip()
            want = getattr(raising, key).strip()
            if got != want:
                return self._fail(
                    raising,
                    "manifest %r is %r but the raising studied %r" % (key, got, want),
                )
        raising.stage = STAGE_GREEN
        raising.evidence = evidence.strip()
        self._put(raising)
        self._stone_append(
            "green",
            raising,
            {
                "module_file": str(path),
                "evidence": raising.evidence or "module-level laws check",
            },
        )
        return raising

    def _fail(self, raising: Raising, reason: str) -> Raising:
        """Compost a failed raising. The stone keeps everything."""
        raising.compost = compost_raising(raising, reason)
        raising.stage = STAGE_COMPOSTED
        self._put(raising)
        self._stone_append(
            "composted", raising, {"reason": reason, "compost": raising.compost}
        )
        return raising

    def compost(self, raising_id: str, reason: str) -> Raising:
        """The warden's explicit compost: a raising the keeper abandons."""
        raising = self.get(raising_id)
        if raising.stage in (STAGE_SHELVED, STAGE_COMPOSTED):
            raise YardRefusedError(
                "raising %s is already %r — the stone does not rewind"
                % (raising_id, raising.stage)
            )
        if not reason or not reason.strip():
            raise YardRefusedError("compost requires a reason — the stone records why")
        return self._fail(raising, reason.strip())

    # -- shelve ---------------------------------------------------------------

    def shelve(self, raising_id: str):
        """Mark a green raising ready for the keeper's review.

        Returns a ``levi.revival.registry.RevivalEntry`` for the shelved
        module — the yard marks ready-for-review; the keeper's review (and
        the registry edit) is his, never claimed here. The proving bar is
        ship-only-when-green: shelving requires the green stage.
        """
        raising = self.get(raising_id)
        if raising.stage != STAGE_GREEN:
            raise YardRefusedError(
                "raising %s is at stage %r; only green raisings shelve (prove first)"
                % (raising_id, raising.stage)
            )
        try:
            from levi.revival.registry import RevivalEntry
        except Exception as exc:
            raise YardRefusedError("revival registry unavailable: %s" % exc) from exc
        entry = RevivalEntry(
            module=raising.module,
            levi_name=raising.levi_name,
            title=raising.title,
            flair=raising.flair,
            origin="levi-revival/%s" % raising.candidate.record_id,
            status="raised",
        )
        raising.stage = STAGE_SHELVED
        self._put(raising)
        with open(self._raised_path, "a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "raising": raising.id,
                        "record_id": raising.candidate.record_id,
                        "entry": {
                            "module": entry.module,
                            "levi_name": entry.levi_name,
                            "title": entry.title,
                            "flair": entry.flair,
                            "origin": entry.origin,
                            "status": entry.status,
                        },
                        "ts": _now(),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        self._stone_append(
            "shelved",
            raising,
            {
                "entry_module": entry.module,
                "note": "ready for the keeper's review — registry edit is his",
            },
        )
        return entry

    def raised_entries(self) -> List[Dict[str, Any]]:
        """Every shelved raising's registry entry, in shelving order."""
        try:
            lines = self._raised_path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        out = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out


# --------------------------------------------------------------------------
# CLI — consistent with `python -m levi.revival list|show|search`
# --------------------------------------------------------------------------


def _cmd_intake(yard: Yard, args: List[str]) -> int:
    hunt_home = args[0] if args else None
    admitted = yard.intake(hunt_home)
    if not admitted:
        print("The yard is quiet — no new hunt finds to admit.")
        return 0
    print("Admitted %d find(s) to the yard:" % len(admitted))
    for r in admitted:
        c = r.candidate
        print("  %s  %s (%s, %s)" % (r.id, c.title, c.kind, c.rating))
    return 0


def _cmd_list(yard: Yard, args: List[str]) -> int:
    stage = args[0] if args else None
    if stage and stage not in _STAGES:
        print(
            "Unknown stage %r — one of: %s" % (stage, ", ".join(_STAGES)),
            file=sys.stderr,
        )
        return 2
    raisings = yard.list_raisings(stage)
    if not raisings:
        print("No raisings%s." % (" at stage %r" % stage if stage else ""))
        return 0
    for r in raisings:
        name = r.levi_name or r.candidate.title or "(unnamed)"
        print("  %s  [%s]  %s" % (r.id, r.stage, name))
    return 0


def _cmd_show(yard: Yard, args: List[str]) -> int:
    if not args:
        print("`show` needs a raising id.", file=sys.stderr)
        return 2
    try:
        r = yard.get(args[0])
    except YardRefusedError as exc:
        print(exc, file=sys.stderr)
        return 1
    c = r.candidate
    print("%s  [%s]" % (r.id, r.stage))
    print("  find     : %s (%s, %s) — wave %s" % (c.title, c.kind, c.rating, c.wave_id))
    print("  died     : %s" % (r.what_died or c.title))
    print("  taught   : %s" % (r.what_it_taught or c.mechanism or "—"))
    print("  rose     : %s — %s" % (r.levi_name or "—", r.title or "—"))
    print("  module   : %s" % (r.module or "—"))
    if r.evidence:
        print("  evidence : %s" % r.evidence)
    if r.compost:
        print(
            "  compost  : %s — %s"
            % (r.compost.get("compost_class"), r.compost.get("lesson"))
        )
    print("  events   : %d" % len(r.events))
    return 0


def _cmd_study(yard: Yard, args: List[str]) -> int:
    # study <id> --levi-name N --title T --flair F --module M --died D --decline X --taught Y
    import argparse

    ap = argparse.ArgumentParser(prog="yard study")
    ap.add_argument("id")
    ap.add_argument("--levi-name", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--flair", required=True)
    ap.add_argument("--module", required=True)
    ap.add_argument("--died", required=True)
    ap.add_argument("--decline", required=True)
    ap.add_argument("--taught", required=True)
    ns = ap.parse_args(args)
    try:
        r = yard.study(
            ns.id,
            levi_name=ns.levi_name,
            title=ns.title,
            flair=ns.flair,
            module=ns.module,
            what_died=ns.died,
            decline=ns.decline,
            what_it_taught=ns.taught,
        )
    except YardRefusedError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 1
    print("Studied %s — %r will rise as %r." % (r.id, r.candidate.title, r.levi_name))
    return 0


def _cmd_scaffold(yard: Yard, args: List[str]) -> int:
    if len(args) < 2:
        print("usage: scaffold <id> <target-dir>", file=sys.stderr)
        return 2
    try:
        path = yard.scaffold(args[0], args[1])
    except (YardRefusedError, OSError) as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 1
    print("Scaffolded %s — the recreation begins there." % path)
    return 0


def _cmd_prove(yard: Yard, args: List[str]) -> int:
    if len(args) < 2:
        print("usage: prove <id> <module-file> [--evidence TEXT]", file=sys.stderr)
        return 2
    evidence = ""
    rest = args[2:]
    if rest and rest[0] == "--evidence":
        evidence = " ".join(rest[1:])
    try:
        r = yard.prove(args[0], args[1], evidence=evidence)
    except YardRefusedError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 1
    if r.stage == STAGE_GREEN:
        print("%s is GREEN — the laws hold." % r.id)
        return 0
    print("%s failed the proving and was composted — the stone keeps it." % r.id)
    print("  reason: %s" % (r.events[-1]["detail"].get("reason") if r.events else "?"))
    return 1


def _cmd_shelve(yard: Yard, args: List[str]) -> int:
    if not args:
        print("usage: shelve <id>", file=sys.stderr)
        return 2
    try:
        entry = yard.shelve(args[0])
    except YardRefusedError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 1
    print(
        "Shelved %s as %r — ready for the keeper's review." % (args[0], entry.levi_name)
    )
    return 0


def _cmd_compost(yard: Yard, args: List[str]) -> int:
    if len(args) < 2:
        print("usage: compost <id> <reason...>", file=sys.stderr)
        return 2
    try:
        r = yard.compost(args[0], " ".join(args[1:]))
    except YardRefusedError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 1
    print("Composted %s — %s" % (r.id, r.compost.get("lesson") if r.compost else ""))
    return 0


def _cmd_ledger(yard: Yard, args: List[str]) -> int:
    entries = yard.ledger()
    if not entries:
        print("The stone is blank — nothing has been raised yet.")
        return 0
    for e in entries:
        print(
            "%s  %-10s  %s  died=%r rose=%r"
            % (
                e.get("ts", "?")[:19],
                e.get("event", "?"),
                e.get("raising", "?"),
                str(e.get("what_died", ""))[:40],
                str(e.get("what_rose", {}).get("levi_name", ""))[:40],
            )
        )
    print()
    print("%d events on the stone. Nothing here is ever deleted." % len(entries))
    return 0


_COMMANDS = {
    "intake": _cmd_intake,
    "list": _cmd_list,
    "show": _cmd_show,
    "study": _cmd_study,
    "scaffold": _cmd_scaffold,
    "prove": _cmd_prove,
    "shelve": _cmd_shelve,
    "compost": _cmd_compost,
    "ledger": _cmd_ledger,
}


def main(argv: Optional[List[str]] = None) -> int:
    """CLI: ``python -m levi.revival.yard <cmd> ...`` — also wired as ``yard`` in ``python -m levi.revival``."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__.strip().split("\n\n")[0])
        print()
        print("commands: %s" % ", ".join(sorted(_COMMANDS)))
        return 0
    cmd, rest = args[0], args[1:]
    fn = _COMMANDS.get(cmd)
    if fn is None:
        print(
            "Unknown command %r — one of: %s" % (cmd, ", ".join(sorted(_COMMANDS))),
            file=sys.stderr,
        )
        return 2
    yard = Yard()
    return fn(yard, rest)


if __name__ == "__main__":
    sys.exit(main())
