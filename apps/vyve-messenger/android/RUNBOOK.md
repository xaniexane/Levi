# VYVE Messenger — Android runbook

Build & release notes for `apps/vyve-messenger/android/`. Rebuilt 2026-09-15
(P2.4): Gradle 9.6.0, AGP 9.4.0, Kotlin 2.4.20, Compose BOM 2026.08.00,
compileSdk/targetSdk 36. (Compose BOM 2026.x / androidx.core 1.19.0 declare
compileSdk 37 in their AAR metadata, but no platforms;android-37 package
exists yet — the check is suppressed with
`android.suppressUnsupportedCompileSdk=37`; see gradle.properties.)

**Why Gradle 9.6.0 (not 9.4.1):** the official AGP 9.4.0 release notes
(<https://developer.android.com/build/releases/agp-9-4-0-release-notes>)
list Gradle **minimum 9.6.0 / default 9.6.0** (SDK Build Tools 36.0.0,
JDK 17). Gradle 9.4.1 predates AGP 9.4.0 by six months and AGP refuses to
run below 9.6.0, so 9.6.0 is mandatory here. The wrapper's
`distributionSha256Sum` was verified against the checksum published in
<https://services.gradle.org/versions/all> (both
`bbaeb2fef8710818cf0e261201dab964c572f92b942812df0c3620d62a529a01`).

## Prerequisites

- JDK 17 (`java -version` → 17.x). AGP 9.4 requires JDK 17.
- Android SDK with **platform-36** and **build-tools 36.0.0**.
  Set `ANDROID_HOME` (or `ANDROID_SDK_ROOT`) or create `local.properties`
  with `sdk.dir=/path/to/sdk`. (`local.properties` is git-ignored.)

## Build

```sh
cd apps/vyve-messenger/android
./gradlew assembleDebug        # debug APK
./gradlew assembleRelease      # release APK (see signing below)
./gradlew lint                 # Android Lint
```

CI runs `./gradlew assembleDebug --no-daemon` (`.github/workflows/ci.yml`,
job `android`).

## Release signing (Play App Signing)

The app uses **Play App Signing**: Google holds the app-signing key; you
upload with an **upload key** that lives OUTSIDE this repo. No keystore is
ever committed (`.gitignore` covers `*.keystore`, `*.jks`, `local.properties`).

### 1. Generate the upload key (do this ONCE, on a secure machine)

```sh
keytool -genkeypair \
  -keystore ~/secure/vyve-upload.keystore \
  -alias vyve-upload \
  -keyalg RSA -keysize 4096 -validity 9125 \
  -storetype PKCS12
```

Back up `vyve-upload.keystore` + its passwords in your password manager.
Register the **upload certificate** in the Play Console
(Release → Setup → App signing): `keytool -export -rfc -keystore
~/secure/vyve-upload.keystore -alias vyve-upload -file upload-cert.pem`.

### 2. Point the build at the keystore (pick ONE)

Env vars (CI — store as secrets):

```sh
export VYVE_KEYSTORE_PATH=$HOME/secure/vyve-upload.keystore
export VYVE_KEYSTORE_PASSWORD=...
export VYVE_KEY_ALIAS=vyve-upload
export VYVE_KEY_PASSWORD=...
```

or Gradle properties (local dev, `~/.gradle/gradle.properties` — NOT the
repo's `gradle.properties`):

```properties
vyve.keystore.path=/home/you/secure/vyve-upload.keystore
vyve.keystore.password=...
vyve.key.alias=vyve-upload
vyve.key.password=...
```

If no keystore is configured, `assembleRelease` still assembles but is
signed with the **debug key** and the build logs a warning — never upload
that artifact to Play.

## Dependency notes (deviations / watch-outs)

- **KSP 2.3.12 with Kotlin 2.4.20 — documented deviation.** Verified
  against Maven Central on 2026-09-15: KSP's latest release is 2.3.12 and
  there is NO KSP release for Kotlin 2.4.x (only an `upgrade-kotlin-2.4.0`
  branch in google/ksp), so "KSP tracks Kotlin exactly" cannot be
  satisfied today. KSP 2.3.10+ understands Kotlin 2.4 module names; whether
  Hilt's KSP processing actually survives Kotlin 2.4.20 class files is
  exactly what the first real `./gradlew assembleDebug` must prove. When
  google/ksp ships a 2.4.x line, bump `ksp` in
  `gradle/libs.versions.toml` to match Kotlin exactly.
- **kotlin-metadata-jvm force** (root `build.gradle.kts`): Hilt 2.59.2's
  bundled metadata reader cannot read Kotlin 2.4 class files. The force is
  the maintainer-endorsed workaround; remove it once Dagger ships a
  Kotlin 2.4-aware release.
- **Crypto choice** (`crypto/CryptoModule.kt`): lazy-sodium was dropped
  (abandoned 2021, JitPack-only, incompatible with current AGP). Local
  secret storage uses JCA AES-256-GCM via AndroidKeyStore. The backend's
  XChaCha20-Poly1305 message envelope is NOT implemented client-side yet;
  when E2EE send/receive lands, use `com.google.crypto.tink:tink-android`
  (JCA has no XChaCha20) — do not reintroduce lazy-sodium.
- **Single JSON converter**: kotlinx-serialization everywhere
  (`retrofit2:converter-kotlinx-serialization:3.0.0`, the upstreamed
  replacement for the archived JakeWharton artifact). No Gson/Moshi.
- **SQLCipher**: `net.zetetic:sqlcipher-android:4.9.0` (the old
  `net.zetetic:android-database-sqlcipher` artifact is deprecated; 4.5.4
  lacks Play's mandatory 16 KB page-size support). Java package is
  `net.zetetic.database.sqlcipher` (not `net.sqlcipher.database`).
- **Flipper removed** (discontinued by Meta). Debug logging goes through
  Timber + OkHttp's logging interceptor (BASIC in debug builds only).
- **Network**: cleartext is denied by default
  (`res/xml/network_security_config.xml`); only the local dev backends
  (`10.0.2.2`, `localhost`, `127.0.0.1` — :8080/:8081) are excepted.

## API contract

`net/ApiService.kt` mirrors `apps/vyve-messenger/docs/openapi.yaml`
(OAuth on :8080, messaging on :8081, no `/v1` prefix, RS256 bearer auth,
auth-first-frame WebSocket `/ws/{user_id}`). Re-check the spec after any
backend route change: `python3 apps/vyve-messenger/docs/check_openapi.py`.
