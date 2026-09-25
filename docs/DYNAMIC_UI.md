# Dynamic UI protocol

LEVI-native protocol that lets the agent generate **interactive UI inline in
chat replies** — buttons, cards, forms, progress — as structured JSON. The
client renders it; the agent never ships code to the client.

> Design constraint (identity rule): the agent emits **data only**. No JS, no
> HTML, no arbitrary navigation. Actions route back to the agent as structured
> intents; the client owns rendering and confirmation.

## Envelope

```json
{
  "kind": "dynamic-ui",
  "version": 1,
  "elements": [ { "type": "text", "text": "…" }, … ]
}
```

- `kind` must be exactly `"dynamic-ui"`.
- `version` is `1` today. A client that sees a higher version it does not
  understand must render the whole envelope as plain text (graceful
  degradation), never crash.
- `elements` is a non-empty array of element objects, at most 16 per envelope.

## Element types (allowlist)

These are the only types a compliant client must render. Unknown `type`
values are **not** an error: the client renders them as plain text plus a
small "unsupported element" note, never crashing.

| type | shape | notes |
|---|---|---|
| `text` | `{text, tone?}` | `tone`: `body` (default), `muted`, `accent`. Max 2000 chars. |
| `buttons` | `{buttons: [{label, action, style?}]}` | 1–8 buttons. `style`: `primary` (default), `ghost`, `danger`. |
| `card` | `{title, body?, actions?}` | Title required, max 120 chars. Optional body + button actions. |
| `form` | `{title?, fields, submit}` | Fields: `text`, `number`, `select`, `toggle`. `submit`: `{label, action}`. |
| `progress` | `{label?, value?, indeterminate?}` | `value` clamped to 0–1. For indeterminate spinners set `indeterminate: true`. |

### Form fields

```json
{
  "name": "goal",
  "label": "Weekly goal",
  "field": "text",
  "placeholder": "e.g. Ship the landing page",
  "required": true
}
```

- `text`: `{name, label, placeholder?, default?, required?}`
- `number`: `{name, label, default?, min?, max?, required?}`
- `select`: `{name, label, options: ["a","b"], default?, required?}` —
  `options` required, 2–12 entries.
- `toggle`: `{name, label, default?}` — boolean.

At most 10 fields per form. `name` must match `^[a-zA-Z0-9_.-]{1,64}$`.

## Actions

Every button and form-submit carries an `action`. Two kinds exist — the
allowlist, nothing else:

```json
{ "kind": "intent", "intent": "goal.set", "args": { "name": "…" } }
{ "kind": "url", "url": "https://example.com/page" }
```

- **`intent`**: routes back to the agent as a structured tool call / chat
  intent. `intent` is a dotted name (`^[a-zA-Z0-9_.-]{1,64}$`); `args` must be
  a JSON object (strings, numbers, booleans, arrays, plain objects only — no
  nested functions, no `undefined`).
- **`url`**: opens an external page. Schemes allowed: `http`, `https` only.
  Never `javascript:`, `data:`, `file:`, or any other scheme — a non-http(s)
  URL is a validation failure, not a degraded render.

Actions are **never raw JS**. There is no `eval`, no inline handler, no
`onClick` payload, no HTML string.

## Security model

1. **Element allowlist.** Only the five types above render. Everything else
   degrades to plain text + a warning. The agent-side emitter
   (`core/levi/ux/dynamic.py`) rejects unknown types at build time, so the
   agent can only emit what the client can safely render.
2. **No script execution.** The protocol has no field that carries code.
   The renderer never uses `dangerouslySetInnerHTML` for protocol content;
   all strings render as text nodes.
3. **URL policy.** Non-http(s) URLs are rejected at validation. `url` actions
   always render with the destination domain shown and open in a new tab
   with `rel="noopener noreferrer"`.
4. **Action confirmation policy.** Actions marked `confirm: true` (or styled
   `danger`) require **two explicit user taps**: first tap arms the action
   (shows an inline "Tap again to confirm" state), second tap fires it.
   Destructive intents (delete, pay, publish, share externally, grant access)
   MUST be emitted with `confirm: true`; the emitter helper requires the flag
   when the intent name contains a destructive verb
   (`delete`, `remove`, `pay`, `publish`, `share`, `grant`, `revoke`).
   The agent confirmation gate is a second layer: a destructive intent
   arriving at the agent must still pass the normal Plan→Preview→Permission
   flow before executing.
5. **Abuse caps.** Envelope ≤ 16 elements, buttons ≤ 8 per group, form ≤ 10
   fields, text ≤ 2000 chars, title ≤ 120 chars. Oversize payloads are
   rejected, not truncated silently (the agent gets a validation error and
   can resend a smaller payload).
6. **No PII/secrets in payloads.** Payloads may travel through logs and chat
   history; never put credentials, tokens, or personal data in labels, args,
   or defaults. The emitter does not enforce this semantically — it is an
   agent-side discipline rule, stated here as protocol policy.

## Client contract

- Validate the envelope defensively; any malformed element renders as plain
  text with a warning instead of throwing.
- Unknown element `type` → plain-text fallback, never crash.
- Unknown `version` → render the whole envelope as plain text.
- Forward fired actions to the chat layer as structured intents
  (`onAction(action)`); the host decides how an `intent` reaches the agent
  (e.g. sends `{intent, args}` to the agent runtime) and how a `url` opens.
- Renderers must be pure presentational components: no fetching, no
  side effects on render.

## Agent-side emitter

`core/levi/ux/dynamic.py` (stdlib-only) provides typed builders —
`text()`, `buttons()`, `card()`, `form()`, `progress()` — and
`envelope(*elements)` which validates the allowlist, caps, URL schemes, and
the destructive-intent confirmation rule, raising `DynamicUIError` on any
violation. `validate_payload()` re-checks an arbitrary dict (for payloads
received or stored). See `tests/test_dynamic_ui.py`.
