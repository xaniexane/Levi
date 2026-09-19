"""The PLATFORM: infrastructure that delivers the curriculum.

The course (``levi.sidewinder.curriculum``) is the training curriculum —
the content that trains agents. This package is the platform runtime that
delivers it: a clean query API, team scoping, and the team learning loop.
LEVI and agents consume the platform; the CLI is one surface today, a web
UI can be another later. Stdlib only.
"""

from __future__ import annotations
