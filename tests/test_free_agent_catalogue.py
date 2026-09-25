"""Free-agent catalogue tests: entries, metering, wallet, billing, views, teams.

Run:  python3 tests/test_free_agent_catalogue.py     (has a real __main__ runner)
      python3 -m pytest tests/test_free_agent_catalogue.py -q
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.catalogue import (  # noqa: E402
    BillingBoundary,
    CatalogueEntry,
    CreditWallet,
    ForceTeam,
    FreeAgentCatalogue,
    UsageLedger,
    catalogue_view,
    seed_entries,
)
from levi.catalogue.wallet import (  # noqa: E402
    AD_GRANT_CREDITS,
    AD_GRANTS_PER_DAY,
    WALLET_CAP,
)

FOUNDER = {"tier": "founder", "name": "chauncey"}
USER = {"tier": "standard", "name": "someone"}

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {name}")


def expect_raises(name, exc, fn, *args, **kwargs):
    global PASS, FAIL
    try:
        fn(*args, **kwargs)
    except exc:
        PASS += 1
    except Exception as e:  # noqa: BLE001
        FAIL += 1
        print(f"FAIL: {name} — raised {type(e).__name__}, wanted {exc.__name__}")
    else:
        FAIL += 1
        print(f"FAIL: {name} — no exception, wanted {exc.__name__}")


def tiny_entry(**kw):
    base = dict(
        id="tiny",
        provider="Test Provider (example)",
        agent_name="Tiny (example)",
        free_quota=2,
        credit_cost_per_use=1,
        provider_price_cents_per_use=7,
        example=True,
    )
    base.update(kw)
    return CatalogueEntry(**base)


# -- 1. seed entries are structural examples ---------------------------

seeds = seed_entries()
check("seeds non-empty", len(seeds) >= 3)
check("all seeds flagged example", all(s.example for s in seeds))
check(
    "seed blurbs disclaim real deals",
    all("not a real provider deal" in s.blurb for s in seeds),
)
check("seed ids unique", len({s.id for s in seeds}) == len(seeds))
expect_raises("bad quota rejected", ValueError, CatalogueEntry, id="x", provider="p",
               agent_name="a", free_quota=-1)

# -- 2. free quota enforcement -----------------------------------------

cat = FreeAgentCatalogue(entries=[tiny_entry()])
r1 = cat.use_agent("u1", "tiny", USER)
r2 = cat.use_agent("u1", "tiny", USER)
check("first two uses free", r1.via == "free_quota" and r2.via == "free_quota")
check("free uses counted", cat.ledger.uses("u1", "tiny") == 2)

# third use, no credits -> provider billed at full price
r3 = cat.use_agent("u1", "tiny", USER)
check("over-quota no-credit -> provider_billed", r3.via == "provider_billed")
rec = r3.detail["billing_record"]
check("billing at full provider price", rec["unit_price_cents"] == 7)
check("billing is user responsibility", rec["responsibility"] == "user")

# with credits -> credit path
cat.wallets.grant("u2", 10, reason="test")
cat.use_agent("u2", "tiny", USER)
cat.use_agent("u2", "tiny", USER)
r = cat.use_agent("u2", "tiny", USER)
check("over-quota with credits -> credits", r.via == "credits")
check("credit spent", r.detail["credits_spent"] == 1 and cat.wallets.balance("u2") == 9)

# founder bypasses metering
rf = cat.use_agent("founder-u", "tiny", FOUNDER)
check("founder unmetered", rf.via == "founder")
check("founder use not ledgered", cat.ledger.uses("founder-u", "tiny") == 0)

expect_raises("unknown entry", Exception, cat.use_agent, "u1", "nope", USER)

# -- 3. wallet: grants, caps, ad option ---------------------------------

w = CreditWallet()
g = w.grant("a", 100, reason="promo")
check("grant adds", g["balance"] == 100 and g["granted"] == 100 and not g["capped"])
g2 = w.grant("a", 1000, reason="whale")
check("wallet cap enforced", g2["balance"] == WALLET_CAP and g2["capped"])
expect_raises("negative grant rejected", ValueError, w.grant, "a", -5)

w2 = CreditWallet()
d1 = w2.grant_for_ad_view("b", day="2026-09-18")
d2 = w2.grant_for_ad_view("b", day="2026-09-18")
d3 = w2.grant_for_ad_view("b", day="2026-09-18")
check("two ad grants pay", not d1["denied"] and not d2["denied"])
check("ad grant size", d1["granted"] == AD_GRANT_CREDITS)
check("third ad view denied (moderate cap)", d3["denied"] and d3["granted"] == 0)
check("cap is moderate (2/day)", AD_GRANTS_PER_DAY == 2)
d4 = w2.grant_for_ad_view("b", day="2026-09-19")
check("cap resets next day", not d4["denied"])
check("spend ok", w2.spend("b", 10) and w2.balance("b") == 3 * AD_GRANT_CREDITS - 10)
check("overspend refused", not w2.spend("b", 10**9))

# wallet serialization roundtrip
w3 = CreditWallet.from_dict(w2.to_dict())
check("wallet roundtrip", w3.balance("b") == w2.balance("b"))

# -- 4. ledger serialization --------------------------------------------

led = UsageLedger()
led.record_use("u", "e", 5)
led2 = UsageLedger.from_dict(led.to_dict())
check("ledger roundtrip", led2.uses("u", "e") == 1)
check("ledger reset", led.reset_user("u") == 1 and led.uses("u", "e") == 0)

# -- 5. founder vs non-founder views ------------------------------------

entries = [
    CatalogueEntry(
        id="v",
        provider="P (example)",
        agent_name="V (example)",
        capabilities=["public thing"],
        full_capabilities=["public thing", "true potential thing"],
        example=True,
    )
]
pub = catalogue_view(entries, USER)
fnd = catalogue_view(entries, FOUNDER)
anon = catalogue_view(entries, None)
check("public view hides true potential", "full_capabilities" not in pub[0])
check("public view keeps gated surface",
      pub[0]["capabilities"] == ["public thing"] and "free_quota" in pub[0])
check("founder sees true potential", fnd[0]["full_capabilities"] == ["public thing", "true potential thing"])
check("anonymous treated as non-founder", "full_capabilities" not in anon[0])

# -- 6. billing boundary -------------------------------------------------

bb = BillingBoundary()
bb.record("u9", "e", "P", "A", uses=3, unit_price_cents=5)
bb.record("u9", "e", "P", "A", uses=1, unit_price_cents=5)
check("billing totals accumulate", bb.total_owed_cents("u9") == 20)
check("other user unaffected", bb.total_owed_cents("nobody") == 0)
bb2 = BillingBoundary.from_dict(bb.to_dict())
check("billing roundtrip", bb2.total_owed_cents("u9") == 20)

# -- 7. team combination ------------------------------------------------

cat2 = FreeAgentCatalogue(entries=[tiny_entry(id="t1"), tiny_entry(id="t2")])
team = cat2.team("crew-1", "Crew One")
seat = cat2.attach_to_team("crew-1", "t1", role="researcher")
check("attach returns catalogue seat",
      seat.kind == "catalogue" and seat.member_ref == "t1" and seat.role == "researcher")
check("team lists catalogue agent",
      [s.member_ref for s in team.catalogue_agents()] == ["t1"])
expect_raises("duplicate attach rejected", ValueError,
              cat2.attach_to_team, "crew-1", "t1")
expect_raises("unknown entry attach rejected", KeyError,
              cat2.attach_to_team, "crew-1", "ghost")
check("detach works", team.detach("t1") and team.catalogue_agents() == [])

# external team record adapter: catalogue never rewrites the source team
ext = {"id": "ext-1", "name": "External", "members": ["native-1"]}
adapted = ForceTeam.from_record(ext)
adapted.attach_catalogue_agent("t2", role="scout", known_entry_ids={"t1", "t2"})
check("adapter keeps native members",
      [s.member_ref for s in adapted.seats()] == ["native-1", "t2"])
rt = ForceTeam.from_dict(adapted.to_dict())
check("team roundtrip", [s.member_ref for s in rt.seats()] == ["native-1", "t2"])

# -- 8. gateway contract: the catalogue never reaches out --------------

MODULE_DIR = ROOT / "core" / "levi" / "catalogue"
NET_RE = re.compile(r"^\s*(import|from)\s+(socket|http|urllib|requests|httpx)\b", re.M)
leaks = []
for path in sorted(MODULE_DIR.glob("*.py")):
    src = path.read_text()
    if NET_RE.search(src):
        leaks.append(path.name)
check("no network imports in catalogue (gateway law)", not leaks)

# -- 9. facade list_for honors founder gating ----------------------------

cat3 = FreeAgentCatalogue()
check("facade list_for gated for user",
      all("full_capabilities" not in e for e in cat3.list_for(USER)))
check("facade list_for full for founder",
      all("full_capabilities" in e for e in cat3.list_for(FOUNDER)))
expect_raises("duplicate registration rejected", Exception,
              cat3.register, tiny_entry(id="tidechart"))

print(f"\n{__file__}: {PASS} passed, {FAIL} failed")


def test_free_agent_catalogue():
    assert FAIL == 0, f"{FAIL} catalogue checks failed"


if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
