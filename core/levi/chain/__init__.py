"""LEVI-native chain composition — compressed engines, linked.

A chain is an ordered list of :class:`Link`, each wrapping a callable
with a declared risk band. Safe links run straight through;
consequential links walk the standing rail in code::

    Plan -> Preview -> Permission -> Execute -> Verify -> Receipt

A consequential link cannot execute without a recorded permission
token, and every execution emits a receipt to an append-only,
owner-only (0600) JSONL ledger under ``<LEVI_HOME>/chain/``.

Built ON ``levi.automation.flows`` — never a duplicate of it.
"""

from .chain import (
    RAIL,
    SAFE_RAIL,
    Chain,
    ChainError,
    ChainReceipt,
    Link,
    LinkReceipt,
    PermissionToken,
    RiskBand,
    build_chain,
    chain_home,
    flow_link,
    grant,
    link,
    permissions_path,
    read_permissions,
    read_receipts,
    receipts_path,
    run_chain,
)

__all__ = [
    "RAIL",
    "SAFE_RAIL",
    "Chain",
    "ChainError",
    "ChainReceipt",
    "Link",
    "LinkReceipt",
    "PermissionToken",
    "RiskBand",
    "build_chain",
    "chain_home",
    "flow_link",
    "grant",
    "link",
    "permissions_path",
    "read_permissions",
    "read_receipts",
    "receipts_path",
    "run_chain",
]
