"""
Future integrations — brought back from 'further out' without abandoning Phase A.

Each item is actionable, HITL-compatible, and SI-aligned.
"""
from __future__ import annotations

from typing import List, Tuple

IDEAS: List[Tuple[str, str, str]] = [
    ("local_rag_ui", "Console corpus browser with cite-back", "near"),
    ("ollama_stream_ws", "Optional WebSocket stream into condensed UI", "near"),
    ("argon2_prod", "argon2-cffi required path; demo HMAC removed when present", "near"),
    ("phase_b_blob_sync", "Encrypted blob sync dry-run → real transport", "mid"),
    ("signed_skills", "Hash-pinned skill allowlist", "mid"),
    ("voice_local", "Local STT/TTS hooks behind HITL", "mid"),
    ("eval_golden_kai", "Golden transcripts per KAI register", "mid"),
    ("multi_approver", "Two-person rule for high-risk agent tools", "mid"),
    ("story_diff", "Beat-level diff for REIM forks", "near"),
    ("life_pack_v2", "Selective namespace export + verify checksum", "near"),
    ("sensor_opt_in", "Embodied optional inputs; default off", "far"),
    ("team_crucible", "Shared HITL queue for orgs", "far"),
    ("prose_bank_expand", "Per-genre sensory + supporting-cast banks ×10", "near"),
    ("calendar_local", "Local ICS awareness for morning loop", "mid"),
    ("git_mirror", "Optional git-backed ~/.levi continuity", "mid"),
]


def format_future() -> str:
    lines = [
        "══ Future integrations (course outward) ══",
        f"ideas={len(IDEAS)}",
        "Phase A stays landed. These are further planets — not requirements to be useful.",
        "",
    ]
    for i, (id_, title, horizon) in enumerate(IDEAS, 1):
        lines.append(f"{i:2}. [{horizon:4}] {id_}")
        lines.append(f"     {title}")
    lines.append("")
    lines.append("Integrate only when they strengthen SI law: local · HITL · export · non-personhood.")
    return "\n".join(lines)
