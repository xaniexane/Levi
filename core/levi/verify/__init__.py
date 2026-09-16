"""levi.verify — pre-digital verification rituals for agentic computation.

Never trust one computation path: every consequential number gets a cheap
independent proof, and a failed proof is a deny-closed receipt, never a
silent pass.

    from levi.verify import check_sum, crossfoot, dual_path, to_sigfigs

    receipt = check_sum([123, 456], 579)   # cast-out-nines proof
    receipt = crossfoot(table)             # ledger two-directional proof
    receipt = dual_path(fn_a, fn_b, x)     # two implementations must agree
    to_sigfigs(0.30000000000000004, 1)     # -> 0.3, no false precision
"""

from .checks import (
    check_product,
    check_product_elevens,
    check_product_nines,
    check_sum,
    elevens,
    nines,
)
from .bulla import append_record, verify_chain
from .crossfoot import crossfoot
from .dual import dual_path
from .trialbalance import TrialBalance, trial_balance
from .precision import (
    format_sigfigs,
    honest_report,
    sigfigs_in,
    to_sigfigs,
)
from .receipts import VerificationReceipt

__all__ = [
    "VerificationReceipt",
    "TrialBalance",
    "nines",
    "elevens",
    "check_sum",
    "check_product",
    "check_product_nines",
    "check_product_elevens",
    "crossfoot",
    "dual_path",
    "append_record",
    "verify_chain",
    "trial_balance",
    "to_sigfigs",
    "format_sigfigs",
    "sigfigs_in",
    "honest_report",
]
