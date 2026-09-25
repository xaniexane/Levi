"""The Kontor Years: Hanseatic merchant immersion training.

Origin: young Hanseatic merchants spent 7-10 years in extraterritorial
trading enclaves under strict discipline — narrow dormitories,
12-hour days, a strict hierarchy from Stubenjunge (lowest) to Meister.
The training was total immersion: the apprentice lived inside the
commercial network — its laws (Lubeck law), its accounting, its
correspondence (Lubeck wax tablets from ~1370 preserve student copies
of business letters). Even the celibacy rules and guard dogs were
explicitly about trade-secret protection: the posting itself was the
training.

What it is in LEVI: ``ImmersionPosting`` — a posting to a host domain
with required practices (the domain's laws, its accounting, its
correspondence) and a duration. Days are served one at a time and
evidence is filed per practice; ``complete`` is refused until every
practice has evidence and the full duration is served. The posting is
the training — there is no shortcut around living inside the domain.

Honesty label: LOAD-BEARING — per-practice evidence checklist plus a
served-duration gate is a concrete, transferable mechanism.

Deny-closed inputs: empty host domain, an empty or duplicate practice
list, a non-positive duration, evidence for an unknown practice, empty
evidence, serving days after completion, and completing before every
practice has evidence and the full duration is served are all rejected
with ValueError.
"""

from __future__ import annotations

__all__ = ["ImmersionPosting"]


class ImmersionPosting:
    """A total-immersion foreign posting: live inside the host domain's
    laws, accounting, and correspondence until the duration is served
    and every practice has evidence."""

    def __init__(
        self,
        host_domain: str,
        practices: list[str] | tuple[str, ...],
        duration_days: int,
    ):
        if not isinstance(host_domain, str) or not host_domain.strip():
            raise ValueError("host_domain must be a non-empty string")
        self.host_domain = host_domain.strip()
        if not isinstance(practices, (list, tuple)) or not practices:
            raise ValueError("practices must be a non-empty list of strings")
        cleaned = []
        for practice in practices:
            if not isinstance(practice, str) or not practice.strip():
                raise ValueError("practices must be non-empty strings")
            practice = practice.strip()
            if practice.lower() in (p.lower() for p in cleaned):
                raise ValueError(f"duplicate practice: {practice!r}")
            cleaned.append(practice)
        self.practices = cleaned
        if (
            not isinstance(duration_days, int)
            or isinstance(duration_days, bool)
            or duration_days < 1
        ):
            raise ValueError("duration_days must be a positive integer")
        self.duration_days = duration_days
        self._evidence: dict[str, str] = {}
        self._days_served = 0
        self._completed = False

    # -- living inside the domain ----------------------------------------------
    def serve_day(self) -> int:
        """Serve one day of the posting. Returns total days served."""
        if self._completed:
            raise ValueError("posting already complete; no more days to serve")
        self._days_served += 1
        return self._days_served

    def submit_evidence(self, practice: str, evidence: str) -> None:
        """File evidence of practicing one of the domain's ways —
        its laws, its accounting, its correspondence."""
        if self._completed:
            raise ValueError("posting already complete; no more evidence needed")
        match = next(
            (p for p in self.practices if p.lower() == str(practice).strip().lower()),
            None,
        )
        if match is None:
            raise ValueError(
                f"unknown practice: {practice!r}; "
                f"required practices are {self.practices}"
            )
        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError("evidence must be a non-empty string")
        self._evidence[match] = evidence.strip()

    # -- the posting is the training ----------------------------------------------
    def missing(self) -> dict:
        """What still stands between the apprentice and completion."""
        return {
            "practices_without_evidence": [
                p for p in self.practices if p not in self._evidence
            ],
            "days_remaining": max(0, self.duration_days - self._days_served),
        }

    def complete(self) -> dict:
        """Close the posting. Refused until every practice has evidence
        and the full duration is served — immersion cannot be shortened."""
        if self._completed:
            raise ValueError("posting already complete")
        gaps = self.missing()
        if gaps["practices_without_evidence"] or gaps["days_remaining"]:
            raise ValueError(
                f"posting incomplete: missing evidence for "
                f"{gaps['practices_without_evidence']}, "
                f"{gaps['days_remaining']} days unserved"
            )
        self._completed = True
        return {
            "host_domain": self.host_domain,
            "days_served": self._days_served,
            "practices_evidenced": list(self._evidence),
            "completed": True,
        }

    def status(self) -> dict:
        return {
            "host_domain": self.host_domain,
            "days_served": self._days_served,
            "duration_days": self.duration_days,
            "practices_evidenced": list(self._evidence),
            "completed": self._completed,
        }
