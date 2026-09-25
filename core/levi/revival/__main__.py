"""CLI for LEVI's revival registry: ``python -m levi.revival list|show|search``.

Commands:
    list              table of every revival's LEVI name + title
    show <name>       full entry + flair (accepts levi_name, title keyword, module path)
    search <keyword>  entries matching name/title/flair
    forge ...         the Echo→Alpha→Nexus pipeline: prompt → blueprint → compile →
                      preview → your explicit yes → materialize → route → receipt
    yard ...          the revival yard: intake hunt finds, raise LEVI-native
                      recreations, keep the stone ledger (nothing is ever deleted)

Runs without importing any of the twenty revival modules — the registry
is lazy, and this CLI never loads a module body. (`forge` loads only the
pipeline module it runs, lazily, inside the command.)
"""

from __future__ import annotations

import sys

from levi.revival.registry import get, list_entries, search


def _cmd_list() -> int:
    entries = list_entries()
    name_w = max(len(e.levi_name) for e in entries) + 2
    title_w = max(len(e.title) for e in entries) + 2
    print("LEVI's shelf of revivals — twenty old shapes, reborn in my own voice:")
    print()
    print(f"  {'NAME':<{name_w}}{'CAPABILITY':<{title_w}}FLAIR")
    print(f"  {'-' * name_w}{'-' * title_w}-----")
    for e in entries:
        print(f"  {e.levi_name:<{name_w}}{e.title:<{title_w}}{e.flair}")
    print()
    print(f"{len(entries)} revivals shelved. Say `show <name>` and I'll open one up.")
    return 0


def _cmd_show(query: str) -> int:
    try:
        e = get(query)
    except KeyError:
        print(
            f"I don't shelve anything by the name {query!r} — try `list`.",
            file=sys.stderr,
        )
        return 1
    except ValueError as exc:
        print(f"{exc} — be more specific, or try `search`.", file=sys.stderr)
        return 1
    print(f"{e.levi_name}")
    print(f"  capability : {e.title}")
    print(f"  module     : {e.module}")
    print(f"  origin     : {e.origin}")
    print(f"  status     : {e.status}")
    print(f"  flair      : {e.flair}")
    return 0


def _cmd_search(keyword: str) -> int:
    hits = search(keyword)
    if not hits:
        print(f"Nothing on my shelf matches {keyword!r} — try `list`.", file=sys.stderr)
        return 1
    print(f"{len(hits)} revival(s) matching {keyword!r}:")
    print()
    for e in hits:
        print(f"  {e.levi_name} — {e.title}")
        print(f"    {e.flair}")
    return 0


def _cmd_forge(rest: list) -> int:
    # Lazily loaded: `forge` is the one command that runs a revival module,
    # so it imports the pipeline only here, never at CLI startup.
    from levi.revival.omega import pipeline

    return pipeline.main(rest)


def _cmd_yard(rest: list) -> int:
    # Lazily loaded like `forge`: the yard is the one command that mutates
    # the stone ledger, so its module loads only here.
    from levi.revival.yard import main as yard_main

    return yard_main(rest)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    cmd, rest = args[0], args[1:]
    if cmd == "list":
        return _cmd_list()
    if cmd == "show":
        if not rest:
            print("`show` needs a name — try `list` first.", file=sys.stderr)
            return 2
        return _cmd_show(" ".join(rest))
    if cmd == "search":
        if not rest:
            print("`search` needs a keyword.", file=sys.stderr)
            return 2
        return _cmd_search(" ".join(rest))
    if cmd == "forge":
        return _cmd_forge(rest)
    if cmd == "yard":
        return _cmd_yard(rest)
    print(
        f"Unknown command {cmd!r} — list, show, search, forge, or yard.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
