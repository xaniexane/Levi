# Dispatch Android 🚚

The LEVI truck-dispatch board, on-device. Thin vertical of the
transportation edition: dispatch automation, checkcalls, fleet admin.

## What it is

- `dispatch/` — the Android app module (`dev.dispatch.app`), Chaquopy
  Python 3.12 bridge over `core/levi/dispatch/`.
- `python-src/dispatch_bridge.py` — JSON in/out wrappers; the single
  source of truth for the bridge. `sync-python.sh` copies it plus the
  engine into `dispatch/src/main/python/` at build time (build-generated,
  gitignored — never commit those copies).
- UI: dark-first, driver-first. Big touch targets, glanceable week
  board. Tabs: BOARD / LOADS / + LOAD / FLEET / LIMITS.
- Every load mutation goes through the DispatcherTwin/VerifierTwin
  pair; refusals surface as plain-speech errors. Every move receipts.

## Hard boundaries (engine law, surfaced in-app)

- NOT an ELD. No FMCSA/DOT compliance claim — the LIMITS tab says so.
- LEVI advises; the dispatcher decides. Nothing dispatches itself.
- Local-only: no network permission in the manifest.

## Build

```bash
./gradlew :dispatch:assembleRelease --no-daemon
```

Conventions (TOOLS.md): `GRADLE_USER_HOME=/home/hatch/.gradle`,
`--no-daemon`, `JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=true"`,
TMPDIR to a workspace dir (never /tmp), release signing via
`~/.keystores/release.properties` (never in tree). minSdk 24, target 36.

Deliverable: `~/workspace/your_files/apks/dispatch-0.1.0-release.apk`.

## Honest gaps (v1)

- Checkcalls use the engine's simulated channel only — no real
  SMS/driver messaging until a keeper-approved channel exists.
- No GPS, no traffic, no live map: the board is date-range scheduling
  on the dispatcher's own book.
- HOS features are a later phase (awareness reminders only, never
  certified compliance).
- No on-device install test yet — APK is built and signature-verified,
  not phone-tested.
