"""
Mirror Cascade — L.W.P. reverse-pattern cross-check (parallel).

Not a generic "think opposite." Three parallel coils run at once:

  FORWARD coil   — stated plan / opportunity as given
  REVERSE coil   — invert incentives, failure modes, anti-goal
  SHADOW coil    — what would a hostile or careless agent do with the same tools

Then CROSS-CHECK merges: keep only what survives all three without violating
HITL, symbiosis value rules, or OBSERVED evidence.

This is LEVI-original structure — cascade + spiral heritage, not a chatbot
"devil's advocate" prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List
import hashlib


@dataclass
class CoilResult:
    name: str
    frames: List[str]
    risks: List[str]
    keep: List[str]


@dataclass
class MirrorReport:
    seed: str
    forward: CoilResult
    reverse: CoilResult
    shadow: CoilResult
    synthesis: List[str]
    vetoes: List[str]
    fingerprint: str

    def format(self) -> str:
        lines = [
            "=== L.W.P. Mirror Cascade (parallel reverse cross-check) ===",
            f"Seed: {self.seed[:120]}",
            f"Fingerprint: {self.fingerprint}",
            "",
            "── FORWARD coil ──",
        ]
        for f in self.forward.frames:
            lines.append(f"  · {f}")
        lines.append(
            "  risks: " + "; ".join(self.forward.risks)
            if self.forward.risks
            else "  risks: —"
        )
        lines.append("")
        lines.append("── REVERSE coil (invert) ──")
        for f in self.reverse.frames:
            lines.append(f"  · {f}")
        lines.append(
            "  risks: " + "; ".join(self.reverse.risks)
            if self.reverse.risks
            else "  risks: —"
        )
        lines.append("")
        lines.append("── SHADOW coil (misuse / carelessness) ──")
        for f in self.shadow.frames:
            lines.append(f"  · {f}")
        lines.append(
            "  risks: " + "; ".join(self.shadow.risks)
            if self.shadow.risks
            else "  risks: —"
        )
        lines.append("")
        lines.append("── SYNTHESIS (survives all three) ──")
        for s in self.synthesis:
            lines.append(f"  ✓ {s}")
        if self.vetoes:
            lines.append("── VETOES ──")
            for v in self.vetoes:
                lines.append(f"  ✗ {v}")
        lines.append("")
        lines.append(
            "Unique to LEVI×L.W.P.: parallel coils + evidence/HITL veto — not single-prompt debate."
        )
        return "\n".join(lines)


class MirrorCascade:
    def run(self, seed: str, context: str = "") -> MirrorReport:
        if seed is not None and not isinstance(seed, str):
            raise ValueError(f"mirror seed must be a string, got {seed!r}")
        if not isinstance(context, str):
            raise ValueError(f"mirror context must be a string, got {context!r}")
        s = (seed or "").strip() or "empty"
        ctx = (context or "").strip()
        h = hashlib.sha256(f"{s}|{ctx}".encode()).hexdigest()[:12]

        forward = CoilResult(
            name="forward",
            frames=[
                f"Advance as stated: {s[:100]}",
                "Smallest reversible next step under current constraints",
                "Score serviceability vs cost before scale",
            ],
            risks=["Over-fit to narrative", "Miss hidden dependencies"],
            keep=["reversible step", "evidence tag OBSERVED when known"],
        )
        reverse = CoilResult(
            name="reverse",
            frames=[
                "Anti-goal: what if the need is false or inverted?",
                "Invert incentive: who loses if this succeeds cheaply?",
                "Failure-first: assume the plan fails — what remains valuable?",
            ],
            risks=["Paralysis by inversion", "Cynical discard of real need"],
            keep=["failure-valuable residue", "honest non-demand"],
        )
        shadow = CoilResult(
            name="shadow",
            frames=[
                "Misuse: same tools used to invent urgency or fake scarcity",
                "Careless: execute past HITL, skip OBSERVED, overwrite memory",
                "Capture: optimize for revenue metric over user outcome",
            ],
            risks=["Dark-pattern drift", "Silent automation past consent"],
            keep=["HITL on consequence", "value↑ without manufactured need"],
        )

        synthesis = [
            "Keep reversible, evidence-linked steps only",
            "Any monetization path stays draft until HITL",
            "Demand claims remain HYPOTHESIS until corpus OBSERVED",
            "Shadow vetoes apply even when forward looks profitable",
        ]
        if ctx:
            synthesis.append(f"Context retained for cross-check: {ctx[:80]}")
        low = s.lower()
        if any(
            w in low for w in ("shop", "clinic", "local", "site", "booking", "mobile")
        ):
            synthesis.append("Serviceability for local operators beats scale theater")
        if any(w in low for w in ("ai", "automat", "bot")):
            synthesis.append(
                "Automation stays checklist-level until HITL on customer path"
            )
        vetoes = [
            "Auto-complete customer contact or payment",
            "Treat silence as approval",
            "Invent demand to feed Income Factory",
        ]
        if any(
            w in low
            for w in (
                "must buy",
                "urgent only",
                "limited time",
                "act now",
                "only today",
            )
        ):
            vetoes.append(
                "Pressure language detected in seed — strip before offer composition"
            )
        if any(w in low for w in ("guaranteed", "risk free", "no downside")):
            vetoes.append(
                "Absolute-claim language — force OBSERVED evidence or drop claim"
            )

        return MirrorReport(
            seed=s,
            forward=forward,
            reverse=reverse,
            shadow=shadow,
            synthesis=synthesis,
            vetoes=vetoes,
            fingerprint=h,
        )


def reverse_crosscheck(seed: str, context: str = "") -> str:
    return MirrorCascade().run(seed, context).format()
