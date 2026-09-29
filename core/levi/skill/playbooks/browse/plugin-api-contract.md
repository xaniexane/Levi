---
skill_id: browse.plugin_api_contract
name: Plugin API Contract
description: The BROWSE_PLUGIN declaration, registration validation, sandbox facade, write ops, and the permissions catalog.
risk: info
permissions: []
requires_confirmation: false
tags: [browse, plugins, api, sandbox, contract]
version: 1.0.0
---

# Plugin API Contract

A plugin is a Python module under `core/levi/browse/plugins/` (or the
keeper's plugin dir) containing a `BROWSE_PLUGIN` declaration. The
contract below is exact — Builder A implements it, Builders B/C/D
build against it frozen.

## The declaration

```python
BROWSE_PLUGIN = {
    "id": "reader",                 # unique, [a-z0-9_]+
    "display_name": "Reader",       # human label
    "version": "1.0.0",             # semver string
    "hooks": ("page_loaded",),      # hook points requested
    "permissions": ("read_page_text",),  # named capabilities, nothing else
    "write_ops": (),                # write ops need keeper confirmation
    "who_pays": {                   # REQUIRED card
        "payer": "user",            # user | sponsor | data | funnel
        "note": "...",              # one honest sentence
        "not": "...",              # honesty footer: what it does NOT do
    },
}
```

## Registration validation (refuse, never warn)

Every item is checked; any failure refuses registration:

- `id` matches `^[a-z0-9_]+$` and is unique in the registry.
- Every hook named exists in the hook catalog.
- Every permission named exists in the permissions catalog below.
- Every write op is confirmable (has a confirmation path).
- The who-pays card is present and complete: `payer` is one of the
  four, `note` non-empty, `not` non-empty. Missing or incomplete card
  = refused. The difference between generosity and theater is
  machine-checked.

## Sandbox

Plugins never get raw stdlib. Each plugin executes against a
capability-limited facade: `page.text()`, `page.links()`,
`cookies.read()`, etc. — exactly the capabilities granted, nothing
more. `socket`, `subprocess`, and file writes are absent from the
facade unless the matching permission was granted AND the keeper
confirmed. A plugin reaching past its facade fails closed with a
receipted denial.

## Write ops

Any hook that changes state (write cookies, seal to vault, export a
profile) is a write op: it requires explicit keeper confirmation at
call time, mirroring the connector contract (`requires_confirmation`,
no per-feature override). Confirmation is per call, not per session.

## Permissions catalog (initial, deny-closed)

`read_page_text`, `read_page_links`, `read_page_images`,
`read_cookies`, `write_cookies`, `network_fetch` (declared hosts
only), `vault_seal`, `vault_read`, `export_data`, `use_camera_frame`,
`automation_read`, `automation_act`, `credential_generate`,
`credential_fill`.

The catalog grows only by recorded ruling. A permission not in the
catalog does not exist — naming it in a declaration is a registration
refusal, not a TODO.

## Agent action classes

The agent surface (`browse/agent.py`, phase 2, Builder E) acts
through the facade — never around it. Every act is wrapped in
Plan→Preview→Permission→Execute→Verify→Receipt (law 9). Classes:

- `read_page`, `extract_structured` — read-only. Covered by the
  plugin's data permissions (`automation_read`); no per-act
  confirmation.
- `fill_form` — writes into fields. Needs `automation_act`;
  confirmation per act.
- `submit_form` — sends data to the site. Needs `automation_act`;
  confirmation per act.
- `navigate` — moves the session. Needs `automation_act`;
  confirmation per act.
- `credential_fill` — releases a credential into a form. Needs
  `credential_fill`; confirmation per act. The credential value never
  touches the plan, the preview, or the receipt — only the facade
  call carries it; the receipt records *that a fill happened*.

Acting classes ship refused-by-default naming DG-8 until Chauncey
rules (read-only first vs acting-on-behalf day one). The refusal is
a named `ActingNotEnabled` carrying the gate id — not a silent no-op.

## Loading

`browse/plugin.py` keeps the registry. A plugin loads only after the
keeper grants every permission it declares. No grant, no load.
Revocation unloads. Expiry unloads. Every transition is receipted.
