"""hub.social_levi_tab: LEVI as a first-class bottom-nav tab + bloodstream wiring.

The directive: X's Grok sits behind a bottom-nav tab as a chatbot; LEVI
gets the tab too — but the tab is the FRONT DOOR and LEVI is the
bloodstream, working across feed, communities, discovery, and creation
under permission gates. *The nav tab is the front door; the intelligence
is the house.*

This module is the first production milestone of that directive:

- ``TAB_DESCRIPTOR`` — the bottom-nav slot LEVI owns: id, label, icon,
  route, position. The 8-vs-12 tab MAP is OPEN (gated on Chauncey), so
  this module only claims its own slot; ``nav_slots()`` returns the
  partial map and ``TAB_MAP_STATUS`` says exactly what is unresolved.
- ``SurfaceBus`` — the registry the four surfaces (feed, communities,
  discovery, creation) subscribe to. Later milestones attach real
  surfaces; the bus exists now so presence wires in with new code only.
- ``PermissionGate`` — every cross-surface LEVI action requires the
  member's explicit grant. Fail-closed by default: no grant, no action.
  Grants persist in local JSON; no network, no ambient data use.
- ``LeviPresence`` — the bloodstream API. ``assist(surface, request)``
  runs a proposer (the draft) plus a verifier (the honest check) —
  the paired mind — and returns an advisory payload marked
  ``advisory=True``: LEVI assists, the member decides. ``ask()`` drives
  the front-door tab: a member question with a TERNARY visibility —
  ``public``, ``community``, or ``just-me`` — the third state binary
  privacy switches skip.
- ``render_tab_html()`` — the tab's HTML fragment. Safe by
  construction: user content is escaped, styling comes from
  ``hub.themes`` CSS variables (so Myspace-style theming applies to
  the LEVI tab too), no inline scripts beyond none at all.

Everything is local-first and deterministic. No network calls, no
telemetry, nothing leaves the device. Real intelligence wiring (Phase 7)
stays behind this module's permission contract.

GATED ON CHAUNCEY: the 8-vs-12 tab map; any cross-device/network
exposure; any release; Companion Schema v2 (planning only — not
implemented here, not implemented anywhere).
"""

from __future__ import annotations

import html
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from levi.hub import themes

# --------------------------------------------------------------------------
# The bottom-nav slot LEVI owns
# --------------------------------------------------------------------------

TAB_DESCRIPTOR = {
    "id": "levi",
    "label": "LEVI",
    "icon": "\u25c8",  # white diamond — distinct, text-safe, no emoji font needed
    "route": "/tab/levi",
    "position": 3,  # fourth slot; placeholder, pending the tab-map decision
    "kind": "intelligence",
}

#: The tab map as a whole is UNRESOLVED — Chauncey's call (8 vs 12 tabs).
#: This module ships only the shape of the partial map it owns.
TAB_MAP_STATUS = {
    "status": "unresolved",
    "decided_by": "Chauncey",
    "claimed_slots": [dict(TAB_DESCRIPTOR)],
    "open_question": "8-tab vs 12-tab map; slot order for non-claimed tabs",
}


def nav_slots() -> List[Dict[str, Any]]:
    """The nav slots this milestone claims: just LEVI's front door."""
    return [dict(TAB_DESCRIPTOR)]


# --------------------------------------------------------------------------
# Surfaces the bloodstream flows through
# --------------------------------------------------------------------------

#: Phase-ordered names of the four surfaces LEVI's presence covers.
#: (The surfaces themselves are built in later milestones; the bus is
#: the contract they plug into.)
SURFACES = ("feed", "communities", "discovery", "creation")


class PermissionDenied(Exception):
    """Raised when LEVI has no member grant for the requested action."""


class UnknownSurface(Exception):
    """Raised when a caller names a surface the bus does not know."""


def _data_file() -> Path:
    root = os.environ.get("LEVI_HUB_SOCIAL_DIR") or os.path.join(
        os.path.expanduser("~"), ".levi", "hub-social"
    )
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    return root_path / "levi-grants.json"


class PermissionGate:
    """Member-granted permissions for cross-surface LEVI actions.

    Fail-closed: ``check()`` is False unless the member explicitly
    granted (surface, action). Grants are stored locally; nothing syncs
    anywhere. Phase 7 adds real intelligence behind this same gate.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else _data_file()
        self._grants: Dict[str, Dict[str, Any]] = {}
        self._load()

    # -- persistence ------------------------------------------------------
    def _load(self) -> None:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._grants = data
            except (OSError, json.JSONDecodeError):
                self._grants = {}  # corrupt file: fail closed, not half-open

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._grants, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _key(surface: str, action: str) -> str:
        return f"{surface}:{action}"

    # -- grants -------------------------------------------------------------
    def grant(self, surface: str, action: str, *, note: str = "") -> None:
        if surface not in SURFACES:
            raise UnknownSurface(surface)
        self._grants[self._key(surface, action)] = {
            "surface": surface,
            "action": action,
            "note": note,
            "granted_at": time.time(),
        }
        self._save()

    def revoke(self, surface: str, action: str) -> None:
        self._grants.pop(self._key(surface, action), None)
        self._save()

    def revoke_all(self, surface: str) -> None:
        for key in [k for k in self._grants if k.startswith(surface + ":")]:
            del self._grants[key]
        self._save()

    def check(self, surface: str, action: str) -> bool:
        return self._key(surface, action) in self._grants

    def grants(self) -> List[Dict[str, Any]]:
        """The full grant ledger — the member can see and audit it."""
        return sorted(self._grants.values(), key=lambda g: (g["surface"], g["action"]))


@dataclass(frozen=True)
class Advisory:
    """One LEVI assistance turn: proposer draft + verifier check.

    The paired mind, honestly labeled: the draft is what LEVI suggests,
    the check is what could be wrong with it, and ``advisory=True`` means
    the member decides — LEVI never self-applies.
    """

    id: str
    surface: str
    request: str
    draft: str
    verifier_note: str
    advisory: bool = True
    needs_member_decision: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "surface": self.surface,
            "request": self.request,
            "draft": self.draft,
            "verifier_note": self.verifier_note,
            "advisory": self.advisory,
            "needs_member_decision": self.needs_member_decision,
            "created_at": self.created_at,
        }


def _propose(surface: str, request: str) -> str:
    """Proposer: the draft. Deterministic, offline, advisory-only."""
    return (
        f"[LEVI draft for {surface}] Working from your local context: "
        f"'{request}'. This is an offline draft — review before use."
    )


def _verify(surface: str, request: str, draft: str) -> str:
    """Verifier: the honest check on the draft. Independent of propose."""
    concerns = []
    if len(request.split()) < 3:
        concerns.append("request is vague — the draft may miss your intent")
    concerns.append("draft generated offline without your latest activity")
    return (
        "Verifier: "
        + "; ".join(concerns)
        + ". Nothing here is a decision — it only becomes one when you say so."
    )


class SurfaceBus:
    """The registry surfaces subscribe to. Later milestones attach real
    feed/community/discovery/creation handlers; the bus already enforces
    the contract: known surface, granted permission, advisory output.
    """

    def __init__(self, gate: Optional[PermissionGate] = None) -> None:
        self.gate = gate or PermissionGate()
        self._handlers: Dict[str, List[Callable[..., Any]]] = {
            surface: [] for surface in SURFACES
        }

    def subscribe(self, surface: str, handler: Callable[..., Any]) -> None:
        """Attach a surface handler (built in a later milestone)."""
        if surface not in SURFACES:
            raise UnknownSurface(surface)
        self._handlers[surface].append(handler)

    def subscribers(self, surface: str) -> List[Callable[..., Any]]:
        if surface not in SURFACES:
            raise UnknownSurface(surface)
        return list(self._handlers[surface])

    def emit(self, surface: str, event: str, payload: Dict[str, Any]) -> List[Any]:
        """Fan out to a surface's handlers. No permission needed to
        *notify*; permission is required to *act* (see LeviPresence)."""
        results = []
        for handler in self.subscribers(surface):
            results.append(handler(event, payload))
        return results


class LeviPresence:
    """The bloodstream: LEVI's advisory presence on every surface.

    Phase 7 will put real intelligence behind these methods; the shape —
    permission-gated, advisory, paired proposer/verifier — is frozen here
    so later phases can't quietly widen it.
    """

    def __init__(
        self,
        gate: Optional[PermissionGate] = None,
        bus: Optional[SurfaceBus] = None,
    ) -> None:
        self.gate = gate or PermissionGate()
        self.bus = bus or SurfaceBus(self.gate)

    def assist(self, surface: str, action: str, request: str) -> Advisory:
        """One assistance turn on one surface. Requires a member grant."""
        if surface not in SURFACES:
            raise UnknownSurface(surface)
        if not self.gate.check(surface, action):
            raise PermissionDenied(
                f"LEVI has no grant for '{action}' on '{surface}'. "
                "The member must grant it first; denial is silent and final."
            )
        draft = _propose(surface, request)
        return Advisory(
            id=f"adv-{uuid.uuid4().hex[:12]}",
            surface=surface,
            request=request,
            draft=draft,
            verifier_note=_verify(surface, request, draft),
        )

    def audit(self) -> Dict[str, Any]:
        """What LEVI is allowed to do, anywhere — auditable by the member."""
        return {"grants": self.gate.grants(), "surfaces": list(SURFACES)}


# --------------------------------------------------------------------------
# The front door: the LEVI tab itself
# --------------------------------------------------------------------------

#: Ternary visibility on every ask from the tab: the third state between
#: the binary public/private is ``community`` — visible to your circles,
#: not the whole wire and not locked in your pocket.
ASK_VISIBILITY = ("public", "community", "just-me")


def ask(
    question: str,
    visibility: str = "just-me",
    gate: Optional[PermissionGate] = None,
) -> Dict[str, Any]:
    """The front-door interaction: ask LEVI from the tab.

    The tab itself needs no grant (it's the member asking, directly).
    Visibility defaults to ``just-me`` — the safest third state — and
    must be one of the three named states; binary-only inputs are
    rejected rather than silently coerced.
    """
    if visibility not in ASK_VISIBILITY:
        raise ValueError(
            f"visibility must be one of {ASK_VISIBILITY}, not '{visibility}'"
        )
    if not question or not question.strip():
        raise ValueError("question must not be empty")
    q = question.strip()
    draft = _propose("levi-tab", q)
    return {
        "tab": TAB_DESCRIPTOR["id"],
        "question": q,
        "visibility": visibility,
        "draft": draft,
        "verifier_note": _verify("levi-tab", q, draft),
        "advisory": True,
    }


def render_tab_html(pack_css: Optional[str] = None) -> str:
    """HTML fragment for the LEVI tab. Safe by construction:

    - styling comes only from ``hub.themes`` CSS variables (the member's
      active Myspace-style pack applies here too — theming THROUGHOUT);
    - all user content is escaped at render time;
    - no inline ``<script>``: the fragment is markup + CSS classes.
    """
    css = pack_css if pack_css is not None else themes.css_variables(themes.void_pack())
    visibility_options = "".join(
        f'<option value="{v}">{html.escape(v)}</option>' for v in ASK_VISIBILITY
    )
    return f"""<style>{css}
.levi-tab{{font-family:var(--hub-font);background:var(--hub-bg);color:var(--hub-fg);border-radius:var(--hub-radius);padding:var(--hub-pad)}}
.levi-tab .card{{background:var(--hub-bg2);border:1px solid var(--hub-line);border-radius:var(--hub-radius);padding:var(--hub-pad);margin:var(--hub-pad) 0}}
.levi-tab .verifier{{color:var(--hub-dim);font-size:13px}}
.levi-tab .draft{{white-space:pre-wrap}}
.levi-tab select,.levi-tab textarea{{width:100%;background:var(--hub-bg);color:var(--hub-fg);border:1px solid var(--hub-line);border-radius:var(--hub-radius);padding:8px;font-size:15px}}
.levi-tab .pill{{display:inline-block;border:1px solid var(--hub-line);border-radius:20px;padding:2px 10px;font-size:12px;color:var(--hub-dim)}}
</style>
<section class="levi-tab" id="tab-levi" aria-label="LEVI">
  <h2>&#9672; LEVI</h2>
  <p><span class="pill">front door</span> Ask directly. LEVI assists on
  feed, communities, discovery, and creation only with your grants.</p>
  <div class="card">
    <textarea id="levi-q" rows="3" placeholder="Ask LEVI&hellip;"></textarea>
    <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
      <select id="levi-vis" aria-label="who sees this">{visibility_options}</select>
    </div>
    <p class="verifier">Visibility defaults to just-me. Grants for each
    surface are audited under the tab's permission ledger.</p>
  </div>
  <div class="card" id="levi-answer">
    <p class="verifier">Answers appear here as drafts, with the verifier's
    honest check beside them. Advisory only — you decide.</p>
  </div>
</section>
"""


def render_nav_html(extra_slots: Optional[List[Dict[str, Any]]] = None) -> str:
    """Bottom-nav HTML containing LEVI's slot. ``extra_slots`` are future
    tabs (from the gated tab-map decision); LEVI's slot is always present
    and marked as the intelligence slot.
    """
    slots = sorted(nav_slots() + list(extra_slots or []), key=lambda s: s["position"])
    buttons = []
    for slot in slots:
        marker = ' data-kind="intelligence"' if slot["id"] == "levi" else ""
        buttons.append(
            f'<button data-tab="{html.escape(slot["id"])}"{marker}>'
            f"{html.escape(slot['icon'])} {html.escape(slot['label'])}</button>"
        )
    return '<nav id="hub-bottomnav" aria-label="Hub">' + "".join(buttons) + "</nav>"
