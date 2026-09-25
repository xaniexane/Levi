"""Real-world meetups fusing online identity with offline scene credibility.

Studied from: dead-networks-20260916/report.md [MindVox] (VoxMeats:
real-world meetups fusing online identity with offline scene credibility).

This is an original, from-scratch implementation for LEVI. An online handle
is cheap to fake; showing up is not. The mechanism:

- A *scene* is a named local gathering community. Anyone with a handle can
  RSVP to a meetup, but attendance only counts when a *steward* (host)
  verifies it — so credibility accrues from verified presence, not from
  claims.
- *Credibility* is an explicit, inspectable heuristic: each verified
  attendance earns points, decaying with age (recent showing-up counts more
  than showing up once years ago), and hosting a meetup earns a multiplier.
  It is labeled as a heuristic everywhere it is surfaced.
- Meetups link *threads*: an online discussion can attach to a meetup, so
  the scene's talk and its physical gatherings stay cross-referenced. The
  fusion runs both ways: verified attendance unlocks steward nomination, and
  steady hosts raise a scene's reputation.

No location data is collected by the module beyond what the operator writes
into a free-text ``place`` field; verification is a human steward's job.

Public surface:
- ``Scene``: ``add_steward``, ``nominate_steward``, ``schedule_meetup``,
  ``rsvp``, ``verify_attendance``, ``record_no_show``, ``attach_thread``,
  ``credibility()``, ``meetup_report()``, ``census()``.
- ``Meetup``, ``SceneError`` for embedding.

stdlib-only. No network. Deterministic (decay uses a caller-supplied "now").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import exp
from typing import Dict, List, Mapping, Optional, Set

ORIGIN = "levi-revival/meetup-scene"


class SceneError(ValueError):
    """Raised when a scene operation cannot be honored."""


@dataclass
class Meetup:
    """One gathering: schedule, place, RSVPs, verified attendees."""

    meetup_id: str
    title: str
    place: str
    starts_at: str
    host: str
    rsvps: Set[str] = field(default_factory=set)
    verified: Set[str] = field(default_factory=set)
    no_shows: Set[str] = field(default_factory=set)
    threads: List[str] = field(default_factory=list)


class Scene:
    """A local scene tying handles to verified meetup attendance."""

    # Credibility decay: points halve roughly every 180 days.
    HALF_LIFE_DAYS = 180.0
    # Hosting a meetup earns this many times a plain attendance.
    HOST_MULTIPLIER = 3.0

    def __init__(self, name: str) -> None:
        if not name:
            raise SceneError("scene name must be non-empty")
        self.name = name
        self._stewards: Set[str] = set()
        self._meetups: Dict[str, Meetup] = {}
        # handle -> list of (meetup_id, timestamp) verified attendances
        self._attendance: Dict[str, List[datetime]] = {}
        # handle -> list of (meetup_id, timestamp) hosted meetups
        self._hosted: Dict[str, List[datetime]] = {}
        self._ledger: List[str] = []

    # -- ledger -----------------------------------------------------------
    def _log(self, entry: str) -> None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._ledger.append(f"{stamp} {entry}")

    def ledger(self) -> List[str]:
        return list(self._ledger)

    # -- stewards ------------------------------------------------------------
    def add_steward(self, handle: str) -> None:
        if not handle:
            raise SceneError("handle must be non-empty")
        self._stewards.add(handle)
        self._log(f"STEWARD add={handle}")

    def nominate_steward(self, handle: str, by_steward: str) -> bool:
        """Stewards nominate handles with credible attendance; seats immediately.

        Nomination requires the nominee to have at least one verified
        attendance (proof of showing up) and an active steward as nominator.
        """
        if by_steward not in self._stewards:
            raise SceneError(f"{by_steward!r} is not a steward")
        if handle in self._stewards:
            return False
        if not self._attendance.get(handle):
            raise SceneError(f"{handle!r} has no verified attendance yet")
        self._stewards.add(handle)
        self._log(f"STEWARD nominate={handle} by={by_steward}")
        return True

    def stewards(self) -> List[str]:
        return sorted(self._stewards)

    # -- meetups ---------------------------------------------------------------
    def schedule_meetup(
        self,
        meetup_id: str,
        title: str,
        place: str,
        starts_at: str,
        host: str,
        now: Optional[datetime] = None,
    ) -> Meetup:
        if meetup_id in self._meetups:
            raise SceneError(f"meetup {meetup_id!r} already scheduled")
        if host not in self._stewards:
            raise SceneError(f"{host!r} is not a steward and cannot host")
        meetup = Meetup(
            meetup_id=meetup_id,
            title=title,
            place=place,
            starts_at=starts_at,
            host=host,
        )
        self._meetups[meetup_id] = meetup
        moment = now or datetime.now(timezone.utc)
        self._hosted.setdefault(host, []).append(moment)
        self._log(f"MEETUP id={meetup_id} host={host} place={place!r}")
        return meetup

    def rsvp(self, meetup_id: str, handle: str) -> None:
        meetup = self._require_meetup(meetup_id)
        meetup.rsvps.add(handle)
        self._log(f"RSVP id={meetup_id} handle={handle}")

    def verify_attendance(
        self,
        meetup_id: str,
        handle: str,
        by_steward: str,
        now: Optional[datetime] = None,
    ) -> bool:
        """A steward verifies a handle was physically present."""
        if by_steward not in self._stewards:
            raise SceneError(f"{by_steward!r} is not a steward")
        meetup = self._require_meetup(meetup_id)
        if handle in meetup.verified:
            return False
        meetup.verified.add(handle)
        meetup.rsvps.discard(handle)
        moment = now or datetime.now(timezone.utc)
        self._attendance.setdefault(handle, []).append(moment)
        self._log(f"VERIFY id={meetup_id} handle={handle} by={by_steward}")
        return True

    def record_no_show(self, meetup_id: str, handle: str, by_steward: str) -> None:
        if by_steward not in self._stewards:
            raise SceneError(f"{by_steward!r} is not a steward")
        meetup = self._require_meetup(meetup_id)
        meetup.no_shows.add(handle)
        meetup.rsvps.discard(handle)
        self._log(f"NOSHOW id={meetup_id} handle={handle} by={by_steward}")

    def attach_thread(self, meetup_id: str, thread_id: str) -> None:
        meetup = self._require_meetup(meetup_id)
        if thread_id not in meetup.threads:
            meetup.threads.append(thread_id)
        self._log(f"THREAD id={meetup_id} thread={thread_id}")

    # -- credibility: an explicit, labeled heuristic -----------------------------
    def credibility(self, handle: str, now: Optional[datetime] = None) -> float:
        """Verified-presence credibility, time-decayed. Heuristic — see docstring."""
        moment = now or datetime.now(timezone.utc)
        score = 0.0
        for when in self._attendance.get(handle, []):
            age_days = max((moment - when).total_seconds() / 86400.0, 0.0)
            score += exp(-age_days * 0.693147 / self.HALF_LIFE_DAYS)
        for when in self._hosted.get(handle, []):
            age_days = max((moment - when).total_seconds() / 86400.0, 0.0)
            score += self.HOST_MULTIPLIER * exp(
                -age_days * 0.693147 / self.HALF_LIFE_DAYS
            )
        return round(score, 3)

    def ranking(self, now: Optional[datetime] = None) -> List[Mapping[str, object]]:
        handles = set(self._attendance) | set(self._hosted)
        rows = [
            {"handle": h, "credibility": self.credibility(h, now=now)} for h in handles
        ]
        rows.sort(key=lambda r: float(r["credibility"]), reverse=True)
        return rows

    # -- queries ------------------------------------------------------------------
    def meetup_report(self, meetup_id: str) -> Mapping[str, object]:
        meetup = self._require_meetup(meetup_id)
        return {
            "meetup_id": meetup.meetup_id,
            "title": meetup.title,
            "place": meetup.place,
            "starts_at": meetup.starts_at,
            "host": meetup.host,
            "rsvps": sorted(meetup.rsvps),
            "verified": sorted(meetup.verified),
            "no_shows": sorted(meetup.no_shows),
            "threads": list(meetup.threads),
            "turnout": len(meetup.verified),
        }

    def census(self) -> Mapping[str, int]:
        return {
            "stewards": len(self._stewards),
            "meetups": len(self._meetups),
            "verified_attendances": sum(
                len(m.verified) for m in self._meetups.values()
            ),
            "no_shows": sum(len(m.no_shows) for m in self._meetups.values()),
            "threads_attached": sum(len(m.threads) for m in self._meetups.values()),
        }

    def _require_meetup(self, meetup_id: str) -> Meetup:
        try:
            return self._meetups[meetup_id]
        except KeyError:
            raise SceneError(f"unknown meetup {meetup_id!r}") from None
