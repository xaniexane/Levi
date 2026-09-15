"""Bug-bounty recon pipeline — scoped, polite, recon-only.

Enumerates attack-surface inventory for bug-bounty programs the hunter is
enrolled in. Every network touch passes the scope gate in scope.py first:
out-of-scope targets are refused with no override. This module never
exploits anything — findings are inventory (hosts, ports, banners,
archived URLs, exposed references), never exploit results.
"""

from levi.bounty.scope import ScopeStore, ScopeError, check_scope
from levi.bounty.enum import enumerate_subdomains
from levi.bounty.probe import probe_host
from levi.bounty.content import collect_content
from levi.bounty.store import Finding, FindingStore
from levi.bounty.pipeline import run_recon, run_monitor

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
]
