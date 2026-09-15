"""Entry point: ``python -m levi.bot``.

Subcommands:
- ``chat``    — interactive REPL.
- ``say TEXT`` — one-shot reply, printed to stdout.
- ``persona``  — print the spark voice card (system prompt rendering).
"""

from __future__ import annotations

import argparse
import sys


def _cmd_chat(_args: argparse.Namespace) -> int:
    """Run the interactive REPL."""
    from levi.bot.chat import repl

    repl()
    return 0


def _cmd_say(args: argparse.Namespace) -> int:
    """Print a one-shot reply to the given text."""
    from levi.bot.chat import say

    print(say(args.text))
    return 0


def _cmd_persona(_args: argparse.Namespace) -> int:
    """Print the spark voice card / system prompt."""
    from levi.bot.persona import render_system_prompt

    print(render_system_prompt())
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for ``python -m levi.bot``."""
    parser = argparse.ArgumentParser(
        prog="python -m levi.bot",
        description="LEVI conversational bot — the spark voice card.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_chat = sub.add_parser("chat", help="Start an interactive chat session.")
    p_chat.set_defaults(func=_cmd_chat)

    p_say = sub.add_parser("say", help="One-shot reply to the given text.")
    p_say.add_argument("text", help="The message to reply to.")
    p_say.set_defaults(func=_cmd_say)

    p_persona = sub.add_parser(
        "persona", help="Print the spark voice card (system prompt)."
    )
    p_persona.set_defaults(func=_cmd_persona)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
