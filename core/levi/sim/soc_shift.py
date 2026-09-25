"""Scenario 2 — ``soc-shift``: a simulated night-shift SOC feed.

A seeded stream of ~25 fictional security events flows past: benign
noise, real attack patterns (brute-force logons, C2 beaconing, data
exfiltration, and friends), and false positives. The operator triages
each alert — investigate / escalate / dismiss — and is scored on the
calls. All prose is original fiction; hosts live in ``.sim``/``.test``
or RFC 5737 documentation ranges so nothing real is ever named.

Zero network, zero disk writes: pure stdlib console interaction.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional

from levi.ux import Table, banner, menu, meter, rule, typing_print

# (title, detail, investigate-reveal) — all original fictional prose.
_ATTACKS = [
    (
        "412 failed VPN logons for svc-backup in 6 minutes",
        "Source 203.0.113.88 has no asset record. Three service accounts "
        "tried in rotation — classic password spray cadence.",
        "Logs confirm the pattern across all three accounts. This is a "
        "live brute-force campaign, not a typo.",
    ),
    (
        "WS-1187 beaconing to 203.0.113.44 every 60 seconds",
        "Outbound HTTPS with near-perfect 60s intervals and tiny jitter. "
        "The destination is not on any allowlist.",
        "The beacon survived a reboot and a new DHCP lease. This is live "
        "command-and-control.",
    ),
    (
        "3.1 GB outbound from FILESRV-02 to an unlisted host",
        "Chunked, encrypted transfers over port 443 to a host with no DNS "
        "history. DLP flagged archive filenames in the flow metadata.",
        "Transfer volume matches the finance share almost byte for byte. "
        "Active data exfiltration.",
    ),
    (
        "Credential-harvest link clicked; session replayed from new ASN",
        "op.nightowl clicked a lookalike-portal link at 01:14. Twenty "
        "minutes later the session token appeared from a new ASN.",
        "Mailbox rules were created to hide replies. The account is compromised.",
    ),
    (
        "Impossible travel: Chicago and Frankfurt 11 minutes apart",
        "op.nightowl authenticated from Chicago at 02:03 and Frankfurt at "
        "02:14. No corporate VPN in either path.",
        "The Frankfurt session exits through a consumer VPN provider. "
        "Real account takeover.",
    ),
    (
        "vssadmin delete shadows executed on WS-1042",
        "Shadow copies were wiped at 03:02, followed by a burst of file "
        "renames with a new extension.",
        "This is the textbook ransomware staging sequence. Encryption is "
        "likely minutes away.",
    ),
    (
        "New webshell: /static/.cache.php on web-03",
        "File first seen 03:12, contains an eval() dropper, and has been "
        "requested 40 times tonight from two external IPs.",
        "The dropper already fetched a second stage. The web tier is compromised.",
    ),
    (
        "PsExec-style service creation WS-1187 -> WS-1190",
        "A remote service was installed with the same credential on three "
        "hosts in nine minutes. No change ticket exists.",
        "Same credential, three hosts, no ticket. Confirmed lateral movement.",
    ),
    (
        "9,400 DNS queries for long random labels from WS-1055",
        "Thousands of TXT queries under throwaway labels, each answered "
        "with an encoded blob. Volume started at midnight.",
        "The TXT answers decode to structured data. This is a DNS "
        "exfiltration channel.",
    ),
]

# False positives: correct call is dismiss.
_FALSE_POSITIVES = [
    (
        "Outbound spike from BACKUP-01 during the 02:00 window",
        "Traffic to the vault range jumped 40x at 02:00. Pattern resembles "
        "bulk exfiltration.",
        "It matches the scheduled backup manifest byte for byte. Expected "
        "traffic — the 02:00 window is sacred.",
    ),
    (
        "Port scan detected from 198.51.100.23 against DMZ hosts",
        "SYN sweep across the DMZ from a documentation-range IP. Looks "
        "hostile at first glance.",
        "The source is the authorized pentest range and change window "
        "CHG-2214 is open. Friendly fire.",
    ),
    (
        "14 MFA pushes to the exec's phone in two minutes",
        "Push fatigue pattern — or an exec at an airport approving logins "
        "while juggling boarding passes.",
        "Helpdesk confirmed the device and the travel itinerary. Benign — "
        "the exec just can't find the gate.",
    ),
    (
        "Vulnerability scanner sweeping 10.0.4.0/24",
        "Nessus-like probe cadence across the whole subnet. Noisy and indiscriminate.",
        "It's SEC-SCANNER-01 running the quarterly scan. Scheduled, authorized, loud.",
    ),
    (
        "Traffic burst to CDN edge nodes after a deploy",
        "Edge traffic spiked 12x right after the 03:40 deploy. Smells "
        "like a cache-poisoning wave.",
        "The deploy pipeline purged the CDN at 03:40. Expected burst — "
        "caches refilling.",
    ),
    (
        "Synthetic login storm from perf-rig-02",
        "Two thousand logins a minute from a single rig. Brute force? Load test?",
        "Perf team ticket PERF-883: authorized load test against staging. "
        "Loud but friendly.",
    ),
]

_NOISE = [
    (
        "Heartbeat OK from 214 agents",
        "Fleet check-in nominal; 3 agents stale, within tolerance.",
    ),
    ("WSUS patch cycle finished on 38 hosts", "Two hosts pending reboot; no failures."),
    ("DNS resolver latency p99 41ms", "Within the normal band for this hour."),
    (
        "Single failed logon for a locked-out intern account",
        "Account already disabled; no follow-up needed.",
    ),
    (
        "Printer spooler restarted on PRINT-01",
        "Queue flushed; nobody will notice at 3 AM.",
    ),
    ("Proxy cache hit ratio 94%", "A quiet night for the web cache."),
    ("NTP drift corrected on DC-02", "Clock skew was 1.8s; now nominal."),
    ("Honeypot untouched for 72 hours", "The decoys sit quiet. Suspiciously peaceful."),
    ("SIEM ingestion 12.4k events/sec", "Within quota; hot storage at 61%."),
    (
        "Status-page cert expires in 21 days",
        "Ticket opened automatically; low priority.",
    ),
]

_OPTIONS = [
    "Investigate — pull logs and context first",
    "Escalate — page the incident commander now",
    "Dismiss — close as benign",
]
_CALL_NAMES = ["investigate", "escalate", "dismiss"]

# points per choice index, and the correct choice index
_ATTACK_POINTS = {0: 5, 1: 15, 2: -20}
_FP_POINTS = {0: 2, 1: -5, 2: 10}
_ATTACK_CORRECT = 1
_FP_CORRECT = 2


@dataclass
class SimEvent:
    time: str
    kind: str  # "noise" | "alert"
    attack: Optional[bool]  # None for noise
    title: str
    detail: str
    reveal: str = ""


def _build_events(seed: int) -> List[SimEvent]:
    rng = random.Random(seed)
    slots: List[tuple] = []
    for title, detail, reveal in _ATTACKS:
        slots.append(("alert", True, title, detail, reveal))
    for title, detail, reveal in _FALSE_POSITIVES:
        slots.append(("alert", False, title, detail, reveal))
    for _ in range(10):
        title, detail = rng.choice(_NOISE)
        slots.append(("noise", None, title, detail, ""))
    rng.shuffle(slots)

    events: List[SimEvent] = []
    minutes = 22 * 60
    for kind, attack, title, detail, reveal in slots:
        minutes += rng.randint(11, 19)
        stamp = f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"
        events.append(SimEvent(stamp, kind, attack, title, detail, reveal))
    return events


def _grade(pct: float) -> str:
    if pct >= 90:
        return "S"
    if pct >= 75:
        return "A"
    if pct >= 50:
        return "B"
    return "C"


def run(seed: int | None = None) -> int:
    """Run the soc-shift simulation. Returns a process exit code."""
    print(
        banner(
            "SIMULATION — SOC NIGHT SHIFT",
            "A fictional 22:00-06:00 shift. Every event, host, and person "
            "below is simulated.",
        )
    )
    if seed is None:
        seed = random.SystemRandom().randrange(1, 999_999)
        print(f"(no seed given — this run's seed is {seed}; reuse it to replay)")
    seed = int(seed)

    typing_print(
        "You are the night-shift analyst. The feed below mixes routine "
        "noise, real attack patterns, and false positives."
    )
    typing_print(
        "Triage each alert: INVESTIGATE for context (partial credit), "
        "ESCALATE real attacks, DISMISS the benign. Missing a real attack "
        "hurts. Crying wolf costs you too."
    )
    print(rule())

    events = _build_events(seed)
    rows: List[List[object]] = []
    earned = 0
    max_pts = 0
    triaged = 0

    for ev in events:
        tag = "ALERT" if ev.kind == "alert" else "noise"
        typing_print(f"[{ev.time}] [{tag}] (simulated) {ev.title}")
        typing_print(f"    {ev.detail}")
        if ev.kind != "alert":
            continue
        triaged += 1
        correct = _ATTACK_CORRECT if ev.attack else _FP_CORRECT
        points = _ATTACK_POINTS if ev.attack else _FP_POINTS
        max_pts += max(points.values())

        choice = menu(_OPTIONS, prompt="Your call (simulated)")
        if choice is None:
            print("  (no input — treated as dismiss)")
            choice = 2
        pts = points[choice]
        earned += pts
        if choice == 0:
            typing_print(f"  Investigation notes (simulated): {ev.reveal}")

        verdict = "CORRECT" if choice == correct else "wrong"
        sign = "+" if pts >= 0 else ""
        typing_print(
            f"  You: {_CALL_NAMES[choice]} ({sign}{pts}) — {verdict}; "
            f"right call was {_CALL_NAMES[correct]}. (simulated scoring)"
        )
        rows.append(
            [
                ev.time,
                ev.title[:34],
                _CALL_NAMES[choice],
                _CALL_NAMES[correct],
                f"{sign}{pts}",
            ]
        )
        print(rule())

    pct = 100.0 * earned / max_pts if max_pts else 0.0
    grade = _grade(pct)
    print(banner("SHIFT REPORT (SIMULATED)", f"{triaged} alerts triaged."))
    Table(["Time", "Alert", "Your call", "Right call", "Pts"], rows).print()
    print()
    typing_print(f"Shift score: {earned} / {max_pts}  {meter(max(earned, 0), max_pts)}")
    print(banner(f"GRADE: {grade} (SIMULATED)", f"{pct:.0f}% of available points."))
    print(
        banner(
            "SIMULATION COMPLETE",
            "No real network, no real incidents, no real pagers were "
            "harmed in this shift.",
        )
    )
    return 0
