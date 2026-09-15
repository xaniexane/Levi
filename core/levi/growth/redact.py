"""Redaction gate for cloud-sourced growth experiences.

Runs BEFORE reflection: cloud API sessions belong to other users, so
nothing from them may reach reflection, memory, or the journal in a
form that could leak secrets or identify anyone.

What the gate does:

* scrubs secrets and credential-like strings (API keys, tokens,
  ``password=`` assignments, …),
* scrubs PII-shaped text (emails, phone numbers, card/SSN-like digit
  runs),
* keeps the *structure* of the experience (who said what kind of
  thing, which tools ran) while removing the private payload.

What the gate does NOT promise (residual risk, stated plainly in
``docs/CLOUD_API.md``): regex scrubbing is heuristic. A secret phrased
in an unusual way, or PII embedded in prose the patterns miss, can
slip through. The gate reduces exposure; it is not a proof of
absence. Keys can opt out entirely (``--no-learn``), which skips
ingestion before any of this runs.
"""

from __future__ import annotations

import re

from levi.growth.experience import Experience


# -- scrub patterns ----------------------------------------------------------

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(
    r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\d)"
)
_SECRET_TOKENS = re.compile(
    r"(levi_sk_[A-Za-z0-9_\-]+|sk-[A-Za-z0-9]{8,}|sk-ant-[A-Za-z0-9\-_]{8,}|"
    r"ghp_[A-Za-z0-9]+|gho_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+|"
    r"AKIA[0-9A-Z]{16}|xox[bap]-[A-Za-z0-9\-]+|hf_[A-Za-z0-9]+|"
    r"AIza[0-9A-Za-z\-_]{20,})"
)
_CREDENTIAL_ASSIGN = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|auth[_-]?token|"
    r"access[_-]?token|client[_-]?secret)\b\s*[:=]\s*\S+"
)
_CARD_RUN = re.compile(r"(?<!\d)\d{13,19}(?!\d)")
_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")

_WS = re.compile(r"\s+")


def redact_text(text: str) -> str:
    """Scrub secrets/PII from ``text``. Best-effort, never total."""
    text = _CREDENTIAL_ASSIGN.sub(
        lambda m: m.group(0).split(":", 1)[0].split("=", 1)[0] + "=[redacted]", text
    )
    text = _SECRET_TOKENS.sub("[secret redacted]", text)
    text = _EMAIL.sub("[email redacted]", text)
    text = _PHONE.sub("[phone redacted]", text)
    text = _SSN.sub("[id redacted]", text)
    text = _CARD_RUN.sub("[digits redacted]", text)
    return text


def _generalize_user_content(text: str, limit: int = 160) -> str:
    """User speech from another user's session is private by default.

    Keep a short scrubbed prefix so *patterns* (corrections, thanks)
    survive, but drop the payload. The reflection engine only needs
    the pattern class, never the user's words.
    """
    text = _WS.sub(" ", (text or "").strip())
    return redact_text(text)[:limit]


def redact_cloud_experiences(experiences: list[Experience]) -> list[Experience]:
    """Apply the redaction gate to cloud experiences.

    Returns new :class:`Experience` objects; the input list is not
    mutated. Every returned experience carries
    ``meta["redacted"] = True`` and ``meta["origin"] = "cloud"``.
    """
    out: list[Experience] = []
    for exp in experiences:
        meta = dict(exp.meta or {})
        meta["origin"] = "cloud"
        meta["redacted"] = True
        if exp.kind == "user-said":
            content = _generalize_user_content(exp.content)
        elif exp.kind == "distilled":
            # Summaries can embed user content verbatim; keep a stub.
            content = "[conversation summary — payload withheld]"
            meta["summary_withheld"] = True
        else:
            content = redact_text(_WS.sub(" ", (exp.content or "").strip()))[:1200]
        out.append(
            Experience(
                id=exp.id,
                kind=exp.kind,
                source=exp.source,
                ts=exp.ts,
                content=content,
                meta=meta,
            )
        )
    return out
