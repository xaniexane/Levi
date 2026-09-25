"""The LEVI interactive console — a menu-driven text dashboard.

Entry point :func:`run` boots the main menu loop over the
:data:`levi.console.screens.SCREENS` registry. Every screen is a thin
handler that calls existing LEVI module functions (security catalog,
bounty pipeline, DemandPulse); the console itself adds no new
capabilities.

Extension point: to add a screen, define a ``screen_*() -> None`` handler
in :mod:`levi.console.screens`, keep it small, put prompting-free logic in
:mod:`levi.console.helpers`, and register one line in ``SCREENS``::

    SCREENS["finance"] = ("Finance", screen_finance)

The menu loop picks it up automatically — nothing here needs editing.
"""

from __future__ import annotations

import sys

from levi.console.screens import SCREENS
from levi.ux import banner, menu


def run() -> int:
    """Boot the interactive console. Returns a process exit code.

    Refuses to run without an interactive terminal (never hangs on
    ``input()`` in a pipe): returns 1 with a one-line explanation.
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("levi console needs an interactive terminal.")
        return 1

    while True:
        print(banner("LEVI console", "interactive dashboard — LEVI only"))
        options = [title for title, _handler in SCREENS.values()] + ["Quit"]
        try:
            choice = menu(options, prompt="Choose")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if choice is None or choice == len(options) - 1:
            print("Goodbye.")
            return 0
        _title, handler = list(SCREENS.values())[choice]
        try:
            handler()
        except (EOFError, KeyboardInterrupt):
            print()
        except Exception as exc:  # a screen must never kill the console
            print(f"Screen error: {exc}")
