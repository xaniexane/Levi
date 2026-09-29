---
skill_id: browse.agent_laws
name: Automation and Credential Laws
description: Laws 9-11 — the consequential-act protocol, acting authority per action class, and the credential crown jewels; the agent surface and credential broker rules.
risk: info
permissions: []
requires_confirmation: false
tags: [browse, laws, automation, credentials, bloodline]
version: 1.0.0
---

# Automation and Credential Laws (9–11)

Companion to `browse.eight_laws`. Laws 1–8 govern the layer; these
three govern what the layer is *allowed to do on the keeper's behalf*.
Violating one is a build-breaking defect, same as the first eight.

## 9. Consequential acts follow the organism's protocol

Every consequential act — anything that changes state on a site, spends
keeper authority, or moves credentials — runs the full sequence:

**Plan → Preview → Permission → Execute → Verify → Receipt.**

- **Plan:** the act is stated as data (action class, target,
  parameters) before anything runs. No plan, no act.
- **Preview:** the keeper sees what *would* happen — the exact form
  fields, the exact navigation, the exact credential to be filled —
  rendered from the plan, never from a guess.
- **Permission:** the keeper confirms. Confirmation is per action
  class (law 10), at act time, never ambient, never pre-authorized
  in bulk.
- **Execute:** the act runs against the capability-limited facade.
- **Verify:** the outcome is read back from the page/site and compared
  to the plan. A mismatch is a failure, not a shrug.
- **Receipt:** the whole chain is receipted — plan, preview hash,
  grant, outcome, verification result. The receipt is the proof.

Skipping a step is not an optimization. A step with no evidence is a
step that didn't happen.

## 10. Acting needs a named grant — never ambient authority

Read-only automation (browse, extract) never implies acting authority.
Acting capability is granted per **action class**, and each class is a
separate keeper decision:

- `read_page`, `extract_structured` — read-only. Covered by the
  plugin's data permissions; no per-act confirmation.
- `fill_form` — writes into fields. Confirmation per act.
- `submit_form` — sends data to the site. Confirmation per act.
- `navigate` — moves the session (follows links, submits navigation).
  Confirmation per act.
- `credential_fill` — releases a credential into a form. Confirmation
  per act, and the credential value never touches the plan, the
  preview, or the receipt — only the facade call carries it. The
  receipt records *that a fill happened*, never the secret.

There is no "act on my behalf generally" grant. Ambient authority is
refused as a concept, not just as a permission name.

Decision gate DG-8 governs whether acting classes ship enabled at all:
read-only automation first, or acting-on-behalf from day one. Until
ruled, builders implement the confirmation machinery and the
read-only classes; acting classes exist as refused-by-default stubs
naming DG-8 in the refusal.

## 11. The credential store is the crown jewels

The credential broker (`browse/credentials.py`) generates, stores, and
retrieves site/app credentials. It is the highest-value target in the
layer, so it gets the strictest claim discipline:

- **Generate:** via `cybrus/vault.py::generate_password` (stdlib
  `secrets` CSPRNG, minimum length 12, returned once, never logged).
  Never reimplemented in the browse tree — a second generator is a
  defect.
- **Store:** veil-encrypted, keeper-held keys (`cybrus/veil.py`). The
  browse layer holds no key material; it calls the binding.
- **Retrieve:** autofill through the plugin facade in the Python core
  (phase 2); Android autofill-service binding in phase 3. The secret
  travels facade-to-field only — never through plans, previews,
  receipts, or logs.
- **Claims:** graded per-mechanism only (extends
  `browse.honest_claims`). No blanket "secure password manager", no
  "military-grade", no "zero-knowledge" until a real audit exists and
  names it. The broker as a whole stays UNVERIFIED until audited,
  however strong the parts grade individually.

### Bloodline metering (the founder tap)

Per the 2026-09-27 bloodline distribution law: **unlimited credential
generation is a founder ability.** Other builds get metering hooks,
not the full tap. The hooks are designed, not noted:

- The broker's generation path calls
  `cybrus/broker_meter.py::entitlement_check` (read-only, never
  consumes quota) before minting. No entitlement → no mint, receipted
  refusal naming the missing entitlement.
- Fulfillment records meter usage via the meter ledger (M3);
  request/fulfill/deny events are audit-logged, metadata only (M5).
- A limited instance can never mint unlimited itself:
  `request_service` files a ticket (M1 NO-SELF-MINT); fulfillment
  requires a live authenticated `FounderSession` (M2
  FOUNDER-FULFILL).
- The browse layer does not reimplement any of this — it binds
  `cybrus/broker_meter.py`. A second metering implementation in the
  browse tree is a defect.

### Boundary with the cybrus broker

`cybrus/broker.py` owns the third-party credential *lifecycle*
(provisioning records, OAuth2 state machine, approval gates). The
browse broker owns the *in-layer surface*: generation for the
keeper's browsing, veil-encrypted storage, facade autofill. The agent
fills what the keeper confirmed; the broker owns the lifecycle. The
two meet at `credential_fill` and nowhere else.

## Local-only automation (the seated-AI ruling stands)

The agent surface runs on stdlib heuristics now; the keeper's native
brain plugs in later. No cloud models — not as fallback, not as
"optional enhancement." A network call to a model provider from the
agent surface is a law-3 violation (undeclared network), not a
feature flag. The brain slot is declared in `browse/agent.py` as an
UNVERIFIED-until-proven interface: honest "no brain wired" states,
never fake cognition.

## The check

Before any commit touching `browse/agent.py`,
`browse/credentials.py`, or `browse/sessions.py`: read laws 9–11
aloud against the diff, then laws 1–8. If the diff grants authority
the keeper didn't name, it does not ship.
