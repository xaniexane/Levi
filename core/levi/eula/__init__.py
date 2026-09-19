"""LEVI EULA / terms-of-service linter.

Rule-based, offline-first: scans terms text for hostile clause patterns and
explains each hit in plain language. No network, no models, stdlib only.

Example:
    from levi.eula import lint
    for finding in lint(open("terms.txt").read()):
        print(finding["severity"], finding["plain_language_flag"])
"""

from .linter import Finding, lint, lint_file, summarize
from .rules import RULES

__all__ = ["Finding", "RULES", "lint", "lint_file", "summarize"]
