"""
Persona Nervous System — scored affect matrix + bond + usage-driven selection.

Emulates a lightweight autonomic layer for LEVI:
  stress / anxiety / workload / energy / bond → persona activation scores
  small stochastic jitter (nervous noise)
  usage over time shifts thresholds (habituation + fatigue)

Does NOT override integrity, policy, or explicit user --personality lock.
Personas remain lenses; companion roles stay higher-order.
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


@dataclass
class AffectState:
    """LEVI internal load — not a claim of biological feeling; a control surface."""
    stress: float = 0.25       # pressure / intensity
    anxiety: float = 0.20      # uncertainty / ambiguity
    workload: float = 0.15     # open tasks, density of asks
    energy: float = 0.75       # inverse fatigue
    bond: float = 0.35         # continuity / trust with this human
    arousal: float = 0.30      # short-term activation
    turns: int = 0
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def clamp(self) -> "AffectState":
        for k in ("stress", "anxiety", "workload", "energy", "bond", "arousal"):
            v = getattr(self, k)
            setattr(self, k, max(0.0, min(1.0, float(v))))
        return self

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AffectState":
        a = cls()
        for k in ("stress", "anxiety", "workload", "energy", "bond", "arousal"):
            if k in d:
                setattr(a, k, float(d[k]))
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
        )


# Matrix: which lens tends to surface under which load.
# High stress → void / strategist / depressed_robot (containment)
# High anxiety → interrogation / observer / philosopher
# High bond + energy → normal / overly_attached / manic_pixie
# High workload → strategist / void / chaotic_good (cut scope)
# Playful arousal → pirate / alien / drunk / conspiracy

AFFINITY_SEED: Dict[str, Dict[str, float]] = {
    "normal": dict(baseline=0.35, w_bond=0.35, w_energy=0.25, w_stress=-0.15, w_anxiety=-0.1),
    "void": dict(baseline=0.15, w_stress=0.55, w_workload=0.35, w_anxiety=0.15, w_energy=-0.1, w_bond=-0.05),
    "interrogation": dict(baseline=0.08, w_anxiety=0.55, w_stress=0.25, w_workload=0.15, w_bond=0.05),
    "no_hero": dict(baseline=0.10, w_stress=0.30, w_workload=0.40, w_energy=-0.20, w_anxiety=0.15),
    "reframe": dict(baseline=0.12, w_anxiety=0.40, w_stress=0.20, w_bond=0.15, w_arousal=0.15),
    "strategist": dict(baseline=0.18, w_workload=0.50, w_stress=0.35, w_anxiety=0.10, w_energy=0.15),
    "creative": dict(baseline=0.15, w_energy=0.40, w_arousal=0.35, w_bond=0.20, w_stress=-0.15),
    "philosopher": dict(baseline=0.12, w_anxiety=0.35, w_bond=0.20, w_energy=0.15, w_stress=-0.05),
    "observer": dict(baseline=0.14, w_anxiety=0.30, w_stress=0.20, w_workload=0.15, w_bond=0.10),
    "chaotic_good": dict(baseline=0.10, w_arousal=0.45, w_workload=0.25, w_stress=0.20, w_energy=0.25),
    "alien": dict(baseline=0.08, w_anxiety=0.25, w_arousal=0.30, w_bond=0.15, w_energy=0.10),
    "pirate": dict(baseline=0.08, w_arousal=0.40, w_energy=0.30, w_bond=0.20, w_stress=-0.10),
    "drunk": dict(baseline=0.05, w_stress=0.20, w_arousal=0.25, w_energy=-0.25, w_bond=0.10),
    "depressed_robot": dict(baseline=0.08, w_stress=0.45, w_energy=-0.40, w_workload=0.25, w_bond=-0.05),
    "conspiracy": dict(baseline=0.06, w_anxiety=0.40, w_arousal=0.35, w_stress=0.15),
    "manic_pixie": dict(baseline=0.08, w_energy=0.45, w_arousal=0.50, w_bond=0.25, w_stress=-0.20),
    "overly_attached": dict(baseline=0.10, w_bond=0.70, w_anxiety=0.20, w_energy=0.15, w_stress=0.10),
}


class NervousSystem:
    """
    Persistent affect + scored persona matrix.
    Selection = affinity(affect) + usage dynamics + nervous noise → weighted sample.
    """

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
        self._last_stack: Optional[Dict[str, Any]] = None
        self._init_affinities(persona_ids or list(AFFINITY_SEED.keys()))
        self._load()

    def _init_affinities(self, ids: List[str]) -> None:
        for pid in ids:
            seed = AFFINITY_SEED.get(pid, dict(baseline=0.12))
            self.affinities[pid] = PersonaAffinity(persona_id=pid, **{
                k: v for k, v in seed.items() if k in (
                    "baseline", "w_stress", "w_anxiety", "w_workload",
                    "w_bond", "w_energy", "w_arousal",
                )
            })

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
            "last_stack": getattr(self, "_last_stack", None),
            "last_scores": self._last_scores,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # ── signal sensing from user text + context ─────────────────

    def sense(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> AffectState:
        """Update affect from this turn's text and optional shelf/workload context."""
        t = (user_text or "").lower()
        ctx = context or {}

        # Stress cues
        if re.search(r"\b(urgent|asap|right now|emergency|deadline|crisis|panic)\b", t):
            self.affect.stress += 0.12
            self.affect.arousal += 0.10
        if re.search(r"\b(angry|furious|hate|broken|ruined|worst)\b", t):
            self.affect.stress += 0.08
            self.affect.anxiety += 0.05

        # Anxiety / ambiguity
        if re.search(r"\b(confused|unsure|don'?t know|maybe|what if|afraid|worried|anxious)\b", t):
            self.affect.anxiety += 0.10
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
            self.affect.workload = min(1.0, self.affect.workload + min(0.15, shelf_n * 0.02))

        # Bond cues
        if re.search(r"\b(thank|thanks|grateful|appreciate|missed you|with you|we)\b", t):
            self.affect.bond += 0.08
            self.affect.energy += 0.04
        if re.search(r"\b(love|care|trust|stay)\b", t):
            self.affect.bond += 0.06
        if re.search(r"\b(shut up|useless|stupid|hate you)\b", t):
            self.affect.bond -= 0.08
            self.affect.stress += 0.06

        # Length / density → mild workload + arousal
        words = len(t.split())
        if words > 80:
            self.affect.workload += 0.05
            self.affect.arousal += 0.04
        if words < 4:
            self.affect.anxiety += 0.03

        # Recovery / baseline drift (homeostasis)
        self.affect.stress *= 0.92
        self.affect.anxiety *= 0.93
        self.affect.arousal *= 0.88
        self.affect.workload *= 0.94
        # Bond decays very slowly without contact; small floor hold
        self.affect.bond = 0.97 * self.affect.bond + 0.03 * max(self.affect.bond, 0.25)
        # Energy recovers when stress low
        if self.affect.stress < 0.35:
            self.affect.energy = min(1.0, self.affect.energy + 0.03)
        else:
            self.affect.energy = max(0.15, self.affect.energy - 0.04)

        self.affect.turns += 1
        self.affect.updated_at = datetime.now(timezone.utc).isoformat()
        self.affect.clamp()
        return self.affect

    # ── scoring + selection ─────────────────────────────────────

    def score_matrix(self) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        # Optional control-daemon bias (lock / boost / suppress)
        daemon_bias = None
        try:
            from levi.daemon.control import ControlDaemon
            daemon_bias = ControlDaemon().persona_bias
        except Exception:
            daemon_bias = None
        # Monotropism: deepen tunnel-friendly lenses, suppress attention-yankers
        mono_bias_fn = None
        try:
            from levi.persona.monotropism import MonotropismTracker
            mono_bias_fn = MonotropismTracker().persona_bias
        except Exception:
            mono_bias_fn = None
        for pid, aff in self.affinities.items():
            base = aff.activation(self.affect)
            # Usage: mild momentum then fatigue
            uses = aff.uses
            momentum = min(0.12, uses * 0.01)
            fatigue = min(0.20, max(0, uses - 8) * 0.015)
            # Recent use bonus (if last selected)
            recent = 0.06 if pid == self._last_selected else 0.0
            # Nervous noise
            jitter = self.rng.gauss(0, self.noise)
            d_bias = 0.0
            if daemon_bias is not None:
                try:
                    d_bias = float(daemon_bias(pid))
                except Exception:
                    d_bias = 0.0
            m_bias = 0.0
            if mono_bias_fn is not None:
                try:
                    m_bias = float(mono_bias_fn(pid))
                except Exception:
                    m_bias = 0.0
            scores[pid] = base + momentum + recent - fatigue + jitter + d_bias + m_bias
        self._last_scores = {k: round(v, 4) for k, v in scores.items()}
        return scores

    def select(self, user_text: str = "", context: Optional[Dict[str, Any]] = None) -> str:
        """Sense → score → regulation mask → softmax. Honors explicit lock if set."""
        if self._locked_persona and self._locked_persona in self.affinities:
            # Still sense so affect tracks the human even when locked
            self.sense(user_text, context)
            self._persist()
            return self._locked_persona

        self.sense(user_text, context)
        scores = self.score_matrix()
        if not scores:
            return "normal"

        # Regulation: reason about user tone so we do not act the wrong way
        avoid: List[str] = []
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
        except Exception:
            pass

        self._last_scores = {k: round(v, 4) for k, v in scores.items()}

        mx = max(scores.values())
        temp = self.temperature
        # Under high-stakes frames, lower temperature → more deterministic steady lens
        try:
            from levi.ei.tone import read_user_tone
            tone2 = read_user_tone(user_text, context)
            if tone2.regulation in ("contain", "soften") and tone2.intensity >= 0.7:
                temp = min(temp, 0.35)
        except Exception:
            pass

        exps = {k: math.exp((v - mx) / temp) for k, v in scores.items()}
        total = sum(exps.values()) or 1.0
        probs = {k: v / total for k, v in exps.items()}

        items = list(probs.keys())
        weights = [probs[k] for k in items]
        chosen = self.rng.choices(items, weights=weights, k=1)[0]

        # Final hard veto under crisis/distress
        try:
            from levi.ei.tone import read_user_tone
            tone3 = read_user_tone(user_text, context)
            if chosen in tone3.avoid and tone3.primary in ("crisis", "distress", "grief", "anger"):
                # pick best non-avoided
                ranked = sorted(scores.items(), key=lambda x: -x[1])
                for pid, _ in ranked:
                    if pid not in tone3.avoid:
                        chosen = pid
                        break
                else:
                    chosen = "normal"
        except Exception:
            pass

        self._note_use(chosen)
        self._persist()
        return chosen

    def _note_use(self, persona_id: str) -> None:
        self._last_selected = persona_id
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


    def select_stack(self, user_text: str = "", context: Optional[Dict[str, Any]] = None):
        """
        Full chameleon selection: score matrix → regulation → composition ensemble.
        Returns PersonaStack (primary + secondary + accent).
        """
        from levi.persona.composition import CompositionEngine, PersonaStack
        from levi.ei.tone import read_user_tone

        if self._locked_persona and self._locked_persona in self.affinities:
            self.sense(user_text, context)
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

        self._last_scores = {k: round(v, 4) for k, v in scores.items()}
        ranked = sorted(scores.items(), key=lambda x: -x[1])

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
        if stack.primary in avoid and tone.primary in ("crisis", "distress", "grief", "anger"):
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

        self._note_use(stack.primary)
        if stack.secondary:
            self._note_use(stack.secondary)
        self._last_selected = stack.primary
        self._persist()
        # stash last stack for status
        self._last_stack = stack.to_dict()
        return stack

    def status(self) -> Dict[str, Any]:
        scores = self.score_matrix()
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return {
            "affect": self.affect.to_dict(),
            "locked": self._locked_persona,
            "last_selected": self._last_selected,
            "last_stack": getattr(self, "_last_stack", None),
            "top": [{"persona": p, "score": round(s, 3)} for p, s in ranked[:8]],
            "matrix_size": len(self.affinities),
            "noise": self.noise,
            "temperature": self.temperature,
            "note": "Scores drive lens selection; integrity/policy are never scored away.",
        }

    def format_status(self) -> str:
        st = self.status()
        a = st["affect"]
        lines = [
            "══ LEVI nervous system ══",
            f"  stress   {a['stress']:.2f}   anxiety {a['anxiety']:.2f}",
            f"  workload {a['workload']:.2f}   energy  {a['energy']:.2f}",
            f"  bond     {a['bond']:.2f}   arousal {a['arousal']:.2f}",
            f"  turns    {a['turns']}",
            "",
            "Top activations:",
        ]
        for row in st["top"]:
            bar = "█" * int(max(0, row["score"]) * 10)
            lines.append(f"  {row['persona']:18} {row['score']:+.2f}  {bar}")
        if st["locked"]:
            lines.append(f"\nLocked: {st['locked']} (explicit)")
        elif st["last_selected"]:
            lines.append(f"\nLast selected: {st['last_selected']}")
        return "\n".join(lines)
