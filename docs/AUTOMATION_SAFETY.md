# LEVI Automation Safety

Binding safety rules for everything under `core/levi/automation/`.
Automation in LEVI is **offline-first, local, and human-gated**: LEVI
plans and assists; the user (or an explicit human confirmation) acts.

## The one boundary

`core/levi/automation/` **plans** automation and emits helper scripts.
It never drives a browser, device, or account on its own. Execution is
always the user's action (Termux / CDP / device) or a HITL-gated step.
Any module that crossed this line would be a bug, not a feature.

## Safety matrix

| Band | Actions | Gate |
|---|---|---|
| 🟢 Green | clipboard read, share-sheet receive, file watch (user-chosen dirs), local HTTP on 127.0.0.1, notifications, snapshots, QR handoff, workflow templates, backup runner | none — user-initiated |
| 🟡 Yellow | CDP evaluate, non-auth form fill, OCR of user-supplied images, Termux catalog scripts, n8n skeletons (described) | HITL confirmation before each run |
| 🔴 Red | login, captcha/2FA handling, payments, SMS/messaging, destructive ops, any security-control bypass | **full HITL — explicit human confirmation, no auto-continue, no timeout-as-yes** |

Red actions also require: what will happen, stated plainly, before the
confirmation is asked. A bare "continue?" is not informed consent.

## Must stay manual

These never automate, even with HITL — the human does them directly:

- Banking / financial transfers
- Government ID / tax portals
- Payment confirmation
- Passwords, 2FA / recovery codes
- Legal signing
- Medical records
- **Any bypass of a security control** (captcha solvers, rate-limit
  evasion, credential reuse) — LEVI does not build these, period.

## HITL protocol (flag-file pattern)

`levi.automation.cdp.HITLFlag`:

1. Write the decision context to `hitl_message.txt` (title, body, options).
2. Poll for `hitl_continue.flag`; the human writes one of the offered
   options into it.
3. On timeout the answer is `"timeout"` — treated as **not approved**.
   Timeout is never consent.

## Termux / CDP hardening

- CDP binds **only** to `127.0.0.1` (`--remote-debugging-address=127.0.0.1`).
  Never open the debugger port to LAN/WAN. `CDPConfig.validate()` refuses
  non-loopback hosts outright.
- No credential or cookie persistence: session state files
  (`~/.levi/cdp/session.json`) carry target id + timestamps only.
  Anything auth-shaped is never written.
- Every auth/captcha-shaped error classifies as `CAPTCHA_OR_AUTH` and
  pauses for a human (`CDPSession._on_error`).
- Verify loopback-only: `ss -tlnp | grep 9222` must show `127.0.0.1:9222`.

## No-bypass constraint

LEVI automation never defeats access controls: no CAPTCHA solving, no
paywall bypass, no credential theft, no session hijacking. Detection and
hardening guidance is in scope; bypass tooling is not, and any proposal
shaped like bypass is refused at the sandbox gate
(`levi.surgeon.sandbox` blocklist).

## Skill risk tags

- `automation_browser_plan`, `automation_browser_emit`,
  `automation_primitives`, `automation_nl_match` → **INFO** (plans/descriptions only)
- `automation_cdp` → **HIGH**, `requires_confirmation=True`
  (drives a real browser once a human opens the session)
