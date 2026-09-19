"""Dweller native SI core package.

The grind engine: takes queued jobs, validates the sandbox, passes the
permission gate, runs the runners, journals everything, and always
produces a receipt. stdlib only; never imports the AI counterpart
bridge.
"""

from __future__ import annotations

from .grind import grind, grind_dry_run

__all__ = ["grind", "grind_dry_run"]
