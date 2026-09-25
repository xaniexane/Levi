"""Bridging-based consensus scoring — clean-room implementation.

THE MATH (derived from first principles; the Community-Notes-style
algorithm is public knowledge, re-derived here rather than copied):

We observe a sparse rating matrix R where rater u rates note n with
``r_un in [-1, 1]`` (+1 helpful, -1 not helpful). The core problem: a
note that is merely popular inside one faction looks "helpful" under a
plain average. Bridging asks: does the note win approval from raters who
NORMALY DISAGREE with each other?

Model each rating as::

    r_un ≈ μ + α_u + β_n + γ_u · δ_n

- μ    global mean of all ratings (baseline leniency of the crowd)
- α_u  rater intercept — this rater's personal leniency/strictness
- β_n  NOTE intercept — the note's intrinsic helpfulness. THIS is the score.
- γ_u  rater factor — the rater's position on the latent disagreement axis
- δ_n  note factor  — how much the note leans toward one camp's taste

Why this finds bridging: suppose a note is rated +1 by raters with
γ_u > 0 AND by raters with γ_u < 0. No single δ_n can make γ_u·δ_n
positive for both camps at once — so the model is forced to explain the
cross-camp agreement through β_n (the intercept). Conversely, a note
loved only by one camp gets a large |δ_n| and a modest β_n: factional
appeal, not bridging legitimacy.

Fitting: regularized alternating least squares (ALS), closed form per
step. For fixed note params, each rater solves a 2×2 ridge regression::

    [α_u, γ_u] = argmin Σ_{n∈N_u} (r_un − μ − β_n − α_u − γ_u·δ_n)²
                            + λ(α_u² + γ_u²)

and symmetrically for notes. Initialization is deterministic
(hash-based) so runs are reproducible; λ and iteration count are
documented constants, not tuned secrets.

LIMITS (honest): the single latent axis is a simplification — real
disagreement is multi-dimensional. The model can be gamed by coordinated
rating blocs that mimic cross-camp behavior. Thresholds for status
labels are heuristics on local data, not platform policy.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

# ---------------------------------------------------------------------------
# Pure math — no storage, no CLI. Importable by other packages (e.g. threads).
# ---------------------------------------------------------------------------

LAMBDA = 0.15  # L2 regularization strength
ALS_ITERATIONS = 25  # fixed; convergence is fast on small local matrices
MIN_RATINGS_FOR_STATUS = 3  # below this a note cannot earn a status label
HELPFULNESS_THRESHOLD = 0.25  # |β_n| above this, with cross-camp evidence


def _init_factor(key: str) -> float:
    """Deterministic pseudo-random init in [-0.5, 0.5) from the id string."""
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    return (h % 1000) / 1000.0 - 0.5


@dataclass
class BridgingFit:
    """Result of fitting the bridging model."""

    note_helpfulness: Dict[str, float]  # β_n per note
    note_factor: Dict[str, float]  # δ_n per note
    rater_factor: Dict[str, float]  # γ_u per rater
    rater_intercept: Dict[str, float]  # α_u per rater
    global_mean: float  # μ
    iterations: int = ALS_ITERATIONS

    def camps(self, rater_id: str) -> int:
        """+1 / -1 camp by sign of the rater's latent factor (0 if ~neutral)."""
        g = self.rater_factor.get(rater_id, 0.0)
        if g > 1e-6:
            return 1
        if g < -1e-6:
            return -1
        return 0

    def cross_camp_support(
        self, note_id: str, ratings: Mapping[str, Mapping[str, float]]
    ) -> Dict[str, int]:
        """Positive raters of this note, split by latent camp."""
        support = {"camp_pos": 0, "camp_neg": 0, "camp_neutral": 0}
        for rater_id, value in ratings.get(note_id, {}).items():
            if value > 0:
                c = self.camps(rater_id)
                if c > 0:
                    support["camp_pos"] += 1
                elif c < 0:
                    support["camp_neg"] += 1
                else:
                    support["camp_neutral"] += 1
        return support


def fit_bridging(
    ratings: Mapping[str, Mapping[str, float]],
    lam: float = LAMBDA,
    iterations: int = ALS_ITERATIONS,
) -> BridgingFit:
    """Fit the bridging model.

    ``ratings``: note_id -> {rater_id: value in [-1, 1]}.
    Pure function: no I/O, deterministic, stdlib-only.
    """
    notes = sorted(ratings.keys())
    raters: List[str] = sorted({u for m in ratings.values() for u in m})
    if not notes or not raters:
        return BridgingFit({}, {}, {}, {}, 0.0, 0)

    all_vals = [v for m in ratings.values() for v in m.values()]
    mu = sum(all_vals) / len(all_vals)

    beta = {n: 0.0 for n in notes}  # note helpfulness
    delta = {n: _init_factor("note:" + n) for n in notes}  # note factor
    alpha = {u: 0.0 for u in raters}  # rater intercept
    gamma = {u: _init_factor("rater:" + u) for u in raters}  # rater factor

    # note -> raters, rater -> notes adjacency
    note_raters: Dict[str, List[str]] = {n: sorted(m) for n, m in ratings.items()}
    rater_notes: Dict[str, List[str]] = {u: [] for u in raters}
    for n, m in ratings.items():
        for u in m:
            rater_notes[u].append(n)

    def solve_2x2(
        s11: float, s12: float, s22: float, t1: float, t2: float
    ) -> Tuple[float, float]:
        a11, a12, a22 = s11 + lam, s12, s22 + lam
        det = a11 * a22 - a12 * a12
        if abs(det) < 1e-12:
            return 0.0, 0.0
        return (t1 * a22 - t2 * a12) / det, (a11 * t2 - a12 * t1) / det

    for _ in range(iterations):
        # rater step: fit (alpha_u, gamma_u) given note params
        for u in raters:
            s11 = s12 = s22 = t1 = t2 = 0.0
            for n in rater_notes[u]:
                resid = ratings[n][u] - mu - beta[n]
                d = delta[n]
                s11 += 1.0
                s12 += d
                s22 += d * d
                t1 += resid
                t2 += resid * d
            alpha[u], gamma[u] = solve_2x2(s11, s12, s22, t1, t2)
        # note step: fit (beta_n, delta_n) given rater params
        for n in notes:
            s11 = s12 = s22 = t1 = t2 = 0.0
            for u in note_raters[n]:
                resid = ratings[n][u] - mu - alpha[u]
                g = gamma[u]
                s11 += 1.0
                s12 += g
                s22 += g * g
                t1 += resid
                t2 += resid * g
            beta[n], delta[n] = solve_2x2(s11, s12, s22, t1, t2)

    return BridgingFit(
        note_helpfulness=beta,
        note_factor=delta,
        rater_factor=gamma,
        rater_intercept=alpha,
        global_mean=mu,
        iterations=iterations,
    )


def note_status(
    note_id: str, fit: BridgingFit, ratings: Mapping[str, Mapping[str, float]]
) -> Dict[str, object]:
    """Honest status label for a note, with the evidence attached."""
    n_ratings = len(ratings.get(note_id, {}))
    helpfulness = fit.note_helpfulness.get(note_id, 0.0)
    support = fit.cross_camp_support(note_id, ratings)
    cross_camp = support["camp_pos"] > 0 and support["camp_neg"] > 0
    if n_ratings < MIN_RATINGS_FOR_STATUS:
        status = "NEEDS-MORE-RATINGS"
    elif helpfulness >= HELPFULNESS_THRESHOLD and cross_camp:
        status = "BRIDGING-HELPFUL"
    elif helpfulness >= HELPFULNESS_THRESHOLD:
        status = "HELPFUL-ONE-CAMP"  # liked, but no cross-camp evidence
    elif helpfulness <= -HELPFULNESS_THRESHOLD:
        status = "NOT-HELPFUL"
    else:
        status = "NEEDS-MORE-RATINGS"
    return {
        "note_id": note_id,
        "status": status,
        "helpfulness": round(helpfulness, 4),
        "n_ratings": n_ratings,
        "cross_camp_support": support,
        "cross_camp": cross_camp,
    }


# ---------------------------------------------------------------------------
# Local store — ratings registry with hermetic JSON persistence
# ---------------------------------------------------------------------------


def _home() -> Path:
    override = os.environ.get("LEVI_HOME")
    if override:
        return Path(override)
    return Path.home() / ".levi"


def _state_path() -> Path:
    return _home() / "bridging" / "bridging.json"


class BridgingError(ValueError):
    """Invalid bridging operation."""


@dataclass
class Note:
    id: str
    text: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class BridgingStore:
    """Local registry of notes + ratings, with on-demand model fits."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or _state_path()
        self.notes: Dict[str, Note] = {}
        self.ratings: Dict[str, Dict[str, float]] = {}  # note_id -> rater_id -> value
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return
        self.notes = {n["id"]: Note(**n) for n in raw.get("notes", [])}
        self.ratings = {nid: dict(m) for nid, m in raw.get("ratings", {}).items()}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "notes": [asdict(n) for n in self.notes.values()],
            "ratings": self.ratings,
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
        tmp.replace(self._path)

    def add_note(self, text: str, note_id: Optional[str] = None) -> Note:
        text = text.strip()
        if not text:
            raise BridgingError("note text must be non-empty")
        nid = (note_id or hashlib.sha256(text.encode()).hexdigest()[:12]).strip()
        if not nid:
            raise BridgingError("note id must be non-empty")
        if nid in self.notes:
            return self.notes[nid]
        note = Note(id=nid, text=text)
        self.notes[nid] = note
        self.ratings.setdefault(nid, {})
        self._save()
        return note

    def add_rating(self, note_id: str, rater_id: str, value: float) -> None:
        if note_id not in self.notes:
            raise BridgingError(f"unknown note {note_id!r}")
        rater_id = rater_id.strip()
        if not rater_id:
            raise BridgingError("rater id must be non-empty")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise BridgingError(f"rating must be a finite number, got {value!r}")
        if not -1.0 <= value <= 1.0:
            raise BridgingError(f"rating must be in [-1, 1], got {value!r}")
        self.ratings[note_id][rater_id] = float(value)
        self._save()

    def fit(self) -> BridgingFit:
        return fit_bridging(self.ratings)

    def statuses(self) -> List[Dict[str, object]]:
        fit = self.fit()
        return [note_status(nid, fit, self.ratings) for nid in sorted(self.notes)]

    def format_notes(self) -> str:
        rows = self.statuses()
        lines = ["=== Notes (bridging-scored) ==="]
        for r in rows:
            note = self.notes[r["note_id"]]
            s = r["cross_camp_support"]
            lines.append(
                f"  [{r['note_id'][:8]}] {r['status']:18s} h={r['helpfulness']:+.3f} "
                f"n={r['n_ratings']} camps(+/-)={s['camp_pos']}/{s['camp_neg']}"
            )
            lines.append(f"           {note.text[:80]}")
        if not rows:
            lines.append("  (none — add with: bridging note --text ...)")
        lines += [
            "",
            "BRIDGING-HELPFUL = rated helpful by raters on BOTH sides of the",
            "latent disagreement axis. No central moderator involved.",
        ]
        return "\n".join(lines)
