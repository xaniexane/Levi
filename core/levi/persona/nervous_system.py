"""
Persona Nervous System — scored affect matrix + bond + usage-driven selection.

A local-first, neuro-symbolic control surface for LEVI. It emulates a
lightweight autonomic layer:

  PAD appraisal (valence / arousal / dominance)
  + load axes (stress / anxiety / workload / energy / fatigue)
  + relational axes (bond / bond_strain)
  → persona activation scores → hysteresis-gated selection → blend weights

Honesty contract (blueprint §2): this is a *control system*, not felt
emotion. LEVI does not claim sentience, consciousness, or genuine
subjective experience. Affect here is a deterministic regulation signal
— "internal load" in the engineering sense — that steers which
persona lens is active. Nothing in this module overrides integrity,
policy, or an explicit user --personality lock.

Affect dimensions (one line each):
  stress      — perceived pressure / intensity of current demands
  anxiety     — uncertainty / ambiguity in the situation
  workload    — density of open tasks and asks
  energy      — momentary available capacity (inverse of acute tiredness)
  fatigue     — accumulated weariness across the session; slow, unlike energy
  bond        — continuity / trust built with this human
  bond_strain — tension or friction in the bond; rises on hostile cues
  arousal     — short-term activation / alertness
  valence     — pleasant-vs-unpleasant appraisal of the context (PAD)
  dominance   — felt control / capacity relative to demands (PAD)

Temporal dynamics:
  * Wall-clock decay: every dimension relaxes toward a setpoint with its
    own time constant (see DECAY_PROFILE), applied from ``updated_at`` on
    each ``sense()`` call — so affect settles realistically *between*
    sessions, not only across turns.
  * Per-turn homeostasis: small multiplicative drift keeps intra-session
    dynamics smooth.

Selection:
  * score_matrix() is pure-ish and deterministic given a fixed seed.
  * explain_scores() returns per-persona factor breakdowns whose values
    sum exactly to the reported score.
  * select() applies a regulation mask, then a hysteresis gate: the
    incumbent persona keeps its seat unless a challenger beats it by
    HYS_MARGIN (or HYS_DWELL_OVERRIDE inside the dwell window), so
    borderline scores cannot flap the lens between turns.
  * blend_weights() returns a continuous top-N activation profile
    (softmax); blending applies to display, composition input, and any
    future response mixing — while the orchestration loop, an explicit
    lock, and crisis hard-vetoes always require a single lens.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone
import json
import math
import random
import re

DEFAULT_PATH = Path.home() / ".levi" / "nervous_system.json"

# (name, one-line definition) — also mirrored in docs/PERSONA.md.
DIMENSIONS: Tuple[Tuple[str, str], ...] = (
    ("stress", "perceived pressure / intensity of current demands"),
    ("anxiety", "uncertainty / ambiguity in the situation"),
    ("workload", "density of open tasks and asks"),
    ("energy", "momentary available capacity (inverse of acute tiredness)"),
    ("fatigue", "accumulated weariness across the session; slow, unlike energy"),
    ("bond", "continuity / trust built with this human"),
    ("bond_strain", "tension or friction in the bond; rises on hostile cues"),
    ("arousal", "short-term activation / alertness"),
    ("valence", "pleasant-vs-unpleasant appraisal of the context (PAD)"),
    ("dominance", "felt control / capacity relative to demands (PAD)"),
)
AFFECT_DIMS = tuple(name for name, _ in DIMENSIONS)


@dataclass
class AffectState:
    """LEVI internal load — not a claim of biological feeling; a control surface."""

    stress: float = 0.25  # pressure / intensity
    anxiety: float = 0.20  # uncertainty / ambiguity
    workload: float = 0.15  # open tasks, density of asks
    energy: float = 0.75  # inverse acute fatigue
    fatigue: float = 0.20  # accumulated weariness (slow)
    bond: float = 0.35  # continuity / trust with this human
    bond_strain: float = 0.05  # tension / friction in the bond
    arousal: float = 0.30  # short-term activation
    valence: float = 0.55  # pleasant ↔ unpleasant (PAD)
    dominance: float = 0.50  # felt control / capacity (PAD)
    turns: int = 0
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def clamp(self) -> "AffectState":
        for k in AFFECT_DIMS:
            v = getattr(self, k)
            setattr(self, k, max(0.0, min(1.0, float(v))))
        return self

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AffectState":
        a = cls()
        for k in AFFECT_DIMS:
            if k in d:
                setattr(a, k, float(d[k]))
        # Migrate pre-PAD / pre-fatigue / pre-bond_strain persisted files.
        # New axes are derived from the closest old signal, not zeroed:
        # fatigue is the slow envelope of (1 - energy); bond_strain is the
        # complement of a thin bond.
        if "fatigue" not in d:
            a.fatigue = max(0.0, min(1.0, 1.0 - a.energy))
        if "bond_strain" not in d:
            a.bond_strain = max(0.0, min(1.0, 0.35 - a.bond))
        a.turns = int(d.get("turns", 0))
        a.updated_at = d.get("updated_at") or a.updated_at
        return a.clamp()


@dataclass
class PersonaAffinity:
    """How a persona 'pops' under different internal loads."""

    persona_id: str
    baseline: float = 0.2
    w_stress: float = 0.0
    w_anxiety: float = 0.0
    w_workload: float = 0.0
    w_bond: float = 0.0
    w_energy: float = 0.0
    w_arousal: float = 0.0
    w_valence: float = 0.0
    w_dominance: float = 0.0
    w_fatigue: float = 0.0
    w_bond_strain: float = 0.0
    # usage
    uses: int = 0
    last_used_at: Optional[str] = None

    def activation(self, affect: AffectState) -> float:
        return (
            self.baseline
            + self.w_stress * affect.stress
            + self.w_anxiety * affect.anxiety
            + self.w_workload * affect.workload
            + self.w_bond * affect.bond
            + self.w_energy * affect.energy
            + self.w_arousal * affect.arousal
            + self.w_valence * affect.valence
            + self.w_dominance * affect.dominance
            + self.w_fatigue * affect.fatigue
            + self.w_bond_strain * affect.bond_strain
        )


# Matrix: which lens tends to surface under which load.
# High stress → void / strategist / depressed_robot (containment)
# High anxiety → interrogation / observer / philosopher
# High bond + energy → normal / overly_attached / manic_pixie
# High workload → strategist / void / chaotic_good (cut scope)
# Playful arousal → pirate / alien / drunk / conspiracy
# Low valence + low dominance → void / depressed_robot (bleak containment)
# High dominance + low fatigue → strategist / no_hero (capacity to act)
# High bond_strain → overly_attached / conspiracy (relational friction)

AFFINITY_SEED: Dict[str, Dict[str, float]] = {
    "normal": dict(
        baseline=0.35,
        w_bond=0.35,
        w_energy=0.25,
        w_stress=-0.15,
        w_anxiety=-0.1,
        w_valence=0.15,
        w_dominance=0.10,
        w_fatigue=-0.10,
    ),
    "void": dict(
        baseline=0.15,
        w_stress=0.55,
        w_workload=0.35,
        w_anxiety=0.15,
        w_energy=-0.1,
        w_bond=-0.05,
        w_valence=-0.20,
        w_dominance=-0.10,
        w_fatigue=0.15,
    ),
    "interrogation": dict(
        baseline=0.08,
        w_anxiety=0.55,
        w_stress=0.25,
        w_workload=0.15,
        w_bond=0.05,
        w_dominance=0.20,
        w_bond_strain=0.15,
    ),
    "no_hero": dict(
        baseline=0.10,
        w_stress=0.30,
        w_workload=0.40,
        w_energy=-0.20,
        w_anxiety=0.15,
        w_dominance=0.25,
        w_fatigue=0.20,
    ),
    "reframe": dict(
        baseline=0.12,
        w_anxiety=0.40,
        w_stress=0.20,
        w_bond=0.15,
        w_arousal=0.15,
        w_valence=0.25,
        w_bond_strain=-0.15,
    ),
    "strategist": dict(
        baseline=0.18,
        w_workload=0.50,
        w_stress=0.35,
        w_anxiety=0.10,
        w_energy=0.15,
        w_dominance=0.30,
        w_fatigue=-0.15,
        w_valence=0.05,
    ),
    "creative": dict(
        baseline=0.15,
        w_energy=0.40,
        w_arousal=0.35,
        w_bond=0.20,
        w_stress=-0.15,
        w_valence=0.25,
        w_dominance=0.15,
        w_fatigue=-0.20,
    ),
    "philosopher": dict(
        baseline=0.12,
        w_anxiety=0.35,
        w_bond=0.20,
        w_energy=0.15,
        w_stress=-0.05,
        w_valence=0.10,
        w_dominance=0.05,
    ),
    "observer": dict(
        baseline=0.14,
        w_anxiety=0.30,
        w_stress=0.20,
        w_workload=0.15,
        w_bond=0.10,
        w_dominance=0.10,
        w_bond_strain=-0.10,
    ),
    "chaotic_good": dict(
        baseline=0.10,
        w_arousal=0.45,
        w_workload=0.25,
        w_stress=0.20,
        w_energy=0.25,
        w_valence=0.20,
        w_fatigue=-0.15,
    ),
    "alien": dict(
        baseline=0.08,
        w_anxiety=0.25,
        w_arousal=0.30,
        w_bond=0.15,
        w_energy=0.10,
        w_valence=-0.05,
        w_dominance=-0.10,
    ),
    "pirate": dict(
        baseline=0.08,
        w_arousal=0.40,
        w_energy=0.30,
        w_bond=0.20,
        w_stress=-0.10,
        w_valence=0.20,
        w_fatigue=-0.10,
    ),
    "drunk": dict(
        baseline=0.05,
        w_stress=0.20,
        w_arousal=0.25,
        w_energy=-0.25,
        w_bond=0.10,
        w_valence=0.10,
        w_dominance=-0.20,
        w_fatigue=0.20,
    ),
    "depressed_robot": dict(
        baseline=0.08,
        w_stress=0.45,
        w_energy=-0.40,
        w_workload=0.25,
        w_bond=-0.05,
        w_valence=-0.30,
        w_dominance=-0.20,
        w_fatigue=0.30,
    ),
    "conspiracy": dict(
        baseline=0.06,
        w_anxiety=0.40,
        w_arousal=0.35,
        w_stress=0.15,
        w_bond_strain=0.25,
        w_valence=-0.10,
    ),
    "manic_pixie": dict(
        baseline=0.08,
        w_energy=0.45,
        w_arousal=0.50,
        w_bond=0.25,
        w_stress=-0.20,
        w_valence=0.40,
        w_fatigue=-0.25,
        w_dominance=0.10,
    ),
    "overly_attached": dict(
        baseline=0.10,
        w_bond=0.70,
        w_anxiety=0.20,
        w_energy=0.15,
        w_stress=0.10,
        w_bond_strain=0.35,
        w_valence=0.10,
    ),
}

_AFFINITY_KEYS = (
    "baseline",
    "w_stress",
    "w_anxiety",
    "w_workload",
    "w_bond",
    "w_energy",
    "w_arousal",
    "w_valence",
    "w_dominance",
    "w_fatigue",
    "w_bond_strain",
)


class NervousSystem:
    """
    Persistent affect + scored persona matrix.
    Selection = affinity(affect) + usage dynamics + nervous noise
                → regulation mask → hysteresis-gated pick → blend weights.
    """

    # Hysteresis: the incumbent keeps its seat unless a challenger clears
    # HYS_MARGIN, or clears HYS_DWELL_OVERRIDE inside the dwell window.
    HYS_MARGIN = 0.06
    HYS_DWELL_MIN = 2  # selects the incumbent must hold before displacement
    HYS_DWELL_OVERRIDE = 0.25  # gap that forces a switch even inside the dwell window

    # Blending: continuous activation profile over the top-N personas.
    BLEND_TOP_N = 3

    # Wall-clock decay profile: dimension -> (tau seconds, setpoint).
    # Applied from ``updated_at`` on every sense(), so affect settles
    # realistically between sessions.
    DECAY_PROFILE: Dict[str, Tuple[float, float]] = {
        "arousal": (300.0, 0.30),  # alertness fades in minutes
        "stress": (1800.0, 0.25),  # pressure eases over ~half an hour
        "anxiety": (1800.0, 0.20),
        "workload": (7200.0, 0.15),  # open asks cool over hours
        "energy": (7200.0, 0.75),  # capacity recovers over hours
        "fatigue": (14400.0, 0.12),  # weariness needs real rest
        "valence": (3600.0, 0.55),  # mood appraisal drifts to neutral+
        "dominance": (3600.0, 0.50),
        "bond_strain": (86400.0, 0.05),  # friction fades over a day
        "bond": (3 * 86400.0, 0.30),  # trust persists for days
    }

    def __init__(
        self,
        path: Optional[Path] = None,
        persona_ids: Optional[List[str]] = None,
        noise: float = 0.08,
        temperature: float = 0.55,
        seed: Optional[int] = None,
    ):
        self.path = Path(path) if path else DEFAULT_PATH
        self.noise = noise
        self.temperature = max(0.15, temperature)
        self.rng = random.Random(seed)
        self.affect = AffectState()
        self.affinities: Dict[str, PersonaAffinity] = {}
        self._locked_persona: Optional[str] = None  # explicit user lock
        self._last_scores: Dict[str, float] = {}
        self._last_selected: Optional[str] = None
        self._incumbent_turns: int = 0
        self._last_blend: Optional[List[Dict[str, Any]]] = None
        self._last_stack: Optional[Dict[str, Any]] = None
        self._init_affinities(persona_ids or list(AFFINITY_SEED.keys()))
        self._load()

    def _init_affinities(self, ids: List[str]) -> None:
        for pid in ids:
            seed = AFFINITY_SEED.get(pid, dict(baseline=0.12))
            self.affinities[pid] = PersonaAffinity(
                persona_id=pid, **{k: v for k, v in seed.items() if k in _AFFINITY_KEYS}
            )

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.affect = AffectState.from_dict(raw.get("affect") or {})
            for pid, data in (raw.get("affinities") or {}).items():
                if pid not in self.affinities:
                    self.affinities[pid] = PersonaAffinity(persona_id=pid)
                a = self.affinities[pid]
                a.uses = int(data.get("uses", 0))
                a.last_used_at = data.get("last_used_at")
            self._locked_persona = raw.get("locked_persona")
            self._last_selected = raw.get("last_selected")
            self._incumbent_turns = int(raw.get("incumbent_turns", 0) or 0)
            self._last_blend = raw.get("last_blend")
        except Exception:
            pass

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "affect": self.affect.to_dict(),
            "affinities": {
                pid: {"uses": a.uses, "last_used_at": a.last_used_at}
                for pid, a in self.affinities.items()
            },
            "locked_persona": self._locked_persona,
            "last_selected": self._last_selected,
            "incumbent_turns": self._incumbent_turns,
            "last_blend": self._last_blend,
            "last_stack": getattr(self, "_last_stack", None),
            "last_scores": self._last_scores,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # ── temporal dynamics ─────────────────────────────────────────

    def _apply_wallclock_decay(self) -> None:
        """Relax each dimension toward its setpoint based on elapsed time.

        Called at the start of sense(): affect settles realistically
        between sessions instead of freezing at last-turn values.
        """
        try:
            last = datetime.fromisoformat(self.affect.updated_at)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
        except Exception:
            self.affect.updated_at = datetime.now(timezone.utc).isoformat()
            return
        now = datetime.now(timezone.utc)
        dt = max(0.0, (now - last).total_seconds())
        if dt <= 0:
            return
        for dim, (tau, setpoint) in self.DECAY_PROFILE.items():
            v = getattr(self.affect, dim)
            k = math.exp(-dt / tau)
            setattr(self.affect, dim, setpoint + (v - setpoint) * k)

    # ── signal sensing from user text + context ─────────────────

    def sense(
        self, user_text: str, context: Optional[Dict[str, Any]] = None
    ) -> AffectState:
        """Update affect from this turn's text and optional shelf/workload context."""
        # Wall-clock settling first: time passed since last sense().
        self._apply_wallclock_decay()

        t = (user_text or "").lower()
        ctx = context or {}

        # Stress cues
        if re.search(r"\b(urgent|asap|right now|emergency|deadline|crisis|panic)\b", t):
            self.affect.stress += 0.12
            self.affect.arousal += 0.10
            self.affect.dominance -= 0.06
        if re.search(r"\b(angry|furious|hate|broken|ruined|worst)\b", t):
            self.affect.stress += 0.08
            self.affect.anxiety += 0.05
            self.affect.valence -= 0.08

        # Anxiety / ambiguity
        if re.search(
            r"\b(confused|unsure|don'?t know|maybe|what if|afraid|worried|anxious)\b", t
        ):
            self.affect.anxiety += 0.10
            self.affect.dominance -= 0.05
        if "?" in t and t.count("?") >= 2:
            self.affect.anxiety += 0.05

        # Workload
        if re.search(r"\b(build|scaffold|factory|automate|ship|deploy)\b", t):
            self.affect.workload += 0.08
            self.affect.stress += 0.04
        if re.search(r"\b(story|write|chapter|scene|genre)\b", t):
            self.affect.workload += 0.05
        shelf_n = int(ctx.get("shelf_count") or 0)
        if shelf_n:
            self.affect.workload = min(
                1.0, self.affect.workload + min(0.15, shelf_n * 0.02)
            )

        # Bond cues
        if re.search(
            r"\b(thank|thanks|grateful|appreciate|missed you|with you|we)\b", t
        ):
            self.affect.bond += 0.08
            self.affect.energy += 0.04
            self.affect.valence += 0.05
            self.affect.bond_strain = max(0.0, self.affect.bond_strain - 0.04)
        if re.search(r"\b(love|care|trust|stay)\b", t):
            self.affect.bond += 0.06
            self.affect.valence += 0.04
        if re.search(r"\b(shut up|useless|stupid|hate you)\b", t):
            self.affect.bond -= 0.08
            self.affect.bond_strain += 0.10
            self.affect.stress += 0.06
            self.affect.valence -= 0.08

        # Valence cues (pleasant ↔ unpleasant appraisal)
        if re.search(
            r"\b(great|awesome|wonderful|excellent|nice|win|won|beautiful|fun)\b", t
        ):
            self.affect.valence += 0.08
        if re.search(r"\b(terrible|awful|sad|horrible|painful|depressing|ugly)\b", t):
            self.affect.valence -= 0.08

        # Dominance cues (felt control / capacity)
        if re.search(
            r"\b(i can'?t|impossible|helpless|stuck|overwhelmed|no idea)\b", t
        ):
            self.affect.dominance -= 0.08
        if re.search(r"\b(done|finished|i'?ll handle|got this|i will)\b", t):
            self.affect.dominance += 0.06

        # Fatigue cues + slow per-turn accumulation
        if re.search(r"\b(tired|exhausted|burnt out|burned out|drained|weary)\b", t):
            self.affect.fatigue += 0.10
            self.affect.energy -= 0.06
        self.affect.fatigue += 0.004  # sessions wear; wall-clock decay recovers

        # Length / density → mild workload + arousal
        words = len(t.split())
        if words > 80:
            self.affect.workload += 0.05
            self.affect.arousal += 0.04
        if words < 4:
            self.affect.anxiety += 0.03

        # Recovery / baseline drift (homeostasis), per turn
        self.affect.stress *= 0.92
        self.affect.anxiety *= 0.93
        self.affect.arousal *= 0.88
        self.affect.workload *= 0.94
        # Bond decays very slowly without contact; small floor hold
        self.affect.bond = 0.97 * self.affect.bond + 0.03 * max(self.affect.bond, 0.25)
        self.affect.bond_strain *= 0.95
        self.affect.valence = 0.96 * self.affect.valence + 0.04 * 0.55
        self.affect.dominance = 0.96 * self.affect.dominance + 0.04 * 0.50
        # Energy recovers when stress low
        if self.affect.stress < 0.35:
            self.affect.energy = min(1.0, self.affect.energy + 0.03)
        else:
            self.affect.energy = max(0.15, self.affect.energy - 0.04)

        self.affect.turns += 1
        self.affect.updated_at = datetime.now(timezone.utc).isoformat()
        self.affect.clamp()
        return self.affect

    # ── scoring + explanation ─────────────────────────────────────

    def _external_biases(self) -> Tuple[Any, Any]:
        """Optional control-daemon bias and monotropism bias (0 when absent)."""
        daemon_bias = None
        try:
            from levi.daemon.control import ControlDaemon

            daemon_bias = ControlDaemon().persona_bias
        except Exception:
            daemon_bias = None
        mono_bias_fn = None
        try:
            from levi.persona.monotropism import MonotropismTracker

            mono_bias_fn = MonotropismTracker().persona_bias
        except Exception:
            mono_bias_fn = None
        return daemon_bias, mono_bias_fn

    def _score_with_factors(
        self,
    ) -> Tuple[Dict[str, float], Dict[str, Dict[str, float]]]:
        """Score every persona, recording each additive factor.

        Returns (scores, factors) where factors[pid] maps a factor label to
        its contribution; sum(factors[pid].values()) == scores[pid] exactly.
        """
        daemon_bias, mono_bias_fn = self._external_biases()
        scores: Dict[str, float] = {}
        factors: Dict[str, Dict[str, float]] = {}
        for pid, aff in self.affinities.items():
            f: Dict[str, float] = {}
            f["baseline"] = aff.baseline
            for dim, w in (
                ("stress", aff.w_stress),
                ("anxiety", aff.w_anxiety),
                ("workload", aff.w_workload),
                ("bond", aff.w_bond),
                ("energy", aff.w_energy),
                ("arousal", aff.w_arousal),
                ("valence", aff.w_valence),
                ("dominance", aff.w_dominance),
                ("fatigue", aff.w_fatigue),
                ("bond_strain", aff.w_bond_strain),
            ):
                if w:
                    f[f"{dim}×{w:.2f}"] = w * getattr(self.affect, dim)
            # Usage: mild momentum, then overuse fatigue
            uses = aff.uses
            f["momentum"] = min(0.12, uses * 0.01)
            f["overuse"] = -min(0.20, max(0, uses - 8) * 0.015)
            # Recent use bonus (if last selected)
            f["recent"] = 0.06 if pid == self._last_selected else 0.0
            # Nervous noise
            f["jitter"] = self.rng.gauss(0, self.noise)
            d_bias = 0.0
            if daemon_bias is not None:
                try:
                    d_bias = float(daemon_bias(pid))
                except Exception:
                    d_bias = 0.0
            if d_bias:
                f["daemon"] = d_bias
            m_bias = 0.0
            if mono_bias_fn is not None:
                try:
                    m_bias = float(mono_bias_fn(pid))
                except Exception:
                    m_bias = 0.0
            if m_bias:
                f["monotropism"] = m_bias
            scores[pid] = sum(f.values())
            factors[pid] = f
        return scores, factors

    def score_matrix(self) -> Dict[str, float]:
        scores, _ = self._score_with_factors()
        self._last_scores = {k: round(v, 4) for k, v in scores.items()}
        return scores

    def explain_scores(self, top_n: int = 5) -> Dict[str, Dict[str, Any]]:
        """Per-persona factor breakdowns for the top-N personas.

        Each entry: {"score": float, "factors": {label: contribution}} with
        sum(factors) == score exactly. This is a fresh scoring pass, so
        jitter draws differ from the most recent score_matrix() call.
        """
        scores, factors = self._score_with_factors()
        ranked = sorted(scores.items(), key=lambda x: -x[1])[: max(1, top_n)]
        return {
            pid: {"score": scores[pid], "factors": dict(factors[pid])}
            for pid, _ in ranked
        }

    def format_explanation(
        self,
        pid: str,
        explanation: Optional[Dict[str, Any]] = None,
        max_factors: int = 5,
    ) -> str:
        """One-line 'why' for a persona, e.g.
        strategist 0.62: workload×0.50=+0.31, stress×0.35=+0.18, momentum=+0.05, jitter=+0.02…"""
        expl = explanation or self.explain_scores(top_n=self.BLEND_TOP_N * 2).get(pid)
        if not expl:
            return f"{pid}: no explanation available"
        fac = expl["factors"]
        top = sorted(fac.items(), key=lambda kv: -abs(kv[1]))[:max_factors]
        parts = [f"{k}={v:+.2f}" for k, v in top]
        if len(fac) > max_factors:
            parts.append("…")
        return f"{pid} {expl['score']:.2f}: " + ", ".join(parts)

    # ── hysteresis ────────────────────────────────────────────────

    def _hysteresis_pick(
        self, scores: Dict[str, float], avoid_hard: frozenset = frozenset()
    ) -> Tuple[str, bool]:
        """Apply the hysteresis gate: incumbent keeps its seat unless a
        challenger beats it by HYS_MARGIN (after HYS_DWELL_MIN selects),
        or by HYS_DWELL_OVERRIDE outright. Hard-avoided personas (crisis
        regulation) can never be incumbent and are excluded from the race.

        Returns (persona_id, switched).
        """
        eligible = [p for p in scores if p not in avoid_hard]
        if not eligible:
            return "normal", True
        challenger = max(eligible, key=lambda p: scores[p])
        incumbent = self._last_selected
        if incumbent not in scores or incumbent in avoid_hard:
            return challenger, True
        gap = scores[challenger] - scores[incumbent]
        if gap > self.HYS_DWELL_OVERRIDE:
            return challenger, True
        if gap > self.HYS_MARGIN and self._incumbent_turns >= self.HYS_DWELL_MIN:
            return challenger, True
        return incumbent, False

    # ── blending ──────────────────────────────────────────────────

    def blend_weights(
        self, scores: Optional[Dict[str, float]] = None, top_n: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Continuous activation profile: softmax over the top-N scores.

        Blending applies to *display* (status), composition input, and any
        future response mixing. It does not replace the single lens the
        orchestration loop, an explicit lock, or crisis hard-vetoes require.
        """
        n = top_n or self.BLEND_TOP_N
        scores = scores if scores is not None else self.score_matrix()
        if not scores:
            return []
        ranked = sorted(scores.items(), key=lambda x: -x[1])[: max(1, n)]
        mx = max(s for _, s in ranked)
        temp = self.temperature
        exps = [(p, math.exp((s - mx) / temp)) for p, s in ranked]
        total = sum(e for _, e in exps) or 1.0
        return [
            {"persona": p, "weight": e / total, "score": round(s, 4)}
            for (p, s), e in zip(ranked, [e for _, e in exps], strict=True)
        ]

    # ── selection ─────────────────────────────────────────────────

    def _apply_regulation(
        self,
        scores: Dict[str, float],
        user_text: str,
        context: Optional[Dict[str, Any]],
    ) -> Tuple[Dict[str, float], frozenset]:
        """Tone-based regulation mask. Returns (adjusted scores, hard-avoid set)."""
        avoid: List[str] = []
        hard: frozenset = frozenset()
        try:
            from levi.ei.tone import read_user_tone

            tone = read_user_tone(user_text, context)
            avoid = list(tone.avoid)
            # Intensity scales the penalty
            penalty = 0.35 + 0.55 * float(tone.intensity)
            for pid in avoid:
                if pid in scores:
                    scores[pid] -= penalty
            # Safe anchors get a lift under contain/soften
            if tone.regulation in ("contain", "soften"):
                for safe in ("normal", "void", "observer", "strategist"):
                    if safe in scores and safe not in avoid:
                        scores[safe] += 0.12 * tone.intensity
            if tone.primary in ("crisis", "distress", "grief"):
                # Hard floor: never let banned playful/chaotic win
                for pid in avoid:
                    if pid in scores:
                        scores[pid] = min(scores[pid], -1.0)
                hard = frozenset(p for p in avoid if p in scores)
            elif tone.primary == "anger":
                hard = frozenset(p for p in avoid if p in scores)
        except Exception:
            pass
        return scores, hard

    def select(
        self, user_text: str = "", context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Sense → score → regulation mask → hysteresis gate → single lens.

        Honors explicit lock if set. The hysteresis gate keeps the
        incumbent unless a challenger clears the documented margin, so
        borderline scores do not flap the lens between turns. Crisis /
        distress hard-vetoes bypass the gate (safety outranks stickiness).
        """
        if self._locked_persona and self._locked_persona in self.affinities:
            # Still sense so affect tracks the human even when locked
            self.sense(user_text, context)
            self._last_blend = self.blend_weights()
            self._persist()
            return self._locked_persona

        self.sense(user_text, context)
        scores = self.score_matrix()
        if not scores:
            return "normal"

        scores, hard_avoid = self._apply_regulation(scores, user_text, context)
        self._last_scores = {k: round(v, 4) for k, v in scores.items()}

        chosen, _switched = self._hysteresis_pick(scores, hard_avoid)

        # Final hard veto under crisis/distress (belt and suspenders)
        if chosen in hard_avoid:
            ranked = sorted(scores.items(), key=lambda x: -x[1])
            for pid, _ in ranked:
                if pid not in hard_avoid:
                    chosen = pid
                    break
            else:
                chosen = "normal"

        self._note_use(chosen, primary=True)
        self._last_blend = self.blend_weights(scores)
        self._persist()
        return chosen

    def _note_use(self, persona_id: str, primary: bool = True) -> None:
        if primary:
            if persona_id == self._last_selected:
                self._incumbent_turns += 1
            else:
                self._last_selected = persona_id
                self._incumbent_turns = 0
        if persona_id in self.affinities:
            a = self.affinities[persona_id]
            a.uses += 1
            a.last_used_at = datetime.now(timezone.utc).isoformat()

    def lock(self, persona_id: Optional[str]) -> None:
        """User explicit lock (--personality). None unlocks."""
        self._locked_persona = persona_id
        self._persist()

    def unlock(self) -> None:
        self.lock(None)

    def reinforce_bond(self, delta: float = 0.05) -> None:
        self.affect.bond = max(0.0, min(1.0, self.affect.bond + delta))
        self._persist()

    def select_stack(
        self, user_text: str = "", context: Optional[Dict[str, Any]] = None
    ):
        """
        Full chameleon selection: score matrix → regulation → hysteresis-gated
        primary → composition ensemble. Returns PersonaStack (primary + secondary + accent).
        """
        from levi.persona.composition import CompositionEngine, PersonaStack
        from levi.ei.tone import read_user_tone

        if self._locked_persona and self._locked_persona in self.affinities:
            self.sense(user_text, context)
            self._last_blend = self.blend_weights()
            self._persist()
            return PersonaStack(
                primary=self._locked_persona,
                reason="user lock",
            )

        self.sense(user_text, context)
        scores = self.score_matrix()
        tone = read_user_tone(user_text, context)
        avoid = list(tone.avoid)
        penalty = 0.35 + 0.55 * float(tone.intensity)
        for pid in avoid:
            if pid in scores:
                scores[pid] -= penalty
        if tone.regulation in ("contain", "soften"):
            for safe in ("normal", "void", "observer", "strategist"):
                if safe in scores and safe not in avoid:
                    scores[safe] += 0.12 * tone.intensity
            for pid in avoid:
                if pid in scores and tone.primary in ("crisis", "distress", "grief"):
                    scores[pid] = min(scores[pid], -1.0)

        hard_avoid = (
            frozenset(p for p in avoid if p in scores)
            if tone.primary in ("crisis", "distress", "grief", "anger")
            else frozenset()
        )

        self._last_scores = {k: round(v, 4) for k, v in scores.items()}

        # Hysteresis on the primary: pin the gated winner to the front of
        # the ranking so composition builds around the stable lens.
        gated_primary, switched = self._hysteresis_pick(scores, hard_avoid)
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        if gated_primary in scores:
            pin = max((s for _, s in ranked), default=0.0) + 2.0
            ranked = [(gated_primary, pin)] + [
                (p, s) for p, s in ranked if p != gated_primary
            ]

        # Ensure affinities exist for expanded personas not in seed matrix
        # (they still appear via bond + baseline default)
        engine = CompositionEngine(seed=None)
        # seed composition rng from nervous rng state lightly
        engine.rng = self.rng
        stack = engine.compose(
            ranked=ranked[:40],
            avoid=avoid,
            user_tone=tone.primary,
            regulation=tone.regulation,
        )
        # Hard veto primary if still avoided
        if stack.primary in avoid and tone.primary in (
            "crisis",
            "distress",
            "grief",
            "anger",
        ):
            for pid, _ in ranked:
                if pid not in avoid:
                    stack.primary = pid
                    stack.secondary = None
                    stack.accent = None
                    stack.intrigue = False
                    stack.reason = "regulation hard veto"
                    break
            else:
                stack.primary = "normal"
        # Post-check: composition must respect the hysteresis gate.
        if stack.primary != gated_primary and gated_primary not in hard_avoid:
            stack.primary = gated_primary
            stack.reason = (
                stack.reason + "; hysteresis held incumbent"
                if not switched
                else stack.reason
            )

        self._note_use(stack.primary, primary=True)
        if stack.secondary:
            self._note_use(stack.secondary, primary=False)
        self._last_blend = self.blend_weights(scores)
        self._persist()
        # stash last stack for status
        self._last_stack = stack.to_dict()
        return stack

    def status(self) -> Dict[str, Any]:
        scores = self.score_matrix()
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        blend = self.blend_weights(scores)
        return {
            "affect": self.affect.to_dict(),
            "locked": self._locked_persona,
            "last_selected": self._last_selected,
            "incumbent_turns": self._incumbent_turns,
            "last_stack": getattr(self, "_last_stack", None),
            "top": [{"persona": p, "score": round(s, 3)} for p, s in ranked[:8]],
            "blend": blend,
            "hysteresis": {
                "margin": self.HYS_MARGIN,
                "dwell_min": self.HYS_DWELL_MIN,
                "dwell_override": self.HYS_DWELL_OVERRIDE,
                "incumbent": self._last_selected,
                "incumbent_turns": self._incumbent_turns,
            },
            "matrix_size": len(self.affinities),
            "noise": self.noise,
            "temperature": self.temperature,
            "note": (
                "Affect is a local control surface (internal load), not felt "
                "emotion. Scores drive lens selection; integrity/policy are "
                "never scored away."
            ),
        }

    def format_status(self) -> str:
        st = self.status()
        a = st["affect"]
        lines = [
            "══ LEVI nervous system ══",
            "  (internal load — a control surface, not biological feeling)",
            f"  stress   {a['stress']:.2f}   anxiety {a['anxiety']:.2f}   arousal {a['arousal']:.2f}",
            f"  workload {a['workload']:.2f}   energy  {a['energy']:.2f}   fatigue {a['fatigue']:.2f}",
            f"  valence  {a['valence']:.2f}   dominance {a['dominance']:.2f}",
            f"  bond     {a['bond']:.2f}   bond_strain {a['bond_strain']:.2f}",
            f"  turns    {a['turns']}",
            "",
            "Top activations (why each):",
        ]
        expl = self.explain_scores(top_n=3)
        for pid in expl:
            lines.append("  " + self.format_explanation(pid, expl[pid]))
        if st["blend"]:
            b = st["blend"]
            lines.append("")
            lines.append(
                "Blend (continuous profile): "
                + " · ".join(f"{r['persona']} {r['weight']:.2f}" for r in b)
            )
        h = st["hysteresis"]
        if st["last_selected"]:
            lines.append(
                f"\nIncumbent: {st['last_selected']} "
                f"(held {h['incumbent_turns']} selects; "
                f"challenger needs +{h['margin']:.2f} to displace)"
            )
        if st["locked"]:
            lines.append(f"Locked: {st['locked']} (explicit)")
        return "\n".join(lines)
