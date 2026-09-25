"""Unified configuration for the synthesis front door.

One place for: which mind answers (brain policy), where state lives, and
whether the offline guard is enforced. JSON on disk, environment overrides.

Precedence: explicit constructor args > environment > config file > defaults.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

ORIGIN = "levi-synthesis/config"

BRAIN_POLICIES = ("auto", "rules-only")


def _default_state_dir() -> Path:
    override = os.environ.get("LEVI_SYNTHESIS_DIR")
    if override:
        return Path(override)
    return Path.home() / ".levi" / "synthesis"


@dataclass
class SynthesisConfig:
    """Knobs for the synthesis front door.

    brain_policy: "auto" — the native-brain weights contribute a labeled
        brain-voice proposal whenever they load; any failure degrades to an
        honest rules-only report. "rules-only" — the weights are never
        touched (Reasoner with brain_chars=0); fastest, no torch needed.
    brain_weights: explicit weights path, or None for the shipped default
        (core/levi/brain/weights/tiny-gpt.pt).
    offline_enforced: prove-offline runs the guard; the guard itself is
        always available regardless of this flag.
    state_dir: where config.json lives.
    scan_budget_ms: per-tick cycle budget in milliseconds (default 100).
        The schedule tick executes due goals until this budget is spent;
        goals that don't fit are skipped honestly, never silently.
        Env override: LEVI_SYNTHESIS_SCAN_BUDGET_MS.
    """

    brain_policy: str = "auto"
    brain_weights: Optional[str] = None
    offline_enforced: bool = True
    state_dir: str = field(default_factory=lambda: str(_default_state_dir()))
    scan_budget_ms: int = 100

    def __post_init__(self) -> None:
        if self.brain_policy not in BRAIN_POLICIES:
            raise ValueError(
                f"unknown brain_policy {self.brain_policy!r}; "
                f"want one of {BRAIN_POLICIES}"
            )
        try:
            budget = int(self.scan_budget_ms)
        except (TypeError, ValueError):
            raise ValueError(
                f"scan_budget_ms must be an integer of milliseconds, "
                f"got {self.scan_budget_ms!r}"
            ) from None
        if budget < 1:
            raise ValueError(
                f"scan_budget_ms must be >= 1, got {self.scan_budget_ms!r}"
            )
        self.scan_budget_ms = budget
        if self.brain_weights is not None:
            self.brain_weights = str(self.brain_weights)
        self.state_dir = str(self.state_dir)

    # -- paths -----------------------------------------------------------

    @property
    def state_path(self) -> Path:
        return Path(self.state_dir)

    @property
    def config_file(self) -> Path:
        return self.state_path / "config.json"

    def weights_path(self) -> Path:
        """Explicit weights path, else the shipped tiny-gpt.pt default."""
        if self.brain_weights:
            return Path(self.brain_weights)
        # core/levi/synthesis/config.py -> parents[1] is core/levi
        return Path(__file__).resolve().parents[1] / "brain" / "weights" / "tiny-gpt.pt"

    # -- persistence -----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SynthesisConfig":
        known = {
            f
            for f in (
                "brain_policy",
                "brain_weights",
                "offline_enforced",
                "state_dir",
                "scan_budget_ms",
            )
        }
        return cls(**{k: v for k, v in data.items() if k in known})

    @classmethod
    def load(cls) -> "SynthesisConfig":
        """Load from disk, then apply environment overrides."""
        cfg = cls()
        try:
            raw = cfg.config_file.read_text(encoding="utf-8")
            cfg = cls.from_dict(json.loads(raw))
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, ValueError, TypeError):
            # A corrupt config file is reported by falling back to defaults,
            # not by crashing the front door.
            cfg = cls()
        policy = os.environ.get("LEVI_SYNTHESIS_BRAIN_POLICY")
        if policy:
            if policy not in BRAIN_POLICIES:
                raise ValueError(
                    f"LEVI_SYNTHESIS_BRAIN_POLICY={policy!r} invalid; "
                    f"want one of {BRAIN_POLICIES}"
                )
            cfg.brain_policy = policy
        state_dir = os.environ.get("LEVI_SYNTHESIS_DIR")
        if state_dir:
            cfg.state_dir = str(state_dir)
        offline = os.environ.get("LEVI_SYNTHESIS_OFFLINE")
        if offline is not None:
            cfg.offline_enforced = offline.strip().lower() not in ("0", "false", "no")
        budget = os.environ.get("LEVI_SYNTHESIS_SCAN_BUDGET_MS")
        if budget is not None:
            try:
                budget_ms = int(budget)
            except (TypeError, ValueError):
                raise ValueError(
                    f"LEVI_SYNTHESIS_SCAN_BUDGET_MS={budget!r} invalid; "
                    "want an integer of milliseconds >= 1"
                ) from None
            if budget_ms < 1:
                raise ValueError(
                    f"LEVI_SYNTHESIS_SCAN_BUDGET_MS={budget!r} invalid; "
                    "want an integer of milliseconds >= 1"
                )
            cfg.scan_budget_ms = budget_ms
        return cfg

    def save(self) -> Path:
        """Write config.json under the state dir; return its path."""
        self.state_path.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return self.config_file


__all__ = ["ORIGIN", "BRAIN_POLICIES", "SynthesisConfig"]
