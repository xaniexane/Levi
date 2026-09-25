"""LEVI Forge — LEVI's own local-first code home.

A code forge (git hosting + collaboration) that lives entirely on the
user's machine: stdlib-only, no network, no accounts, no telemetry.

Ownership guarantee (binding): LEVI Forge never transmits your code
anywhere. There is no telemetry, no training corpus, nothing leaves
localhost unless you explicitly push it.

Layout of the forge home (``~/.levi/forge/``)::

    repos/<name>.git/        bare git repositories (stock git, bare format)
    issues/<name>.jsonl      issues, one JSON object per line
    prs/<name>.jsonl         pull requests, one JSON object per line
    stars.json               starred repos (favorites, portable reputation)
    ci/<name>/pipeline.json  local-first CI pipeline definition
    ci/<name>/runs/          CI run logs + run records
"""

from .home import forge_home, validate_name

__all__ = ["forge_home", "validate_name"]
