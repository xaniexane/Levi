"""counsel-desk — LEVI's local legal-capability intake (KFX2 LEGAL, Stage 1).

HARD BOUNDARY: this is a capability, never a law practice. It organizes and
retrieves the owner's own documents. It does not advise, does not strategize,
does not predict outcomes, and never presents itself as attorney-equivalent.
Every legal workflow terminates in a consult-a-licensed-attorney handoff;
a workflow without a named attorney reviewer is incomplete by definition.

Physics of this module:
* Everything is stdlib-only and local-first. Documents never leave the machine.
* Vault storage is 0600 files / 0700 dirs. No sync, no cloud, no exceptions.
* Intake verdicts are ternary: ACCEPT / QUARANTINE / REJECT — quarantine is
  the skipped third state between accept and reject.
* Intake runs as a paired mind: ``intake.propose_intake`` (proposer) hands a
  proposal to ``verify.verify_proposal`` (verifier); only verified proposals
  reach the vault.
* Gate registry (``gates``) names which approvals each action requires; the
  attorney handoff is the terminal gate of every legal workflow.
* The not-legal-advice wording in ``notices`` is a DRAFT — the exact language
  is gated on Chauncey's word.
"""

from levi.counsel.gates import (
    ACTIONS,
    VERDICT_ACCEPT,
    VERDICT_QUARANTINE,
    VERDICT_REJECT,
    check,
    require_attorney,
)
from levi.counsel.index import CounselIndex, Hit
from levi.counsel.intake import (
    EncryptedPDFError,
    ExtractionResult,
    OCRUnavailableError,
    UnsupportedTypeError,
    extract_text,
    propose_intake,
)
from levi.counsel.notices import (
    NOT_LEGAL_ADVICE_DRAFT,
    NOTICE_STATUS,
    handoff_seed,
)
from levi.counsel.vault import CounselVault, StoredDoc
from levi.counsel.verify import Verification, verify_proposal

__all__ = [
    "ACTIONS",
    "VERDICT_ACCEPT",
    "VERDICT_QUARANTINE",
    "VERDICT_REJECT",
    "CounselIndex",
    "CounselVault",
    "EncryptedPDFError",
    "ExtractionResult",
    "Hit",
    "NOT_LEGAL_ADVICE_DRAFT",
    "NOTICE_STATUS",
    "OCRUnavailableError",
    "StoredDoc",
    "UnsupportedTypeError",
    "Verification",
    "check",
    "extract_text",
    "handoff_seed",
    "propose_intake",
    "require_attorney",
    "verify_proposal",
]
