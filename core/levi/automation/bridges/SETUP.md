# MacroDroid bridge — setup

LEVI side is code; everything here is configured by you in the
MacroDroid app. Honest map: this file documents the external half.
`macrodroid.py` is the LEVI half.

## Inbound: MacroDroid → LEVI (phone event fires a LEVI workflow)

LEVIlane listens where your webhook serving stack listens. A MacroDroid
macro posts to it. Example macro: **SMS received → fire LEVI workflow.**

1. In MacroDroid, create a macro.
2. **Trigger:** `SMS Received` (or any trigger: call, notification,
   location, time, etc.).
3. **Action:** `HTTP Request`
   - **URL:** `http://<levi-host>:<port>/hooks/macrodroid/<path>`
     (e.g. `http://192.168.1.50:8400/hooks/macrodroid/sms` —
     `<path>` is yours; it becomes the `macrodroid:<path>` source)
   - **Method:** `POST`
   - **Body / data:** JSON, e.g.
     ```json
     {"from": "{sms_number}", "text": "{sms_message}"}
     ```
     (MacroDroid magic-text in braces works inside the body.)
   - **Content type:** `application/json`
4. Test the macro: it should hit the LEVI webhook URL; LEVI builds
   `{"kind": "webhook", "source": "macrodroid:<path>", "payload": {...}}`
   via `build_macrodroid_event` and calls the workflow engine.

**Out of scope here:** the inbound HTTP receiver itself. LEVI has no
standing server in this task; the URL above must be served by whatever
serves LEVI webhooks, and that server hands `(path, payload)` to
`macrodroid_event(webhook_path, payload)`.

## Outbound: LEVI → MacroDroid (a LEVI workflow step fires a macro)

1. In MacroDroid, create a macro.
2. **Trigger:** `Webhook` → `Get URL`. MacroDroid shows a URL like
   `https://trigger.macrodroid.com/<uuid>/incoming`.
3. **Actions:** whatever the macro should do (send SMS, toggle wifi,
   speak, run shell, etc.).
4. In your LEVI workflow (node config or `levi` CLI step), call:
   ```python
   from levi.automation.bridges.macrodroid import fire_macrodroid
   fire_macrodroid("https://trigger.macrodroid.com/<uuid>/incoming",
                   {"event": "nightly_digest", "text": "..."})
   ```
   Real POST, 10s timeout; the return dict carries ok/status/evidence.
   Non-2xx responses and unreachable hosts come back as
   `{"ok": False, ...}` — never a silent fake fire.
