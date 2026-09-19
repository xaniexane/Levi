"""CLI: ``python -m levi.teletext`` — the local page broadcast."""

from __future__ import annotations

import argparse
import sys
import time

from levi.teletext.pages import PageStore, render_frame
from levi.teletext.serve import build_local_pages, index_page, serve


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="levi.teletext", description="Local Ceefax-style page broadcast")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index", help="render the front page (100)")
    p = sub.add_parser("render", help="render one numbered page")
    p.add_argument("number", type=int)
    p = sub.add_parser("serve", help="serve the broadcast on localhost")
    p.add_argument("--port", type=int, default=8477)
    p = sub.add_parser("carousel", help="print the endless broadcast loop")
    p.add_argument("--steps", type=int, default=3)
    args = ap.parse_args(argv)

    store = build_local_pages()
    if args.cmd == "index":
        print(render_frame(index_page(store)))
    elif args.cmd == "render":
        page = store.get(args.number)
        if page is None:
            print(f"page {args.number} not on air", file=sys.stderr)
            return 1
        print(render_frame(page))
    elif args.cmd == "serve":
        server, _thread = serve(store, port=args.port)
        print(f"teletext on air: http://127.0.0.1:{args.port}/  (Ctrl-C to stop)")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
        finally:
            server.shutdown()
    elif args.cmd == "carousel":
        cycle = store.carousel()
        for _ in range(args.steps):
            print(render_frame(next(cycle)))
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
