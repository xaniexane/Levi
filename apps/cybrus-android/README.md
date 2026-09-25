# Cybrus — UI-preview Android shell

A local-only WebView wrapper around the finished Cybrus UI preview
(`cybrus/src/main/assets/cybrus-ui-preview.html`).

## Honest scope

This APK is a **UI preview, not the product**:

- The bundled HTML is fully self-contained (inline CSS/JS, zero external
  resources) and runs **mock data**.
- **No real vault crypto** exists in this build.
- The manifest declares **no network permissions** — local-only is the point.

## Build

```sh
cd apps/cybrus-android
export JAVA_HOME=/home/hatch/jdk17
export ANDROID_HOME=/home/hatch/android-sdk
export ANDROID_SDK_ROOT=/home/hatch/android-sdk
export JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=true"
export GRADLE_USER_HOME=/home/hatch/.gradle
./gradlew :cybrus:assembleDebug --no-daemon
```

APK lands at `cybrus/build/outputs/apk/debug/cybrus-debug.apk`
(applicationId `dev.cybrus.app.debug` for the debug variant).

## Structure

- `settings.gradle.kts` / `build.gradle.kts` — project wiring (AGP 9.4.0,
  same as the messenger module; zero library dependencies).
- `cybrus/` — the app module: one `MainActivity` (Java) hosting a
  full-screen WebView, dark void-theme window chrome, back-press walks
  WebView history.
