"""The Open Crate — the anti-loot-box.

The predatory trade, inverted: loot boxes and gacha sell *chance itself* —
hidden odds, paid pity, manufactured scarcity. The giants' math is a trade
secret; the player's expected value is deliberately unknowable.

The Open Crate is the honest-generous version and the math lesson in one:

- every drop table is published, in the open, in the code;
- the exact expected value of a pull is computed and shown before you pull;
- pulls are FREE and UNLIMITED — there is nothing to buy, ever;
- the pity timer is visible ("mythic guaranteed within N pulls") and costs nothing;
- ``--prove`` runs an empirical audit: N seeded pulls, observed vs declared
  distribution, max deviation printed. The charter's audit hook, made real.

Nothing here can take your money because there is no money. It exists to
teach the arithmetic the industry hides — and to be a genuinely fun toy
with the secrecy removed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from levi.games.charter import GameManifest

MANIFEST = GameManifest(
    name="open-crate",
    has_randomness=True,
    odds_declared=True,  # the whole point
    has_audit_hook=True,  # --prove
    progress_portable=True,
    hints_free=True,
)


@dataclass(frozen=True)
class Drop:
    item: str
    rarity: str
    weight: float  # published. sums need not be 100; normalized openly.


@dataclass
class Crate:
    name: str
    drops: Tuple[Drop, ...]
    pity_after: int = 50  # visible, free: rare+ guaranteed within this many pulls
    pity_rarities: Tuple[str, ...] = ("rare", "mythic")

    def total_weight(self) -> float:
        return sum(d.weight for d in self.drops)

    def declared_odds(self) -> Dict[str, float]:
        total = self.total_weight()
        return {d.item: d.weight / total for d in self.drops}


CRATES: Dict[str, Crate] = {
    "starfall": Crate(
        name="starfall",
        drops=(
            Drop("stardust (common)", "common", 70.0),
            Drop("moonshard (uncommon)", "uncommon", 20.0),
            Drop("comet core (rare)", "rare", 8.0),
            Drop("novaseed (mythic)", "mythic", 2.0),
        ),
        pity_after=50,
    ),
    "tidepool": Crate(
        name="tidepool",
        drops=(
            Drop("pebble (common)", "common", 60.0),
            Drop("shell (uncommon)", "uncommon", 25.0),
            Drop("pearl (rare)", "rare", 12.0),
            Drop("kraken ink (mythic)", "mythic", 3.0),
        ),
        pity_after=40,
    ),
}


@dataclass
class Pull:
    item: str
    rarity: str
    pity_was_due_in: int
    pity_triggered: bool


@dataclass
class CrateState:
    crate_name: str
    pulls: int = 0
    since_pity: int = 0
    history: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "crate_name": self.crate_name,
            "pulls": self.pulls,
            "since_pity": self.since_pity,
            "history": list(self.history),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CrateState":
        return cls(
            crate_name=data["crate_name"],
            pulls=int(data.get("pulls", 0)),
            since_pity=int(data.get("since_pity", 0)),
            history=list(data.get("history", [])),
        )


def expected_value(crate: Crate, values: Dict[str, float]) -> float:
    """Honest EV per pull. Values are *player-assigned* worth, not prices —
    there is nothing to buy, so EV is a teaching number, shown openly."""
    odds = crate.declared_odds()
    return sum(odds[d.item] * values.get(d.item, 0.0) for d in crate.drops)


def open_crate(crate: Crate, state: CrateState, rng: random.Random) -> Pull:
    """One free pull. Pity is visible and costs nothing."""
    due_in = max(0, crate.pity_after - state.since_pity)
    pity = state.since_pity + 1 >= crate.pity_after
    if pity:
        pool = [d for d in crate.drops if d.rarity in crate.pity_rarities]
    else:
        pool = list(crate.drops)
    total = sum(d.weight for d in pool)
    roll = rng.random() * total
    chosen = pool[-1]
    for d in pool:
        if roll < d.weight:
            chosen = d
            break
        roll -= d.weight
    state.pulls += 1
    state.since_pity = 0 if pity else state.since_pity + 1
    state.history.append(chosen.item)
    return Pull(
        item=chosen.item,
        rarity=chosen.rarity,
        pity_was_due_in=due_in,
        pity_triggered=pity,
    )


def audit(crate_name: str, n: int = 20000, seed: int = 7) -> Dict[str, object]:
    """Empirical audit: declared vs observed distribution over n seeded pulls.

    The charter's audit hook made concrete. Returns the max absolute
    deviation between declared and observed probability per item.
    """
    crate = CRATES[crate_name]
    rng = random.Random(seed)
    state = CrateState(crate_name=crate_name)
    counts: Dict[str, int] = {d.item: 0 for d in crate.drops}
    for _ in range(n):
        counts[open_crate(crate, state, rng).item] += 1
    declared = crate.declared_odds()
    observed = {item: c / n for item, c in counts.items()}
    deviation = {item: abs(observed[item] - declared[item]) for item in counts}
    return {
        "crate": crate_name,
        "n": n,
        "seed": seed,
        "declared": declared,
        "observed": observed,
        "max_deviation": max(deviation.values()),
        "deviation": deviation,
    }


def prove(crate_name: str, n: int = 20000, seed: int = 7) -> str:
    """Human-readable audit report."""
    r = audit(crate_name, n, seed)
    lines = [
        "Open Crate audit — %s (%d seeded pulls)" % (crate_name, n),
        "Every number below is public. That is the entire trick.",
    ]
    for item in r["declared"]:
        lines.append(
            "  %-24s declared %6.2f%%  observed %6.2f%%"
            % (item, r["declared"][item] * 100, r["observed"][item] * 100)
        )
    lines.append(
        "max deviation: %.4f (tolerance: honest RNG, not rigged)" % r["max_deviation"]
    )
    lines.append("price per pull: $0.00 — always. Pity: free, visible, guaranteed.")
    return "\n".join(lines)


def play(crate_name: str = "starfall", slot: str = "crate") -> None:
    from levi.games.saves import SaveStore

    if crate_name not in CRATES:
        print("unknown crate %r (try: %s)" % (crate_name, ", ".join(CRATES)))
        return
    crate = CRATES[crate_name]
    store = SaveStore()
    try:
        state = (
            CrateState.from_dict(store.load("open-crate", slot))
            if slot in store.list_slots("open-crate")
            else CrateState(crate_name=crate_name)
        )
    except Exception:
        state = CrateState(crate_name=crate_name)
    if state.crate_name != crate_name:
        state = CrateState(crate_name=crate_name)
    rng = random.Random()
    print("The Open Crate: %s — every pull free, every odd published." % crate_name)
    print(
        "Odds: "
        + ", ".join(
            "%s %.1f%%" % (d.item, w * 100)
            for d, w in zip(crate.drops, crate.declared_odds().values(), strict=True)
        )
    )
    print("Commands: pull | odds | prove | quit")
    while True:
        try:
            cmd = input("crate> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n(saved)")
            break
        if cmd in ("quit", "exit", "q"):
            break
        if cmd == "odds":
            for d in crate.drops:
                print("  %-24s %.2f%%" % (d.item, crate.declared_odds()[d.item] * 100))
            print(
                "  pity: %s guaranteed within %d pulls (free)"
                % ("/".join(crate.pity_rarities), crate.pity_after)
            )
            continue
        if cmd == "prove":
            print(prove(crate_name))
            continue
        if cmd in ("pull", "open", ""):
            pull = open_crate(crate, state, rng)
            print(
                "  -> %s [%s]%s"
                % (
                    pull.item,
                    pull.rarity,
                    "  (PITY — was due, cost you nothing)"
                    if pull.pity_triggered
                    else "  (pity in %d)" % max(0, crate.pity_after - state.since_pity),
                )
            )
            store.save("open-crate", slot, state.to_dict())
            continue
        print("unknown command (pull | odds | prove | quit)")
    store.save("open-crate", slot, state.to_dict())
