"""Entry point for the LEVI interactive console (``levi console``).

``run() -> int`` is wired to the CLI by the parent — see :mod:`levi.console.app`.
"""

from levi.console.app import run
from levi.console.screens import SCREENS

__all__ = ["run", "SCREENS"]
