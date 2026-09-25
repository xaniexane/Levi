"""Legion service operations over Cybrus — Wren + Sidewinder.

Routes both services' operations through Cybrus: job inputs and results
travel as sealed Veil envelopes (attested, replay-protected); every
operation crosses the choke point (``levi.cybrus.enforce``)
authenticated, rate-limited, policy-checked, and audit-logged;
money-intent jobs stay fail-closed; twin verification runs over the
wire; every run leaves the audit trail. The personas' public surface
is untouched — transport lives behind the Operator contract, and no
Veil/Cybrus mechanics leak into user-visible text.

LAWS (binding — what must always hold; the proof gate is
tests/test_legion_cybrus_ops.py, honestly named — machine-checked,
nothing formally proven):
  O1  Every operation (submit/run/verify/receipt) crosses the choke
      point authenticated, rate-limited, policy-checked, and
      audit-logged. An unauthenticated or policy-denied operation
      NEVER executes — fail closed.
  O2  Job inputs and results travel sealed over Veil. The audit log
      carries metadata only (ids, tickets, refs, decisions) — never
      job content, never secrets.
  O3  Twin verification runs over the wire: the verifier opens the
      primary's sealed output envelope (attestation + replay checked),
      verifies independently, and seals its verdict back. A job with
      no VERIFIED verdict never ships — no agent ships alone, even
      over the wire.
  O4  Money-intent jobs route to the money path and fail closed: this
      bus plans nothing and moves nothing without a registered rail
      AND explicit keeper authorization — refusal names the remedy.
  O5  No Veil (absent) -> honest local fallback labeled
      ``local-unsealed``; the bus never claims sealed transport it
      did not provide. A *locked* Veil refuses construction outright
      (fail closed — a deliberately locked vault is not consent to
      run unsealed).
  O6  Nothing is invented: routes, policy rules, tiers, tokens, and
      device identities resolve against the registered originals
      (RouteRegistry, policy store, tiers store, token store, Veil
      device registry). No default-allow anywhere.
  O7  The personas' public prose is untouched by this module.

Stdlib only. No network (Cybrus performs none; neither does this).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping, Optional

from levi.cybrus.audit import AuditEngine
from levi.cybrus.enforce import route_service_call
from levi.cybrus.money import MoneyRefused
from levi.cybrus.policy import PolicyEngine
from levi.cybrus.rate_limits import set_tier
from levi.cybrus.router import RouteRegistry
from levi.cybrus.tokens import TokenEngine
from levi.cybrus.veil import Veil, VeilError

from .registry import SERVICE_SEATS, SERVICE_TWINS_CONFIG

__all__ = [
    "SERVICE_ROUTES",
    "TRANSPORT_LOCAL",
    "TRANSPORT_SEALED",
    "JobNotShipped",
    "ServiceBusError",
    "ServiceJob",
    "CybrusServiceBus",
    "new_job",
]

#: Seat -> first-class internal Cybrus route. Registered via
#: RouteRegistry.register_internal at provision time (the sanctioned
#: extension path — Cybrus's own INTERNAL_ROUTES constant is untouched).
SERVICE_ROUTES: Dict[str, str] = {
    "service.dev-lift": "levi.service.dev-lift",
    "service.goal-line": "levi.service.goal-line",
}

#: The choke-point tier service identities run at. Explicit and
#: registered (tiers store) — never the founder/admin exemption.
SERVICE_TIER = "starter"

TRANSPORT_SEALED = "veil-sealed"
TRANSPORT_LOCAL = "local-unsealed"

_VERIFIED = "VERIFIED"
_CHALLENGED = "CHALLENGED"


class ServiceBusError(Exception):
    """Bus failures: unknown seats, missing envelopes, bad verifier
    output, locked vaults. Fail-closed by construction."""


class JobNotShipped(ServiceBusError):
    """The twin verifier did not return VERIFIED — the job's output
    never ships. Carries the verdict."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _ref(obj: Any) -> str:
    """Content reference (sha256) — what the audit log is allowed to
    carry (O2: metadata only, never content)."""
    return hashlib.sha256(_canonical(obj)).hexdigest()


def _check_job_id(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ServiceBusError("job_id must be a non-empty string")
    if len(value) > 64 or not all(c.isalnum() or c in "._-" for c in value):
        raise ServiceBusError(
            "job_id must be 1-64 chars of [A-Za-z0-9._-] (Veil-safe)"
        )
    return value


@dataclass(frozen=True)
class ServiceJob:
    """One unit of service work. ``input`` travels sealed over Veil;
    it never enters the audit log (O2)."""

    job_id: str
    seat: str  # "service.dev-lift" | "service.goal-line"
    action: str
    input: Mapping[str, Any]
    money_intent: bool = False
    requester: str = "keeper"


def new_job(
    seat: str,
    action: str,
    input: Mapping[str, Any],
    *,
    money_intent: bool = False,
    requester: str = "keeper",
    job_id: Optional[str] = None,
) -> ServiceJob:
    """Build a job. Unknown seats are refused here, not at the wire."""
    if seat not in SERVICE_ROUTES:
        raise ServiceBusError(
            f"unknown seat {seat!r}; must be one of {sorted(SERVICE_ROUTES)}"
        )
    if not isinstance(input, Mapping) or not isinstance(action, str) or not action:
        raise ServiceBusError("job needs a non-empty action and a mapping input")
    return ServiceJob(
        job_id=_check_job_id(job_id or uuid.uuid4().hex),
        seat=seat,
        action=action,
        input=dict(input),
        money_intent=bool(money_intent),
        requester=requester,
    )


#: Process-wide cache of minted service tokens (label -> plaintext),
#: validated before reuse so bus constructions don't bloat the token
#: store. Plaintext lives in memory only — never logged, never written.
_TOKEN_CACHE: Dict[str, str] = {}


def _service_token(label: str) -> str:
    engine = TokenEngine()
    old = _TOKEN_CACHE.get(label)
    if old is not None and engine.validate(old) is not None:
        return old
    _token_id, plaintext = engine.issue(
        scopes=["service.call"], label=label, kind="api"
    )
    _TOKEN_CACHE[label] = plaintext
    return plaintext


class CybrusServiceBus:
    """Service operations over Cybrus for the Wave 1 service seats.

    ``veil`` is injected by the caller (the keeper unlocks it — the bus
    never sees a passphrase). ``veil=None`` selects the honest local
    fallback (O5); a *locked* Veil refuses construction (O5).
    """

    def __init__(
        self,
        *,
        veil: Optional[Veil] = None,
        twins_config: Optional[Dict] = None,
    ) -> None:
        if veil is not None and veil.is_locked:
            raise ServiceBusError(
                "veil is locked — unlock it before constructing the bus; "
                "a deliberately locked vault is not consent to run unsealed"
            )
        self._veil = veil
        self._twins = twins_config or SERVICE_TWINS_CONFIG
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self.provisioned = self.provision()

    # -- provisioning (idempotent) --------------------------------------

    def provision(self) -> Dict[str, Any]:
        """Register routes, policy rules, tiers, and Veil devices.

        Idempotent: re-running adds nothing twice. Everything lands in
        the registered originals (O6) — never invented, never bypassed.
        """
        added: Dict[str, Any] = {
            "routes": [],
            "rules": [],
            "tiers": [],
            "devices": [],
        }
        routes = RouteRegistry()
        for seat, route in SERVICE_ROUTES.items():
            routes.register_internal(
                route, f"Legion service seat {seat} (Wren/Sidewinder ops)"
            )
            added["routes"].append(route)

        policy = PolicyEngine()
        existing = {
            (r["subject"], r["resource"], r["action"], r["effect"])
            for r in policy.list_rules()
        }
        for seat, persona in SERVICE_SEATS.items():
            # _policy_resource() in enforce.py builds
            # "service.<route>" for named internal routes.
            resource = f"service.{SERVICE_ROUTES[seat]}"
            key = (persona, resource, "*", "allow")
            if key not in existing:
                policy.add_rule(persona, resource, "*", "allow", "medium")
                added["rules"].append(
                    {"subject": persona, "resource": resource, "risk": "medium"}
                )
            set_tier(persona, SERVICE_TIER)
            added["tiers"].append({persona: SERVICE_TIER})

        # O3 ("no agent ships alone"): the twin verifier must cross the
        # choke point to verify on the primary's seat. Narrowest rule
        # possible — action-scoped to job.verify only.
        twins = (self._twins.get("twins") or {}).get("seats") or {}
        for seat, route in SERVICE_ROUTES.items():
            verifier = (twins.get(seat) or {}).get("verifier")
            if not verifier:
                continue
            resource = f"service.{route}"
            key = (verifier, resource, "job.verify", "allow")
            if key not in existing:
                policy.add_rule(verifier, resource, "job.verify", "allow", "medium")
                added["rules"].append(
                    {
                        "subject": verifier,
                        "resource": resource,
                        "action": "job.verify",
                        "risk": "medium",
                    }
                )

        if self._veil is not None:
            for persona in SERVICE_SEATS.values():
                name = f"{persona}-svc"
                try:
                    self._veil.create_device(name)
                    added["devices"].append(name)
                except VeilError:
                    pass  # already registered — idempotent

        self._audit(
            "svc.bus.provisioned",
            "cybrus-ops",
            {
                "routes": added["routes"],
                "rules": added["rules"],
                "tiers": added["tiers"],
                "devices": added["devices"],
                "transport": self._transport(),
            },
        )
        return added

    # -- internals --------------------------------------------------------

    def _transport(self) -> str:
        return TRANSPORT_SEALED if self._veil is not None else TRANSPORT_LOCAL

    def _audit(self, event: str, actor: str, details: Dict[str, Any]) -> Dict:
        # O2: details are metadata only — callers pass ids/refs/tickets,
        # never job content or secrets.
        return AuditEngine().append(event, actor, details)

    def _twin(self, seat: str) -> tuple:
        seats = (self._twins.get("twins") or {}).get("seats") or {}
        spec = seats.get(seat) or {}
        primary, verifier = spec.get("primary"), spec.get("verifier")
        if not primary or not verifier:
            raise ServiceBusError(f"no twin configured for seat {seat!r}")
        return primary, verifier

    def _device_id(self, persona: str) -> str:
        """Veil device id for a service persona. Same-organism access to
        the device registry (metadata, not key material)."""
        assert self._veil is not None
        name = f"{persona}-svc"
        for did, rec in self._veil._read_devices().items():
            if rec.get("name") == name:
                return did
        raise ServiceBusError(
            f"no Veil device {name!r} — provision the bus first"
        )

    def _conversation(self, job_id: str) -> str:
        return f"svc-{job_id}"

    def _choke(
        self,
        persona: str,
        seat: str,
        action: str,
        payload_ref: str,
        credential: Optional[str] = None,
    ) -> Dict:
        """One authenticated crossing of the choke point (O1).

        Raises NotAuthenticated / RateLimitDenied / CallDenied /
        ApprovalRequired — a refused call never reaches the work.
        """
        return route_service_call(
            persona,
            SERVICE_ROUTES[seat],
            action,
            payload_ref=payload_ref,
            credential=credential or _service_token(f"svc:{persona}"),
        )

    def _require_job(self, job_id: str) -> Dict[str, Any]:
        try:
            return self._jobs[_check_job_id(job_id)]
        except KeyError:
            raise ServiceBusError(f"unknown job {job_id!r}") from None

    def _seal(
        self, job_id: str, sender: str, recipient: str, payload: Dict
    ) -> Dict[str, Any]:
        """Seal + store one envelope. Returns envelope metadata
        (never the plaintext)."""
        assert self._veil is not None
        envelope = self._veil.seal_message(
            self._conversation(job_id),
            self._device_id(sender),
            self._device_id(recipient),
            _canonical(payload),
        )
        self._veil.store_envelope(envelope)
        return {"message_id": envelope["message_id"], "seq": envelope["seq"]}

    def _refuse_money(self, job: ServiceJob, primary: str) -> None:
        """O4: money-intent jobs fail closed. The bus never calls
        MoneyGateway.execute — movement needs a registered rail AND
        explicit keeper authorization, neither of which this bus holds.
        The refusal names the remedy (keeper's law / anticipation)."""
        reason = (
            "money-intent job refused: this bus never moves money without "
            "a registered rail AND explicit keeper authorization. Remedy: "
            "MoneyGateway().register_rail(...) then authorize explicitly "
            "with MoneyAuthorization(plan_id=..., authorized_by=<keeper "
            "identity>), then resubmit."
        )
        self._audit(
            "svc.job.money_refused",
            primary,
            {"job_id": job.job_id, "seat": job.seat, "reason": reason},
        )
        raise MoneyRefused(reason)

    # -- job lifecycle ----------------------------------------------------

    def submit(self, job: ServiceJob, *, credential: Optional[str] = None) -> Dict:
        """Submit a job: choke-point auth first (O1), money guard (O4),
        then the sealed input envelope over Veil (O2)."""
        primary, verifier = self._twin(job.seat)
        ticket = self._choke(primary, job.seat, f"job.submit:{job.action}", job.job_id, credential)
        if job.money_intent:
            self._refuse_money(job, primary)  # raises MoneyRefused
        transport = self._transport()
        envelope_id = None
        if self._veil is not None:
            meta = self._seal(
                job.job_id,
                primary,
                verifier,
                {
                    "kind": "job.input",
                    "job_id": job.job_id,
                    "seat": job.seat,
                    "action": job.action,
                    "input": job.input,
                    "ts": _utcnow(),
                },
            )
            envelope_id = meta["message_id"]
        self._jobs[job.job_id] = {
            "job": job,
            "primary": primary,
            "verifier": verifier,
            "transport": transport,
            "input_envelope_id": envelope_id,
            "input": dict(job.input),
            "phases": [
                {
                    "phase": "submitted",
                    "ts": _utcnow(),
                    "ticket": ticket["ticket"][:8],
                    "transport": transport,
                }
            ],
        }
        self._audit(
            "svc.job.submitted",
            primary,
            {
                "job_id": job.job_id,
                "seat": job.seat,
                "action": job.action,
                "ticket": ticket["ticket"][:8],
                "transport": transport,
                "envelope_id": envelope_id,
            },
        )
        return {
            "job_id": job.job_id,
            "ticket": ticket["ticket"],
            "transport": transport,
            "envelope_id": envelope_id,
            "primary": primary,
            "verifier": verifier,
        }

    def run_primary(
        self,
        job_id: str,
        worker: Callable[[Dict[str, Any]], Dict[str, Any]],
        *,
        credential: Optional[str] = None,
    ) -> Dict:
        """Run the primary's work and seal the output envelope.

        ``worker`` maps the job input to a JSON-serializable output
        dict. The output travels sealed to the verifier (O2); the
        audit carries only its content ref.
        """
        rec = self._require_job(job_id)
        job, primary, verifier = rec["job"], rec["primary"], rec["verifier"]
        ticket = self._choke(primary, job.seat, "job.run", job_id, credential)
        output = worker(dict(rec["input"]))
        if not isinstance(output, dict):
            raise ServiceBusError("worker must return a dict")
        json.dumps(output)  # JSON-serializable, or fail here loudly
        output_ref = _ref(output)
        transport = self._transport()
        envelope_id = None
        if self._veil is not None:
            meta = self._seal(
                job_id,
                primary,
                verifier,
                {
                    "kind": "job.output",
                    "job_id": job_id,
                    "output": output,
                    "output_ref": output_ref,
                    "ts": _utcnow(),
                },
            )
            envelope_id = meta["message_id"]
        rec["output"] = output
        rec["output_ref"] = output_ref
        rec["output_envelope_id"] = envelope_id
        rec["phases"].append(
            {
                "phase": "output_sealed",
                "ts": _utcnow(),
                "ticket": ticket["ticket"][:8],
                "transport": transport,
            }
        )
        self._audit(
            "svc.job.output_sealed",
            primary,
            {
                "job_id": job_id,
                "output_ref": output_ref,
                "ticket": ticket["ticket"][:8],
                "transport": transport,
                "envelope_id": envelope_id,
            },
        )
        return {
            "job_id": job_id,
            "output_ref": output_ref,
            "transport": transport,
            "envelope_id": envelope_id,
        }

    def verify(
        self,
        job_id: str,
        verifier_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        *,
        credential: Optional[str] = None,
    ) -> Dict:
        """Twin verification over the wire (O3).

        The verifier authenticates as itself, opens the primary's
        sealed output envelope (Veil checks attestation + replay),
        runs ``verifier_fn`` over the output, and seals its verdict
        back. Only VERIFIED ships; anything else raises
        :class:`JobNotShipped`.
        """
        rec = self._require_job(job_id)
        job, primary, verifier = rec["job"], rec["primary"], rec["verifier"]
        if "output" not in rec:
            raise ServiceBusError(f"job {job_id!r} has no primary output to verify")
        ticket = self._choke(verifier, job.seat, "job.verify", job_id, credential)
        output = rec["output"]
        transport = self._transport()
        if self._veil is not None:
            envelope = self._find_envelope(job_id, rec["output_envelope_id"])
            opened = self._veil.open_message(envelope)  # attestation + replay
            if opened["sender"] != self._device_id(primary):
                raise ServiceBusError("output envelope not from the primary device")
            if opened["recipient"] != self._device_id(verifier):
                raise ServiceBusError("output envelope not addressed to the verifier")
            body = json.loads(opened["plaintext"].decode("utf-8"))
            if body.get("output_ref") != rec["output_ref"]:
                raise ServiceBusError("output ref mismatch on the wire")
            output = body["output"]
        verdict = verifier_fn(dict(output))
        if not isinstance(verdict, dict) or verdict.get("verdict") not in (
            _VERIFIED,
            _CHALLENGED,
        ):
            raise ServiceBusError(
                "verifier_fn must return {'verdict': 'VERIFIED'|'CHALLENGED', ...}"
            )
        envelope_id = None
        if self._veil is not None:
            meta = self._seal(
                job_id,
                verifier,
                primary,
                {
                    "kind": "job.verdict",
                    "job_id": job_id,
                    "verdict": verdict,
                    "ts": _utcnow(),
                },
            )
            envelope_id = meta["message_id"]
        rec["phases"].append(
            {
                "phase": "verified",
                "ts": _utcnow(),
                "ticket": ticket["ticket"][:8],
                "transport": transport,
                "verdict": verdict["verdict"],
            }
        )
        self._audit(
            "svc.job.verified",
            verifier,
            {
                "job_id": job_id,
                "verdict": verdict["verdict"],
                "ticket": ticket["ticket"][:8],
                "transport": transport,
                "envelope_id": envelope_id,
            },
        )
        if verdict["verdict"] != _VERIFIED:
            self._audit(
                "svc.job.not_shipped",
                verifier,
                {
                    "job_id": job_id,
                    "verdict": verdict["verdict"],
                    "reason": str(verdict.get("reason", ""))[:280],
                },
            )
            raise JobNotShipped(
                f"job {job_id!r} not shipped: verifier returned "
                f"{verdict['verdict']} ({verdict.get('reason', 'no reason given')})"
            )
        rec["verdict"] = verdict
        rec["shipped"] = True
        return {"job_id": job_id, "verdict": _VERIFIED, "transport": transport}

    def _find_envelope(self, job_id: str, message_id: Optional[str]) -> Dict:
        assert self._veil is not None
        for envelope in self._veil.fetch_envelopes(self._conversation(job_id)):
            if envelope.get("message_id") == message_id:
                return envelope
        raise ServiceBusError(
            f"envelope {message_id!r} missing from the wire store for job {job_id!r}"
        )

    def run_persona(
        self,
        job_id: str,
        persona_name: str,
        registry,
        prompt: str,
        *,
        credential: Optional[str] = None,
        tools: Optional[list] = None,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Run a registered service persona as the primary worker.

        The persona's step (persona prompt + backing brain) becomes the
        job's output; the output still travels sealed and still faces
        the twin verifier. Public surface unchanged (O7).
        """
        from levi.operator.contract import OperatorMessage

        persona = registry.resolve(persona_name)
        messages = [OperatorMessage(role="user", content=prompt)]

        def worker(job_input: Dict[str, Any]) -> Dict[str, Any]:
            ctx = dict(context or {})
            ctx["job_input"] = job_input
            result = persona.step(messages, tools or [], ctx)
            return {
                "text": result.text or "",
                "finish_reason": result.finish_reason,
                "note": result.note or "",
            }

        return self.run_primary(job_id, worker, credential=credential)

    def receipt(self, job_id: str) -> Dict:
        """Audit-backed receipt for a job: every phase crossed the
        choke point; inputs/results traveled sealed (or honestly
        labeled local-unsealed)."""
        rec = self._require_job(job_id)
        job = rec["job"]
        return {
            "job_id": job_id,
            "seat": job.seat,
            "action": job.action,
            "primary": rec["primary"],
            "verifier": rec["verifier"],
            "transport": rec["transport"],
            "phases": [dict(p) for p in rec["phases"]],
            "output_ref": rec.get("output_ref"),
            "verdict": (rec.get("verdict") or {}).get("verdict"),
            "shipped": rec.get("shipped", False),
            "note": (
                "inputs/results traveled sealed over Veil; every phase "
                "crossed the Cybrus choke point authenticated"
                if rec["transport"] == TRANSPORT_SEALED
                else "ran WITHOUT Veil — transport local-unsealed, "
                "labeled honestly; no sealed-transport claim is made"
            ),
        }

    def describe_posture(self) -> Dict:
        """Honest backend posture (O5/O7: honesty over polish)."""
        return {
            "bus": "levi.legion.operators.cybrus_ops.CybrusServiceBus",
            "laws": ["O1", "O2", "O3", "O4", "O5", "O6", "O7"],
            "transport": self._transport(),
            "routes": dict(SERVICE_ROUTES),
            "service_tier": SERVICE_TIER,
            "money": (
                "fail-closed: money-intent jobs are refused with a named "
                "remedy; the bus never calls MoneyGateway.execute"
            ),
            "audit": "metadata only — job content never enters the audit log",
            "deletes_data": False,
            "persona_surface": "unchanged — no Veil/Cybrus mechanics in user-visible text",
        }
