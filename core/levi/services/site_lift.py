"""The strengthened Site Lift — the five-pass program.

A single lift is a coat of paint. The strengthened lift runs a site
through five passes so it brings users in, retains them, intrigues
them, procures income, and leaves the site feature-rich:

  Round 1  FOUNDATION  — baseline: speed-readiness, structure, copy
                           clarity, contact paths, trust. (measured)
  Round 2  FEATURE     — enrichment: booking, pricing, proof, gallery,
                           FAQ, social, analytics. (measured)
  Sig A    INTERPENETRATION — Echo/REIM/RIEM/Mandella pass: graft winning
                           patterns from across the lift portfolio,
                           compost what failed elsewhere. (attested)
  Sig B    ABSORB-RETURN — absorb best-in-class patterns, reverse the
                           structure, improve it, return it in an
                           original unreplicable form. (attested)
  Round 3  CROWN       — regression over rounds 1-2, goal-coverage
                           thresholds on all five goals, showcase
                           readiness. (measured + attested)

Measured checks parse the site's HTML and report what they found —
never fabricated. Attested passes are recorded as performed-by with
notes; the module never auto-passes what it cannot measure.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from levi.packaging.roster_matrix import (
    advise_upgrades,
    resolve_roster,
    roster_receipt,
)

GOALS = ("bring", "retain", "intrigue", "income", "feature")


class LiftError(ValueError):
    """Raised when a lift program is misconfigured."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _home() -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    return Path(base).expanduser()


def _lifts_dir(home: Optional[Path] = None) -> Path:
    d = (home or _home()) / "services" / "lifts"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Site snapshot — honest static parse of a site directory.
# ---------------------------------------------------------------------------


class _Snap(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.titles: List[str] = []
        self.metas: Dict[str, str] = {}
        self.h1: List[str] = []
        self.links: List[Tuple[str, str]] = []  # (href, text)
        self.imgs: List[str] = []  # alt texts ("" when missing)
        self.forms = 0
        self.scripts: List[str] = []
        self.text: List[str] = []
        self._in_title = False
        self._in_h1 = False
        self._cur_href = ""
        self._cur_link_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
        elif tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            if name:
                self.metas[name] = a.get("content", "")
        elif tag == "a":
            self._cur_href = a.get("href", "")
            self._cur_link_text = []
        elif tag == "img":
            self.imgs.append(a.get("alt", ""))
        elif tag == "form":
            self.forms += 1
        elif tag == "script":
            src = a.get("src", "")
            if src:
                self.scripts.append(src)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "a":
            self.links.append((self._cur_href, " ".join(self._cur_link_text).strip()))
            self._cur_href = ""
            self._cur_link_text = []

    def handle_data(self, data: str) -> None:
        s = data.strip()
        if not s:
            return
        if self._in_title:
            self.titles.append(s)
        if self._in_h1:
            self.h1.append(s)
        if self._cur_href:
            self._cur_link_text.append(s)
        self.text.append(s)


@dataclass
class SiteSnapshot:
    """Everything the measured checks observed across the site's pages."""

    pages: int = 0
    titles: List[str] = field(default_factory=list)
    metas: Dict[str, str] = field(default_factory=dict)
    h1: List[str] = field(default_factory=list)
    links: List[Tuple[str, str]] = field(default_factory=list)
    imgs: List[str] = field(default_factory=list)
    forms: int = 0
    scripts: List[str] = field(default_factory=list)
    text: str = ""


def surfaces(snap: SiteSnapshot) -> List[Tuple[str, str]]:
    """The named searchable surfaces of a snapshot, in probe priority
    order. Probes report which surface a match came from, so a hit on a
    bare href or a script src is evidence, not a guess."""
    return [
        ("page text", snap.text),
        ("link text", "\n".join(t for _, t in snap.links)),
        ("headings", "\n".join(snap.titles + snap.h1)),
        ("link urls", "\n".join(h for h, _ in snap.links)),
        ("script srcs", "\n".join(snap.scripts)),
    ]


def snapshot_site(site_dir: str | Path) -> SiteSnapshot:
    """Parse every .html/.htm page under site_dir. Honest: reports only
    what the files contain; a missing directory is an error, not an
    empty site."""
    root = Path(site_dir)
    if not root.is_dir():
        raise LiftError(f"site_dir is not a directory: {site_dir}")
    snap = SiteSnapshot()
    pages: List[Path] = []
    for suffix in ("*.html", "*.htm"):
        pages.extend(p for p in root.rglob(suffix) if p.is_file())
    pages.sort()
    texts: List[str] = []
    for page in pages:
        try:
            raw = page.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        p = _Snap()
        try:
            p.feed(raw)
        except Exception:
            continue
        snap.pages += 1
        snap.titles += p.titles
        snap.h1 += p.h1
        snap.links += p.links
        snap.imgs += p.imgs
        snap.forms += p.forms
        snap.scripts += p.scripts
        texts += p.text
        for k, v in p.metas.items():
            snap.metas.setdefault(k, v)
    snap.text = "\n".join(texts)
    return snap


# ---------------------------------------------------------------------------
# Measured checks — (id, label, goals, probe). Probe returns (passed, evidence).
# ---------------------------------------------------------------------------

Probe = Callable[[SiteSnapshot], Tuple[bool, str]]


def _has(pattern: str) -> Probe:
    rx = re.compile(pattern, re.IGNORECASE)

    def probe(snap: SiteSnapshot) -> Tuple[bool, str]:
        for name, text in surfaces(snap):
            m = rx.search(text)
            if m:
                return True, f"matched {m.group(0)!r} in {name}"
        return (
            False,
            "no match in page text, link text, headings, link urls, or script srcs",
        )

    return probe


FOUNDATION_CHECKS: List[Tuple[str, str, Tuple[str, ...], Probe]] = [
    (
        "f-title",
        "page has a real <title>",
        ("bring",),
        lambda s: (
            any(t.strip() for t in s.titles),
            f"titles: {s.titles[:2]}" if s.titles else "no <title> found",
        ),
    ),
    (
        "f-meta-desc",
        "meta description present",
        ("bring",),
        lambda s: (
            bool(s.metas.get("description", "").strip()),
            f"description: {s.metas.get('description', '')[:80]!r}",
        ),
    ),
    (
        "f-viewport",
        "mobile viewport declared",
        ("retain",),
        lambda s: ("viewport" in s.metas, f"viewport: {s.metas.get('viewport', '')!r}"),
    ),
    (
        "f-h1",
        "page has an h1 heading",
        ("bring",),
        lambda s: (bool(s.h1), f"h1s: {s.h1[:2]}" if s.h1 else "no h1 found"),
    ),
    (
        "f-contact",
        "a contact path exists (tel: link, form, or contact page)",
        ("income",),
        lambda s: (
            any(h.startswith("tel:") for h, _ in s.links)
            or s.forms > 0
            or any("contact" in h.lower() for h, _ in s.links),
            f"{sum(1 for h, _ in s.links if h.startswith('tel:'))} tel: links, "
            f"{s.forms} forms",
        ),
    ),
    (
        "f-cta",
        "a call-to-action is present",
        ("income",),
        _has(
            r"book|call now|schedule|sign up|get started|order|buy|contact us|free quote"
        ),
    ),
    (
        "f-alt",
        "images carry alt text",
        ("bring",),
        lambda s: (
            (all(a.strip() for a in s.imgs) if s.imgs else True),
            f"{sum(1 for a in s.imgs if a.strip())}/{len(s.imgs)} imgs with alt",
        ),
    ),
    (
        "f-pages",
        "site has depth (3+ pages)",
        ("feature",),
        lambda s: (s.pages >= 3, f"{s.pages} html pages found"),
    ),
]

FEATURE_CHECKS: List[Tuple[str, str, Tuple[str, ...], Probe]] = [
    (
        "t-booking",
        "booking / scheduling path",
        ("income",),
        _has(r"book|schedule|appointment|reserve"),
    ),
    (
        "t-pricing",
        "prices or service menu visible",
        ("income",),
        _has(r"\$|pricing|prices|rates|packages"),
    ),
    (
        "t-proof",
        "social proof (testimonials / reviews)",
        ("retain",),
        _has(r"testimonial|review|\brating\b|stars"),
    ),
    (
        "t-gallery",
        "gallery / portfolio / results",
        ("intrigue",),
        _has(r"gallery|portfolio|our work|results|before.*after"),
    ),
    ("t-faq", "FAQ answers objections", ("retain",), _has(r"faq|frequently asked")),
    (
        "t-social",
        "social links outward",
        ("bring",),
        _has(r"facebook|instagram|tiktok|youtube|x\.com|twitter"),
    ),
    (
        "t-og",
        "open-graph tags for sharing",
        ("bring",),
        lambda s: (
            "og:title" in s.metas,
            f"og:title: {s.metas.get('og:title', '')[:60]!r}",
        ),
    ),
    (
        "t-analytics",
        "analytics hook for measuring income",
        ("income",),
        _has(r"analytics|gtag|plausible|umami|matomo"),
    ),
]


# ---------------------------------------------------------------------------
# Signature passes — attested, never auto-passed.
# ---------------------------------------------------------------------------


@dataclass
class Graft:
    """One pattern grafted in during interpenetration."""

    pattern: str
    source: str  # which site / lift in the portfolio it came from
    note: str = ""


@dataclass
class Compost:
    """One failure composted out during interpenetration."""

    failure: str  # what didn't work elsewhere
    lesson: str  # what it taught


@dataclass
class AbsorbReturn:
    """Signature B: absorb -> reverse -> improve -> return."""

    absorbed_from: str  # best-in-class pattern studied
    reversed_into: str  # how its structure was reversed
    improvement: str  # what was made better
    returned_form: str  # the original form it now takes
    unreplicable_note: str = ""


# ---------------------------------------------------------------------------
# Report.
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    check_id: str
    label: str
    goals: Tuple[str, ...]
    kind: str  # measured | attested
    passed: bool
    evidence: str


@dataclass
class RoundResult:
    round_id: str
    name: str
    kind: str  # lift | signature
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def score(self) -> Tuple[int, int]:
        ok = sum(1 for c in self.checks if c.passed)
        return ok, len(self.checks)


@dataclass
class LiftReport:
    report_id: str
    site: str
    provider: str
    rounds: List[RoundResult] = field(default_factory=list)
    goal_tally: Dict[str, int] = field(default_factory=dict)
    created_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        raw = asdict(self)
        return raw

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "LiftReport":
        data = dict(raw)
        rounds = []
        for r in data.get("rounds", []):
            checks = [CheckResult(**c) for c in r.get("checks", [])]
            rounds.append(
                RoundResult(
                    round_id=r["round_id"],
                    name=r["name"],
                    kind=r["kind"],
                    checks=checks,
                )
            )
        data["rounds"] = rounds
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


def _run_measured(
    round_id: str,
    name: str,
    checks: List[Tuple[str, str, Tuple[str, ...], Probe]],
    snap: SiteSnapshot,
) -> RoundResult:
    out = RoundResult(round_id=round_id, name=name, kind="lift")
    for cid, label, goals, probe in checks:
        try:
            passed, evidence = probe(snap)
        except Exception as e:  # a probe must never kill the program
            passed, evidence = False, f"probe error: {e}"
        out.checks.append(
            CheckResult(
                check_id=cid,
                label=label,
                goals=goals,
                kind="measured",
                passed=bool(passed),
                evidence=str(evidence),
            )
        )
    return out


def _run_interpenetration(grafts: List[Graft], composts: List[Compost]) -> RoundResult:
    out = RoundResult(
        round_id="sig-a", name="Signature A — interpenetration", kind="signature"
    )
    for g in grafts:
        out.checks.append(
            CheckResult(
                check_id="s-graft",
                label=f"graft: {g.pattern}",
                goals=("intrigue", "feature"),
                kind="attested",
                passed=True,
                evidence=f"source: {g.source}" + (f" — {g.note}" if g.note else ""),
            )
        )
    for c in composts:
        out.checks.append(
            CheckResult(
                check_id="s-compost",
                label=f"composted: {c.failure}",
                goals=("retain",),
                kind="attested",
                passed=True,
                evidence=f"lesson: {c.lesson}",
            )
        )
    if not grafts and not composts:
        out.checks.append(
            CheckResult(
                check_id="s-empty",
                label="no grafts or composts attested",
                goals=("intrigue",),
                kind="attested",
                passed=False,
                evidence="attest at least one graft or compost to complete the pass",
            )
        )
    return out


def _run_absorb_return(ar: Optional[AbsorbReturn]) -> RoundResult:
    out = RoundResult(
        round_id="sig-b",
        name="Signature B — absorb / reverse / improve / return",
        kind="signature",
    )
    if ar is None:
        out.checks.append(
            CheckResult(
                check_id="s-arir",
                label="absorb-return pass",
                goals=("intrigue", "feature"),
                kind="attested",
                passed=False,
                evidence="no absorb-return attestation supplied",
            )
        )
        return out
    for label, val in (
        ("absorbed", ar.absorbed_from),
        ("reversed", ar.reversed_into),
        ("improved", ar.improvement),
        ("returned", ar.returned_form),
    ):
        ok = bool(val and val.strip())
        out.checks.append(
            CheckResult(
                check_id=f"s-arir-{label}",
                label=f"{label}: {(val or '')[:60]}",
                goals=("intrigue", "feature"),
                kind="attested",
                passed=ok,
                evidence=val or "missing",
            )
        )
    if ar.unreplicable_note:
        out.checks.append(
            CheckResult(
                check_id="s-unreplicable",
                label="unreplicable form noted",
                goals=("intrigue",),
                kind="attested",
                passed=True,
                evidence=ar.unreplicable_note,
            )
        )
    return out


def _run_crown(snap: SiteSnapshot, showcase_summary: str = "") -> RoundResult:
    out = RoundResult(round_id="round-3", name="Round 3 — crown lift", kind="lift")
    # regression: every foundation + feature check must still pass
    for cid, label, goals, probe in FOUNDATION_CHECKS + FEATURE_CHECKS:
        try:
            passed, evidence = probe(snap)
        except Exception as e:
            passed, evidence = False, f"probe error: {e}"
        out.checks.append(
            CheckResult(
                check_id="c-reg:" + cid,
                label=f"regression — {label}",
                goals=goals,
                kind="measured",
                passed=bool(passed),
                evidence=str(evidence),
            )
        )
    # goal coverage: per-goal threshold = min(2, measured checks tagged with
    # that goal). A goal with a single measured check (e.g. intrigue has
    # only t-gallery, feature only f-pages) is covered when that check
    # passes — demanding 2 where only 1 exists made the crown unreachable.
    measured = FOUNDATION_CHECKS + FEATURE_CHECKS
    tagged: Dict[str, List[str]] = {}
    for _cid, _label, _goals, _ in measured:
        for g in _goals:
            tagged.setdefault(g, []).append(_cid)
    tally: Dict[str, int] = {}
    passing: Dict[str, List[str]] = {}
    failing: Dict[str, List[str]] = {}
    _reg_prefix = "c-reg:"
    for c in out.checks:
        base = (
            c.check_id[len(_reg_prefix) :]
            if c.check_id.startswith(_reg_prefix)
            else c.check_id
        )
        for g in c.goals:
            if c.passed:
                tally[g] = tally.get(g, 0) + 1
                passing.setdefault(g, []).append(base)
            else:
                failing.setdefault(g, []).append(base)
    for goal in GOALS:
        n_measured = len(tagged.get(goal, []))
        thr = min(2, max(1, n_measured))
        n = tally.get(goal, 0)
        out.checks.append(
            CheckResult(
                check_id=f"c-goal-{goal}",
                label=f"goal coverage: {goal} ({n}/{thr})",
                goals=(goal,),
                kind="measured",
                passed=n >= thr,
                evidence=(
                    f"{n} passing of {n_measured} measured checks tagged {goal} "
                    f"(threshold {thr}); passing: "
                    f"{', '.join(passing.get(goal, [])) or 'none'}; failing: "
                    f"{', '.join(failing.get(goal, [])) or 'none'}"
                ),
            )
        )
    # showcase readiness is attested
    out.checks.append(
        CheckResult(
            check_id="c-showcase",
            label="showcase summary written",
            goals=("bring", "income"),
            kind="attested",
            passed=bool(showcase_summary and showcase_summary.strip()),
            evidence=showcase_summary or "no showcase summary attested",
        )
    )
    return out


def run_lift_program(
    site_dir: str | Path,
    *,
    provider: str = "levi",
    grafts: Optional[List[Graft]] = None,
    composts: Optional[List[Compost]] = None,
    absorb_return: Optional[AbsorbReturn] = None,
    showcase_summary: str = "",
    report_id: str = "",
) -> LiftReport:
    """Run the five-pass program against a site directory.

    Attested passes (signatures, showcase) are only as complete as the
    attestations supplied — the program never invents them.
    """
    if not provider or not provider.strip():
        raise LiftError("provider must be non-empty")
    snap = snapshot_site(site_dir)
    report = LiftReport(
        report_id=report_id or ("lift_" + uuid.uuid4().hex[:10]),
        site=str(site_dir),
        provider=provider,
    )
    report.rounds.append(
        _run_measured("round-1", "Round 1 — foundation lift", FOUNDATION_CHECKS, snap)
    )
    report.rounds.append(
        _run_measured("round-2", "Round 2 — feature lift", FEATURE_CHECKS, snap)
    )
    report.rounds.append(_run_interpenetration(grafts or [], composts or []))
    report.rounds.append(_run_absorb_return(absorb_return))
    report.rounds.append(_run_crown(snap, showcase_summary))
    tally: Dict[str, int] = {g: 0 for g in GOALS}
    for r in report.rounds:
        for c in r.checks:
            if c.passed:
                for g in c.goals:
                    tally[g] = tally.get(g, 0) + 1
    report.goal_tally = tally
    return report


def save_report(report: LiftReport, *, home: Optional[Path] = None) -> Path:
    p = _report_path(report.report_id, home)
    p.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return p


def load_report(report_id: str, *, home: Optional[Path] = None) -> Optional[LiftReport]:
    p = _report_path(report_id, home)
    if not p.exists():
        return None
    return LiftReport.from_dict(json.loads(p.read_text(encoding="utf-8")))


_SAFE_REPORT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$")


def _report_path(report_id: str, home: Optional[Path] = None) -> Path:
    """The lifts-dir path for a report id. Ids are fenced to a safe
    filename shape so a caller-supplied id can never escape the dir."""
    if not report_id or not _SAFE_REPORT_ID.match(report_id):
        raise LiftError(f"unsafe report id: {report_id!r}")
    return _lifts_dir(home) / f"{report_id}.json"


def describe_program() -> List[Dict[str, str]]:
    """The five passes, for menus and quotes."""
    return [
        {
            "id": "round-1",
            "name": "Round 1 — foundation lift",
            "blurb": "structure, copy clarity, contact paths, trust, mobile baseline",
        },
        {
            "id": "round-2",
            "name": "Round 2 — feature lift",
            "blurb": "booking, pricing, proof, gallery, FAQ, social, analytics",
        },
        {
            "id": "sig-a",
            "name": "Signature A — interpenetration",
            "blurb": "graft winning portfolio patterns; compost what failed",
        },
        {
            "id": "sig-b",
            "name": "Signature B — absorb / reverse / improve / return",
            "blurb": "best-in-class absorbed, reversed, improved, returned original",
        },
        {
            "id": "round-3",
            "name": "Round 3 — crown lift",
            "blurb": "regression, five-goal coverage, showcase-ready",
        },
    ]


# ---------------------------------------------------------------------------
# Tailored team recommendation — the monetizable shape.
#
# The lift doesn't just report gaps; it prescribes the Legion crew that
# fills them. Every seat resolves through roster_matrix at Genesis basic:
# all 'rules', zero external keys, nothing auth-gated.
# ---------------------------------------------------------------------------


#: Every measured check id -> the Legion crew slot that owns closing it.
#: Unknown ids are simply skipped by the mapper (defensive, never a crash).
CHECK_TO_SLOT: Dict[str, str] = {
    # Round 1 — foundation
    "f-title": "face",
    "f-meta-desc": "marketer",
    "f-viewport": "face",
    "f-h1": "face",
    "f-contact": "receptionist",
    "f-cta": "booker",
    "f-alt": "marketer",
    "f-pages": "librarian",
    # Round 2 — feature
    "t-booking": "booker",
    "t-pricing": "cashier",
    "t-proof": "marketer",
    "t-social": "marketer",
    "t-og": "marketer",
    "t-gallery": "merchandiser",
    "t-faq": "librarian",
    "t-analytics": "analyst",
}


@dataclass
class AddonPack:
    """One specialized add-on pack: what gap it closes, honestly."""

    pack_id: str
    name: str
    goal: str  # the lift goal this pack serves
    fills: Tuple[str, ...]  # measured check ids this pack closes
    note: str = ""


#: The honest PACK catalog — a pack is only ever recommended for a gap
#: the lift actually measured. No gap, no pack.
PACKS: Dict[str, AddonPack] = {
    "booking-pack": AddonPack(
        "booking-pack",
        "Booking pack",
        "income",
        ("t-booking",),
        "a booking/scheduling path the booker crew can run",
    ),
    "proof-pack": AddonPack(
        "proof-pack",
        "Social-proof pack",
        "retain",
        ("t-proof",),
        "testimonials/reviews collection and display",
    ),
    "social-pack": AddonPack(
        "social-pack",
        "Social pack",
        "bring",
        ("t-social", "t-og"),
        "outbound social links and share tags",
    ),
    "analytics-pack": AddonPack(
        "analytics-pack",
        "Analytics pack",
        "income",
        ("t-analytics",),
        "income measurement hooks the analyst can read",
    ),
    "gallery-pack": AddonPack(
        "gallery-pack",
        "Gallery pack",
        "intrigue",
        ("t-gallery",),
        "portfolio/results showcase the merchandiser keeps fresh",
    ),
    "faq-pack": AddonPack(
        "faq-pack",
        "FAQ pack",
        "retain",
        ("t-faq",),
        "objection-answering FAQ the librarian maintains",
    ),
    "pricing-pack": AddonPack(
        "pricing-pack",
        "Pricing pack",
        "income",
        ("t-pricing",),
        "visible prices/service menu the cashier quotes from",
    ),
}


@dataclass
class TeamRecommendation:
    """The tailored crew for a lift report."""

    report_id: str
    slots: List[Dict[str, Any]]  # resolved SlotAssignments, as dicts
    packs: List[Dict[str, Any]]  # recommended add-on pack catalog entries
    model_mix: Dict[str, int]  # model_id -> seat count
    upgrade_advice: List[Dict[str, str]]  # roster_matrix.advise_upgrades, advisory only
    pitch: str  # plain-language recommendation for the customer
    owner_review: Optional[str] = None  # set when the crown round failed


def _pack_dict(p: AddonPack) -> Dict[str, Any]:
    return {
        "pack_id": p.pack_id,
        "name": p.name,
        "goal": p.goal,
        "fills": list(p.fills),
        "note": p.note,
    }


def _team_pitch(
    failed: List[str],
    slot_ids: List[str],
    rec_packs: List[AddonPack],
    owner_review: Optional[str],
) -> str:
    if not failed:
        base = (
            "The site earned its lift — no measured gaps. Keep the face on call, "
            "the one voice the customer talks to. Every seat runs the honest "
            "local rules engine: zero external keys, nothing auth-gated."
        )
    else:
        plural = "s" if len(failed) != 1 else ""
        base = (
            f"The lift found {len(failed)} measured gap{plural}: "
            f"{', '.join(failed)}. Recommended Legion crew: {', '.join(slot_ids)} "
            "— the face stays the one voice the customer talks to. Every seat "
            "runs the honest local rules engine: zero external keys, nothing "
            "auth-gated."
        )
        if rec_packs:
            base += (
                " Add-on packs that close these gaps: "
                + "; ".join(
                    f"{p.pack_id} ({p.goal} — closes {', '.join(p.fills)})"
                    for p in rec_packs
                )
                + "."
            )
    if owner_review:
        base += " " + owner_review
    return base


def recommend_team(report: LiftReport) -> TeamRecommendation:
    """Prescribe the Legion crew for a lift report.

    Every FAILED measured check maps to a crew slot via CHECK_TO_SLOT;
    the 'face' slot is always included. Round-3 (crown) failures add an
    owner-review note instead of seats. Resolution is Genesis basic:
    resolve_roster('crew', ...) with no model_overrides and no authorized
    teachers, so every seat is 'rules' and all_real_or_authorized holds.
    """
    failed: List[str] = []  # failed measured check ids, rounds 1-2
    crown_failed: List[str] = []  # failed checks in round-3
    for r in report.rounds:
        if r.round_id == "round-3":
            crown_failed += [c.check_id for c in r.checks if not c.passed]
            continue
        if r.round_id not in ("round-1", "round-2"):
            continue
        for c in r.checks:
            if c.passed or c.kind != "measured":
                continue
            if c.check_id not in failed:
                failed.append(c.check_id)

    slot_ids = ["face"]
    for cid in failed:
        slot = CHECK_TO_SLOT.get(cid)
        if slot is not None and slot not in slot_ids:
            slot_ids.append(slot)

    assignments = resolve_roster("crew", slot_ids=slot_ids)
    receipt = roster_receipt("crew", assignments)

    rec_packs = [
        pack
        for _pid, pack in sorted(PACKS.items())
        if any(cid in failed for cid in pack.fills)
    ]

    owner_review: Optional[str] = None
    if crown_failed:
        owner_review = (
            "Owner review: the crown round failed on "
            + ", ".join(crown_failed)
            + " — a human reviews these before any more seats are added."
        )

    return TeamRecommendation(
        report_id=report.report_id,
        slots=[a.to_dict() for a in assignments],
        packs=[_pack_dict(p) for p in rec_packs],
        model_mix=receipt["model_mix"],
        upgrade_advice=advise_upgrades(assignments),
        pitch=_team_pitch(failed, slot_ids, rec_packs, owner_review),
        owner_review=owner_review,
    )
