"""The bulla: tamper-evident append-only logs, clay-tablet style.

Uruk administrators (4th millennium BCE) sealed clay tokens inside a hollow
clay ball (bulla) with the same marks impressed on the outside: break the
seal and the inside tokens must match the outside marks. Verification by
destruction — a checksum you cannot forge without leaving evidence.

LEVI-native version: hash-chained JSONL. Each record embeds the SHA-256 of
the previous line, so deleting, editing, or reordering a line breaks the
chain detectably. stdlib hashlib only — no blockchain, no network.

Intended use: upgrade LEVI's append-only logs (growth journal, receipts) to
hash-chained entries; a `levi verify bulla` replay reports tampering or gaps.
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, Iterable, List, Tuple

GENESIS_PREV = "0" * 64


def _canonical(record: Dict) -> str:
    return json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def append_record(prev_line: str, payload: Dict) -> str:
    """Build the next chained JSONL line.

    prev_line: the previous full line ("" for genesis). Returns the new
    line (without trailing newline) carrying prev_hash + hash.
    """
    prev_hash = (
        hashlib.sha256(prev_line.encode("utf-8")).hexdigest()
        if prev_line
        else GENESIS_PREV
    )
    entry = {"prev_hash": prev_hash, "payload": dict(payload)}
    entry["hash"] = hashlib.sha256(_canonical(entry).encode("utf-8")).hexdigest()
    return json.dumps(entry, ensure_ascii=False)


def verify_chain(lines: Iterable[str]) -> Tuple[bool, List[str]]:
    """Replay a chained log. Returns (ok, problems).

    Problems name the first bad line: bad hash, broken link, or malformed
    JSON. A gap (missing line) breaks the link and is reported exactly
    where the chain stops matching.
    """
    problems: List[str] = []
    prev_line = ""
    for idx, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            expect_prev = (
                hashlib.sha256(prev_line.encode("utf-8")).hexdigest()
                if prev_line
                else GENESIS_PREV
            )
            body = {"prev_hash": entry["prev_hash"], "payload": entry["payload"]}
            expect_hash = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
        except (ValueError, KeyError, TypeError) as exc:
            problems.append("line %d malformed: %s" % (idx, exc))
            break
        if entry.get("prev_hash") != expect_prev:
            problems.append("line %d breaks the chain (prev_hash mismatch)" % idx)
            break
        if entry.get("hash") != expect_hash:
            problems.append("line %d edited after sealing (hash mismatch)" % idx)
            break
        prev_line = line
    return (not problems, problems)
