"""The export covenant verifier — the Yahoo Groups purge revival.

The dead platform: Yahoo Groups (purge announced Oct 16, 2019; ~10M
groups deleted by Dec 14, 2019; full shutdown Dec 15, 2020). The
official export missed whole content classes; rate limits and CAPTCHAs
obstructed Archive Team's rescue (~1.8B messages from ~1.5M groups).
The contract the purge revealed: your decades of community labor are
their liability.

LEVI's addition, inside the Liberation Ledger's export -> verify ->
migrate -> delete pipeline:

- ``declare_manifest`` — the owner declares what the community holds:
  every content class (messages, files, photos, polls, calendars,
  databases, links, ...) with an expected item count and a class
  digest.
- ``export_integrity_check`` — proves the export honors the manifest:
  no content class silently dropped, counts and digests matching.
  A dropped class is a *failure*, never a warning.
- ``shutdown_gate`` — the dead-man's trigger: it refuses to declare
  the export complete (and therefore refuses shutdown/migration) while
  the check fails. There is no flag that skips it.

Invariants (law -> guard -> prove; the tests are the proof):
1. No silent drops — a declared class missing from the artifacts is
   always reported as a failure naming the class.
2. Counts and digests are evidence — a mismatch is a failure, never
   downgraded to a warning.
3. The gate cannot be bypassed — ``shutdown_gate`` takes only the
   check report; there is no ``force`` parameter and no env var.
4. Clearance is a receipt — it names every class, its count, and its
   digest, so a future audit can re-verify.
5. Undeclared classes are noticed — artifacts carrying a class the
   manifest never declared are reported as warnings (a leak in the
   other direction is still a leak).

Stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Mapping, Sequence

__all__ = [
    "CovenantError",
    "CheckReport",
    "class_digest",
    "declare_manifest",
    "export_integrity_check",
    "shutdown_gate",
]


class CovenantError(Exception):
    """The manifest or the check inputs were malformed."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def class_digest(items: Sequence[bytes]) -> str:
    """Stable digest for one content class.

    sha256 over the sorted per-item sha256 hex digests — order-free,
    so the same class exported in any order verifies identically.
    """
    if any(not isinstance(i, (bytes, bytearray)) for i in items):
        raise CovenantError("class items must be bytes")
    item_digests = sorted(
        hashlib.sha256(bytes(i)).hexdigest() for i in items
    )
    return hashlib.sha256("\n".join(item_digests).encode("utf-8")).hexdigest()


def declare_manifest(
    classes: Mapping[str, Mapping[str, object]],
) -> Dict:
    """Declare what the community holds.

    ``classes`` maps a content-class name (``"messages"``, ``"photos"``,
    ...) to ``{"count": int, "digest": hex}``. The digest should come
    from :func:`class_digest` over the source data.
    """
    if not classes:
        raise CovenantError("a manifest must declare at least one class")
    declared: Dict[str, Dict[str, object]] = {}
    for name, spec in classes.items():
        name = str(name).strip()
        if not name:
            raise CovenantError("content class names must be non-empty")
        if not isinstance(spec, Mapping):
            raise CovenantError("class %r spec must be a mapping" % name)
        count = spec.get("count")
        digest = spec.get("digest")
        if not isinstance(count, int) or count < 0:
            raise CovenantError("class %r needs a non-negative int count" % name)
        if not isinstance(digest, str) or not digest:
            raise CovenantError("class %r needs a digest" % name)
        declared[name] = {"count": count, "digest": digest}
    return {
        "manifest_id": "xcm-" + uuid.uuid4().hex[:12],
        "declared_at": _now(),
        "classes": declared,
    }


@dataclass
class CheckReport:
    manifest_id: str
    checked_at: str = field(default_factory=_now)
    ok: bool = False
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    verified_classes: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "manifest_id": self.manifest_id,
            "checked_at": self.checked_at,
            "ok": self.ok,
            "failures": list(self.failures),
            "warnings": list(self.warnings),
            "verified_classes": [dict(v) for v in self.verified_classes],
        }


def export_integrity_check(
    manifest: Mapping, artifacts: Mapping[str, Sequence[bytes]]
) -> CheckReport:
    """Prove the export honors the manifest.

    ``artifacts`` maps content-class names to the exported item bytes.
    Every declared class must be present with matching count and
    digest; artifact classes the manifest never declared are warnings.
    """
    if not isinstance(manifest, Mapping) or "classes" not in manifest:
        raise CovenantError("manifest malformed")
    declared = manifest["classes"]
    if not isinstance(declared, Mapping):
        raise CovenantError("manifest classes malformed")
    if not isinstance(artifacts, Mapping):
        raise CovenantError("artifacts must be a mapping")

    report = CheckReport(manifest_id=str(manifest.get("manifest_id", "unknown")))
    for name, spec in sorted(declared.items()):
        if name not in artifacts:
            report.failures.append(
                "class %r declared in the manifest is MISSING from the "
                "export — silently dropped" % name
            )
            continue
        items = artifacts[name]
        if not isinstance(items, Sequence) or isinstance(items, (bytes, str)):
            report.failures.append(
                "class %r artifacts are not an item sequence" % name
            )
            continue
        expected_count = int(spec["count"])
        if len(items) != expected_count:
            report.failures.append(
                "class %r count mismatch: manifest declares %d, export "
                "holds %d" % (name, expected_count, len(items))
            )
            continue
        try:
            digest = class_digest(items)
        except CovenantError as exc:
            report.failures.append("class %r unreadable: %s" % (name, exc))
            continue
        if digest != spec["digest"]:
            report.failures.append(
                "class %r digest mismatch: export does not match the "
                "declared content" % name
            )
            continue
        report.verified_classes.append(
            {"class": name, "count": len(items), "digest": digest}
        )
    for name in sorted(artifacts):
        if name not in declared:
            report.warnings.append(
                "class %r present in the export but never declared in the "
                "manifest — undeclared content" % name
            )
    report.ok = not report.failures
    return report


def shutdown_gate(report: CheckReport) -> Dict:
    """The dead-man's trigger: refuse shutdown while export is incomplete.

    Takes only the check report — there is no bypass. Returns
    ``{"allowed": True, "receipt": {...}}`` on a clean check, or
    ``{"allowed": False, "reason": ..., "failures": [...]}`` refusing.
    """
    if not isinstance(report, CheckReport):
        raise CovenantError("shutdown_gate takes a CheckReport")
    if not report.ok:
        return {
            "allowed": False,
            "reason": (
                "export incomplete — %d failed class check(s); shutdown "
                "refused until every declared class verifies"
                % len(report.failures)
            ),
            "failures": list(report.failures),
            "manifest_id": report.manifest_id,
        }
    return {
        "allowed": True,
        "receipt": {
            "manifest_id": report.manifest_id,
            "checked_at": report.checked_at,
            "classes": [dict(v) for v in report.verified_classes],
            "warnings": list(report.warnings),
            "covenant": "every declared class verified present, counted, "
            "and digest-matched; shutdown permitted",
        },
    }
