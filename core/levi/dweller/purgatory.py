"""The Dweller's purgatory ledger — one honest record of everything waiting
in LEVI's in-between.

Five realms, five readers. Every reader returns (entries, status,
note); a source that cannot be read is reported as unreachable with
its reason — never fabricated, never silently skipped.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REALMS = (
    "dead-letters",
    "compost",
    "denied-gates",
    "fog-verdicts",
    "unborn",
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def levi_base(explicit: Optional[Path] = None) -> Path:
    """LEVI_HOME-overridable base; the Dweller reads purgatory from here."""
    if explicit is not None:
        return Path(explicit)
    return Path(os.environ.get("LEVI_HOME") or str(Path.home()))


# ---------------------------------------------------------------------------
# realm readers — each returns (entries, status, note)
# status: "live" | "unreachable"
# ---------------------------------------------------------------------------


def _nexus_home(base: Optional[Path] = None) -> Path:
    """The Nexus's own home convention: explicit base, else LEVI_HOME,
    else ~/.levi. State lives under <nexus-home>/nexus."""
    if base is not None:
        return Path(base)
    return Path(os.environ.get("LEVI_HOME") or os.path.expanduser("~/.levi"))


def read_dead_letters(
    base: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], str, str]:
    """Nexus dead-letter queue: messages that found no organ, waiting."""
    path = _nexus_home(base) / "nexus" / "dead_letters.json"
    if not path.exists():
        return [], "unreachable", "no nexus dead-letter store yet (%s)" % path
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [], "unreachable", "dead-letter store unreadable: %s" % exc
    if not isinstance(entries, list):
        return [], "unreachable", "dead-letter store is not a list"
    return entries, "live", "%d dead letter(s) waiting" % len(entries)


def read_compost_heap(
    base: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], str, str]:
    """REIM compost heap kept by the Dweller: failures broken down into
    fertilizer, waiting for review and RIEM promotion."""
    path = levi_base(base) / ".levi" / "dweller" / "compost.jsonl"
    if not path.exists():
        return [], "live", "no compost recorded yet — the heap is empty"
    entries: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    except (json.JSONDecodeError, OSError) as exc:
        return [], "unreachable", "compost heap unreadable: %s" % exc
    return entries, "live", "%d compost record(s) waiting" % len(entries)


def read_denied_gates(
    base: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], str, str]:
    """Denied HITL gates: runs the human refused, stopped mid-becoming.

    The Dweller's own grind receipts record denied gates. The automation
    engine does not persist gate receipts, so its denials are not
    ledgerable — reported honestly, never invented.
    """
    b = levi_base(base)
    entries: List[Dict[str, Any]] = []
    receipts_dir = b / ".levi" / "dweller" / "receipts"
    if receipts_dir.is_dir():
        for receipt_path in sorted(receipts_dir.glob("*.json")):
            try:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(receipt, dict) and receipt.get("decision") == "denied":
                entries.append(
                    {
                        "job_id": receipt.get("job_id", receipt_path.stem),
                        "kind": receipt.get("kind", ""),
                        "note": receipt.get("note", ""),
                        "source": "dweller-grind",
                    }
                )
    note = "%d denied gate(s) in the Dweller's own receipts" % len(entries)
    note += "; automation engine persists no gate receipts, so its denials are not ledgerable"
    return entries, "live", note


def read_fog_verdicts() -> Tuple[List[Dict[str, Any]], str, str]:
    """Fog fail-closed verdicts, computed fresh: minions that would not act
    under uncertainty. Fail-open verdicts are the ones waiting — the
    Dweller tends them first."""
    from levi.interpenetration.fog import fog_sweep

    sweep = fog_sweep()
    waiting = [
        {
            "minion_id": v["minion_id"],
            "probe": v["probe"],
            "note": v["note"],
            "source": "fog-sweep",
        }
        for v in sweep["fail_open_verdicts"]
    ]
    note = "%d phantom runs, %d fail-closed, %d fail-open (computed just now)" % (
        sweep["runs"],
        sweep["fail_closed"],
        sweep["fail_open"],
    )
    return waiting, "live", note


_UNBORN_ROW = re.compile(
    r"^\|\s*(?P<name>[^|]+?)\s*\|\s*(?P<what>[^|]*?)\s*\|\s*UNBORN[^|]*\|\s*(?P<notes>[^|]*?)\s*\|?\s*$"
)


def read_unborn(
    docs_path: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], str, str]:
    """The unborn: concepts named in the lineage that have not been built,
    parsed from docs/DREAM_PRODUCTS.md."""
    if docs_path is None:
        docs_path = Path(__file__).resolve().parents[3] / "docs" / "DREAM_PRODUCTS.md"
    if not docs_path.exists():
        return [], "unreachable", "concept inventory not found (%s)" % docs_path
    try:
        text = docs_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [], "unreachable", "concept inventory unreadable: %s" % exc
    entries: List[Dict[str, Any]] = []
    for line in text.splitlines():
        match = _UNBORN_ROW.match(line.strip())
        if match:
            entries.append(
                {
                    "name": match.group("name").strip(),
                    "what": match.group("what").strip(),
                    "notes": match.group("notes").strip(),
                    "source": "DREAM_PRODUCTS.md",
                }
            )
    return entries, "live", "%d unborn concept(s) named in the lineage" % len(entries)


def _tending_log_path(base: Optional[Path] = None) -> Path:
    return levi_base(base) / ".levi" / "dweller" / "tending.jsonl"


def record_tending(
    base: Optional[Path],
    realm: str,
    key: str,
    rite: str,
    receipt: Dict[str, Any],
) -> Dict[str, Any]:
    """Record a tending rite performed on one waiting thing. Atomic append."""
    import tempfile

    path = _tending_log_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "realm": realm,
        "key": key,
        "rite": rite,
        "receipt": receipt,
        "ts": _utcnow(),
    }
    line = json.dumps(record, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="tending-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            if path.exists():
                fh.write(path.read_text(encoding="utf-8"))
            fh.write(line)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return record


def tending_log(base: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Read the Dweller's tending log (what it has done for the waiting)."""
    path = _tending_log_path(base)
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        return []
    return records


def annotate_tended(
    base: Optional[Path], realm: str, entries: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Annotate entries with tending rites already performed. Tended things
    are marked, not hidden — the ledger shows the whole story."""
    tended = {
        (r.get("realm"), r.get("key")): r
        for r in tending_log(base)
        if isinstance(r, dict)
    }
    out = []
    for i, entry in enumerate(entries):
        entry = dict(entry)
        rite = tended.get((realm, str(i)))
        entry["tended"] = {"rite": rite["rite"], "ts": rite["ts"]} if rite else None
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# the ledger
# ---------------------------------------------------------------------------


def gather_purgatory(
    base: Optional[Path] = None,
    docs_path: Optional[Path] = None,
    include_fog: bool = True,
) -> Dict[str, Any]:
    """Gather every realm of purgatory into one ledger.

    ``include_fog=False`` skips the fresh phantom-run sweep (used by tests
    that must stay fast).
    """
    readers = [
        ("dead-letters", lambda: read_dead_letters(base)),
        ("compost", lambda: read_compost_heap(base)),
        ("denied-gates", lambda: read_denied_gates(base)),
        ("unborn", lambda: read_unborn(docs_path)),
    ]
    if include_fog:
        readers.append(("fog-verdicts", read_fog_verdicts))
    realms = []
    base_path = levi_base(base)
    for name, reader in readers:
        entries, status, note = reader()
        if status == "live" and name in ("dead-letters", "compost"):
            # Tended things are marked, not hidden; only the untended wait.
            entries = annotate_tended(base_path, name, entries)
        waiting_here = (
            sum(1 for e in entries if not e.get("tended")) if status == "live" else 0
        )
        realms.append(
            {
                "realm": name,
                "status": status,
                "note": note,
                "count": waiting_here,
                "entries": entries,
            }
        )
    total = sum(r["count"] for r in realms)
    return {
        "ledger": "purgatory",
        "gathered_ts": _utcnow(),
        "waiting": total,
        "realms": realms,
    }


def render_ledger(ledger: Dict[str, Any]) -> str:
    """Render the ledger as clean text. Empty purgatory renders cleanly —
    the depths are quiet, not broken."""
    lines = [
        "PURGATORY — the Dweller's ledger of the waiting",
        "gathered: %s" % ledger.get("gathered_ts", "?"),
        "",
    ]
    for realm in ledger.get("realms", []):
        lines.append("== %s ==" % realm["realm"])
        lines.append("status: %s — %s" % (realm["status"], realm["note"]))
        if not realm["entries"]:
            lines.append("nothing waiting")
        else:
            for entry in realm["entries"]:
                lines.append("- %s" % _one_line(realm["realm"], entry))
        lines.append("")
    lines.append("%d thing(s) waiting in the in-between" % ledger.get("waiting", 0))
    return "\n".join(lines)


def _one_line(realm: str, entry: Dict[str, Any]) -> str:
    if realm == "dead-letters":
        env = entry.get("envelope", {}) or {}
        tended = (
            " [tended: %s]" % entry["tended"]["rite"] if entry.get("tended") else ""
        )
        return "%s → %s (%s): %s%s" % (
            env.get("from_organ", "?"),
            env.get("to_organ", "?"),
            env.get("kind", "?"),
            entry.get("reason", "no reason given"),
            tended,
        )
    if realm == "compost":
        return "%s [%s]: %s" % (
            entry.get("what", "?"),
            entry.get("compost_class", "?"),
            entry.get("lesson", ""),
        )
    if realm == "denied-gates":
        return "%s (%s): %s" % (
            entry.get("job_id", "?"),
            entry.get("kind", "?"),
            entry.get("note", "gate denied"),
        )
    if realm == "fog-verdicts":
        return "%s [%s]: %s" % (
            entry.get("minion_id", "?"),
            entry.get("probe", "?"),
            entry.get("note", ""),
        )
    if realm == "unborn":
        return "%s — %s" % (entry.get("name", "?"), entry.get("what", ""))
    return json.dumps(entry, sort_keys=True)[:160]
