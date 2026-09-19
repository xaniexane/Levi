"""The Story Table — LEVI-native tabletop RPG engine (games warehouse).

Levi-shuffle of the "swappable agent plugins + dice-first receipts +
portable world packs" pattern:

REIM (composted failure):
  The retcon — an AI narrator quietly rewriting a dice outcome after
  seeing it. Compost class: wrong-assumption ("the storyteller can be
  trusted with the outcome"). The lesson is enforced structurally, not
  by policy prose: ROLL FIRST, RECEIPT FIRST, NARRATE SECOND. A check
  seals its outcome in a hash-chained receipt *before* any narration
  function runs, so the story cannot change what the dice said.
  Also composted: cloud-locked worlds and account-gated tables. The
  table is local files + local SQLite: no network, no sign-in, no
  server that can take the game with it (Charter: no_kill_switch).

RIEM (genome — what promoted into LEVI):
  - Swappable role agents: narrator / loremaster / cast / herald are
    plain registered classes, hot-swappable mid-session, no framework
    fork required.
  - Dice-first protocol with a hash-chained receipt ledger (stdlib
    sqlite3, local-first). Every receipt prints BEFORE narration.
  - Portable world packs: lore, cast, rules, quests, scenes as plain
    files; export/import as a zip the player owns outright.
  - Fair Play Charter manifest: all 10 rules pass — odds declared AND
    empirically auditable via ``prove``.

Stdlib only. Offline. No accounts, no telemetry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

from levi.games.charter import GameManifest, check_manifest, is_fair
from levi.games.saves import SaveStore

GAME_ID = "table"
LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS receipts (
    seq       INTEGER NOT NULL,
    slot      TEXT    NOT NULL,
    spec      TEXT    NOT NULL,
    dice      TEXT    NOT NULL,
    modifier  INTEGER NOT NULL,
    total     INTEGER NOT NULL,
    target    INTEGER,
    success   INTEGER,
    label     TEXT    NOT NULL,
    ts        TEXT    NOT NULL,
    prev_hash TEXT    NOT NULL,
    hash      TEXT    NOT NULL,
    PRIMARY KEY (slot, seq)
);
"""

_DICE_RE = re.compile(r"^\s*(\d*)\s*[dD]\s*(\d+)\s*([+-]\s*\d+)?\s*$")


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _default_root() -> Path:
    root = Path.home() / ".levi" / "games" / "table"
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    return root


def _shipped_packs_dir() -> Path:
    return Path(__file__).resolve().parent / "packs"


# ---------------------------------------------------------------------------
# Dice
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiceSpec:
    count: int
    faces: int
    modifier: int = 0

    def __str__(self) -> str:
        base = f"{self.count}d{self.faces}"
        if self.modifier > 0:
            return f"{base}+{self.modifier}"
        if self.modifier < 0:
            return f"{base}{self.modifier}"
        return base


def parse_spec(text: str) -> DiceSpec:
    """Parse '2d6+3', 'd20', '4d6-2' — ValueError on anything else."""
    m = _DICE_RE.match(text or "")
    if not m:
        raise ValueError(f"bad dice spec: {text!r} (want like 2d6+3, d20)")
    count = int(m.group(1)) if m.group(1) else 1
    faces = int(m.group(2))
    modifier = int(m.group(3).replace(" ", "")) if m.group(3) else 0
    if not (1 <= count <= 100):
        raise ValueError("dice count must be 1..100")
    if not (2 <= faces <= 1000):
        raise ValueError("die faces must be 2..1000")
    return DiceSpec(count, faces, modifier)


# ---------------------------------------------------------------------------
# Receipts — the dice-first protocol
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RollReceipt:
    """A sealed dice outcome. Frozen: narration receives it, never edits it."""

    seq: int
    slot: str
    spec: str
    dice: Tuple[int, ...]
    modifier: int
    total: int
    target: Optional[int]
    success: Optional[bool]
    label: str
    ts: str
    prev_hash: str
    hash: str

    def canonical(self) -> str:
        return "|".join(
            [
                str(self.seq),
                self.slot,
                self.spec,
                ",".join(str(d) for d in self.dice),
                str(self.modifier),
                str(self.total),
                "" if self.target is None else str(self.target),
                "" if self.success is None else ("1" if self.success else "0"),
                self.label,
                self.ts,
                self.prev_hash,
            ]
        )

    def format(self) -> str:
        dice_s = "[" + ", ".join(str(d) for d in self.dice) + "]"
        mod_s = f"{self.modifier:+d}" if self.modifier else "+0"
        outcome = ""
        if self.target is not None and self.success is not None:
            outcome = f"  vs {self.target} … {'SUCCESS' if self.success else 'FAIL'}"
        lines = [
            f"┌─ ROLL RECEIPT #{self.seq:04d} ─────────────────────────────",
            f"│ {self.spec} → {dice_s} {mod_s} = {self.total}{outcome}",
            f"│ label: {self.label or '—'}    slot: {self.slot}",
            f"│ hash: {self.hash[:12]}…  prev: {self.prev_hash[:12]}…",
            "│ sealed before narration — the story cannot retcon this.",
            "└──────────────────────────────────────────────────────────",
        ]
        return "\n".join(lines)


def _receipt_hash(canonical: str) -> str:
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ReceiptLedger:
    """Hash-chained roll receipts in local SQLite. Tamper-evident."""

    GENESIS = "0" * 64

    def __init__(self, db_path: "str | os.PathLike[str]"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute(LEDGER_SCHEMA)
        self._conn.commit()

    def _last(self, slot: str) -> Tuple[int, str]:
        row = self._conn.execute(
            "SELECT seq, hash FROM receipts WHERE slot=? ORDER BY seq DESC LIMIT 1",
            (slot,),
        ).fetchone()
        if row is None:
            return 0, self.GENESIS
        return int(row[0]), str(row[1])

    def append(
        self,
        slot: str,
        spec: DiceSpec,
        dice: Tuple[int, ...],
        label: str = "",
        target: Optional[int] = None,
        rng: Optional[random.Random] = None,
    ) -> RollReceipt:
        _ = rng  # dice are rolled by the caller; ledger only seals
        total = sum(dice) + spec.modifier
        success = (total >= target) if target is not None else None
        seq, prev_hash = self._last(slot)
        seq += 1
        ts = datetime.now(timezone.utc).isoformat()
        provisional = RollReceipt(
            seq=seq,
            slot=slot,
            spec=str(spec),
            dice=tuple(dice),
            modifier=spec.modifier,
            total=total,
            target=target,
            success=success,
            label=label,
            ts=ts,
            prev_hash=prev_hash,
            hash="",
        )
        digest = _receipt_hash(provisional.canonical())
        receipt = RollReceipt(**{**provisional.__dict__, "hash": digest})
        self._conn.execute(
            "INSERT INTO receipts (seq, slot, spec, dice, modifier, total,"
            " target, success, label, ts, prev_hash, hash)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                receipt.seq,
                receipt.slot,
                receipt.spec,
                json.dumps(list(receipt.dice)),
                receipt.modifier,
                receipt.total,
                receipt.target,
                None if receipt.success is None else int(receipt.success),
                receipt.label,
                receipt.ts,
                receipt.prev_hash,
                receipt.hash,
            ),
        )
        self._conn.commit()
        return receipt

    def list(self, slot: str) -> List[RollReceipt]:
        rows = self._conn.execute(
            "SELECT seq, slot, spec, dice, modifier, total, target, success,"
            " label, ts, prev_hash, hash FROM receipts WHERE slot=?"
            " ORDER BY seq",
            (slot,),
        ).fetchall()
        out = []
        for r in rows:
            out.append(
                RollReceipt(
                    seq=int(r[0]),
                    slot=str(r[1]),
                    spec=str(r[2]),
                    dice=tuple(json.loads(str(r[3]))),
                    modifier=int(r[4]),
                    total=int(r[5]),
                    target=None if r[6] is None else int(r[6]),
                    success=None if r[7] is None else bool(r[7]),
                    label=str(r[8]),
                    ts=str(r[9]),
                    prev_hash=str(r[10]),
                    hash=str(r[11]),
                )
            )
        return out

    def verify(self, slot: str) -> Tuple[bool, Optional[int]]:
        """Recompute the chain. Returns (ok, bad_seq)."""
        prev = self.GENESIS
        for rc in self.list(slot):
            if rc.prev_hash != prev:
                return False, rc.seq
            expect = _receipt_hash(
                RollReceipt(**{**rc.__dict__, "hash": ""}).canonical()
            )
            if expect != rc.hash:
                return False, rc.seq
            prev = rc.hash
        return True, None

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Swappable role agents
# ---------------------------------------------------------------------------


class Role:
    """One seat at the story table. Subclass and register to swap in."""

    name = "role"
    voice = "a plain voice"

    def describe(self) -> str:
        return f"{self.name} — {self.voice}"

    # -- the four seats ----------------------------------------------------
    def narrate(self, ctx: Dict[str, Any]) -> str:
        raise NotImplementedError

    def present(self, ctx: Dict[str, Any]) -> str:
        raise NotImplementedError

    def speak(self, ctx: Dict[str, Any]) -> str:
        raise NotImplementedError

    def herald(self, ctx: Dict[str, Any]) -> str:
        raise NotImplementedError


ROLE_SLOTS = ("narrator", "loremaster", "cast", "herald")
ROLE_IMPLS: Dict[str, Type[Role]] = {}


def register_role(name: str, cls: Type[Role]) -> None:
    if not (isinstance(name, str) and name and isinstance(cls, type)):
        raise ValueError("register_role needs a name and a Role subclass")
    if not issubclass(cls, Role):
        raise ValueError("register_role: cls must subclass levi.games.table.Role")
    ROLE_IMPLS[name] = cls


_SUCCESS_BEATS = [
    "Against the odds, it holds.",
    "Clean. Even the dice sound surprised.",
    "It lands exactly where it needed to.",
]
_FAIL_BEATS = [
    "It slips sideways at the last breath.",
    "Not this time — the table keeps its counsel.",
    "So close the air tastes of it, then gone.",
]


class HearthNarrator(Role):
    """Default narrator: outcome-honest, warm, brief."""

    name = "hearth"
    voice = "warm and brief, never purple, never lies about the roll"

    def narrate(self, ctx: Dict[str, Any]) -> str:
        rc: RollReceipt = ctx["receipt"]
        rng: random.Random = ctx.get("rng") or random.Random()
        label = rc.label or "the attempt"
        if rc.success is None:
            return (
                f"The dice settle: {rc.total} on {rc.spec} for {label}. "
                "No target was set, so the table simply notes it and moves on."
            )
        beat = rng.choice(_SUCCESS_BEATS if rc.success else _FAIL_BEATS)
        margin = abs(rc.total - (rc.target or 0))
        if rc.success:
            return (
                f"{beat} {label} — {rc.total} against {rc.target}, "
                f"cleared by {margin}. The table nods; play continues."
            )
        return (
            f"{beat} {label} — {rc.total} against {rc.target}, "
            f"short by {margin}. The table marks it and moves on; "
            "failure is a door, not a wall."
        )


class Loremaster(Role):
    """Default loremaster: reads the pack's lore, scenes, and quests aloud."""

    name = "loremaster"
    voice = "measured, a keeper of old maps"

    def present(self, ctx: Dict[str, Any]) -> str:
        kind = ctx.get("kind", "lore")
        text = ctx.get("text", "")
        title = ctx.get("title", kind)
        return f"── {title} ──\n{text.strip()}\n── the loremaster closes the book ──"


class CastDirector(Role):
    """Default cast: voices NPCs from the pack's cast list."""

    name = "cast-director"
    voice = "a different throat for every name on the cast list"

    def speak(self, ctx: Dict[str, Any]) -> str:
        npc = ctx.get("npc") or {}
        prompt = (ctx.get("prompt") or "").strip()
        rng: random.Random = ctx.get("rng") or random.Random()
        name = npc.get("name", "A stranger")
        quirk = npc.get("voice", "")
        greet = npc.get("greet", "")
        aside = rng.choice(npc.get("asides", []) or ["Hm."])
        if prompt:
            return (
                f'{name} ({quirk}): "{aside}" '
                f'— at your words "{prompt}", they answer plainly: "{greet}"'
            )
        return f'{name} ({quirk}): "{greet}"'


class Herald(Role):
    """Default herald: character creation, quick and kind."""

    name = "herald"
    voice = "ceremonial but quick — no twenty-page backstory required"

    def herald(self, ctx: Dict[str, Any]) -> str:
        name = ctx.get("name", "the wanderer")
        archetype = ctx.get("archetype") or "drifter"
        rng: random.Random = ctx.get("rng") or random.Random()
        boon = rng.choice(
            ["a steady hand", "a borrowed map", "a debt owed to them", "sharp ears"]
        )
        return (
            f"The herald strikes the table once. '{name}, {archetype} of "
            f"Emberfall — take {boon}, and mind the tide.' "
            "Character sealed. Play when ready."
        )


register_role("hearth", HearthNarrator)
register_role("loremaster", Loremaster)
register_role("cast-director", CastDirector)
register_role("herald", Herald)

DEFAULT_CAST = {
    "narrator": "hearth",
    "loremaster": "loremaster",
    "cast": "cast-director",
    "herald": "herald",
}


# ---------------------------------------------------------------------------
# World packs
# ---------------------------------------------------------------------------


PACK_REQUIRED = ("pack.json", "lore.md", "cast.json", "rules.json")


def load_pack(path: "str | os.PathLike[str]") -> Dict[str, Any]:
    """Load and validate a world pack directory."""
    d = Path(path)
    if not d.is_dir():
        raise ValueError(f"not a pack directory: {d}")
    missing = [f for f in PACK_REQUIRED if not (d / f).is_file()]
    if missing:
        raise ValueError(f"pack {d} missing: {', '.join(missing)}")
    meta = json.loads((d / "pack.json").read_text(encoding="utf-8"))
    cast = json.loads((d / "cast.json").read_text(encoding="utf-8"))
    rules = json.loads((d / "rules.json").read_text(encoding="utf-8"))
    lore = (d / "lore.md").read_text(encoding="utf-8")
    scenes = (
        {
            p.stem: p.read_text(encoding="utf-8")
            for p in sorted((d / "scenes").glob("*.md"))
        }
        if (d / "scenes").is_dir()
        else {}
    )
    quests = (
        {
            p.stem: p.read_text(encoding="utf-8")
            for p in sorted((d / "quests").glob("*.md"))
        }
        if (d / "quests").is_dir()
        else {}
    )
    return {
        "dir": str(d),
        "meta": meta,
        "cast": cast,
        "rules": rules,
        "lore": lore,
        "scenes": scenes,
        "quests": quests,
    }


def list_packs(root: Optional[Path] = None) -> List[Tuple[str, str]]:
    """User packs plus the packs shipped with LEVI. (name, dir)."""
    found: Dict[str, str] = {}
    shipped = _shipped_packs_dir()
    if shipped.is_dir():
        for p in sorted(shipped.iterdir()):
            if p.is_dir() and (p / "pack.json").is_file():
                found[p.name] = str(p)
    base = (root or _default_root()) / "packs"
    if base.is_dir():
        for p in sorted(base.iterdir()):
            if p.is_dir() and (p / "pack.json").is_file():
                found[p.name] = str(p)  # user packs win on name clash
    return sorted(found.items())


def export_pack(
    src_dir: "str | os.PathLike[str]", dest_zip: "str | os.PathLike[str]"
) -> Path:
    src = Path(src_dir)
    load_pack(src)  # validate first
    dest = Path(dest_zip)
    if dest.suffix != ".zip":
        dest = dest.with_suffix(".zip")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(src))
    return dest


def import_pack(
    src_zip: "str | os.PathLike[str]",
    root: Optional[Path] = None,
    name: Optional[str] = None,
) -> Path:
    src = Path(src_zip)
    if not (src.is_file() and zipfile.is_zipfile(src)):
        raise ValueError(f"not a pack zip: {src}")
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(src) as zf:
            # fail closed on zip-slip
            for member in zf.namelist():
                if member.startswith("/") or ".." in member.split("/"):
                    raise ValueError(f"unsafe path in pack zip: {member!r}")
            zf.extractall(tmp)
        probed = load_pack(tmp)  # validate before installing
        pack_name = name or probed["meta"].get("name") or Path(tmp).name
        safe = "".join(c for c in pack_name if c.isalnum() or c in "-_")
        if not safe:
            raise ValueError("pack name is unusable")
        dest = (root or _default_root()) / "packs" / safe
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(tmp, dest)
    return dest


# ---------------------------------------------------------------------------
# The table session
# ---------------------------------------------------------------------------


@dataclass
class Table:
    """One game at the story table: pack + cast of roles + sealed ledger."""

    pack: Dict[str, Any]
    slot: str = "table"
    seed: Optional[int] = None
    root: Optional[Path] = None
    quiet: bool = False
    roles: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_CAST))

    def __post_init__(self) -> None:
        self.root = Path(self.root) if self.root else _default_root()
        self.rng = random.Random(self.seed)
        self.ledger = ReceiptLedger(self.root / "ledger.db")
        self.store = SaveStore(self.root / "saves")
        for slot_name, impl in self.roles.items():
            if slot_name not in ROLE_SLOTS:
                raise ValueError(f"unknown role slot: {slot_name!r}")
            if impl not in ROLE_IMPLS:
                raise ValueError(f"unknown role impl: {impl!r}")

    # -- roles -------------------------------------------------------------
    def role(self, slot_name: str) -> Role:
        return ROLE_IMPLS[self.roles[slot_name]]()

    def swap_role(self, slot_name: str, impl_name: str) -> str:
        """Hot-swap one seat mid-session. Returns the displaced impl name."""
        if slot_name not in ROLE_SLOTS:
            raise ValueError(f"unknown role slot: {slot_name!r} (try {ROLE_SLOTS})")
        if impl_name not in ROLE_IMPLS:
            raise ValueError(
                f"unknown role impl: {impl_name!r} (try {sorted(ROLE_IMPLS)})"
            )
        old = self.roles[slot_name]
        self.roles[slot_name] = impl_name
        return old

    # -- dice-first protocol -----------------------------------------------
    def _seal(
        self,
        spec: DiceSpec,
        label: str,
        target: Optional[int] = None,
    ) -> RollReceipt:
        dice = tuple(self.rng.randint(1, spec.faces) for _ in range(spec.count))
        receipt = self.ledger.append(self.slot, spec, dice, label=label, target=target)
        if not self.quiet:
            print(receipt.format(), flush=True)
        return receipt

    def roll(self, spec_text: str, label: str = "") -> RollReceipt:
        """Roll first, seal it, print the receipt. Narrate only after."""
        return self._seal(parse_spec(spec_text), label)

    def check(
        self, spec_text: str, vs: int, label: str = ""
    ) -> Tuple[RollReceipt, bool]:
        """The dice-first check: the receipt is sealed and printed BEFORE
        any narration runs. The narrator receives the frozen receipt."""
        receipt = self._seal(parse_spec(spec_text), label, target=int(vs))
        return receipt, bool(receipt.success)

    def narrate(self, receipt: RollReceipt, extra: str = "") -> str:
        """Narrate an already-sealed receipt. Cannot alter the outcome —
        the receipt is frozen and the ledger already holds it."""
        text = self.role("narrator").narrate(
            {"receipt": receipt, "pack": self.pack, "rng": self.rng, "extra": extra}
        )
        if not self.quiet:
            print(text, flush=True)
        return text

    # -- the other seats ----------------------------------------------------
    def scene(self, scene_id: str) -> str:
        text = self.pack["scenes"].get(scene_id)
        if text is None:
            known = ", ".join(sorted(self.pack["scenes"])) or "none"
            raise ValueError(f"unknown scene {scene_id!r} (try: {known})")
        out = self.role("loremaster").present(
            {"kind": "scene", "title": scene_id, "text": text, "pack": self.pack}
        )
        if not self.quiet:
            print(out, flush=True)
        return out

    def lore(self) -> str:
        out = self.role("loremaster").present(
            {
                "kind": "lore",
                "title": self.pack["meta"].get("title", "lore"),
                "text": self.pack["lore"],
                "pack": self.pack,
            }
        )
        if not self.quiet:
            print(out, flush=True)
        return out

    def npc(self, cast_id: str, prompt: str = "") -> str:
        npc = next((c for c in self.pack["cast"] if c.get("id") == cast_id), None)
        if npc is None:
            known = ", ".join(c.get("id", "?") for c in self.pack["cast"])
            raise ValueError(f"unknown cast member {cast_id!r} (try: {known})")
        out = self.role("cast").speak(
            {"npc": npc, "prompt": prompt, "pack": self.pack, "rng": self.rng}
        )
        if not self.quiet:
            print(out, flush=True)
        return out

    def create_character(self, name: str, archetype: Optional[str] = None) -> str:
        out = self.role("herald").herald(
            {"name": name, "archetype": archetype, "pack": self.pack, "rng": self.rng}
        )
        if not self.quiet:
            print(out, flush=True)
        return out

    # -- persistence ---------------------------------------------------------
    def save(self) -> Path:
        return self.store.save(
            GAME_ID,
            self.slot,
            {
                "pack_dir": self.pack["dir"],
                "seed": self.seed,
                "roles": dict(self.roles),
            },
        )

    @classmethod
    def load(
        cls, slot: str = "table", root: Optional[Path] = None, quiet: bool = False
    ) -> "Table":
        store = SaveStore((Path(root) if root else _default_root()) / "saves")
        state = store.load(GAME_ID, slot)
        pack = load_pack(state["pack_dir"])
        return cls(
            pack=pack,
            slot=slot,
            seed=state.get("seed"),
            root=root,
            quiet=quiet,
            roles=dict(state.get("roles") or DEFAULT_CAST),
        )

    @classmethod
    def new(
        cls,
        pack_name: str,
        slot: str = "table",
        seed: Optional[int] = None,
        root: Optional[Path] = None,
        quiet: bool = False,
    ) -> "Table":
        packs = dict(list_packs(root))
        if pack_name not in packs:
            known = ", ".join(sorted(packs)) or "none"
            raise ValueError(f"unknown pack {pack_name!r} (try: {known})")
        table = cls(
            load_pack(packs[pack_name]), slot=slot, seed=seed, root=root, quiet=quiet
        )
        table.save()
        return table

    def receipts(self) -> List[RollReceipt]:
        return self.ledger.list(self.slot)

    def verify(self) -> Tuple[bool, Optional[int]]:
        return self.ledger.verify(self.slot)

    def close(self) -> None:
        self.ledger.close()


# ---------------------------------------------------------------------------
# Charter + odds audit
# ---------------------------------------------------------------------------


def manifest() -> GameManifest:
    return GameManifest(
        name="story-table",
        has_randomness=True,
        has_audit_hook=True,
        odds_declared=True,
        progress_portable=True,
        hints_free=True,
    )


def charter_report() -> str:
    results = check_manifest(manifest())
    lines = ["Story Table — Fair Play Charter check:"]
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        lines.append(f"  [{mark}] {r['id']}: {r['title']}")
    lines.append(
        "verdict: " + ("FAIR — all rules pass" if is_fair(manifest()) else "UNFAIR")
    )
    return "\n".join(lines)


def prove(trials: int = 6000, seed: int = 7) -> str:
    """Empirical odds audit: d20 uniformity. The audit hook the Charter demands."""
    rng = random.Random(seed)
    faces = 20
    counts = [0] * faces
    for _ in range(trials):
        counts[rng.randint(1, faces) - 1] += 1
    expected = trials / faces
    worst = max(abs(c - expected) / expected for c in counts)
    ok = worst <= 0.10
    lines = [
        f"d20 × {trials} rolls (seed {seed}): expected {expected:.0f}/face",
        f"min {min(counts)}, max {max(counts)}, worst deviation {worst:.1%}",
        "verdict: " + ("ODDS HONEST — within 10% of uniform" if ok else "ODDS SUSPECT"),
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _open(slot: str, root: Optional[Path], quiet: bool) -> Table:
    try:
        return Table.load(slot, root=root, quiet=quiet)
    except Exception:
        packs = list_packs(root)
        if not packs:
            raise SystemExit(
                "no world packs found and no saved table; run `table new` first"
            ) from None
        # fall back to a fresh table on the first pack
        return Table.new(packs[0][0], slot=slot, root=root, quiet=quiet)


def cmd(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="table", description="The Story Table — dice-first tabletop RPG"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new", help="start a table on a world pack")
    s.add_argument("--pack", required=True)
    s.add_argument("--slot", default="table")
    s.add_argument("--seed", type=int, default=None)

    s = sub.add_parser(
        "check", help="dice-first check: roll, seal receipt, then narrate"
    )
    s.add_argument("spec", help="e.g. 2d6+3, d20")
    s.add_argument("--vs", type=int, required=True, help="target number")
    s.add_argument("--label", default="")
    s.add_argument("--slot", default="table")

    s = sub.add_parser("roll", help="plain roll with a sealed receipt")
    s.add_argument("spec")
    s.add_argument("--label", default="")
    s.add_argument("--slot", default="table")

    s = sub.add_parser("scene", help="loremaster presents a scene")
    s.add_argument("scene_id")
    s.add_argument("--slot", default="table")

    s = sub.add_parser("lore", help="loremaster reads the pack lore")
    s.add_argument("--slot", default="table")

    s = sub.add_parser("npc", help="talk to a cast member")
    s.add_argument("cast_id")
    s.add_argument("prompt", nargs=argparse.REMAINDER, default=[])
    s.add_argument("--slot", default="table")

    s = sub.add_parser("create", help="herald seals a new character")
    s.add_argument("name")
    s.add_argument("--archetype", default=None)
    s.add_argument("--slot", default="table")

    s = sub.add_parser("receipts", help="show the sealed roll ledger")
    s.add_argument("--slot", default="table")
    s.add_argument("--verify", action="store_true", help="verify the hash chain")

    s = sub.add_parser("roles", help="list the seats and who sits in them")
    s.add_argument("--slot", default="table")

    s = sub.add_parser("swap", help="hot-swap one seat mid-session")
    s.add_argument("--seat", required=True, choices=list(ROLE_SLOTS))
    s.add_argument("--impl", required=True)
    s.add_argument("--slot", default="table")

    sub.add_parser("packs", help="list world packs")

    s = sub.add_parser("pack-export", help="export a pack dir to a portable zip")
    s.add_argument("src")
    s.add_argument("dest")

    s = sub.add_parser("pack-import", help="import a pack zip (player-owned)")
    s.add_argument("src")
    s.add_argument("--name", default=None)

    s = sub.add_parser("prove", help="empirical d20 odds audit")
    s.add_argument("--trials", type=int, default=6000)
    s.add_argument("--seed", type=int, default=7)

    sub.add_parser("charter", help="Fair Play Charter check for the story table")

    args = p.parse_args(argv)
    root = _default_root()

    if args.cmd == "new":
        t = Table.new(args.pack, slot=args.slot, seed=args.seed, root=root)
        meta = t.pack["meta"]
        print(f"Table set: {meta.get('title', args.pack)} (slot {args.slot})")
        if args.seed is not None:
            print(f"seeded: {args.seed} — same seed, same dice, same story bones")
        t.close()
        return 0

    if args.cmd == "packs":
        packs = list_packs(root)
        if not packs:
            print("no world packs")
            return 0
        for name, path in packs:
            print(f"  {name}  ({path})")
        return 0

    if args.cmd == "pack-export":
        dest = export_pack(args.src, args.dest)
        print(f"packed: {dest}")
        return 0

    if args.cmd == "pack-import":
        dest = import_pack(args.src, root=root, name=args.name)
        print(f"installed: {dest}")
        return 0

    if args.cmd == "prove":
        print(prove(trials=args.trials, seed=args.seed))
        return 0

    if args.cmd == "charter":
        print(charter_report())
        return 0

    if args.cmd == "roles":
        t = _open(args.slot, root, quiet=True)
        print("Seats at the table:")
        for seat in ROLE_SLOTS:
            impl = t.roles[seat]
            print(f"  {seat:10s} ← {impl:15s} ({ROLE_IMPLS[impl]().voice})")
        print(f"\nknown impls: {', '.join(sorted(ROLE_IMPLS))}")
        t.close()
        return 0

    if args.cmd == "swap":
        t = _open(args.slot, root, quiet=True)
        old = t.swap_role(args.seat, args.impl)
        t.save()
        print(f"{args.seat}: {old} → {args.impl}")
        print(f"now speaking: {ROLE_IMPLS[args.impl]().describe()}")
        t.close()
        return 0

    if args.cmd == "receipts":
        t = _open(args.slot, root, quiet=True)
        if args.verify:
            ok, bad = t.verify()
            print(
                "chain intact — no retcon possible"
                if ok
                else f"CHAIN BROKEN at receipt #{bad:04d}"
            )
            t.close()
            return 0 if ok else 1
        receipts = t.receipts()
        if not receipts:
            print("no rolls sealed yet")
        for rc in receipts:
            print(rc.format())
        t.close()
        return 0

    # -- session commands below need a live table ---------------------------
    t = _open(args.slot, root, quiet=False)
    try:
        if args.cmd == "check":
            receipt, success = t.check(args.spec, args.vs, label=args.label)
            t.narrate(receipt)  # narration AFTER the sealed receipt
            t.save()
        elif args.cmd == "roll":
            t.roll(args.spec, label=args.label)
            t.save()
        elif args.cmd == "scene":
            t.scene(args.scene_id)
        elif args.cmd == "lore":
            t.lore()
        elif args.cmd == "npc":
            t.npc(args.cast_id, " ".join(args.prompt))
        elif args.cmd == "create":
            t.create_character(args.name, args.archetype)
            t.save()
    finally:
        t.close()
    return 0


if __name__ == "__main__":
    sys.exit(cmd())
