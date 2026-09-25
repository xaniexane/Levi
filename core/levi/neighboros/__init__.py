"""NeighborOS — LEVI product line 01: local-services dispatch OS.

LEVI-native recreation of Chauncey's own NeighborOS venture IP
(dispatch-first operating system for local services). Product line 01
per docs/PRODUCT_LINES.md: "it's all LEVI" — NeighborOS presents as
LEVI, runs on LEVI's organism, built by LEVI's factory.

Scope of this module (v1):
- tracker: the live Jobs project — service-job pipeline plus the
  worker roster that makes dispatch possible.
- brief: the founder's daily operations brief generator — dispatch
  bottlenecks, urgent work, supply gaps, and the single
  highest-leverage action for the day.

Explicitly out of scope (founder decisions required, see
docs/PRODUCT_LINES.md): NeighborPay / live money, Worker Twin and
Property Twin living records, compliance-gated market launch. No
external services are wrapped or required — stdlib only, local-first.

State lives under ``~/.levi/neighboros/`` with owner-only permissions.
"""

__version__ = "1.0.0"
