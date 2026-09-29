"""Evidence exhibits: the evidence bag, revived as a local-first primitive.

History: the paper evidence bag — a sealed envelope with a chain-of-custody
tag. Whatever went in was logged: who sealed it, when, what it claimed to
be; every hand it passed through signed the tag. The bag proved one thing
only: that the contents had not changed since sealing. It never proved the
contents were true. (arch-addon-xposed-signal-not-verdict)

Clean-room recreation: an exhibit binds a CLAIM plus its metadata and
attachments into one sealed object with an append-only, hash-chained
handling log. Inspection recomputes every digest. The verdict covers
custody integrity only — INTEGRITY IS NOT TRUTH, and the exhibit says so
on its face (honesty footer, like the routing slip).

LAWS (law-guard-prove; the proof is tests/test_custody_exhibit.py):
  1. An exhibit proves custody integrity only — it never vouches for the
     truth of the claim inside. INTEGRITY IS NOT TRUTH.
  2. Sealing is fail-closed: claim, metadata, and attachment bytes are all
     digested at seal time. Anything added later requires a new seal.
  3. The handling log is append-only and hash-chained to the seal. Entries
     carry timestamp, handler, and action.
  4. Verdict INTACT means the bytes are exactly what was sealed; it never
     claims identity beyond the bound label.
  5. Every exhibit states what it is NOT (honesty footer).
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Tuple

EXHIBIT_FORMAT = "levi-exhibit/1"

INTACT = "INTACT"
TAMPERED = "TAMPERED"

HONESTY_FOOTER = (
    "This exhibit proves custody integrity only: the sealed bytes have not "
    "changed since sealing. It does NOT prove the claim inside is true, the "
    "source is who it says it is, or the attachments are authentic. "
    "INTEGRITY IS NOT TRUTH."
)


class ExhibitError(ValueError):
    """Malformed exhibit input."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _attachment_digests(attachments: Mapping[str, bytes]) -> Dict[str, str]:
    return {
        name: hashlib.sha256(data).hexdigest() for name, data in attachments.items()
    }


@dataclass(frozen=True)
class HandlingEntry:
    """One append-only entry in the chain-of-custody log."""

    timestamp: str
    handler: str
    action: str
    entry_digest: str


@dataclass(frozen=True)
class Exhibit:
    """A sealed evidence exhibit: claim + metadata + attachments + log."""

    format: str
    label: str
    claim: str
    metadata: Tuple[Tuple[str, str], ...]
    attachments: Tuple[Tuple[str, bytes], ...]
    sealed_at: str
    salt: str
    seal: str
    log: Tuple[HandlingEntry, ...] = ()

    def attachment(self, name: str) -> Optional[bytes]:
        for key, data in self.attachments:
            if key == name:
                return data
        return None


def _seal_digest(
    label: str,
    claim: str,
    metadata: Mapping[str, str],
    att_digests: Mapping[str, str],
    sealed_at: str,
    salt: str,
) -> str:
    payload = {
        "format": EXHIBIT_FORMAT,
        "label": label,
        "claim": claim,
        "metadata": dict(sorted(metadata.items())),
        "attachments": dict(sorted(att_digests.items())),
        "sealed_at": sealed_at,
        "salt": salt,
    }
    return _digest(_canonical(payload))


def seal_exhibit(
    claim: str,
    metadata: Optional[Mapping[str, str]] = None,
    attachments: Optional[Mapping[str, bytes]] = None,
    label: str = "",
) -> Exhibit:
    """Seal a claim and its supporting material into an exhibit.

    The claim is quoted verbatim — sealing never paraphrases. Metadata
    values must be strings; attachment values must be bytes.
    """
    if not claim or not claim.strip():
        raise ExhibitError("claim is required; an exhibit seals SOMETHING")
    meta: Dict[str, str] = dict(metadata or {})
    for key, value in meta.items():
        if not isinstance(value, str):
            raise ExhibitError(
                "metadata values must be strings (got %r for %r)"
                % (type(value).__name__, key)
            )
    atts: Dict[str, bytes] = dict(attachments or {})
    for key, value in atts.items():
        if not isinstance(value, (bytes, bytearray)):
            raise ExhibitError(
                "attachment values must be bytes (got %r for %r)"
                % (type(value).__name__, key)
            )
    sealed_at = _utcnow()
    salt = secrets.token_hex(16)
    seal = _seal_digest(label, claim, meta, _attachment_digests(atts), sealed_at, salt)
    return Exhibit(
        format=EXHIBIT_FORMAT,
        label=label,
        claim=claim,
        metadata=tuple(sorted(meta.items())),
        attachments=tuple(sorted(atts.items())),
        sealed_at=sealed_at,
        salt=salt,
        seal=seal,
        log=(),
    )


def _entry_digest(prev: str, timestamp: str, handler: str, action: str) -> str:
    return _digest(
        _canonical(
            {"prev": prev, "timestamp": timestamp, "handler": handler, "action": action}
        )
    )


def log_handling(exhibit: Exhibit, handler: str, action: str) -> Exhibit:
    """Append one handling entry to the exhibit's chain-of-custody log.

    Returns a NEW exhibit; the input is unchanged (append-only, no edits).
    """
    if not handler or not handler.strip():
        raise ExhibitError("handler is required")
    if not action or not action.strip():
        raise ExhibitError("action is required")
    prev = exhibit.log[-1].entry_digest if exhibit.log else exhibit.seal
    timestamp = _utcnow()
    entry = HandlingEntry(
        timestamp=timestamp,
        handler=handler,
        action=action,
        entry_digest=_entry_digest(prev, timestamp, handler, action),
    )
    # Rebuild via object.__new__-free path: dataclasses.replace keeps frozen intact.
    from dataclasses import replace

    return replace(exhibit, log=exhibit.log + (entry,))


def inspect_exhibit(exhibit: Exhibit) -> str:
    """Verify an exhibit: recompute the seal and the whole handling chain.

    Returns INTACT only if the seal recomputes from the sealed fields AND
    every handling entry's digest recomputes. TAMPERED otherwise.
    The verdict covers custody integrity — never claim truth.
    """
    if exhibit.format != EXHIBIT_FORMAT:
        return TAMPERED
    recomputed = _seal_digest(
        exhibit.label,
        exhibit.claim,
        dict(exhibit.metadata),
        _attachment_digests(dict(exhibit.attachments)),
        exhibit.sealed_at,
        exhibit.salt,
    )
    if recomputed != exhibit.seal:
        return TAMPERED
    prev = exhibit.seal
    for entry in exhibit.log:
        if entry.entry_digest != _entry_digest(
            prev, entry.timestamp, entry.handler, entry.action
        ):
            return TAMPERED
        prev = entry.entry_digest
    return INTACT


def render_exhibit(exhibit: Exhibit) -> str:
    """Render the exhibit as a plain-text evidence card."""
    lines = [
        "EXHIBIT %s" % (exhibit.label or "(unlabeled)"),
        "sealed: %s" % exhibit.sealed_at,
        "seal: %s" % exhibit.seal[:16],
        "",
        "CLAIM (verbatim):",
        exhibit.claim,
    ]
    if exhibit.metadata:
        lines.append("")
        lines.append("METADATA:")
        for key, value in exhibit.metadata:
            lines.append("  %s: %s" % (key, value))
    if exhibit.attachments:
        lines.append("")
        lines.append("ATTACHMENTS:")
        for name, data in exhibit.attachments:
            lines.append(
                "  %s (%d bytes, sha256:%s)"
                % (name, len(data), hashlib.sha256(data).hexdigest()[:16])
            )
    if exhibit.log:
        lines.append("")
        lines.append("CHAIN OF CUSTODY:")
        for entry in exhibit.log:
            lines.append(
                "  %s  %s  %s" % (entry.timestamp, entry.handler, entry.action)
            )
    lines.append("")
    lines.append("VERDICT: %s" % inspect_exhibit(exhibit))
    lines.append("")
    lines.append(HONESTY_FOOTER)
    return "\n".join(lines)
