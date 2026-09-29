# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Shared base for the DDD SI operator agents (PROVISIONAL names throughout).

LAWS — declared in plain words, enforced in code below:
  L1 DRAFT-ONLY: every output is a draft written to the local drafts dir,
     labeled DRAFT. Nothing is published, posted, sent, or contacted.
  L2 NO PAYMENT: no agent accepts, charges, or processes payment, ever.
  L3 NO OUTBOUND: any task shaped like send/publish/post/charge/pay/
     outreach/contact is refused loudly via ``refuse_outbound``.
  L4 READ-ONLY WATCH: queue scans never mutate anything. Missing queues
     yield honest zero-state — rows are never invented.
  L5 REVIEW HARD RULE: reply drafts are drafts only. The machine drafts,
     a human posts. (Carries the standing ReviewReply law.)

Machine-checkable flags: ``advisory_only=True``, ``draft_only=True``,
``outbound_actions=()``, ``allowed_wares=()`` (zero outward capability).

NAMING: all display names are PROVISIONAL. Chauncey births every name;
final names await his word (naming sovereignty).
"""

from __future__ import annotations

import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.dynasty.dna import AgentError, DynastyAgent

__all__ = ["DDDOperatorAgent", "DRAFT_BANNER", "OUTBOUND_KINDS"]

#: Banner stamped on every draft. The draft waits on Chauncey's word.
DRAFT_BANNER = (
    "**DRAFT — advisory only. Nothing here is sent, published, posted, "
    "or charged. It waits on Chauncey's word.**"
)

#: Task kinds that are refused outright (L3). Anything outbound dies here.
OUTBOUND_KINDS = frozenset(
    {
        "send",
        "publish",
        "post",
        "charge",
        "pay",
        "outreach",
        "contact",
        "remind",  # sending reminders is outbound; drafts only
        "chase",  # chasing an invoice is outbound; drafts only
    }
)

#: Where DDD queue inputs live (read-only scans).
_DDD_ROOT = Path.home() / "workspace" / "ddd"

#: Default home for draft outputs. Local files only — never outbound.
_DEFAULT_DRAFTS_DIR = _DDD_ROOT / "launch" / "drafts"

_STEM_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,60}$")


class DDDOperatorAgent(DynastyAgent):
    """Advisory-only DDD product operator. Drafts, never acts outward.

    Subclasses set the DynastyAgent class attributes and implement
    ``watch()`` (read-only queue scan) plus their draft methods.
    """

    #: L1/L2 machine flags — asserted by tests on every subclass.
    advisory_only: bool = True
    draft_only: bool = True
    #: L3 — no outbound actions exist on these agents, by construction.
    outbound_actions: tuple = ()
    #: Zero outward capability: no ware shelves open.
    allowed_wares: tuple = ()

    generation = 2
    commissioned_by = "factory-genesis"

    def __init__(
        self, home: Optional[Path] = None, drafts_dir: Optional[Path] = None
    ) -> None:
        super().__init__(home=home)
        self._drafts_dir = Path(drafts_dir) if drafts_dir else _DEFAULT_DRAFTS_DIR

    # ── L3: the outbound guard ──────────────────────────────────────
    def _guard_kind(self, kind: str) -> None:
        """Refuse any outbound-shaped task kind, loudly (L3)."""
        if str(kind).lower() in OUTBOUND_KINDS:
            raise AgentError(
                f"advisory-only: {self.agent_id} refuses outbound task "
                f"{kind!r} — drafts only, Chauncey's word required"
            )

    def refuse_outbound(self, action: str) -> None:
        """Explicit refusal entry point. Always raises (L1/L2/L3)."""
        raise AgentError(
            f"advisory-only: {self.agent_id} never {action} — "
            "drafts only, Chauncey's word required"
        )

    # ── L1: draft writing ───────────────────────────────────────────
    def save_draft(self, stem: str, text: str) -> str:
        """Write a labeled draft to the local drafts dir (L1).

        Returns the path written. The stem is sanitized and the write is
        confined to the drafts dir — it cannot escape elsewhere.
        """
        if not _STEM_RE.match(stem):
            raise AgentError(f"bad draft stem {stem!r}")
        target_dir = self._drafts_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = (target_dir / f"{stem}-{stamp}.md").resolve()
        if target_dir.resolve() not in path.parents:
            raise AgentError("draft path escapes the drafts dir — refused")
        path.write_text(f"{DRAFT_BANNER}\n\n{text.rstrip()}\n", encoding="utf-8")
        return str(path)

    # ── L4: read-only queue scans ───────────────────────────────────
    def _scan_queues(self, *patterns: str) -> List[Path]:
        """Find queue files under the DDD root. Read-only; never mutates."""
        found: List[Path] = []
        if not _DDD_ROOT.is_dir():
            return found
        for pattern in patterns:
            found.extend(p for p in _DDD_ROOT.rglob(pattern) if p.is_file())
        # De-duplicate, stable order.
        return sorted(set(found))

    def _read_rows(self, path: Path, limit: int = 200) -> List[Dict[str, str]]:
        """Read up to ``limit`` CSV rows. Any failure → [] (L4)."""
        try:
            with path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                rows = []
                for row in reader:
                    rows.append({k: (v or "") for k, v in row.items() if k})
                    if len(rows) >= limit:
                        break
                return rows
        except (OSError, csv.Error, UnicodeDecodeError):
            return []

    def _checked_at(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── default task shape ──────────────────────────────────────────
    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(task.get("kind", "watch")).lower()
        self._guard_kind(kind)
        if kind == "watch":
            return self.watch()
        raise AgentError(f"{self.agent_id}: unknown task kind {kind!r}")

    def watch(self) -> Dict[str, Any]:  # pragma: no cover - overridden
        raise NotImplementedError

    def first_task(self) -> Dict[str, Any]:
        return self.watch()
