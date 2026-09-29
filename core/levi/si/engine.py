"""The SI intelligence layer: analyze / decide / generate, local-first.

Two runtime tiers, in order:
  rules — deterministic, always available, honest about being rules.
  brain — his own tiny-gpt weights (explicit-only). Raw continuation,
          labeled "not reasoning", low confidence, never a contract.

Big-provider models are teachers only (offline training signal for
future operator brains) and are NOT a runtime tier — see L2. When the
operator-training thread lands trained operator brains, they slot in
as a third tier behind this same interface (the upgrade lane).

This module never touches the network and never modifies core files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .laws import LAWS  # noqa: F401  (laws ride with the module)

TIERS = ("rules", "brain")

_BRAIN_LIMITS = (
    "brain output is raw continuation, not reasoning",
    "the tiny brain cannot reliably write code, JSON, or plans",
    "treat brain text as a spark to inspect, never as an answer",
)

_STOPWORDS = frozenset(
    "a an the and or for with that this from into over under to of in on "
    "is are was were be been it its as at by we you he she they them his "
    "her our your my me i so if not no do does did will would can could "
    "should have has had all any each more most other some such than too "
    "very just app system build make use using used via per".split()
)

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{2,}")


@dataclass(frozen=True)
class SIResult:
    """One answered consult. Tier is always named (L1)."""

    kind: str
    tier: str  # "rules" | "brain"
    text: str
    data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    limits: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "tier": self.tier,
            "text": self.text,
            "data": self.data,
            "confidence": self.confidence,
            "limits": list(self.limits),
        }


def _keywords(text: str, limit: int = 12) -> List[str]:
    counts: Dict[str, int] = {}
    for w in _WORD_RE.findall(text.lower()):
        if w not in _STOPWORDS:
            counts[w] = counts.get(w, 0) + 1
    return sorted(counts, key=lambda w: (-counts[w], w))[:limit]


class SIEngine:
    """analyze / decide / generate over local SI. consult() never raises
    on backend failure (L3): it degrades to rules and says so."""

    def __init__(
        self,
        brain_loader: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._brain_loader = brain_loader  # None -> default lazy loader
        self._brain: Any = None
        self._brain_tried = False
        self._brain_error: Optional[str] = None

    # -- brain access -------------------------------------------------
    def _default_loader(self) -> Any:
        from levi.brain.inference import load_brain

        return load_brain()

    def _brain_or_none(self) -> Optional[Any]:
        if self._brain_tried:
            return self._brain
        self._brain_tried = True
        try:
            loader = self._brain_loader or self._default_loader
            self._brain = loader()
        except Exception as exc:  # L3: broken brain degrades, never kills
            self._brain = None
            self._brain_error = f"{exc.__class__.__name__}: {exc}"
        return self._brain

    def brain_available(self) -> bool:
        return self._brain_or_none() is not None

    def status(self) -> Dict[str, Any]:
        self._brain_or_none()
        return {
            "tiers": {
                "rules": True,
                "brain": self._brain is not None,
                "brain_error": self._brain_error,
            },
            "teacher": (
                "big-provider models are offline teachers only; "
                "not a runtime tier (L2)"
            ),
            "upgrade_lane": (
                "trained operator brains slot in as a third tier "
                "behind this interface when operator-training lands"
            ),
        }

    # -- analyze / decide / generate ----------------------------------
    def analyze(self, text: str) -> Dict[str, Any]:
        """Rules-tier structural read of free text. Deterministic."""
        text = text or ""
        sents = [s.strip() for s in re.split(r"[.!?\n]+", text) if s.strip()]
        questions = [s for s in re.split(r"[.\n]+", text) if "?" in s]
        return {
            "tier": "rules",
            "chars": len(text),
            "sentences": len(sents),
            "keywords": _keywords(text),
            "questions": [q.strip()[:120] for q in questions[:5]],
        }

    def decide(
        self, options: List[Dict[str, Any]], criteria: Dict[str, float]
    ) -> Dict[str, Any]:
        """Rules-tier deterministic ranking. options carry numeric attrs;
        criteria maps attr -> weight. Returns ranking + winner + rationale."""
        if not options:
            raise ValueError("decide needs at least one option")
        scored = []
        for opt in options:
            score = sum(
                float(opt.get(attr, 0.0)) * w for attr, w in criteria.items()
            )
            scored.append((score, str(opt.get("id", "?"))))
        scored.sort(key=lambda t: (-t[0], t[1]))
        crit_txt = ", ".join(f"{k}×{v}" for k, v in criteria.items())
        return {
            "tier": "rules",
            "ranking": [oid for _, oid in scored],
            "scores": {oid: round(s, 4) for s, oid in scored},
            "winner": scored[0][1],
            "rationale": f"weighted sum over {crit_txt}; deterministic",
        }

    def generate_draft(self, prompt: str, seed: int = 7) -> SIResult:
        """Free-text draft. Brain when available, rules template otherwise.
        Always labeled (L1, L4)."""
        brain = self._brain_or_none()
        if brain is not None:
            try:
                out = brain.generate(
                    prompt, max_new_chars=220, temperature=0.7, seed=seed
                )
                cont = str(out.get("continuation", "")).strip()
                if cont:
                    return SIResult(
                        kind="generate-draft",
                        tier="brain",
                        text=cont,
                        data={"prompt": prompt[:200], "seed": seed},
                        confidence=0.25,
                        limits=_BRAIN_LIMITS,
                    )
            except Exception as exc:  # fall through to rules (L3)
                self._brain = None
                self._brain_error = f"{exc.__class__.__name__}: {exc}"
        keys = _keywords(prompt, 8)
        draft = (
            "draft sketch (rules tier — no brain available): "
            + "; ".join(f"address {k}" for k in keys)
            or "draft sketch (rules tier): nothing to address"
        )
        return SIResult(
            kind="generate-draft",
            tier="rules",
            text=draft,
            data={"prompt": prompt[:200], "keywords": keys},
            confidence=0.4,
            limits=("rules tier: structural sketch only, not prose",),
        )

    # -- consult --------------------------------------------------------
    def consult(self, kind: str, payload: Dict[str, Any]) -> SIResult:
        """The front door for Builder steps and Hicomb. Never raises on
        backend failure (L3); unknown kinds raise ValueError."""
        try:
            if kind == "plan-brief":
                return self._plan_brief(payload)
            if kind == "idea-spark":
                return self._idea_spark(payload)
            if kind == "review-notes":
                return self._review_notes(payload)
            if kind == "focus-pick":
                return self._focus_pick(payload)
            raise ValueError(f"unknown consult kind {kind!r}")
        except ValueError:
            raise
        except Exception as exc:  # L3: degrade, don't die
            return SIResult(
                kind=kind,
                tier="rules",
                text=f"SI consult degraded: {exc.__class__.__name__}",
                data={},
                confidence=0.0,
                limits=("consult hit an unexpected error; rules fallback",),
            )

    # -- kinds ----------------------------------------------------------
    def _plan_brief(self, payload: Dict[str, Any]) -> SIResult:
        """Deterministic build brief via the builders planner seat."""
        from levi.builders.planner import plan as deterministic_plan

        description = str(payload.get("description", "") or "")
        if not description.strip():
            raise ValueError("plan-brief needs payload['description']")
        bp = deterministic_plan(description)
        entities = [
            {"name": e.name, "fields": [f.name for f in e.fields]}
            for e in bp.data_model
        ]
        data = {
            "app_slug": bp.app_slug,
            "domain": bp.domain,
            "entities": entities,
            "modules": [m.path for m in bp.modules],
            "api_surface": bp.api_surface,
            "ambiguities": bp.ambiguities,
            "design_directives": bp.design_directives,
        }
        lines = [
            f"brief: {bp.app_slug} [{bp.domain}]",
            f"  entities: {', '.join(e['name'] for e in entities)}",
            f"  api: {', '.join(bp.api_surface[:6])}",
        ]
        if bp.ambiguities:
            lines.append(f"  ambiguities: {len(bp.ambiguities)} flagged")
        return SIResult(
            kind="plan-brief",
            tier="rules",
            text="\n".join(lines),
            data=data,
            confidence=0.8,
            limits=("deterministic heuristics; ambiguities flagged, not guessed",),
        )

    def _idea_spark(self, payload: Dict[str, Any]) -> SIResult:
        prompt = str(payload.get("prompt", "") or "")
        if not prompt.strip():
            raise ValueError("idea-spark needs payload['prompt']")
        seed = int(payload.get("seed", 7))
        res = self.generate_draft(prompt, seed=seed)
        return SIResult(
            kind="idea-spark",
            tier=res.tier,
            text=res.text,
            data=res.data,
            confidence=res.confidence,
            limits=res.limits,
        )

    def _review_notes(self, payload: Dict[str, Any]) -> SIResult:
        description = str(payload.get("description", "") or "")
        notes: List[str] = []
        a = self.analyze(description)
        if not description.strip():
            notes.append("empty description — nothing to review")
        else:
            if a["sentences"] < 2:
                notes.append("one-line description: expect heavy defaults")
            verbs = [k for k in a["keywords"] if k.endswith(("e", "k", "t"))]
            if a["keywords"]:
                notes.append(
                    "core concepts: " + ", ".join(a["keywords"][:6]))
            if a["questions"]:
                notes.append(
                    f"{len(a['questions'])} open question(s) in the brief — "
                    "answer before building")
            notes.append("smoke-test on localhost before any share")
            notes.append("no network calls in generated code paths")
        return SIResult(
            kind="review-notes",
            tier="rules",
            text="\n".join(f"- {n}" for n in notes),
            data={"notes": notes, "analysis": a},
            confidence=0.7,
            limits=("checklist heuristics, not a security audit",),
        )

    def _focus_pick(self, payload: Dict[str, Any]) -> SIResult:
        """Pick ambience params for a focus session. Deterministic."""
        minutes = max(5, min(180, int(payload.get("minutes", 25))))
        mood = str(payload.get("mood", "calm") or "calm").lower()
        chords = {
            "calm": ["Am", "F", "C", "G"],
            "deep": ["Dm", "Bb", "F", "C"],
            "bright": ["C", "G", "Am", "F"],
        }.get(mood, ["Am", "F", "C", "G"])
        data = {
            "minutes": minutes,
            "mood": mood,
            "chords": chords,
            "noise_level": 0.05 if mood == "deep" else 0.08,
            "pad_level": 0.30,
            "render_seconds": min(600, minutes * 60),
        }
        return SIResult(
            kind="focus-pick",
            tier="rules",
            text=(f"focus session: {minutes} min, mood {mood}, "
                  f"chords {'-'.join(chords)}"),
            data=data,
            confidence=0.85,
            limits=("params are deterministic picks, not psychoacoustics",),
        )
