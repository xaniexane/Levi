# Cybrus Router — the choke-point doctrine

Cybrus is THE internal/external API router for the platform. Every
service-to-service call and every external API egress crosses Cybrus.
No product rolls its own egress. No product rolls its own auth.

## The laws (plain words)

- **L1 — Every internal call is checked.** Any service calling another
  service must prove who it is (a Cybrus credential), stay inside its
  rate-limit quota, pass the policy engine, and get audit-logged. A call
  that fails any of those never reaches the other service. When in
  doubt, the call is refused.
- **L2 — Outside traffic needs a signed grant.** Nothing in the
  platform does its own HTTP calls to the outside world. A product that
  needs an external API asks Cybrus for a routing grant
  (`request_egress`) and uses the grant. No grant, no egress.
- **L3 — Deny always wins.** If the policy engine says no, that is the
  end of it — even if a human approval exists, even if a grant was
  already issued. There is no bypass path, for anyone.
- **L4 — The audit log sees metadata only.** It records who called
  whom, what action, a payload *reference* (an id, never content), the
  decision, and the risk. It never records payloads, secrets, passwords,
  or tokens.
- **L5 — Grants expire; approvals are single-use.** A routing grant is
  bound to one actor, one destination, one purpose, and a short expiry
  (5 minutes by default). One human approval authorizes at most one call
  and mints at most one grant — it cannot be spent twice, even by two
  processes racing.

## The three pieces

| Piece | Module | Job |
|---|---|---|
| Route table | `levi.cybrus.router` | The address book. Internal services are first-class; external providers exist only as deliberate, human-approved additions. |
| Grant mint | `levi.cybrus.gateway` | `route_external` is the sole external gateway — stdlib-only, no network. It issues signed, short-lived routing grants. |
| **Choke point** | `levi.cybrus.enforce` | **This is what product code calls.** `route_service_call` gates every internal call; `request_egress` is the single sanctioned path for external egress; `@cybrus_guarded` wraps a function in one line. |

## The internal call flow

```
product code
  → route_service_call(caller, callee, action, payload_ref=...)
      1. authenticate caller   (session token / service token / API key)
      2. resolve callee        (must be an internal route; external → refused)
      3. rate-limit check      (tier quota; over-limit → refused)
      4. policy evaluate       (deny → refused, deny always wins)
      5. human approval        (only when a high-risk allow needs it)
      6. audit (metadata only) → return routing ticket
  → callee runs
```

One line on a function does the same:

```python
from levi.cybrus.enforce import cybrus_guarded

@cybrus_guarded(service="levi.jobs", callee="levi.knowledge")
def search_jobs(query, *, cybrus_credential=None):
    ...

search_jobs("cook", cybrus_credential=token)
```

The wrapper pops the `cybrus_*` kwargs, crosses the choke point, and
only then runs the body — a refused call means the body never executes.
Pass a reference, never content: `cybrus_payload_ref="job-412"` is
logged; the payload itself never is. There is deliberately no
`payload=` parameter anywhere in this module.

## The external egress flow (the only legal one)

```
product code
  → request_egress(actor, destination, purpose, credential=...)
      1. authenticate actor
      2. router resolve        (must be a REGISTERED external route;
                                unregistered → refused, internal → refused)
      3. rate-limit check
      4. policy evaluate       (deny → refused, deny always wins)
      5. human approval        (high-risk → ApprovalRequired w/ approval_id)
      6. signed short-lived grant minted by the gateway
         (bound: actor, destination, scope, expiry, purpose)
      7. audit (metadata only)
  → product hands the GRANT to its transport; Cybrus performs no HTTP
```

`request_egress` and the gateway's `route_external` share the approval
ledger (same action + details shape), so a human approval granted for
one path is consumable by the other — and single-use still holds.

Grants are validated with `CybrusGateway().validate_grant(token)`; an
unknown, revoked, or expired grant returns `None`.

## What must route through Cybrus

- **Every service-to-service call** — `levi.jobs` → `levi.knowledge`,
  `levi.king` → `levi.finance`, anything → anything. No direct imports
  that skip the choke point for cross-service work.
- **Every external API call** — no `urllib`/`requests`/`http.client`
  egress from product code, ever. Request a grant; use the grant.
- **QID-addressed internal targets** (`3.42.7.0` style) are internal by
  construction and also cross the choke point.

The gateway's bare `route_internal(target)` (no credentials) remains as
the low-level logged primitive for infrastructure that cannot present
a service credential. Product code must prefer the gated form:
`route_internal(target, caller=..., credential=...)`, `route_service_call`,
or `@cybrus_guarded`.

## Policy namespaces

- Internal calls evaluate as `(caller, "service.<route>", action)` —
  e.g. `("levi.jobs", "service.levi.knowledge", "search")`. QID targets
  evaluate as `(caller, "qid.<qid>", action)`.
- External egress evaluates as `(actor, "external.<destination>", "route")`
  — same shape the gateway has always used.

Seed policy is default-deny: with no matching rule the call is denied
at critical risk. Service owners add allow rules at the risk level the
call deserves; high-risk allows gate on a human approval.

## Credentials

- **Session token** — from `CybrusGateway().auth(identity, password)`;
  bound to the caller by its `session:<name>` label. Present as
  `credential=<token>`.
- **Service token** — a Cybrus `api`-kind token carrying the
  `service.call` scope. Present as `credential=<token>`.
- **API key** — a named vault-stored key carrying the `service.call`
  scope; the key name must equal the caller identity. Present as
  `api_key=(name, secret)` plus `gateway=CybrusGateway(vault_passphrase=...)`.

The presented credential itself is never written to any log.

## Migration notes for product code

1. Find direct cross-service calls (imports + calls into another
   organ's module, raw HTTP via `urllib`/`requests`/`http.client`).
2. Internal calls → wrap the calling function with
   `@cybrus_guarded(service="<your service>", callee="<target>")` and
   pass `cybrus_credential=` at the call site. Replace any payload
   argument that crossed with it by `cybrus_payload_ref=<id>`.
3. External calls → delete the HTTP client code; call
   `request_egress(actor, destination, purpose, credential=...)`,
   approve when `ApprovalRequired` is raised, and hand the returned
   grant token to the transport.
4. Add policy allow rules for your service's (resource, action) pairs at
   the right risk level; add the external destination with
   `RouteRegistry().add_external(...)` (a deliberate human decision,
   carrying provider, scope, approver, reason).
5. Give the service a tier of at least `starter` (`rate_limits.set_tier`)
   — free-tier callers cannot cross the choke point at all.
6. Run the choke-point tests: `pytest tests/test_cybrus_enforce.py`.

## Proof

`tests/test_cybrus_enforce.py` — invariant tests against L1–L5:
unauthenticated refused, wrong-identity token refused, over-limit
refused, deny wins even with an approval in hand, high-risk gates on a
human (and the approval is single-use), grant expiry enforced, audit
carries no payload data, the decorator routes through the choke point,
`route_internal`'s gated form crosses it too. Honestly named: these are
machine-checked invariants, not formal proofs.

## Operating laws (L6–L12) — built into the module, not just followed

Chauncey's seven operating laws are declared as laws L6–L12 in
`enforce.py`'s docstring, mirrored in the machine-readable `LAWS`
tuple, and checked by the `TestOperatingLaws` suite:

- **Keeper's law / anticipation (L6)** — every refusal names its remedy.
- **Originals-first (L7)** — nothing invented: decisions resolve
  against the registered originals; unregistered destinations are
  refused, never auto-discovered.
- **Law→guard→prove (L8)** — laws declared first, guards enforce them,
  invariant tests check them.
- **No-cancellation (L9)** — the module never removes or disables
  another organ's routes, rules, keys, or grants.
- **Nothing-thrown-away (L10)** — state only grows; audit appends,
  approvals are marked consumed, grants expire but their records stay.
- **Forward-motion (L11)** — the choke point never blocks on a human;
  gated calls raise immediately with a resumable approval id.
- **Honesty over polish (L12)** — `describe_posture()` reports the
  backend posture at runtime: no network, no deletes, no default-allow.

One organism: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
