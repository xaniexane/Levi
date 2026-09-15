# LEVI on Android — install & setup

The LEVI Android app is a thin native shell: it opens the LEVI web
client (the Talk UI) in a full-screen view, with your phone's system
WebView. Your conversations run against the LEVI web client served from
your own computer — LEVI stays yours, on your hardware.

## 1. Get the APK

Every push to GitHub builds the app automatically:

1. On your phone or computer, open
   **github.com/xaniexane/Levi** → the **Actions** tab.
2. Open the latest run of the **CI** workflow (green checkmark).
3. Scroll to **Artifacts** → download **levi-android-debug-apk**.
4. Unzip it if needed; you'll have `app-debug.apk`.

## 2. Install it on your phone

1. Copy `app-debug.apk` to your phone (USB, Drive, Files app — any way).
2. Tap it. Android will ask you to **allow installs from this source**
   (your file manager or browser) — allow it once.
3. Tap **Install**. If Play Protect warns that it's from an unknown
   developer, that's expected: this APK is signed with a debug key, not
   a Play Store identity. Tap "Install anyway".
4. You'll get a black **LEVI** icon (amber L) in your app drawer.

No auto-updates: when a new build lands, repeat steps 1–2. Your server
URL setting survives updates.

## 3. Serve LEVI from your computer

The app is a window — it needs the LEVI web client running somewhere
it can reach.

**At home (same Wi-Fi):**

1. On your computer, in the repo: `cd web && npm install` (first time
   only), then `npm run dev`.
2. It prints `http://0.0.0.0:8080`. Find your computer's LAN address
   (on the home network it's usually `192.168.x.x` — check your Wi-Fi
   settings or run `ip addr` / `ipconfig`).
3. Open the LEVI app → **Settings** (⋮ menu) → enter
   `http://192.168.x.x:8080` → **Save**. The Talk UI loads.

**Away from home:** expose the same server with a tunnel, e.g.
`cloudflared tunnel --url http://localhost:8080`, and put the
`tunnel` `https://…` URL in the app's settings instead. (Anyone with
that URL can open your LEVI — treat tunnel URLs like passwords.)

Your computer must be on and reachable while you use the app. Close the
laptop lid and the app can't connect — that's the offline-first
tradeoff, by design.

## What works / honest limits

- The full Talk UI: streaming chat, register switcher (Muse, Grok, …),
  void/light themes — the same UI verified on mobile (390×844).
- The app itself stores exactly one thing: your server URL. No account,
  no tracking, no cloud.
- This is a **debug-signed** build for personal sideloading, not a Play
  Store release. A release build with a proper signing key is a later
  step if you want one.
- Push notifications, background sync, and offline chat are not in this
  build — it needs the live connection described above.

## For developers

Source: `apps/levi-android/` (Kotlin, AGP 9.4.0, compileSdk 36,
stdlib-free of Compose — plain Views + WebView). CI builds
`assembleDebug` for both Android apps in one matrix job and uploads the
LEVI APK as the `levi-android-debug-apk` artifact.
