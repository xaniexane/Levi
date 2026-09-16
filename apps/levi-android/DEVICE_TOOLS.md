# LEVI Android — Device Tools

On-device capabilities the LEVI agent may invoke: notifications, calendar,
alarms, coarse location, opening URLs/files, local time, web search, and a
bounded HTTPS fetch. LEVI-native originals; the design reference was only the
idea of a tools settings screen (toggles per capability).

## Files

| File | Purpose |
|---|---|
| `app/src/main/java/dev/levi/app/tools/ToolSpec.kt` | `ToolSpec` / `ParamSpec` / `RiskLevel` contract types |
| `app/src/main/java/dev/levi/app/tools/DeviceTools.kt` | Native implementations (9 tools) + specs |
| `app/src/main/java/dev/levi/app/tools/ToolStore.kt` | Per-tool on/off toggles (`levi_device_tools` SharedPreferences) |
| `app/src/main/java/dev/levi/app/tools/ToolGateway.kt` | Agent bridge: `(toolName, paramsJson) -> resultJson` |
| `app/src/main/java/dev/levi/app/tools/ToolsFragment.kt` | Settings > Device tools screen |
| `app/src/main/assets/levi_tools.json` | Machine-readable manifest for the agent runtime |
| `app/src/main/res/values/strings_tools.xml`, `res/drawable/ic_tools.xml` | Screen strings + icon |

## Tool list

| Tool | What it does | Android permission | Risk |
|---|---|---|---|
| `notify` | Posts a notification (title + body); tap opens LEVI | `POST_NOTIFICATIONS` (runtime, 33+) | low |
| `calendar_event` | Opens the system calendar editor pre-filled; **the user confirms on screen** | none (insert intent) | low |
| `alarm` | `kind=alarm` (hour/minute) or `kind=timer` (length_seconds) via system clock intents | none | low |
| `location_coarse` | Coarse **network/IP-based** position estimate (lat/lon/accuracy/fix time) | `ACCESS_COARSE_LOCATION` (runtime) | **high** |
| `open_url` | Opens an http(s) URL in the default browser | none | medium |
| `open_file` | Opens a file **inside the app's own storage** in its default app (read-only content URI) | none | medium |
| `local_time` | Device time: epoch millis, ISO-8601, timezone, UTC offset | none | low |
| `web_search` | Hands a query to the device's default search handler | none | low |
| `fetch_url` | HTTPS fetch, body returned to the agent | `INTERNET` (install-time) | medium |

## Permission model

Three independent gates, checked **in order** by `ToolGateway.execute()`:

1. **Known tool** — unknown names return `{"ok": false, "error": "unknown_tool"}`.
2. **User toggle** — `ToolStore.isEnabled()` must be true, else `tool_disabled`.
   The toggle is the user's standing consent (Settings > Device tools).
3. **Android permission** — the tool's declared runtime permission must be
   granted *right now*, else `permission_denied`. Fail-closed: the tool never
   runs partially, and denial is reported as data, not an exception.

No silent collection: `location_coarse` reads a fix only when invoked (last
known network fix; never background tracking); `notify` posts only on
invocation; `fetch_url` runs only on invocation.

Honest failure modes: `no_handler` (no app can handle the intent),
`notifications_disabled`, `provider_disabled`, `location_unavailable`,
`path_outside_scope`, `insecure_scheme`, `fetch_failed`, `main_thread`
(`fetch_url` refuses the main thread), `bad_param` / `bad_params`.

## Toggle gating

- Toggles live in plain `SharedPreferences` (`levi_device_tools`), same
  pattern as `SettingsStore`'s non-sensitive prefs — they are UI preferences,
  not secrets. Defaults are ON; the permission gate is what keeps sensitive
  tools inert until granted.
- The Tools screen (Settings > Device tools, entry row added to the settings
  home) shows one switch row per tool plus a permission row for the two
  runtime-permission tools (`notify`, `location_coarse`). Tapping the
  permission row requests the permission; if already granted it opens the
  app's system settings page.
- A toggle OFF is absolute: the gateway rejects the call before any
  permission check or side effect.

## Manifest contract (`assets/levi_tools.json`)

The agent runtime's machine-readable contract. Keep it in sync with
`DeviceTools.specs()` — same names, params, permissions, risk levels.
Result envelope:

```json
{"ok": true, ...tool-specific fields}
{"ok": false, "error": "<code>", "message": "<human-readable>", ...}
```

Bridge signature: `ToolGateway.execute(context, toolName, paramsJson) -> resultJson`.
`paramsJson` is a JSON object string (may be blank for parameterless tools).
Call from a background thread — `fetch_url` fails closed on the main thread.

## Safety notes

- `fetch_url` enforces **HTTPS only** (plain HTTP refused), follows at most 5
  redirects (https-only), caps bodies at 256KB / `max_chars`, and clamps
  timeouts to 1–30s. It complements the manifest's `usesCleartextTraffic=false`.
- `open_file` canonicalizes the path and refuses anything outside the app's
  own `cacheDir`/`filesDir`/external app dirs, served via the existing
  `FileProvider` (plus a `files-path` entry added for the tool).
- `open_url` / `web_search` accept only http/https and verify an activity can
  handle the intent before launching.
- `ACCESS_COARSE_LOCATION` is declared in the manifest for the coarse tool;
  fine location is deliberately never requested.
- Synthetic/test data only in development; no PII is collected or stored by
  these tools.
