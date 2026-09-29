"""plumb — LEVI's user-owned dispatch table.

Studied from: Plan 9's plumber (Rob Pike, "Plumbing and Other Utilities",
USENIX 2000). The load-bearing idea is not the 9P file server — it is the
*user-owned declarative dispatch table*: any selected text, anywhere, is
matched against the keeper's own pattern rules and routed to a destination
*port*. The giants rebuilt this closed (Android intents, iOS share sheets,
ShellExecute registries): the vendor decides which handlers exist. LEVI's
honest inversion is the table itself — the keeper writes the rules, the
keeper names the ports, nothing dispatches by default.

This is a clean-room recreation, not a port: LEVI's own rule syntax,
stdlib only, no Plan 9 code, no network. The engine returns *decisions*;
it never executes anything (see law 4).

Laws (declared here, proven in tests/test_plumb.py):
1. Deny-closed — no matching rule means no action. There is no default
   handler, no fallthrough, no "helpful" guess.
2. User-owned table — no rules ship enabled. ``default_rules()`` exists
   as an explicitly opt-in starter set, clearly labeled as such.
3. Winnow before act — every pattern must match the same winnowed
   portion of the data and every ``require`` predicate must hold before
   an action is produced. A rule never half-fires.
4. No shell, no execution — the engine returns a ``PlumbResult`` naming a
   port and a rendered action string. Ports are resolved by the caller
   through an explicit ``PortRegistry``; unregistered ports refuse.
5. First match wins — rule order is priority, and it is the keeper's
   file order, documented and inspectable.
6. Local and stdlib-only — ``re``, ``os.path``. Nothing leaves the
   machine; matching never touches the network.
"""

from __future__ import annotations

from .engine import PlumbError, PlumbResult, PortRegistry, plumb
from .rules import Rule, RuleError, default_rules, parse_rules

__all__ = [
    "PlumbError",
    "PlumbResult",
    "PortRegistry",
    "Rule",
    "RuleError",
    "default_rules",
    "parse_rules",
    "plumb",
]
