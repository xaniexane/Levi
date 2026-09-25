"""MOOD — honeypot decoy for abusive/snooping sessions. The declared laws.

Provenance (Chauncey, 2026-09-22):
    doom.py (struck play-to-lose engine; stored/2026-09-22-doom-engine/)
      -> mood (this module; the decoy reframing)

The OLD play-to-lose framing stays STRUCK. This module is NOT a game,
NOT a narrative engine, and NEVER touches real systems. It is a
honeypot: an open, readable frame full of defensive tripwires for
sessions Chauncey has decided are abusive. Defensive blue-team only.

Zone law: SFW, stdlib-only, no network, no subprocess, no filesystem
writes outside the caller-supplied home. Files are written mode 0600.
"""

from __future__ import annotations

__all__ = ["LAWS", "LAW_NAMES", "ZONE"]

ZONE = "mood"

#: Laws L1..L9 — the invariants everything in this module must hold.
LAWS = {
    "L1": (
        "NO_SILENT_REROUTE — mood never decides who is abusive. A session "
        "enters the decoy only through an explicit, recorded routing decision "
        "made by Chauncey or his delegate. routing.route_to_mood raises "
        "PolicyRequiredError unless a policy entry names that session. No "
        "automatic, heuristic, or model-driven rerouting of users, ever."
    ),
    "L2": (
        "NEVER_REAL — the decoy never touches real systems. No real vault, "
        "no real files, no real credentials, no network, no subprocess. "
        "Everything the decoy shows is canned, fake, and canary-marked."
    ),
    "L3": (
        "CHAINED_RECEIPTS — every trip and every escalation writes a "
        "hash-chained receipt. Each receipt commits the previous chain head; "
        "evidence is append-only JSONL under a caller-supplied home, mode 0600. "
        "Tampering breaks the chain and is detectable."
    ),
    "L4": (
        "ALERT_CHAUNCEY — every trip enqueues an alert for Chauncey "
        "immediately. The module writes the alert to the local alert queue; "
        "delivery to Chauncey is the host's job. The module itself never sends "
        "anything over a network."
    ),
    "L5": (
        "DEFENSIVE_ONLY — booby traps are observation and containment only: "
        "canary tokens, fake admin surfaces, tripwire paths, throttles. They "
        "never damage, never counter-attack, never exfiltrate, never touch the "
        "visitor's machine. Blue-team only; this is a decoy, not a weapon."
    ),
    "L6": (
        "REVERSIBLE_CONTAINMENT — rate-limit escalation is local, bounded, "
        "and decays. The decoy may slow and contain a probing session; it may "
        "not ban, destroy, or permanently mark anyone. Escalation always "
        "unwinds."
    ),
    "L7": (
        "FLAGGED — every interaction inside mood is tagged MOOD in receipts "
        "and alerts. Decoy traffic never mixes with genuine traffic in any "
        "log or record."
    ),
    "L8": (
        "DETERMINISTIC — canned decoy responses are seed-deterministic: same "
        "session seed plus same input yields the same output. Responses are "
        "fixed templates, so no real data can ever leak through them."
    ),
    "L9": (
        "OPEN_FRAME — the code is readable and documented; traps are declared "
        "in the README as defensive only. Nothing is obfuscated, packed, or "
        "hidden. The frame is open like system files; the defenses are traps, "
        "not secrets."
    ),
}

#: Law short names, in order.
LAW_NAMES = [
    "NO_SILENT_REROUTE",
    "NEVER_REAL",
    "CHAINED_RECEIPTS",
    "ALERT_CHAUNCEY",
    "DEFENSIVE_ONLY",
    "REVERSIBLE_CONTAINMENT",
    "FLAGGED",
    "DETERMINISTIC",
    "OPEN_FRAME",
]
