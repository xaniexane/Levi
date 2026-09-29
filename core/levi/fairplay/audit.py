"""The sly-trade detector: audit a game's offer design against the known
predatory patterns, and name the honest alternative for each.

Pattern catalog from the 2010-2024 record (archived this run under
``predators-hunt-20260928-evening``):

- ``opaque-odds`` — paid random draws with no published odds. The loot box
  as it shipped 2010-2017; Belgium's Gaming Commission ruled it gambling
  in 2018 (FIFA 18, CS:GO, Overwatch). The house could claim "high odds"
  while the true rate sat at 0.00005%.
- ``no-worst-case`` — odds published (the 2017 floor: China's law, Apple's
  App Store rule) but no pity ceiling and no worst-case spend declared.
  Complying with the letter while keeping the mercy rule hidden.
- ``time-fenced-grind`` — the battle-pass trade: every reward visible, but
  the buy is really "a $10 promise to play as much as possible for
  the length of a season" (PC Gamer). Unearned tiers evaporate forever.
- ``revocable-license`` — the storefront says BUY, the EULA says LICENSE,
  the license is revocable. The Crew kill, March 2024: Ubisoft decommissioned
  a decade-old game and revoked it from buyers' libraries.
- ``pay-to-win`` — power gated behind paying (Battlefront II's original sin).
- ``vanishing-inventory`` — acquired items live only on the seller's
  server with no export; Stadia's January 2023 shutdown is the shape.
- ``euphemism`` — the language of evasion: "surprise mechanics" (EA, UK
  Parliament 2019) and friends.

Defensive blue-team: detection and analysis only. This module names
patterns so they can be refused or inverted — it never builds a funnel.

LAWS:
1. Every pattern check is pure: the offer dict is read, never mutated.
2. Every sly finding carries an honest alternative — detection without
   a way out is just a lecture.
3. Unknown offer fields are ignored; missing fields are treated as
   "not claimed" and the finding says so honestly.
4. Package law: detection never runs a till. This module names predatory
   patterns without commerce vocabulary — it detects the funnel, it is
   not one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional

SEVERITY_SLY = "sly"
SEVERITY_CAUTION = "caution"
SEVERITY_CLEAN = "clean"


@dataclass(frozen=True)
class Finding:
    """One audit verdict."""

    pattern: str
    severity: str  # sly | caution | clean
    evidence: str
    honest_alternative: str
    source: str = ""  # archive record id, when the pattern is archived


@dataclass
class AuditReport:
    offer_name: str
    findings: List[Finding] = field(default_factory=list)

    def sly_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == SEVERITY_SLY)

    def caution_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == SEVERITY_CAUTION)

    def verdict(self) -> str:
        """One-word verdict: predatory, risky, or honest."""
        if self.sly_count():
            return "predatory"
        if self.caution_count():
            return "risky"
        return "honest"

    def summary(self) -> Dict[str, object]:
        return {
            "offer": self.offer_name,
            "verdict": self.verdict(),
            "sly": self.sly_count(),
            "caution": self.caution_count(),
            "clean": sum(1 for f in self.findings if f.severity == SEVERITY_CLEAN),
        }


# Euphemisms the industry uses to avoid saying "gambling" or "grind".
EUPHEMISMS = (
    "surprise mechanics",
    "player choice",
    "engagement",
    "live service",
    "games as a service",
)


def _flag(offer: Mapping, key: str) -> Optional[bool]:
    """Read a boolean claim; None means the offer doesn't say."""
    value = offer.get(key)
    return None if value is None else bool(value)


def audit_offer(offer: Mapping) -> AuditReport:
    """Audit one game offer. Pure: never mutates the offer.

    Recognized offer fields (all optional; absence is reported honestly):
    ``paid_random_draws``, ``odds_published``, ``pity_ceiling_declared``,
    ``worst_case_spend_declared``, ``progress_expiry`` ("never" | "season" |
    "event"), ``sale_is_license``, ``license_revocable``, ``eol_covenant``,
    ``paid_power``, ``server_only_inventory``, ``inventory_exportable``,
    ``marketing_language`` (list of phrases).
    """
    name = str(offer.get("name", "unnamed offer"))
    report = AuditReport(offer_name=name)

    # 1. Opaque odds — the original sin.
    if _flag(offer, "paid_random_draws"):
        if _flag(offer, "odds_published") is not True:
            report.findings.append(
                Finding(
                    pattern="opaque-odds",
                    severity=SEVERITY_SLY,
                    evidence="paid random draws with no published odds sheet",
                    honest_alternative=(
                        "publish a sum-validated odds card before the first draw "
                        "(see levi.fairplay.honestdraw.DropTable.publish)"
                    ),
                    source="arch-games-loot-box-lineage",
                )
            )
        elif (
            _flag(offer, "pity_ceiling_declared") is not True
            or _flag(offer, "worst_case_spend_declared") is not True
        ):
            report.findings.append(
                Finding(
                    pattern="no-worst-case",
                    severity=SEVERITY_CAUTION,
                    evidence="odds published but no declared pity ceiling or worst-case spend",
                    honest_alternative=(
                        "declare the pity ceiling in the published contract and "
                        "print the worst-case draws-to-tier on the tin"
                    ),
                    source="arch-games-odds-disclosure-imposed",
                )
            )
        else:
            report.findings.append(
                Finding(
                    pattern="declared-odds",
                    severity=SEVERITY_CLEAN,
                    evidence="odds published with declared pity ceiling and worst-case spend",
                    honest_alternative="keep it: this is the 2017 floor made native",
                    source="arch-games-odds-disclosure-imposed",
                )
            )

    # 2. Time-fenced grind — the battle-pass trade.
    expiry = offer.get("progress_expiry")
    if expiry in ("season", "event"):
        report.findings.append(
            Finding(
                pattern="time-fenced-grind",
                severity=SEVERITY_SLY,
                evidence="earned progress expires on a %s clock" % expiry,
                honest_alternative=(
                    "earned tiers never expire and pause across seasons "
                    "(see levi.fairplay.ownedtrack)"
                ),
                source="arch-games-battle-pass",
            )
        )
    elif expiry == "never":
        report.findings.append(
            Finding(
                pattern="progress-kept",
                severity=SEVERITY_CLEAN,
                evidence="earned progress never expires",
                honest_alternative="keep it: the player's effort is the player's",
                source="arch-games-battle-pass",
            )
        )

    # 3. Revocable license labeled as a sale.
    if _flag(offer, "sale_is_license") and _flag(offer, "license_revocable"):
        if _flag(offer, "eol_covenant") is not True:
            report.findings.append(
                Finding(
                    pattern="revocable-license",
                    severity=SEVERITY_SLY,
                    evidence="labeled BUY but licensed and revocable, with no end-of-life covenant",
                    honest_alternative=(
                        "publish a machine-readable end-of-life covenant at the point of sale "
                        "time (offline mode / local server / data export); label "
                        "revocable licenses RENTAL at the point of sale"
                    ),
                    source="arch-games-the-crew-kill",
                )
            )
        else:
            report.findings.append(
                Finding(
                    pattern="covenanted-license",
                    severity=SEVERITY_CAUTION,
                    evidence="revocable license but an end-of-life covenant is published",
                    honest_alternative="verify the covenant names a concrete playable fallback",
                    source="arch-games-the-crew-kill",
                )
            )

    # 4. Pay-to-win.
    if _flag(offer, "paid_power"):
        report.findings.append(
            Finding(
                pattern="pay-to-win",
                severity=SEVERITY_SLY,
                evidence="gameplay power is gated behind paying",
                honest_alternative="sell cosmetics only; power is earned by play",
                source="arch-games-loot-box-lineage",
            )
        )

    # 5. Vanishing inventory.
    if (
        _flag(offer, "server_only_inventory")
        and _flag(offer, "inventory_exportable") is not True
    ):
        report.findings.append(
            Finding(
                pattern="vanishing-inventory",
                severity=SEVERITY_SLY,
                evidence="acquired items live only on the seller's server with no export",
                honest_alternative=(
                    "player-held, hash-chained, portable ownership ledger "
                    "(see levi.fairplay.library)"
                ),
                source="arch-games-the-crew-kill",
            )
        )
    elif _flag(offer, "inventory_exportable"):
        report.findings.append(
            Finding(
                pattern="exportable-inventory",
                severity=SEVERITY_CLEAN,
                evidence="inventory is exportable by the player",
                honest_alternative="keep it: what you bought, you can carry",
                source="arch-games-the-crew-kill",
            )
        )

    # 6. Euphemism language.
    language = [str(p).lower() for p in (offer.get("marketing_language") or [])]
    hits = [e for e in EUPHEMISMS if any(e in phrase for phrase in language)]
    if hits:
        report.findings.append(
            Finding(
                pattern="euphemism",
                severity=SEVERITY_CAUTION,
                evidence="marketing uses evasive phrasing: %s"
                % ", ".join(sorted(set(hits))),
                honest_alternative="name the mechanism plainly: odds, grind, license",
                source="arch-games-loot-box-lineage",
            )
        )

    if not report.findings:
        report.findings.append(
            Finding(
                pattern="nothing-to-flag",
                severity=SEVERITY_CLEAN,
                evidence="no recognized predatory patterns in the declared offer",
                honest_alternative="keep the declarations honest and re-audit on every change",
            )
        )
    return report
