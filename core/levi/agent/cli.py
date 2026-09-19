"""LEVI command line: one-shot ``ask`` and interactive ``chat``.

Stdlib only. ``ask`` runs a single task through the agentic tool loop and
prints the final answer; ``chat`` opens the persistent-session REPL.
With no subcommand, ``chat`` is the default.
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="levi",
        description="LEVI — local-first synthetic intelligence.",
    )
    parser.add_argument(
        "--version", action="store_true", help="Print the LEVI version and exit."
    )
    sub = parser.add_subparsers(dest="cmd")

    ask = sub.add_parser("ask", help="Run one task through the agent loop.")
    ask.add_argument("task", nargs="+", help="The task / question to run.")
    ask.add_argument(
        "--provider",
        default=None,
        help="Provider name (default: LEVI_PROVIDER env or the local offline engine).",
    )
    ask.add_argument(
        "--max-steps", type=int, default=10, help="Max tool-loop steps (default: 10)."
    )

    chat = sub.add_parser("chat", help="Interactive chat with a persistent session.")
    chat.add_argument(
        "--provider",
        default=None,
        help="Provider name (default: LEVI_PROVIDER env or the local offline engine).",
    )
    chat.add_argument(
        "--session", default="default", help="Session name to resume or create."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.version:
        from levi import __version__

        print(__version__)
        return 0

    if args.cmd == "ask":
        from levi.agent.loop import run_subtask

        transcript = run_subtask(
            " ".join(args.task),
            provider=args.provider,
            max_steps=args.max_steps,
        )
        if transcript.final:
            print(transcript.final)
        if not transcript.ok and transcript.error:
            print(f"error: {transcript.error}", file=sys.stderr)
        return 0 if transcript.ok else 1

    from levi.agent.chat import run_chat_repl

    run_chat_repl(
        session_name=getattr(args, "session", "default"),
        provider=getattr(args, "provider", None),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
