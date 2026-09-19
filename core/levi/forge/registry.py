"""Forge registry — every recreation in the dynasty is a manifest.

The Forge (canon: docs/LEXICON.md entry cut as f011bb0) widens the forge
into the dynasty's creation surface: LEVI-native recreations of everything
the operators need — the code forge, data stores, cloud services, workflow
engines, the browser, the computer itself — plus the revival yard, the
multidomain social platform, agentic teams, the content creation machine,
and everything else to come.

This module is the manifest ledger for that program. The NeighborOS site
lift (keeper's cut 50e2979, "the Site Lift") is the flagship active
recreation: LEVI's gig-dispatch organ, built by worker 7 in
``core/levi/neighbor/`` per ``docs/NEIGHBOROS_SPEC.md``. Each recreation is
one manifest::

    {
        "name":   "forge-code",                 # ledger name
        "idea":   "code collaboration",         # the *idea* recreated — never
                                               # a product as identity
        "twist":  "local-first single-user code home on bare git repos, no
                   cloud, no accounts, nothing leaves localhost",
        "module": "levi.forge",                # importable module path, or
                                               # None (design/docs seat only)
        "ring":   "open",                      # open | closed | government
        "status": "green",                     # proving-bar status
        "worker": "worker-1",                  # dynasty worker track, or None
        "notes":  "...",
    }

PROVING BAR (canon, binding): a recreation ships only when it is green
(tests pass), lawful (canon laws honored), and keeper-reviewed. Status
values walk that bar left to right::

    planned -> in-flight -> ready-for-review -> green -> keeper-reviewed

"reserved" is not a stage: it marks a seat recorded but never designed
or built here — the keeper explains it later.

RINGS (canon: LEXICON.md "The three rings"): open = bare-minimal source,
outside minds run free with integrations; closed = diehard developers +
keeper, full source, crown jewels never leave; government = hardened,
auditable, sovereign. Each ring is a team edition, not a separate
product. A reserved seat has ring None — it is recorded, not placed.

IMPORT-TIME VALIDATION: :func:`load_registry` validates every manifest
against live modules at load time — each manifest's ``module`` path is
imported (guarded), and the result is recorded on the entry as
``import_ok`` / ``import_error``. Nothing raises: a missing module is an
honest record, not a crash.

RE-RUNNABLE: call :func:`load_registry` again any time; it re-validates
and re-discovers. Later workers' modules are picked up through two
mechanisms:

1. Static seats — manifests below list the sibling tracks' expected
   module paths. The moment a worker lands ``core/levi/forge/datastore.py``,
   the ``forge-datastore`` seat flips ``import_ok`` to True on the next load.
2. Self-declaration — any module may declare a top-level
   ``FORGE_MANIFEST`` dict with the schema above; :func:`discover_manifests`
   walks the dynasty roots (``levi.forge``, ``levi.revival``, ``levi.lwp``)
   and seats it automatically. Discovered manifests override static seats
   with the same name.

Revival laws hold over every seat: original recreations with LEVI's
twist — never copies, never masks, never reverse-engineered.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# vocabularies
# ---------------------------------------------------------------------------

#: Proving-bar walk, left to right. "reserved" is a recorded seat, not a stage.
STATUSES = (
    "planned",
    "in-flight",
    "ready-for-review",
    "green",
    "keeper-reviewed",
    "reserved",
)

#: The three rings. A reserved seat carries ring=None (recorded, not placed).
RINGS = ("open", "closed", "government")

#: Dynasty roots walked by discover_manifests() for self-declared manifests.
DISCOVERY_ROOTS = ("levi.forge", "levi.revival", "levi.lwp", "levi.neighbor")

#: Attribute a module declares to self-seat in the registry.
MANIFEST_ATTR = "FORGE_MANIFEST"


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------


@dataclass
class Manifest:
    """One recreation in the dynasty's Forge program."""

    name: str
    idea: str
    twist: str
    module: "str | None"
    ring: "str | None"
    status: str
    worker: "str | None" = None
    notes: str = ""
    discovered: bool = False
    import_ok: bool = False
    import_error: str = ""

    def validate(self) -> None:
        """Raise ValueError if the manifest breaks registry law."""
        if not self.name or not isinstance(self.name, str):
            raise ValueError("manifest needs a non-empty string name")
        if self.status not in STATUSES:
            raise ValueError(
                "manifest %r: unknown status %r" % (self.name, self.status)
            )
        if self.status == "reserved":
            if self.ring is not None:
                raise ValueError(
                    "manifest %r: reserved seats are recorded, not placed "
                    "(ring must be None)" % self.name
                )
            return
        if self.ring not in RINGS:
            raise ValueError(
                "manifest %r: ring must be one of %s (got %r)"
                % (self.name, RINGS, self.ring)
            )
        if not self.idea or not self.idea.strip():
            raise ValueError(
                "manifest %r: the recreated *idea* must be named" % self.name
            )
        if not self.twist or not self.twist.strip():
            raise ValueError(
                "manifest %r: LEVI's native twist must be stated" % self.name
            )

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "idea": self.idea,
            "twist": self.twist,
            "module": self.module,
            "ring": self.ring,
            "status": self.status,
            "worker": self.worker,
            "notes": self.notes,
            "discovered": self.discovered,
            "import_ok": self.import_ok,
            "import_error": self.import_error,
        }


# ---------------------------------------------------------------------------
# static seats — the dynasty's recreation program as of 2026-09-17
# ---------------------------------------------------------------------------


def _static_manifests() -> list[Manifest]:
    """The registry's static seats. Later workers flip import_ok by landing."""
    return [
        # -- the code forge: the first recreation, shipped green by worker 1
        Manifest(
            name="forge-code",
            idea="code collaboration",
            twist=(
                "local-first single-user code home on stock-git bare repos — "
                "smart-HTTP hosting, issues/PRs/stars as JSONL, local CI, "
                "one-command portable export. No cloud, no accounts, no "
                "telemetry; nothing leaves localhost unless you push it."
            ),
            module="levi.forge",
            ring="open",
            status="green",
            worker="worker-1",
            notes=(
                "Proving bar: green (tests/test_forge.py pass, stdlib-only, "
                "no stubs). Not yet keeper-reviewed. Ring open: the export "
                "format is stock git + open JSONL so outside minds can run "
                "free with integrations; hardening editions (closed, "
                "government) follow later."
            ),
        ),
        # -- worker 2: data stores + automation flow extension
        Manifest(
            name="forge-datastore",
            idea="data stores",
            twist=(
                "LEVI-native local-first stores behind the forge's ownership "
                "guarantee — plain-file portability discipline like the forge's "
                "JSONL/bundle habit, no hosted database dependency."
            ),
            module="levi.forge.datastore",
            ring="open",
            status="planned",
            worker="worker-2",
            notes=(
                "Seat for worker 2 (core/levi/forge/datastore.py). Empty until "
                "landed; import_ok flips True on the next load once it exists."
            ),
        ),
        Manifest(
            name="forge-flow",
            idea="workflow engines",
            twist=(
                "automation flows as plain local artifacts — rerunable, "
                "inspectable, no cloud runner, same atomic-write discipline "
                "as forge JSONL."
            ),
            module=None,
            ring="open",
            status="planned",
            worker="worker-2",
            notes=(
                "Seat for worker 2's automation-flow extension. Module path "
                "not yet chosen — it declares itself via FORGE_MANIFEST when "
                "it lands, or the seat is updated. Discoverable on re-run."
            ),
        ),
        # -- worker 3: sandbox computer + browser surface
        Manifest(
            name="forge-computer",
            idea="the computer itself",
            twist=(
                "a LEVI-native sandbox computer — the operator's own machine, "
                "recreated as a contained, auditable execution surface instead "
                "of an opaque host."
            ),
            module="levi.forge.computer",
            ring="open",
            status="planned",
            worker="worker-3",
            notes=(
                "Worker 3's sandbox computer, landed 2026-09-17 as "
                'core/levi/forge/computer.py ("LEVI\'s operable machine"). '
                "Seat validated live: import_ok flips True on re-run. "
                "Browser surface still to land; it self-declares via "
                "FORGE_MANIFEST when it does."
            ),
        ),
        Manifest(
            name="forge-browser",
            idea="the browser",
            twist=(
                "LEVI-native browser surface — the web as a recreatable tool "
                "of the forge, not a foreign application borrowed from "
                "outside."
            ),
            module=None,
            ring="open",
            status="planned",
            worker="worker-3",
            notes=(
                "Seat for worker 3's browser surface. Self-declares via "
                "FORGE_MANIFEST when it lands."
            ),
        ),
        # -- worker 4: revival yard (worker 4 owns the build; forge holds a seat)
        Manifest(
            name="forge-revival",
            idea="the revival yard",
            twist=(
                "things begun and left to die get raised again — dead software "
                "brought back under the revival laws, re-homed in the forge, "
                "rebuilt LEVI-native."
            ),
            module="levi.revival.yard",
            ring="closed",
            status="planned",
            worker="worker-4",
            notes=(
                "Worker 4's home is core/levi/revival/yard.py — this seat only "
                "records the forge-side interface (raise -> re-home -> rebuild). "
                "Ring closed: revival is keeper-gated resurrection work; the "
                "diehard developers and the keeper decide what rises."
            ),
        ),
        # -- worker 5: social platform (design docs only — no module seat yet)
        Manifest(
            name="forge-social",
            idea="multidomain social platform",
            twist=(
                "town square by forum by code commons — one platform, many "
                "domains, LEVI-native; the forge's code home extended into "
                "the commons where operators gather."
            ),
            module=None,
            ring="open",
            status="planned",
            worker="worker-5",
            notes=(
                "Worker 5 delivers design docs only. No module until the "
                "build stage seats a module path and self-declares."
            ),
        ),
        # -- worker 6: content machine under core/levi/lwp/
        Manifest(
            name="forge-content",
            idea="the content creation machine",
            twist=(
                "LEVI-native content engine grown out of L.W.P.'s writing "
                "physics — direction/phase/power, modes and forms as "
                "composable machinery, not templates."
            ),
            module=None,
            ring="open",
            status="planned",
            worker="worker-6",
            notes=(
                "Worker 6's home is core/levi/lwp/. Self-declares via "
                "FORGE_MANIFEST on the lwp modules when it lands; the "
                "levi.lwp discovery root covers it."
            ),
        ),
        # -- future recreations, sequenced in docs/FORGE_DESIGN.md
        Manifest(
            name="forge-cloud",
            idea="cloud services",
            twist=(
                "LEVI-native service surfaces with the forge's ownership "
                "guarantee — local-first, portable, no hostage formats; "
                "what the cloud does, recreated as LEVI's own."
            ),
            module=None,
            ring="open",
            status="planned",
            worker=None,
            notes=(
                "Sequenced after the computer/browser/datastore tracks. An "
                "older core/levi/cloud/ exists — the recreation is original "
                "LEVI-native work, never a copy of it or of anything else."
            ),
        ),
        Manifest(
            name="forge-teams",
            idea="agentic teams",
            twist=(
                "teams of LEVI agents as forge citizens — work happens in the "
                "forge's own home, under the proving bar, with receipts."
            ),
            module=None,
            ring="closed",
            status="planned",
            worker=None,
            notes=(
                "The six forge workers are the first team; the recreation "
                "generalizes the pattern. Ring closed: the team's charter "
                "lives with the diehard developers and the keeper."
            ),
        ),
        # -- ACTIVE: the Site Lift — NeighborOS, the gig-dispatch organ.
        # Keeper's cut 50e2979 ("the Site Lift"): the seat went from
        # RESERVED to ACTIVE. Worker 7 owns the build in
        # core/levi/neighbor/ per docs/NEIGHBOROS_SPEC.md. This seat
        # records the flagship recreation; the registry picks up
        # levi.neighbor.* modules as they land (see DISCOVERY_ROOTS).
        Manifest(
            name="forge-neighboros",
            idea="gig dispatch",
            twist=(
                "LEVI's gig-dispatch organ, un-hedged: neighbors post work, "
                "trusted workers claim it; every job fingerprinted (Job "
                "DNA), proven (Proof-of-Work Ledger), settled (NeighborPay "
                "ledger) on local infrastructure the operator owns. Workers "
                "keep 90%+ by config floor; the platform earns only on "
                "completed + paid jobs; twins and ledgers export in one "
                "command. The twin-powered, ledger-proven model the "
                "incumbents refuse — an addition, never a rebuild."
            ),
            module="levi.neighbor",
            ring="open",
            status="in-flight",
            worker="worker-7",
            notes=(
                "Flagship of the Site Lift (keeper's cut 50e2979). Spec: "
                "docs/NEIGHBOROS_SPEC.md (2026-09-16). Phase 1 builds "
                "waitlist/admin/post/work + pay ledger + monetize fee math; "
                "twins, supply, academy, ROI engine sit behind flags. Laws: "
                "zero-startup-cost, free core forever, earn-first "
                "monetization, worker_keep_floor=0.90, compliance-gated "
                "expansion, full audit logging. Not a payment processor, not "
                "a background-check vendor — external rails are labeled "
                "plug-ins, the core keeps the ledger and the proof. Ring "
                "open: the dispatch surface is creational — neighborhoods, "
                "workers, and outside minds run free with integrations."
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# validation + discovery
# ---------------------------------------------------------------------------


def _validate_module(module: "str | None") -> tuple[bool, str]:
    """Attempt the import. Returns (import_ok, import_error)."""
    if not module:
        return False, ""
    try:
        importlib.import_module(module)
    except Exception as e:  # guarded: a missing seat is a record, not a crash
        return False, "%s: %s" % (type(e).__name__, e)
    return True, ""


def discover_manifests(roots: tuple = DISCOVERY_ROOTS) -> list[Manifest]:
    """Walk dynasty roots for modules declaring FORGE_MANIFEST.

    ``roots`` is overridable for tests. Every import is guarded; a broken
    module is simply skipped (the static seat, if any, keeps its record).
    """
    found: dict[str, Manifest] = {}
    for root in roots:
        try:
            pkg = importlib.import_module(root)
        except Exception:
            continue
        path = getattr(pkg, "__path__", None)
        if path is None:
            continue
        for info in pkgutil.iter_modules(path):
            modname = "%s.%s" % (root, info.name)
            try:
                mod = importlib.import_module(modname)
            except Exception:
                continue
            decl = getattr(mod, MANIFEST_ATTR, None)
            if not isinstance(decl, dict):
                continue
            try:
                m = Manifest(
                    name=decl["name"],
                    idea=decl.get("idea", ""),
                    twist=decl.get("twist", ""),
                    module=decl.get("module", modname),
                    ring=decl.get("ring"),
                    status=decl.get("status", "in-flight"),
                    worker=decl.get("worker"),
                    notes=decl.get("notes", ""),
                    discovered=True,
                )
                m.validate()
            except (KeyError, ValueError, TypeError):
                continue  # malformed self-declaration is not seated
            # It was just imported above: import_ok is known true right now.
            # load_registry() re-validates anyway on every re-run.
            m.import_ok, m.import_error = True, ""
            found[m.name] = m
    return list(found.values())


def load_registry(roots: tuple = DISCOVERY_ROOTS) -> dict[str, Manifest]:
    """Build and validate the full registry. Safe to re-run any time.

    Static seats + discovered self-declarations (discovery wins on name
    clash). Every manifest is validated and its module path checked
    against live modules, recording import_ok / import_error on the entry.
    """
    registry: dict[str, Manifest] = {}
    for m in _static_manifests():
        m.validate()
        m.import_ok, m.import_error = _validate_module(m.module)
        registry[m.name] = m
    for m in discover_manifests(roots):
        m.import_ok, m.import_error = _validate_module(m.module)
        registry[m.name] = m  # discovered seats override static ones
    return registry


# ---------------------------------------------------------------------------
# queries
# ---------------------------------------------------------------------------

#: The registry, loaded and import-time validated. Re-run load_registry()
#: any time to pick up later workers' modules.
REGISTRY: dict[str, Manifest] = load_registry()


def refresh() -> dict[str, Manifest]:
    """Re-run the whole load (validation + discovery). Replaces REGISTRY."""
    global REGISTRY
    REGISTRY = load_registry()
    return REGISTRY


def all_manifests() -> list[Manifest]:
    return list(REGISTRY.values())


def get(name: str) -> "Manifest | None":
    return REGISTRY.get(name)


def by_ring(ring: str) -> list[Manifest]:
    return [m for m in REGISTRY.values() if m.ring == ring]


def by_status(status: str) -> list[Manifest]:
    return [m for m in REGISTRY.values() if m.status == status]


def seats_missing_modules() -> list[Manifest]:
    """Seats with a module path that does not import — the honest gap list."""
    return [m for m in REGISTRY.values() if m.module and not m.import_ok]


def proving_summary() -> dict:
    """Counts for the proving bar: status -> count, plus ring -> count."""
    return {
        "status": {s: len(by_status(s)) for s in STATUSES},
        "ring": {r: len(by_ring(r)) for r in RINGS},
        "reserved": len(by_status("reserved")),
    }


def as_json() -> list[dict]:
    return [m.as_dict() for m in all_manifests()]
