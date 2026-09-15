# P2.4 Android rebuild — verification log (2026-09-15)

No Android SDK / Gradle toolchain exists in this environment, so no
`./gradlew` build was run. Everything below was verified by the next-best
real checks: executed scripts, live Maven Central / Google Maven /
services.gradle.org / developer.android.com lookups, and line-by-line
source review. Anything a real build alone can prove is listed under
**NEEDS REAL BUILD** — nothing there is claimed as working.

## Version pins verified live (2026-09-15)

Checked against `repo1.maven.org/.../maven-metadata.xml`,
`dl.google.com/dl/android/maven2/.../maven-metadata.xml`,
`services.gradle.org/versions/all`, and the official AGP 9.4.0 release
notes (`developer.android.com/build/releases/agp-9-4-0-release-notes`):

| Pin | Status |
|---|---|
| Gradle wrapper 9.6.0 | EXISTS; `distributionSha256Sum` in `gradle-wrapper.properties` == checksum published by services.gradle.org (`bbaeb2…a529a01`) |
| AGP 9.4.0 | EXISTS; official release notes: **Gradle min 9.6.0 / default 9.6.0**, SDK Build Tools 36.0.0, JDK 17 |
| Kotlin 2.4.20 | EXISTS (latest; published 2026-09-07) |
| KSP 2.3.12 | EXISTS and is the **latest KSP on Maven Central — no KSP for Kotlin 2.4.x exists** (deviation, see below) |
| Compose BOM 2026.08.00 | EXISTS (latest is 2026.09.00; plan pin kept) |
| OkHttp 5.4.0 | EXISTS (latest is 5.5.0; plan pin kept) |
| Retrofit 3.0.0 | EXISTS (latest) |
| `retrofit2:converter-kotlinx-serialization:3.0.0` | EXISTS — first-party upstreamed converter (JakeWharton artifact retired) |
| `net.zetetic:sqlcipher-android:4.9.0` | EXISTS (latest is 4.19.0; task pinned 4.9.0, kept) |
| Hilt 2.59.2 | EXISTS (latest is 2.60.1; plan pin kept) |
| kotlinx-coroutines 1.11.0 | EXISTS (latest) |
| kotlinx-serialization-json 1.11.0 | EXISTS (latest stable; 1.12.0-RC not taken) |
| kotlinx-datetime 0.8.0 | EXISTS (latest) |
| lifecycle 2.10.0 | EXISTS |
| navigation-compose 2.9.8 | EXISTS |
| activity-compose 1.13.0 | EXISTS (latest stable) |
| core-ktx 1.19.0 | EXISTS (latest) |
| appcompat 1.8.0 | EXISTS (latest) |
| material 1.13.0 | EXISTS (1.14.0 is latest; plan pin kept) |
| security-crypto 1.1.0 (stable) | EXISTS (latest) |
| biometric 1.1.0 (stable) | EXISTS (latest stable; 1.4.0-alpha07 is alpha) |

Not individually re-verified (routine, low-risk; previous worker claimed
2026-09-15 verification): datastore 1.2.1, work-runtime-ktx 2.11.2,
timber 5.0.1, hilt-navigation-compose 1.2.0, hilt-work 1.2.0, junit
4.13.2, mockito-core 5.12.0, mockito-kotlin 5.4.0, test-ext junit 1.2.1,
espresso-core 3.6.1.

## Deviations from the audit plan / task spec (evidence-backed)

1. **Gradle 9.6.0, not 9.4.1.** The task spec asked for Gradle 9.4.1 +
   AGP 9.4.0, but AGP 9.4.0's official release notes require Gradle
   **minimum 9.6.0** — 9.4.1 (released 2026-03-19, six months before AGP
   9.4.0) would make AGP refuse to run. 9.6.0 is mandatory, not a choice.
2. **KSP 2.3.12 with Kotlin 2.4.20** ("KSP must track Kotlin exactly" is
   unsatisfiable today — verified: no KSP 2.4.x line exists). The first
   real `./gradlew assembleDebug` is the test; bump KSP the day google/ksp
   ships a 2.4.x release.

## API contract cross-check (Android ↔ `docs/openapi.yaml`)

All 19 REST operations + the WebSocket protocol checked by hand —
method, path, request/response field names, status codes:

- OAuth (:8080): `GET /.well-known/openid-configuration`, `GET
  /oauth/jwks`, `POST /oauth/token` (form: grant_type/code/code_verifier/
  redirect_uri/refresh_token/client_id/client_secret), `GET
  /oauth/userinfo`, `POST /oauth/revoke` (form: token/token_type_hint →
  200 always), `GET /me`, `GET /me/devices` → `{devices:[...]}`,
  `POST /me/devices` → 201 `{status, device_id}`, `DELETE
  /me/devices/{device_id}` → **200** `{status, device_id}` (not 204).
- Messaging (:8081): `GET/POST /conversations` (POST → 201 unwrapped),
  `GET/DELETE /conversations/{id}` (DELETE → 204), `GET
  /conversations/{id}/messages` (`limit`, `before` ISO-8601 string →
  `{messages:[oneOf Message|Tombstone], total}`), `POST
  /conversations/{id}/messages` → 201 unwrapped envelope,
  `GET/DELETE /messages/{id}` (DELETE → 204; GET may return tombstone),
  `GET /messages/{id}/deliver` → 200 `{status, delivered_at}`,
  `GET /queue` → 200 `{messages, count}` (read-once), `GET /health`
  (per-service body shape).
- WebSocket `ws(s)://host:8081/ws/{user_id}`: auth-first-frame
  `{"type":"auth","token"}` ✓; close codes 4001/4002/4003 ✓; server
  frames `connected/queued_messages/new_message/conversation_created/
  typing/pong` ✓; client frames `auth/typing/read_receipt/ping` ✓.

## Code checks run

- Brace/paren/bracket balance on all 8 `.kt` + 3 `.kts` files: **balanced**
  (state-machine scan handling `//`, `/* */`, `"…"`, `'…'`, `"""…"""`).
- Import → dependency cross-check: every import resolves to a declared
  catalog dependency, the Android SDK, or the stdlib. No lazy-sodium /
  Gson / Moshi / Flipper anywhere in code (Flipper only in RUNBOOK as a
  historical note).
- SQLCipher uses the correct `net.zetetic.database.sqlcipher` package
  (the old `net.sqlcipher.*` collision is gone); `loadLibs(context)`,
  `SQLiteOpenHelper(ctx, name, null, version)`,
  `getWritableDatabase(char[])`, `insertWithOnConflict`,
  `CONFLICT_REPLACE` all match the 4.9.0 API.
- CryptoModule: JCA `AES/GCM/NoPadding` + AndroidKeyStore
  (`KeyGenParameterSpec`, `GCMParameterSpec(128, iv)`) — stdlib only.
- Manifest ↔ code ↔ resources: `.VYVEApplication`, `.ui.MainActivity`,
  `.auth.OAuthCallbackActivity`, `.net.MessageSyncService`,
  `@xml/network_security_config`, `@mipmap/*`, `@string/app_name`,
  `@style/Theme.VYVE` all resolve. Every permission is justified by a
  real code path (unjustified ones removed — see below).
- `gradle-wrapper.jar` is a valid jar; `gradlew` has the exec bit;
  `.gradle/` and `local.properties` are git-ignored (root `.gitignore`
  covers `*.keystore`, `*.jks`, `local.properties`, `.gradle/`); no
  keystore is committed.

## Fixes applied in this pass

1. `app/build.gradle.kts` — removed duplicated `ksp(libs.hilt.compiler)`
   (declared twice).
2. `ui/MainActivity.kt` — added `@file:OptIn(ExperimentalMaterial3Api::class)`:
   `TopAppBar` is experimental; without the opt-in this is a compile error.
3. `AndroidManifest.xml` — removed unjustified permissions
   (`READ/WRITE_EXTERNAL_STORAGE`, `RECEIVE_BOOT_COMPLETED`,
   `FOREGROUND_SERVICE`, `VIBRATE` — no code path uses them) and the
   fictional `android.hardware.keystore` `<uses-feature>`; fixed the
   "Foreground service" comment (the service is not a foreground service).
4. `res/values/colors.xml` — added `colorTextPrimary`,
   `colorTextSecondary`, `colorOnAccent`: `themes.xml` referenced them and
   they did not exist (AAPT would fail).
5. `res/values/themes.xml` — parent is now
   `Theme.Material3.DayNight.NoActionBar` (the Compose UI is Material3).
6. `VYVEApplication.kt` — fixed the inaccurate Timber comment.
7. `RUNBOOK.md` + `gradle/libs.versions.toml` — recorded the verified
   Gradle-9.6.0 requirement and the KSP deviation with sources.

## NEEDS REAL BUILD (`./gradlew assembleDebug` on a machine with Android SDK 37 + JDK 17)

- Whether KSP 2.3.12 + the `kotlin-metadata-jvm:2.4.20` force actually
  lets Hilt process Kotlin 2.4.20 (the single biggest risk).
- Hilt/Dagger codegen, Compose compiler plugin, R8 full-mode minify with
  these proguard rules, AAPT linking, SQLCipher native `.so` packaging.
- Retrofit 3 behavior details: `Response<Unit>` on 204s, `JsonObject`
  lenient decoding, the upstreamed kotlinx-serialization converter.
- Runtime behavior: real API calls, OAuth PKCE exchange (TODO in code),
  WebSocket auth-first-frame against the live backend, E2EE
  XChaCha20-Poly1305 (not implemented — Tink recommended in code/RUNBOOK).
- The 10 routine pins listed above as "not individually re-verified".

## Known honest gaps (in code, not hidden)

- OAuth sign-in flow is UI + TODOs only (`MainActivity.onNewIntent`,
  `OAuthCallbackActivity` forwards the code; no token exchange yet).
- Message E2EE is not implemented client-side (documented; do not
  reintroduce lazy-sodium — use Tink when it lands).
- `MessageSyncService` acknowledges start requests and stops; the real
  sync belongs in a WorkManager worker (TODO in code).
- Declared-but-unused dependencies (navigation, biometric, datastore,
  work, security-crypto, appcompat, material, datetime,
  lifecycle-service): kept deliberately for the roadmap; harmless to the
  build.
