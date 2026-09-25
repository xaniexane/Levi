"""linda — Linda coordination dialect (tuple spaces). WORKING TITLE.

Naming is Chauncey's; this name is never canon.  ``out`` / ``in`` /
``rd`` / ``eval`` as the substrate's coordination dialect: every
delegation is a tuple operation with a receipt, every wait is bounded
by the scan-cycle boundary.
"""

from .space import (
    BlackboardSpace,
    EvalTask,
    LindaFault,
    LocalSpace,
    PendingTicket,
    TupleSpace,
    match_template,
)

__all__ = [
    "BlackboardSpace",
    "EvalTask",
    "LindaFault",
    "LocalSpace",
    "PendingTicket",
    "TupleSpace",
    "match_template",
]
