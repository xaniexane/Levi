"""SOXI daemon — the offline-first main loop.

    python -m levi.soxi.daemon --prompt "rewrite this in my voice: ..."
    python -m levi.soxi.daemon --correct "orig text" --as "fixed text" [--mood tired]
    python -m levi.soxi.daemon --etch "Don't take freelance work that kills weekends."
    python -m levi.soxi.daemon --nightly        # RT shutdown hook
    python -m levi.soxi.daemon --status

LN routes every prompt to the right class(es). Offline always: nothing
here touches the network, ever. If a query would need the web, LN says
"offline — want me to save it for later?" and files it.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from .ln_router import LoomRouter

DEFAULT_DATA_DIR = Path.home() / ".levi" / "soxi"


def load_config() -> dict:
    cfg_path = Path(__file__).with_name("config.toml")
    try:
        return tomllib.loads(cfg_path.read_text())
    except FileNotFoundError:
        return {"soxi": {"online": False}}


def data_dir() -> Path:
    cfg = load_config()
    d = cfg.get("soxi", {}).get("data_dir", str(DEFAULT_DATA_DIR))
    return Path(d).expanduser()


def handle_prompt(prompt: str) -> str:
    from .fr_friction import FrictionStore
    from .et_etch import EtchBoard
    from .bt_bent import BentMind

    dd = data_dir()
    router = LoomRouter(dd)
    ranked = router.route(prompt)
    top, score, reason = ranked[0]
    lines = [f"[LN routed → {top} ({score:+.1f}) — {reason}]"]

    if top == "FR":
        store = FrictionStore(dd)
        fixed, hit = store.apply(prompt)
        if hit:
            lines.append(f"[FR] on file (overlap {hit['overlap']}): {fixed}")
        else:
            similar = store.find_similar(prompt)
            if similar:
                lines.append("[FR] close corrections on file:")
                lines += [f"  - '{s['original']}' → '{s['corrected']}'" for s in similar]
            else:
                lines.append("[FR] no corrections on file yet — correct me and I'll learn.")
        store.close()
    elif top == "ET":
        board = EtchBoard(dd)
        hits = board.check_decision(prompt)
        if hits:
            lines.append("[ET] this touches etched law:")
            lines += [f"  - #{h['seq']}: {h['text']}" for h in hits]
        else:
            lines.append("[ET] no etched law conflicts with this.")
    elif top == "BT":
        mind = BentMind(domain="journal")
        res = mind.generate(prompt)
        lines.append(f"[BT/{res.backend}] {res.text}")
    else:
        lines.append(f"[{top}] class acknowledged — handler scaffold ready, "
                     "wire it into handle_prompt as it grows.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SOXI offline daemon")
    ap.add_argument("--prompt", help="route a prompt through LN")
    ap.add_argument("--correct", help="original text you want to correct")
    ap.add_argument("--as", dest="corrected", help="what you meant instead")
    ap.add_argument("--mood", default="", help="your state when correcting")
    ap.add_argument("--etch", help="etch an unchangeable law/memory/boundary")
    ap.add_argument("--etch-kind", default="law")
    ap.add_argument("--nightly", action="store_true", help="RT shutdown hook")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_config()
    if cfg.get("soxi", {}).get("online"):
        print("[SOXI] config says online=true — refusing: SOXI runs offline-first. "
              "Set online=false or use ghost-sync explicitly.", file=sys.stderr)
        return 2

    dd = data_dir()

    if args.status:
        router = LoomRouter(dd)
        st = router.status()
        print(f"SOXI status: {st['classes']} classes, scoreboard={st['scoreboard']}, data={dd}")
        return 0

    if args.correct and args.corrected:
        from .fr_friction import FrictionStore
        store = FrictionStore(dd)
        cid = store.correct(args.correct, args.corrected, args.mood)
        n = store.count()
        store.close()
        print(f"[FR] correction #{cid} filed ({n} total). I'll stop making that mistake.")
        return 0

    if args.etch:
        from .et_etch import EtchBoard
        board = EtchBoard(dd)
        rec = board.etch(args.etch, kind=args.etch_kind)
        print(f"[ET] etched #{rec['seq']} ({args.etch_kind}): {args.etch}")
        return 0

    if args.nightly:
        from .rt_root import write_morning_md, collect_sections
        path = write_morning_md(dd, collect_sections(dd))
        print(f"[RT] wrote {path}")
        return 0

    if args.prompt:
        print(handle_prompt(args.prompt))
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
