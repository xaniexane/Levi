"""LEVI Sentinel — defensive blue-team host tooling.

Original LEVI-native implementation. Concepts adapted from legacy LEVI
August-lineage defensive scripts (source-sync entry ``the-pack``):
auto-defense monitoring, forensic orchestration, elite-guard watching,
network new-device detection, file triage scanning, HITL malware triage.
No source text copied.

Everything here is strictly defensive: read-only detection, HITL-gated
containment, file-integrity baselines, and forensic case management for
systems you own or are authorized to protect. Nothing here attacks,
scans anyone else's systems, or runs automatically — consequential
actions follow Plan → Preview → Permission → Execute → Verify → Receipt.

Stdlib-only.
"""

from __future__ import annotations

from . import contain, forensics, integrity, triage, watch

__all__ = ["watch", "integrity", "triage", "forensics", "contain"]
