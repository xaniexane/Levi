"""FairPlay plugin — the sly-trade detector as a connector plugin.

Where ``units`` answers "how many X in Y" with pure math, ``fairplay``
answers "is this offer honest" with pure detection: it runs
``levi.fairplay.audit.audit_offer`` over a caller-supplied offer dict
and returns the verdict plus an honest alternative for every finding.

Operations (all read-only; no confirmation gate can ever trigger):
* ``audit`` — audit one offer (params: ``offer``, a mapping of declared
  claims; see ``levi.fairplay.audit.audit_offer`` for recognized fields);
* ``catalog`` — list the seven sly-trade patterns with their tells and
  honest alternatives (params: none).

Honesty rules, deny-closed:
* ``offer`` must be a mapping — anything else → ``invalid_params``,
  never a guessed audit;
* the audit never mutates the offer; unknown fields are ignored and
  missing fields are reported as "not claimed" by the detector itself;
* the catalog is documentation over the detector: the test suite
  asserts every pattern id the detector can emit appears in the
  catalog, so the two cannot silently drift apart.

Defensive blue-team: detection and analysis only — it names predatory
patterns so they can be refused or inverted, never builds a funnel.

``fairplay`` is the reference detector ("fairplay"), never LEVI identity.
Credentialless by design: ``credential()`` returns the ``"public"``
sentinel so the registry's credential gate never fires for reads.

NOTE: registration activates on import. Add ``fairplay`` to the import
list in ``levi.plugins.__init__`` to wire it into the plugin catalog
(queued — that file is in-flight with another worker; do not edit it
from here).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from .registry import (
    Capability,
    Connector,
    InvalidParams,
    Operation,
    Transport,
    register_connector,
)

_REFERENCE = "fairplay"

# Pattern catalog: documentation over levi.fairplay.audit.audit_offer,
# which is the executable source of truth. ``severity`` mirrors the
# detector's finding severities.
_PATTERNS: List[Dict[str, str]] = [
    {
        "pattern": "opaque-odds",
        "severity": "sly",
        "tell": "paid random draws with no published odds sheet",
        "honest_alternative": "publish a sum-validated odds card before the first draw",
        "source": "arch-games-loot-box-lineage",
    },
    {
        "pattern": "no-worst-case",
        "severity": "caution",
        "tell": "odds published but no declared pity ceiling or worst-case spend",
        "honest_alternative": "declare the pity ceiling in the contract; print worst-case draws-to-tier on the tin",
        "source": "arch-games-odds-disclosure-imposed",
    },
    {
        "pattern": "time-fenced-grind",
        "severity": "sly",
        "tell": "earned progress expires on a season/event clock",
        "honest_alternative": "earned tiers never expire and pause across seasons",
        "source": "arch-games-battle-pass",
    },
    {
        "pattern": "revocable-license",
        "severity": "sly",
        "tell": "labeled BUY but licensed and revocable, with no end-of-life covenant",
        "honest_alternative": "publish a machine-readable end-of-life covenant at point of sale; label revocable licenses RENTAL",
        "source": "arch-games-the-crew-kill",
    },
    {
        "pattern": "pay-to-win",
        "severity": "sly",
        "tell": "gameplay power gated behind paying",
        "honest_alternative": "sell cosmetics only; power is earned by play",
        "source": "arch-games-loot-box-lineage",
    },
    {
        "pattern": "vanishing-inventory",
        "severity": "sly",
        "tell": "acquired items live only on the seller's server with no export",
        "honest_alternative": "player-held, hash-chained, portable ownership ledger",
        "source": "arch-games-the-crew-kill",
    },
    {
        "pattern": "euphemism",
        "severity": "caution",
        "tell": "marketing uses evasive phrasing (e.g. 'surprise mechanics')",
        "honest_alternative": "name the mechanism plainly: odds, grind, license",
        "source": "arch-games-loot-box-lineage",
    },
]


def _finding_to_dict(finding: Any) -> Dict[str, str]:
    return {
        "pattern": finding.pattern,
        "severity": finding.severity,
        "evidence": finding.evidence,
        "honest_alternative": finding.honest_alternative,
        "source": finding.source,
    }


@register_connector
class FairPlayConnector(Connector):
    """Sly-trade detector as a read-only connector plugin."""

    id = _REFERENCE
    display_name = "FairPlay"
    credential_env_var = "LEVI_FAIRPLAY_TOKEN"  # never set: credentialless by design
    capabilities = (
        Capability(
            name="audit",
            description="Detect predatory patterns in a game offer; read-only.",
        ),
        Capability(
            name="catalog",
            description="List the sly-trade patterns with honest alternatives.",
        ),
    )
    operations = (
        Operation(
            name="audit",
            description="Audit one offer dict; returns verdict + findings.",
            params=("offer",),
        ),
        Operation(
            name="catalog",
            description="Return the seven sly-trade patterns.",
            params=(),
        ),
    )

    def credential(self) -> Optional[str]:
        return "public"

    def perform(
        self,
        operation: str,
        params: Dict[str, Any],
        token: Optional[str],
        transport: Optional[Transport],
    ) -> Dict[str, Any]:
        if operation == "catalog":
            return {"patterns": [dict(p) for p in _PATTERNS]}
        if operation == "audit":
            offer = params.get("offer")
            if not isinstance(offer, Mapping):
                raise InvalidParams(
                    "fairplay.audit: 'offer' must be a mapping of declared "
                    f"claims, got {type(offer).__name__} — nothing was audited."
                )
            from levi.fairplay.audit import audit_offer

            report = audit_offer(offer)
            return {
                "offer_name": report.offer_name,
                "verdict": report.verdict(),
                "sly_count": report.sly_count(),
                "caution_count": report.caution_count(),
                "findings": [_finding_to_dict(f) for f in report.findings],
            }
        raise InvalidParams(
            f"fairplay: unknown operation {operation!r}. Known: audit, catalog."
        )
