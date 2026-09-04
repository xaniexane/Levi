"""
Ultimate path — interpenetrating synthesis for offline synthetic intelligence.

Order (hardwired): crisis soft → tone → nervous → monotropism → charter
→ core logic (alchemy/equation/chess) → atlas retrieve → mirror pressure
→ craft-aware if story → continuity snapshot.
Not a chatbot stack of prompts — one organism pass.
"""
from __future__ import annotations

from typing import Optional


def ultimate_reply(user_text: str) -> str:
    text = (user_text or "").strip()
    if not text:
        return "Say what's real. Empty input gets empty leverage."

    parts = []

    # 1 Offline companion (crisis + tone + core)
    try:
        from levi.ei.offline_companion import synthesize
        parts.append(synthesize(text))
    except Exception as e:
        parts.append(f"(companion unavailable: {e})")

    # 2 Atlas hits
    try:
        from levi.brain.corpus import Corpus
        hits = Corpus().search(text)
        if hits:
            u = hits[0]
            body = getattr(u, "text", None) or str(u)
            parts.append("\n— Offline brain —\n" + body[:320])
    except Exception:
        pass

    # 3 Mirror vetoes if pressure language
    if any(w in text.lower() for w in ("must buy", "guaranteed", "only today", "limited time")):
        try:
            from levi.lwp.mirror_cascade import MirrorCascade
            r = MirrorCascade().run(text)
            parts.append("\n— Mirror —\n" + (r.synthesis if hasattr(r, "synthesis") else str(r))[:400])
        except Exception:
            parts.append("\n— Mirror — pressure language detected; strip urgency before any offer.")

    # 4 Continuity
    try:
        from levi.runtime.continuity import ContinuityShelf
        ContinuityShelf().snapshot(last_ask=text, last_reply=(parts[0] if parts else "")[:200])
    except Exception:
        pass

    out = "\n".join(parts)
    out += "\n\n— LEVI ultimate path: local · charter-bound · HITL on consequences —"
    return out
