---
skill_id: browse.deny_closed_default
name: Deny-Closed Default
description: The browse layer's default posture — undeclared means refused, everywhere, with a receipt.
risk: info
permissions: []
requires_confirmation: false
tags: [browse, deny-closed, permissions, defaults]
version: 1.0.0
---

# Deny-Closed Default

The browse layer is deny-closed at every boundary. This playbook states
the default once so no builder re-derives it per module.

## Where deny-closed applies

- **Plugins:** undeclared capability use is refused at the execution
  boundary. The plugin never sees an error it can swallow into a retry
  loop — the call fails closed with a receipted denial.
- **Permissions:** no grant, no load. A plugin loads only after the
  keeper grants *every* permission it declares. Partial grants do not
  partially load.
- **Network:** hosts not declared are unreachable. There is no
  allowlist-plus-exception mechanism.
- **Claims:** the default grade is UNVERIFIED. Nothing is OBSERVED until
  a named observation exists; nothing is INFERRED until a named
  heuristic ran.
- **Registration:** a `BROWSE_PLUGIN` declaration missing its who-pays
  card, naming an unknown permission, or declaring an unconfirmable
  write op is refused. Registration never warns-and-continues.
- **Acting:** no named action-class grant, no act. Acting classes
  default refused (DG-8) — the burden of proof is on enabling action,
  never on the refusal.
- **Credentials:** no entitlement, no mint. The generation path
  checks `entitlement_check` before `generate_password`; a missing
  entitlement is a receipted refusal, not a fallback.
- **Sync:** the no-cloud path is the default; the cloud path is the
  opt-in footnote. Defaults are policy.

## What deny-closed is not

- Not a firewall rule list. It is a posture: the burden of proof is on
  the action, never on the refusal.
- Not "ask the user every time." Keeper grants carry scope and expiry;
  confirmation is per write op at call time. The ledger remembers so
  the user is not nagged.
- Not silent. Every refusal is receipted — who asked, what was asked,
  what was refused, when. A refusal nobody can audit is theater.

## The test

For every boundary you build, write the refusal test first: the
undeclared call, the missing grant, the unknown host, the absent card.
If the refusal path is untested, the boundary is unverified.
