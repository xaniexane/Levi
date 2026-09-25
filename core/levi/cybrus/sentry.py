"""Cybrus silent-movement sentry — RIGHT direction (accounts + money).

Chauncey's mandate: *NOTHING moves silently.* Any account or money action
attempted outside the gateway is DENIED and logged as a violation — not
warned, not counted, denied.

Two layers:

1. **Runtime** — :class:`RightSentry`: the primitive every gated wrapper
   calls when it catches a bypass attempt. ``report_violation()`` appends
   a ``right.violation`` record to the hash-chained audit log
   (metadata only — actor, action, evidence ref) and raises
   :class:`SilentMovementDenied`. ``check_grant()`` lets a wrapper verify
   it is running under a live gateway grant; without one, the attempt is
   a violation.
2. **Static** — :func:`scan_account_verbs`: the repo scanner used by
   tests/test_cybrus_right.py. Any function definition outside
   ``core/levi/cybrus/`` whose name performs an account action
   (email/drive/github/financial/credential verbs) must either route
   through ``levi.cybrus.accounts.AccountActionGateway`` or carry an
   explicit entry in ``ACCOUNT_ACTION_ALLOWLIST`` with the honest reason.
   Silent account-action verbs are a violation the same as silent money
   verbs (see tests/test_money_law.py).

Stdlib-only, no network. Violations land in the hash-chained audit log
(``~/.levi/cybrus/audit.jsonl``; ``LEVI_HOME`` override honored).

Proof: tests/test_cybrus_right.py.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class SecurityViolation(Exception):
    """Base class for right-direction security violations."""


class SilentMovementDenied(SecurityViolation):
    """An account/money action was attempted outside the gateway.

    Denied and logged as a violation. The audit record carries the
    actor, the attempted action, and an evidence reference — never
    secrets or payloads.
    """


def _audit(event: str, actor: str, details: Optional[Dict] = None) -> Dict:
    from levi.cybrus.audit import AuditEngine

    return AuditEngine().append(event, actor, details or {})


class RightSentry:
    """Denies and logs silent account/money movement (mandate R5)."""

    def report_violation(
        self,
        actor: str,
        attempted_action: str,
        evidence: str = "",
        *,
        account_id: str = "",
    ) -> None:
        """Log a gateway-bypass attempt as a violation, then deny it.

        Always raises :class:`SilentMovementDenied` — there is no
        warn-and-continue path. The violation record is hash-chained in
        the audit log so it cannot be silently dropped later.
        """
        record = _audit(
            "right.violation",
            actor,
            {
                "attempted_action": attempted_action,
                "account_id": account_id,
                "evidence": evidence,
                "law": "NOTHING moves silently: account/money actions "
                       "route through the Cybrus gateway.",
            },
        )
        raise SilentMovementDenied(
            f"silent movement denied and logged as violation "
            f"(audit seq {record['seq']}, hash {record['hash'][:12]}): "
            f"{actor} attempted {attempted_action!r} outside the gateway. "
            f"Remedy: route it through "
            f"levi.cybrus.accounts.AccountActionGateway."
        )

    def check_grant(self, actor: str, attempted_action: str, grant) -> None:
        """Deny when a wrapper is invoked without a gateway grant.

        Wrappers that perform account actions call this first: a missing
        or ``None`` grant is a bypass attempt — denied + logged.
        """
        if grant is None:
            self.report_violation(
                actor, attempted_action,
                evidence="wrapper invoked with grant=None",
            )


# ---------------------------------------------------------------------------
# Static scanner: account-action verbs outside cybrus/
# ---------------------------------------------------------------------------

#: Function-name verbs that perform external account actions. Any ``def``
#: matching these outside ``core/levi/cybrus/`` must route through the
#: account gateway or be declared in ACCOUNT_ACTION_ALLOWLIST.
ACCOUNT_VERB_RE = re.compile(
    r"^\s*def\s+("
    r"send_mail|send_email|gmail_send|smtp_login|"
    r"drive_upload|drive_download|gdrive_|onedrive_|"
    r"github_push|github_create|gh_"
    r"plaid_sync|fetch_transactions|read_transactions|"
    r"use_credential|checkout_secret|oauth_exchange"
    r")\w*\s*\(",
    re.M,
)

#: Direct reads of the account-credential vault namespace outside
#: ``core/levi/cybrus/accounts.py`` are silent credential use (R1).
CREDENTIAL_NAMESPACE_RE = re.compile(r"cybrus\.accounts\.")


def scan_account_verbs(
    core_root: Path,
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Scan for account-action defs and credential-namespace reads outside cybrus/.

    Returns ``(verb_hits, namespace_hits)`` — each a list of
    ``(relative_path, matched_text)``. The test pins every hit to the
    allowlist; an undeclared hit fails the build.
    """
    verb_hits: List[Tuple[str, str]] = []
    namespace_hits: List[Tuple[str, str]] = []
    for path in sorted(core_root.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        rel = str(path.relative_to(core_root))
        if rel.startswith("cybrus/"):
            continue
        try:
            src = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in ACCOUNT_VERB_RE.finditer(src):
            name = m.group(0).strip().split("(")[0]
            verb_hits.append((rel, name))
        if rel != "cybrus/accounts.py" and CREDENTIAL_NAMESPACE_RE.search(src):
            namespace_hits.append((rel, "cybrus.accounts."))
    return verb_hits, namespace_hits


# Every file outside cybrus/ that defines an account-action verb, with the
# honest reason it is NOT silent movement. Additions require an explicit
# entry here — silent account verbs are a violation.
ACCOUNT_ACTION_ALLOWLIST = {
    # path relative to core/levi : reason
    "oath/daemon.py": "send_mail() is gateway-routed: requests an "
    "AccountActionGateway grant for scope email.send (human-approved) and "
    "executes the SMTP send under it. The SMTP password use is receipted "
    "via attest_credential_use (grant + metadata-only receipt, source "
    "declared; vault storage is the end state) — nothing is silent.",
}
