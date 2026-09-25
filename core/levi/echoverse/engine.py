"""Echoverse REIM/RIEM recursion engine — Grok-made LEVI engine.

REIM (Forward Recursion Echo Mapping): expand a seed into multiple
positive candidate paths; score and prefer.

RIEM (Reverse Inverse Echo Mapping): vault negative variants, but
extract *good qualities* from them — do not discard the whole branch,
carry forward what still works.

Lineage: the_pack/echoverse.py (August lineage, Grok-built) adapted to
the repo layout: caller-supplied data dir (default ~/.levi/echoverse),
stdlib only. Upholds LAWS L1, L4, L5, L6, L9.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.echoverse.laws import (
    DREAM_MAX_CYCLES,
    DREAM_MIN_CYCLES,
    HISTORY_KEEP,
    SUCCESS_KEEP,
    VAULT_KEEP,
)

#: L1 — the bounded-simulation mark every run carries.
BOUNDED_MARK = "bounded simulation — not a literal timeline"

DEFAULT_DIR = Path.home() / ".levi" / "echoverse"


@dataclass
class EchoNode:
    """One vaulted branch: a negative variant kept WITH its salvage."""

    id: str
    label: str
    quality: float  # negative => vaulted branch
    note: str = ""
    # RIEM: good facets extracted FROM a negative variant (not the whole failure)
    good_qualities: List[str] = field(default_factory=list)
    parent: Optional[str] = None
    ts: float = field(default_factory=time.time)


def extract_good_qualities(label: str, note: str = "") -> List[str]:
    """RIEM core: do not throw away the whole negative variant.

    Pull reusable positives (intent, constraints, skills, partial wins).
    """
    blob = f"{label} {note}".strip()
    goods: List[str] = []
    patterns = [
        (r"\b(fast|quick|rapid|speed)\b", "speed / urgency awareness"),
        (r"\b(simple|minimal|thin|mvp|small)\b", "prefer small scope"),
        (r"\b(test|verify|check|validate)\b", "verify before commit"),
        (r"\b(user|customer|human)\b", "keep user impact in view"),
        (r"\b(secure|safety|privacy|consent)\b", "safety / privacy posture"),
        (r"\b(document|readme|note)\b", "document decisions"),
        (r"\b(reuse|existing|prior)\b", "reuse prior work"),
        (r"\b(local|offline)\b", "offline / local bias"),
        (r"\b(plan|design|architect)\b", "planning impulse"),
        (r"\b(creative|novel|new)\b", "novelty impulse"),
    ]
    low = blob.lower()
    for pat, qual in patterns:
        if re.search(pat, low, re.I):
            goods.append(qual)
    # always keep a compressed intent fragment (first clause)
    intent = blob.split(".")[0].strip()[:80]
    if intent:
        goods.append(f"intent fragment: {intent}")
    # dedupe preserve order
    seen = set()
    out = []
    for g in goods:
        if g not in seen:
            seen.add(g)
            out.append(g)
    return out[:8]


class EchoverseEngine:
    """REIM/RIEM recursion engine with persistent vault + success memory."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.data_dir / "echoverse_state.json"
        self.negative_vault: List[EchoNode] = []
        self.success_memory: List[Dict[str, Any]] = []
        self.round_history: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.negative_vault = []
            for n in data.get("vault", []):
                n = dict(n)
                n.setdefault("good_qualities", [])
                self.negative_vault.append(EchoNode(**n))
            self.success_memory = data.get("success_memory", [])
            self.round_history = data.get("round_history", [])
        except Exception:
            pass

    def _save(self) -> None:
        # L6: bounded persistence.
        payload = {
            "vault": [asdict(n) for n in self.negative_vault[-VAULT_KEEP:]],
            "success_memory": self.success_memory[-SUCCESS_KEEP:],
            "round_history": self.round_history[-HISTORY_KEEP:],
            "ts": time.time(),
        }
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.state_path)

    def _salvage_qualities(self) -> List[str]:
        """RIEM: only good qualities extracted from negative variants — never full failed paths."""
        out: List[str] = []
        for n in self.negative_vault[-12:]:
            qs = n.good_qualities or extract_good_qualities(n.label, n.note)
            out.extend(qs)
        seen = set()
        uniq = []
        for g in out:
            if g not in seen:
                seen.add(g)
                uniq.append(g)
        return uniq[-12:]

    def _reim_paths(self, seed: str, depth: int = 0) -> List[Dict[str, Any]]:
        """REIM: generate forward positive path options (templates + vault salvage)."""
        salvage = self._salvage_qualities()
        base = [
            {"id": "p-" + uuid.uuid4().hex[:8], "label": f"Advance: {seed[:60]}", "quality": 0.7, "kind": "forward"},
            {"id": "p-" + uuid.uuid4().hex[:8], "label": f"Stabilize then scale: {seed[:50]}", "quality": 0.65, "kind": "forward"},
            {"id": "p-" + uuid.uuid4().hex[:8], "label": f"Minimal viable path for: {seed[:50]}", "quality": 0.6, "kind": "forward"},
        ]
        if salvage:
            base.append(
                {
                    "id": "p-" + uuid.uuid4().hex[:8],
                    "label": f"Carry forward quality: {salvage[-1][:70]}",
                    "quality": 0.55,
                    "kind": "salvage",
                }
            )
        if depth > 0:
            base.append(
                {
                    "id": "p-" + uuid.uuid4().hex[:8],
                    "label": f"Deeper recurse (depth {depth}): refine {seed[:40]}",
                    "quality": 0.5,
                    "kind": "recurse",
                }
            )
        return base

    def vault_negative(self, label: str, note: str = "", quality: float = -0.5) -> EchoNode:
        """RIEM: vault the negative variant but store extracted good_qualities for later REIM."""
        goods = extract_good_qualities(label, note)
        node = EchoNode(
            id="v-" + uuid.uuid4().hex[:8],
            label=label,
            quality=quality,
            note=note,
            good_qualities=goods,
        )
        self.negative_vault.append(node)
        self._save()
        return node

    def mark_success(self, seed: str, path_id: str, label: str) -> None:
        self.success_memory.append({"seed": seed, "path_id": path_id, "label": label, "ts": time.time()})
        self._save()

    def round(
        self,
        seed: str,
        pick_id: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """One REIM round. L1: result carries the bounded mark."""
        meta = meta or {}
        seed = (seed or "silence").strip()
        depth = int(meta.get("depth") or 0)
        paths = self._reim_paths(seed, depth=depth)

        def _base(mode: str) -> Dict[str, Any]:
            return {
                "mode": mode,
                "seed": seed,
                "mark": BOUNDED_MARK,
                "optionalPaths": paths,
                "vault_size": len(self.negative_vault),
                "success_count": len(self.success_memory),
            }

        if pick_id:
            chosen = next((p for p in paths if p["id"] == pick_id), None)
            if not chosen:
                for h in reversed(self.round_history):
                    chosen = next((p for p in h.get("optionalPaths", []) if p["id"] == pick_id), None)
                    if chosen:
                        break
            if chosen:
                if chosen.get("quality", 0) < 0:
                    self.vault_negative(chosen["label"], note="picked negative")
                else:
                    self.mark_success(seed, chosen["id"], chosen["label"])
                result = _base("REIM+RIEM")
                result["picked"] = chosen
                self.round_history.append(result)
                self._save()
                return result

        if meta.get("autoPrefer"):
            # L5: pick the maximum-quality path; ties break deterministically (first max).
            best = max(paths, key=lambda p: p.get("quality", 0))
            self.mark_success(seed, best["id"], best["label"])
            result = _base("REIM")
            result["auto"] = best
            self.round_history.append(result)
            self._save()
            return result

        result = _base("REIM")
        result["salvage_hints"] = self._salvage_qualities()[-3:]
        result["hint"] = "pick <id> to commit a path; negative qualities vault via RIEM"
        self.round_history.append(result)
        self._save()
        return result

    def dream(self, seed: str, cycles: int = 3) -> Dict[str, Any]:
        """Multi-cycle REIM expansion (GROK 1/4). L4: cycles clamp to 1..7."""
        cycles = max(DREAM_MIN_CYCLES, min(int(cycles or DREAM_MIN_CYCLES), DREAM_MAX_CYCLES))
        trail = []
        current = seed
        for i in range(cycles):
            r = self.round(current, None, {"depth": i, "autoPrefer": True})
            trail.append(r)
            current = (r.get("auto") or {}).get("label", current)
        return {"mode": "dream", "cycles": cycles, "trail": trail, "mark": BOUNDED_MARK}

    def status(self) -> Dict[str, Any]:
        return {
            "vault": len(self.negative_vault),
            "success_memory": len(self.success_memory),
            "rounds": len(self.round_history),
            "mark": BOUNDED_MARK,
            "last": self.round_history[-1] if self.round_history else None,
        }


class EchoverseSimulation:
    """Multi-agent style event generator (local templates; optional LLM later)."""

    ROLES = ("strategist", "critic", "builder", "guardian")

    def run(self, seed: str, steps: int = 3) -> Dict[str, Any]:
        events = []
        for i in range(max(1, steps)):
            role = self.ROLES[i % len(self.ROLES)]
            events.append(
                {
                    "step": i + 1,
                    "agent": role,
                    "event": f"[{role}] on '{seed[:50]}' -> propose move {i+1}",
                }
            )
        return {"mode": "simulation", "seed": seed, "events": events, "mark": BOUNDED_MARK}
