"""owned_inference — cost law for owned-hardware local inference.

Studied from: hybrid-cost-cutting-combos-20260916-0006 report.md (section 1,
local-first inference on owned GPUs).

Functional pattern studied: the watts-divided-by-throughput cost law, plus
quantized local serving as the cost driver (smaller weights -> more tokens
per second per watt on owned hardware) as an alternative to per-token API
bills.

What this module is: an honest budgeting mechanism. An operator registers
*measured* numbers for their own hardware (power draw, sustained
tokens/second from their own benchmark runs), plus model profiles, and the
module computes cost-per-token, checks whether a quantized model fits in a
rig's memory, and compares owned cost against a quoted API price. It is a
planner, not a benchmark: it never claims to measure your hardware.

Cost law (all terms in USD):
    usd_per_token = (watt_cost_per_second + amortized_cost_per_second) / tok_s
where watt_cost_per_second = (watts / 1000) * electricity_usd_per_kwh / 3600
and amortized_cost_per_second = purchase_usd / (service_hours * 3600).

Memory fit heuristic: weights_gb ~= params_b * bits / 8, plus a runtime
overhead allowance (KV cache + runtime). Heuristic only — real occupancy
depends on sequence length and the serving stack.

No network calls, no vendor or provider branding, no model serving: just
arithmetic over operator-supplied measurements.

This is an original, from-scratch implementation for LEVI. Not artificial.
Synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/owned-inference"

# Conservative runtime overhead beyond raw weights (KV cache, runtime).
RUNTIME_OVERHEAD_GB = 2.0


@dataclass
class ModelProfile:
    """One quantized model variant the operator might serve."""

    name: str
    params_b: float  # billions of parameters
    quant_bits: float  # effective bits per weight (e.g. 4, 5, 8)
    measured_tok_s: float  # operator-measured sustained tok/s on a rig

    @property
    def weights_gb(self) -> float:
        """Heuristic weight footprint."""
        return self.params_b * self.quant_bits / 8.0

    def fits(self, memory_gb: float) -> bool:
        """Heuristic fit check including runtime overhead."""
        return self.weights_gb + RUNTIME_OVERHEAD_GB <= memory_gb


@dataclass
class Rig:
    """One owned machine, described by the operator's own measurements."""

    name: str
    watts: float  # measured wall power under inference load
    memory_gb: float  # usable accelerator memory
    purchase_usd: float  # total hardware cost
    service_years: float  # expected useful life
    electricity_usd_per_kwh: float

    def usd_per_second(self) -> float:
        energy = (self.watts / 1000.0) * self.electricity_usd_per_kwh / 3600.0
        amortized = self.purchase_usd / (self.service_years * 365.25 * 24 * 3600)
        return energy + amortized

    def usd_per_token(self, profile: ModelProfile) -> float:
        if profile.measured_tok_s <= 0:
            raise ValueError("measured_tok_s must be positive")
        return self.usd_per_second() / profile.measured_tok_s

    def monthly_cost(self, duty_cycle: float = 1.0) -> float:
        """Owned monthly cost at a given duty cycle (0..1); idle still
        amortizes the hardware, energy scales with duty cycle."""
        energy = (self.watts / 1000.0) * self.electricity_usd_per_kwh
        energy_monthly = energy * 24 * 30 * duty_cycle
        amortized_monthly = self.purchase_usd / (self.service_years * 12)
        return energy_monthly + amortized_monthly


@dataclass
class CostComparison:
    rig_name: str
    model_name: str
    owned_usd_per_1m: float
    api_usd_per_1m: float

    @property
    def owned_cheaper_by(self) -> float:
        return self.api_usd_per_1m - self.owned_usd_per_1m

    @property
    def owned_wins(self) -> bool:
        return self.owned_cheaper_by > 0


@dataclass
class Fleet:
    """A set of rigs + models; answers planning questions."""

    rigs: Dict[str, Rig] = field(default_factory=dict)
    models: Dict[str, ModelProfile] = field(default_factory=dict)

    def add_rig(self, rig: Rig) -> None:
        self.rigs[rig.name] = rig

    def add_model(self, profile: ModelProfile) -> None:
        self.models[profile.name] = profile

    def servable(self, rig_name: str) -> List[ModelProfile]:
        """Models that heuristically fit on the rig, fastest first."""
        rig = self.rigs[rig_name]
        fits = [m for m in self.models.values() if m.fits(rig.memory_gb)]
        return sorted(fits, key=lambda m: m.measured_tok_s, reverse=True)

    def cheapest_plan(
        self, rig_name: str, tokens_per_month: float, api_usd_per_1m: float
    ) -> Optional[CostComparison]:
        """Cheapest owned deployment vs the quoted API price."""
        rig = self.rigs[rig_name]
        options = self.servable(rig_name)
        if not options:
            return None
        best = min(options, key=lambda m: rig.usd_per_token(m))
        owned = rig.usd_per_token(best) * 1_000_000
        return CostComparison(
            rig_name=rig_name,
            model_name=best.name,
            owned_usd_per_1m=owned,
            api_usd_per_1m=api_usd_per_1m,
        )

    def break_even_months(
        self, rig_name: str, api_usd_per_1m: float, tokens_per_month: float
    ) -> Optional[float]:
        """Months until hardware pays for itself vs the API bill, given
        steady monthly token volume. None if owned is not cheaper."""
        rig = self.rigs[rig_name]
        options = self.servable(rig_name)
        if not options:
            return None
        owned_per_1m = min(rig.usd_per_token(m) for m in options) * 1_000_000
        saving_per_month = (
            (api_usd_per_1m - owned_per_1m) * tokens_per_month / 1_000_000
        )
        if saving_per_month <= 0:
            return None
        return rig.purchase_usd / saving_per_month
