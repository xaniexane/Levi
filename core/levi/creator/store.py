"""Per-track local stores. The tracks never merge.

SI store: ``~/.levi/creator/si/`` — directory 0700, records sealed with
the Veil-lineage envelope (:mod:`levi.creator.seal`), files 0600.
AI store: ``~/.levi/creator/ai/`` — plain local JSONL, SFW by rule.

No function in this module crosses tracks: ``si_*`` touches only the SI
dir, ``ai_*`` only the AI dir. Enforced by construction, asserted by test.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.creator.seal import open_record, seal_record

_SI_CTX = "creator/si"


def _base(home: Optional[Path] = None) -> Path:
    return (Path(home) if home is not None else Path.home()) / ".levi" / "creator"


def _si_dir(home: Optional[Path] = None) -> Path:
    d = _base(home) / "si"
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def _ai_dir(home: Optional[Path] = None) -> Path:
    d = _base(home) / "ai"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _new_id(prefix: str) -> str:
    return "%s_%s" % (prefix, uuid.uuid4().hex[:12])


def _append_jsonl(path: Path, obj: Dict[str, Any], mode: int = 0o600) -> None:
    existed = path.exists()
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, sort_keys=True) + "\n")
    if not existed:
        try:
            os.chmod(path, mode)
        except OSError:
            pass


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


# -- SI (sealed) --------------------------------------------------------


def si_write(home: Optional[Path], kind: str, record: Dict[str, Any]) -> Dict[str, Any]:
    """Seal and append a record to the SI store. Returns the stored record."""
    rec = dict(record)
    rec.setdefault("id", _new_id(kind))
    envelope = seal_record(rec, home=home, context=_SI_CTX + "/" + kind)
    _append_jsonl(_si_dir(home) / ("%s.jsonl" % kind), envelope)
    return rec


def si_read_all(home: Optional[Path], kind: str) -> List[Dict[str, Any]]:
    """Read and verify every sealed record of a kind. Tampering raises."""
    out = []
    for env in _read_jsonl(_si_dir(home) / ("%s.jsonl" % kind)):
        out.append(open_record(env, home=home, context=_SI_CTX + "/" + kind))
    return out


def si_update(home: Optional[Path], kind: str, record_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Apply updates to one sealed record (read all, patch, rewrite sealed).

    The store is tamper-evident, not append-only-immutable: updates are
    re-sealed with the keeper key, so any out-of-band edit still fails
    verification on read.
    """
    records = si_read_all(home, kind)
    target = next((r for r in records if r.get("id") == record_id), None)
    if target is None:
        raise ValueError("unknown %s record %r" % (kind, record_id))
    target.update(updates)
    path = _si_dir(home) / ("%s.jsonl" % kind)
    path.write_text("", encoding="utf-8")
    for rec in records:
        envelope = seal_record(rec, home=home, context=_SI_CTX + "/" + kind)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(envelope, sort_keys=True) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return target


def si_paths(home: Optional[Path] = None) -> List[Path]:
    """All SI store paths (for permission audits)."""
    d = _si_dir(home)
    return [d] + sorted(d.glob("*.jsonl"))


def si_delete(home: Optional[Path], kind: str, record_id: str) -> bool:
    """Delete one sealed record by id (read all, drop, re-seal the rest).

    Returns True when a record was removed. Re-sealed with the keeper key,
    so the tamper-evident property of the remaining records is preserved.
    """
    records = si_read_all(home, kind)
    if not any(r.get("id") == record_id for r in records):
        return False
    path = _si_dir(home) / ("%s.jsonl" % kind)
    path.write_text("", encoding="utf-8")
    for rec in records:
        if rec.get("id") == record_id:
            continue
        envelope = seal_record(rec, home=home, context=_SI_CTX + "/" + kind)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(envelope, sort_keys=True) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return True


# -- AI (plain, SFW) ----------------------------------------------------


def ai_write(home: Optional[Path], kind: str, record: Dict[str, Any]) -> Dict[str, Any]:
    """Append a record to the AI store. Returns the stored record."""
    rec = dict(record)
    rec.setdefault("id", _new_id(kind))
    _append_jsonl(_ai_dir(home) / ("%s.jsonl" % kind), rec, mode=0o600)
    return rec


def ai_read_all(home: Optional[Path], kind: str) -> List[Dict[str, Any]]:
    """Read every record of a kind from the AI store."""
    return _read_jsonl(_ai_dir(home) / ("%s.jsonl" % kind))


def ai_update(home: Optional[Path], kind: str, record_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Apply updates to one record in the plain AI store (rewrite file)."""
    records = ai_read_all(home, kind)
    target = next((r for r in records if r.get("id") == record_id), None)
    if target is None:
        raise ValueError("unknown %s record %r" % (kind, record_id))
    target.update(updates)
    path = _ai_dir(home) / ("%s.jsonl" % kind)
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return target
