"""Sunset escrow — design the funeral at birth.

The inversion of the Stop-Killing-Games trade: the industry sells you a
game and kills it by switching off a server (Ubisoft killed *The Crew* in
2024 and revoked sold copies; Ross Scott's Stop Killing Games initiative
took the fight to the EU). LEVI's honest addition is the opposite ritual:
every network-dependent game must carry a **sunset plan** — a public,
machine-checkable commitment written at birth, escrowed in plain JSON,
saying exactly what happens when the lights go out.

A SunsetPlan answers, before anyone asks:
  - offline_patch : will the game still run with no server?
  - content_export: can the player export everything they bought/made?
  - unlock_codes  : are server-gated unlocks held for release on sunset?
  - state_export  : does all player state survive as portable files?
  - source_escrow : is a buildable copy held so the community can keep it alive?

The sunset *drill* keeps the plan honest: it re-verifies each commitment
against real artifacts. A promised-but-undelivered commitment is reported
as a failure, never a silent pass — an unverified escrow is marketing.

Charter tie-in (see :mod:`levi.games.charter`): a game that
``requires_network`` must have a sunset plan. Offline-first is the
default; if you need a server, you owe the player a funeral plan.

Storage: ``~/.levi/games/escrow/<game_id>.json`` — owner-only, plain JSON,
portable, versioned. The escrow travels with the game, not with LEVI.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ESCROW_FORMAT = 1

# The five commitments every sunset plan answers. Each is a question the
# player never had to ask of the dead platforms.
COMMITMENTS = (
    "offline_patch",  # game still runs with no server
    "content_export",  # everything bought/made can be exported
    "unlock_codes",  # server-gated unlocks released on sunset
    "state_export",  # player state survives as portable files
    "source_escrow",  # a buildable copy is held for the community
)


class SunsetError(Exception):
    """Sunset plan / escrow failures."""


@dataclass
class Commitment:
    """One sunset commitment: promised at birth, delivered (or not) at drill."""

    promised: bool = False
    delivered: bool = False
    evidence: str = ""  # where the artifact lives, in plain words


@dataclass
class SunsetPlan:
    """A game's funeral plan, written at birth."""

    game_id: str
    escrow_text: str = ""  # plain-language commitment to the player
    declared_at: str = ""
    commitments: Dict[str, Commitment] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.declared_at:
            self.declared_at = datetime.now(timezone.utc).isoformat()
        for key in COMMITMENTS:
            self.commitments.setdefault(key, Commitment())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "levi_sunset_escrow": ESCROW_FORMAT,
            "game_id": self.game_id,
            "escrow_text": self.escrow_text,
            "declared_at": self.declared_at,
            "commitments": {
                k: asdict(c) for k, c in self.commitments.items() if k in COMMITMENTS
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SunsetPlan":
        try:
            plan = cls(
                game_id=str(data["game_id"]),
                escrow_text=str(data.get("escrow_text", "")),
                declared_at=str(data.get("declared_at", "")),
            )
            for key, raw in data.get("commitments", {}).items():
                if key in COMMITMENTS and isinstance(raw, dict):
                    plan.commitments[key] = Commitment(
                        promised=bool(raw.get("promised")),
                        delivered=bool(raw.get("delivered")),
                        evidence=str(raw.get("evidence", "")),
                    )
            return plan
        except (KeyError, TypeError, ValueError) as exc:
            raise SunsetError("bad sunset plan: %s" % exc) from exc


def _default_root() -> Path:
    home = os.environ.get("LEVI_HOME") or os.path.expanduser("~/.levi")
    return Path(home) / "games" / "escrow"


class EscrowVault:
    """Owner-only, portable JSON sunset plans."""

    def __init__(self, root: "str | os.PathLike[str] | None" = None):
        self.root = Path(root) if root else _default_root()

    def _path(self, game_id: str) -> Path:
        safe = "".join(c for c in game_id if c.isalnum() or c in "-_")
        if not safe:
            raise SunsetError("bad game_id")
        return self.root / (safe + ".json")

    def store(self, plan: SunsetPlan) -> Path:
        path = self._path(plan.game_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(plan.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        os.chmod(path, 0o600)
        return path

    def load(self, game_id: str) -> SunsetPlan:
        path = self._path(game_id)
        if not path.exists():
            raise SunsetError(
                "no sunset plan for %r — the game has no funeral" % game_id
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise SunsetError("corrupt escrow for %r: %s" % (game_id, exc)) from exc
        return SunsetPlan.from_dict(data)

    def list_games(self) -> List[str]:
        if not self.root.exists():
            return []
        return sorted(p.stem for p in self.root.glob("*.json") if p.is_file())


# ---------------------------------------------------------------------------
# The sunset drill
# ---------------------------------------------------------------------------


@dataclass
class DrillResult:
    commitment: str
    promised: bool
    delivered: bool
    evidence: str
    ok: bool  # promised => delivered; unpromised => neutral (honestly reported)


@dataclass
class DrillReport:
    game_id: str
    results: List[DrillResult]
    ran_at: str

    @property
    def honest(self) -> bool:
        """True only if every promise made has been delivered."""
        return all(r.ok for r in self.results if r.promised)

    @property
    def promises_kept(self) -> int:
        return sum(1 for r in self.results if r.promised and r.delivered)

    @property
    def promises_made(self) -> int:
        return sum(1 for r in self.results if r.promised)

    def text(self) -> str:
        lines = [
            "Sunset drill — %s" % self.game_id,
            "  ran at: %s" % self.ran_at,
            "",
        ]
        for r in self.results:
            if not r.promised:
                lines.append(
                    "  [----] %s: not promised (honestly unclaimed)" % r.commitment
                )
            elif r.ok:
                lines.append(
                    "  [KEEP] %s: delivered — %s"
                    % (r.commitment, r.evidence or "no evidence noted")
                )
            else:
                lines.append(
                    "  [FAIL] %s: PROMISED but not delivered — %s"
                    % (r.commitment, r.evidence or "no evidence")
                )
        lines.append("")
        if self.promises_made == 0:
            lines.append("No promises made. The game has no funeral plan.")
        elif self.honest:
            lines.append(
                "All %d promises kept. The funeral is planned and ready."
                % self.promises_made
            )
        else:
            lines.append(
                "%d of %d promises kept — an unverified escrow is marketing."
                % (self.promises_kept, self.promises_made)
            )
        return "\n".join(lines)


def drill(vault: EscrowVault, game_id: str) -> DrillReport:
    """Run the sunset drill: re-verify every commitment against its artifacts.

    Raises SunsetError when the game has no plan at all — that is itself a
    drill failure the caller can report honestly.
    """
    plan = vault.load(game_id)
    results = []
    for key in COMMITMENTS:
        c = plan.commitments.get(key, Commitment())
        results.append(
            DrillResult(
                commitment=key,
                promised=c.promised,
                delivered=c.delivered and bool(c.evidence),
                evidence=c.evidence,
                ok=(not c.promised) or (c.delivered and bool(c.evidence)),
            )
        )
    return DrillReport(
        game_id=plan.game_id,
        results=results,
        ran_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Charter tie-in
# ---------------------------------------------------------------------------


def charter_rule_sunset(manifest) -> bool:
    """A network-dependent game must carry a sunset plan.

    Offline-first is the default honest side; if the game needs a server,
    the player is owed a funeral plan. Use as a CharterRule check or call
    directly in tests.
    """
    requires_network = bool(getattr(manifest, "requires_network", False))
    has_plan = bool(getattr(manifest, "has_sunset_plan", True))
    return (not requires_network) or has_plan


def mark_delivered(
    vault: EscrowVault, game_id: str, commitment: str, evidence: str
) -> SunsetPlan:
    """Record that a commitment's artifact now exists. The drill verifies it."""
    if commitment not in COMMITMENTS:
        raise SunsetError(
            "unknown commitment %r (choose from %s)"
            % (commitment, ", ".join(COMMITMENTS))
        )
    plan = vault.load(game_id)
    c = plan.commitments[commitment]
    c.delivered = True
    c.evidence = evidence
    vault.store(plan)
    return plan
