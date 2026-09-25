"""Adapter: bounty findings → knowledge-corpus-ready units.

Pure transform: defensive bounty finding dicts (as produced by
:mod:`levi.bounty.store`) become dated corpus units the knowledge layer can
ingest — without importing the knowledge layer, so this adapter stays
testable and dependency-light.

Output schema per finding::

    {"id": "bounty:<finding-id>",
     "kind": "security-finding",
     "text": str,               # detail (+ evidence, when present)
     "tags": [<finding kind>, "bounty", "defensive"],
     "provenance": {"source": "bounty", "finding_id": str, "target": str,
                    "scope": str, "first_seen": str, "last_seen": str},
     "metadata": {"detail": str, "evidence": str}}

Deny-closed: a finding that is not a dict or lacks a non-empty ``id`` /
``detail`` raises :class:`ValueError` — the transform never emits
half-formed units, and raw evidence is carried verbatim (analysis, not
attack instructions, is the knowledge layer's job downstream).
"""

from __future__ import annotations

from typing import Any, Dict, List


def findings_to_corpus_units(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform bounty finding dicts into knowledge-corpus-ready units."""
    if not isinstance(findings, list):
        raise ValueError(
            "findings_to_corpus_units: expected a list, got %s"
            % type(findings).__name__
        )
    out: List[Dict[str, Any]] = []
    for idx, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise ValueError("finding #%d: not a dict" % idx)
        fid = finding.get("id")
        detail = finding.get("detail")
        if not isinstance(fid, str) or not fid.strip():
            raise ValueError("finding #%d: missing non-empty 'id'" % idx)
        if not isinstance(detail, str) or not detail.strip():
            raise ValueError("finding #%d: missing non-empty 'detail'" % idx)
        evidence = finding.get("evidence") or ""
        text = detail.strip()
        if isinstance(evidence, str) and evidence.strip():
            text += "\nEvidence: %s" % evidence.strip()
        kind = str(finding.get("kind", "finding") or "finding")
        out.append(
            {
                "id": "bounty:%s" % fid.strip(),
                "kind": "security-finding",
                "text": text,
                "tags": [kind, "bounty", "defensive"],
                "provenance": {
                    "source": "bounty",
                    "finding_id": fid.strip(),
                    "target": finding.get("target"),
                    "scope": finding.get("scope"),
                    "first_seen": finding.get("first_seen"),
                    "last_seen": finding.get("last_seen"),
                },
                "metadata": {
                    "detail": detail.strip(),
                    "evidence": evidence if isinstance(evidence, str) else "",
                },
            }
        )
    return out
