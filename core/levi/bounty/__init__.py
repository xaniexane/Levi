"""Bug-bounty recon pipeline — scoped, polite, recon-only.

Enumerates attack-surface inventory for bug-bounty programs the hunter is
enrolled in. Every network touch passes the scope gate in scope.py first:
out-of-scope targets are refused with no override. This module never
exploits anything — findings are inventory (hosts, ports, banners,
archived URLs, exposed references), never exploit results.

The service-bounty hunter lives here too (hunts.py, payment.py,
showcase.py): Chauncey's bounty hunter — hunt the problem, deliver a
detailed accurate solution, secure payment through the Cybrus money
gateway, and showcase only verified, paid hunts.
"""

from __future__ import annotations

from levi.bounty.scope import ScopeStore, ScopeError, check_scope
from levi.bounty.enum import enumerate_subdomains
from levi.bounty.probe import probe_host
from levi.bounty.content import collect_content
from levi.bounty.store import Finding, FindingStore
from levi.bounty.pipeline import run_recon, run_monitor
from levi.bounty.hunts import (
    Bounty,
    BountyError,
    BountyState,
    BountyStore,
    new_bounty,
    transition,
    quote_bounty,
    sense_bounties,
)
from levi.bounty.payment import (
    MoneyRefused,
    request_payment,
    record_agreement,
    mark_delivered_for_payment,
    settle_bounty,
    payment_status,
)
from levi.bounty.showcase import (
    ShowcaseEntry,
    ShowcaseRefused,
    ShowcaseStore,
    admit,
    render as render_showcase,
)

__all__ = [
    "ScopeStore",
    "ScopeError",
    "check_scope",
    "enumerate_subdomains",
    "probe_host",
    "collect_content",
    "Finding",
    "FindingStore",
    "run_recon",
    "run_monitor",
    "Bounty",
    "BountyError",
    "BountyState",
    "BountyStore",
    "new_bounty",
    "transition",
    "quote_bounty",
    "sense_bounties",
    "MoneyRefused",
    "request_payment",
    "record_agreement",
    "mark_delivered_for_payment",
    "settle_bounty",
    "payment_status",
    "ShowcaseEntry",
    "ShowcaseRefused",
    "ShowcaseStore",
    "admit",
    "render_showcase",
]
