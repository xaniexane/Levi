"""LEVI teletext — the broadcast page carousel, clean-room revived.

Ceefax (1974-2012) sent numbered text pages in an endless broadcast loop;
the dumb terminal just waited for its page to come around. No account, no
login, no request/response, no tracking.

This module is the honest inversion of the modern dashboard: LEVI's own
data rendered as numbered pages in the 40x24 Ceefax grid, cycling on a
carousel over a local stdlib HTTP server. The pages just come around.

stdlib-only, local-first. No network needed except localhost serving.
"""

from __future__ import annotations

__all__ = ["pages", "serve"]
