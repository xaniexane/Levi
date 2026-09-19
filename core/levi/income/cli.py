"""CLI for the income portfolio engine. Thin layer over levi.income.engine."""

from __future__ import annotations

import json


def _engine():
    from levi.income import engine

    return engine


def cmd_income(args) -> int:
    """levi income <subcommand>."""
    eng = _engine()
    eng.discover()
    sub = getattr(args, "income_cmd", None) or "summary"

    if sub == "summary":
        print(json.dumps(eng.summary(), indent=2))
        return 0
    if sub == "list":
        for g in eng.REGISTRY.list():
            price = (
                f"${g['entry_price_usd']:.2f}"
                if g["entry_price_usd"] is not None
                else "unpriced"
            )
            print(f"[{g['slot']:>3}] {g['id']} ({g['kind']}) {price} — {g['name']}")
        return 0
    if sub == "run":
        rec = eng.run_generator(
            args.generator_id, dry_run=not args.apply, params={}
        )
        print(json.dumps(rec, indent=2))
        return 0
    if sub == "run-all":
        recs = eng.run_all(dry_run=not args.apply)
        ok = sum(1 for r in recs if "error" not in r)
        print(f"{ok}/{len(recs)} generators ran clean")
        for r in recs:
            if "error" in r:
                print(f"  FAIL {r['generator_id']}: {r['error']}")
        return 0
    if sub == "record":
        ev = eng.record_income(
            args.generator_id,
            args.amount,
            args.kind,
            basis=args.basis,
            counterparty=getattr(args, "counterparty", "") or "",
            note=getattr(args, "note", "") or "",
        )
        print(json.dumps(ev, indent=2))
        return 0
    if sub == "events":
        from levi.income.engine import _events_path, _read_jsonl

        for e in _read_jsonl(_events_path()):
            print(
                f"{e['at']} {e['generator_id']} {e['kind']} "
                f"${e['amount']:.2f} (keeper ${e['keeper']:.2f} / "
                f"pool ${e['pool']:.2f})"
            )
        return 0
    if sub == "pool":
        print(json.dumps(eng.pool_balance(), indent=2))
        return 0
    if sub == "spend":
        rec = eng.approve_pool_spend(
            args.amount, args.purpose, by=getattr(args, "by", "") or ""
        )
        print(json.dumps(rec, indent=2))
        return 0
    if sub == "price":
        giant = getattr(args, "giant", None)
        print(json.dumps(eng.advise_entry_price(giant), indent=2))
        return 0
    print(f"unknown income subcommand: {sub}")
    return 2
