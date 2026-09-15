"""
HITL gates — human-controlled on consequences (pre-MVP).

Never treat silence as approval. Format approval cards for money, production,
customer data, DNS, legal, public claims, destructive ops.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone
import json
import uuid


DEFAULT_PATH = Path.home() / ".levi" / "hitl_pending.json"

# Domains that always require HITL (Easy Touch master prompt + LEVI policy)
ALWAYS_HITL = frozenset(
    {
        "money",
        "payment",
        "customer_data",
        "customer_comms",
        "domain",
        "dns",
        "production",
        "pricing",
        "advertising",
        "subscription",
        "legal",
        "public_claim",
        "destructive",
        "business_policy",
        "opportunity_rail",
        "core_source",
        "daemon_execute",
        "customer_contact",
    }
)


@dataclass
class HITLRequest:
    id: str
    what: str
    why: str
    changes: str
    cost: str = "$0"
    risk: str = "LOW"  # LOW | MEDIUM | HIGH
    benefit: str = ""
    if_approved: str = ""
    if_denied: str = ""
    domain: str = "general"
    status: str = "pending"  # pending | approved | denied | edited
    decision_note: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    decided_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "HITLRequest":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})  # type: ignore

    def format_card(self) -> str:
        return "\n".join(
            [
                "════════ HUMAN APPROVAL REQUIRED ════════",
                f"ID: {self.id}",
                f"Domain: {self.domain}  Risk: {self.risk}  Cost: {self.cost}",
                "",
                f"What I want to do:\n  {self.what}",
                f"Why:\n  {self.why}",
                f"What changes:\n  {self.changes}",
                f"Potential benefit:\n  {self.benefit or '—'}",
                f"If approved:\n  {self.if_approved or '—'}",
                f"If denied:\n  {self.if_denied or '—'}",
                "",
                "Choose: APPROVE | DENY | EDIT | PROVIDE INFO",
                "Silence is NOT approval.",
                "══════════════════════════════════════════",
            ]
        )


class HITLGate:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT_PATH
        self.pending: Dict[str, HITLRequest] = {}
        self.history: List[HITLRequest] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.pending = {
                k: HITLRequest.from_dict(v)
                for k, v in (raw.get("pending") or {}).items()
            }
            self.history = [
                HITLRequest.from_dict(x) for x in (raw.get("history") or [])
            ][-100:]
        except Exception:
            pass

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pending": {k: v.to_dict() for k, v in self.pending.items()},
            "history": [h.to_dict() for h in self.history[-100:]],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def requires_hitl(domain: str, risk: str = "LOW") -> bool:
        d = (domain or "").lower().replace(" ", "_")
        if d in ALWAYS_HITL or any(x in d for x in ALWAYS_HITL):
            return True
        return (risk or "").upper() in ("MEDIUM", "HIGH", "CRITICAL")

    def propose(
        self,
        what: str,
        why: str,
        changes: str,
        cost: str = "$0",
        risk: str = "LOW",
        benefit: str = "",
        if_approved: str = "",
        if_denied: str = "",
        domain: str = "general",
    ) -> HITLRequest:
        req = HITLRequest(
            id=str(uuid.uuid4())[:8],
            what=what,
            why=why,
            changes=changes,
            cost=cost,
            risk=risk.upper(),
            benefit=benefit,
            if_approved=if_approved,
            if_denied=if_denied,
            domain=domain,
        )
        self.pending[req.id] = req
        self._persist()
        return req

    def decide(self, req_id: str, decision: str, note: str = "") -> HITLRequest:
        req = self.pending.get(req_id)
        if not req:
            raise KeyError(f"No pending HITL request {req_id}")
        decision = decision.lower().strip()
        if decision in ("approve", "approved", "yes"):
            req.status = "approved"
        elif decision in ("deny", "denied", "no"):
            req.status = "denied"
        else:
            req.status = "edited"
        req.decision_note = note
        req.decided_at = datetime.now(timezone.utc).isoformat()
        self.history.append(req)
        del self.pending[req_id]
        self._persist()
        return req

    def get(self, req_id: str):
        if req_id in self.pending:
            return self.pending[req_id]
        for h in self.history:
            if h.id == req_id:
                return h
        return None

    def list_pending(self) -> List[HITLRequest]:
        return list(self.pending.values())

    def format_pending(self) -> str:
        items = self.list_pending()
        if not items:
            return "No pending HITL requests."
        return "\n\n".join(r.format_card() for r in items)
