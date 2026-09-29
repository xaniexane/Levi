# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""DDD daily income daemons (PROVISIONAL names throughout).

Three daemons, three runs a day (08:00/13:00/18:00 America/Chicago), every
day of the year. Each run reads its input queue, drafts income plays from
the NEXT undrafted rows, and writes them as DRAFT-labeled files into
``~/workspace/ddd-inbox/``. Nothing is ever sent, published, posted, or
charged — the drafts wait on Chauncey's word. A queue row drafted once is
never drafted again the same day.

  1. audit-daemon   — up to 3 info-only site audits/day → $49 AuditNow
                      audit drafts + outreach drafts.
  2. listing-daemon — resale/marketplace listing drafts + pricing guidance.
  3. leads-daemon   — review-reply drafts (DRAFT-labeled, never posts) +
                      lead-gen pitch drafts. Contacts nobody.

LAWS — declared in plain words, enforced in code (see base.py):
  L1 DRAFT-ONLY: every output is a local draft file, DRAFT-labeled.
  L2 NO PAYMENT: no daemon accepts, charges, or processes payment, ever.
  L3 NO OUTBOUND: send/publish/post/charge/contact shapes are refused.
  L4 HONEST ZERO-STATE: queues start empty. Empty or missing queues yield
     an honest "nothing to work" receipt. Rows are never invented.
  L5 IDEMPOTENT: one run per daemon per day. Re-runs reuse the receipt.
  L6 NAMED SITES ONLY: the audit daemon reads only URLs Chauncey himself
     put in the queue. Polite single reads, never a crawl.

NAMING: all display names are PROVISIONAL. Chauncey births every name;
final names await his word (naming sovereignty).
"""

from __future__ import annotations

__all__ = ["DAEMON_IDS"]

#: Stable daemon ids. Cron jobs and automation records use these.
DAEMON_IDS = ("audit-daemon", "listing-daemon", "leads-daemon")
