"""Interactive videotex terminal: python -m levi.videotex

A passive terminal in the Minitel spirit: numbered trees, ``*`` to go
back, ``sommaire`` for the contents page, ``guide`` for the key help.
Reading only — nothing here executes.
"""

from __future__ import annotations

import argparse

from .navigate import Navigator


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="LEVI videotex — browse LEVI from any terminal, Minitel-style."
    )
    ap.add_argument(
        "--script",
        nargs="*",
        default=None,
        help="non-interactive: replay these inputs and print each screen",
    )
    args = ap.parse_args(argv)

    nav = Navigator.build()
    if args.script is not None:
        for text in nav.run_script(args.script):
            print(text)
            print()
        return 0

    print(nav._render(""))
    try:
        while True:
            try:
                line = input("3615> ")
            except EOFError:
                print("\nAu revoir.")
                break
            text, quit_flag = nav.handle(line)
            print(text)
            if quit_flag:
                break
    except KeyboardInterrupt:
        print("\nAu revoir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
