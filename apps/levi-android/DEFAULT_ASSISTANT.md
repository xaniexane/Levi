# LEVI as the default Android assistant

Long-press home (or the assistant gesture) opens LEVI instead of Google/Gemini.
Local-first: speech-to-text uses the device's own recognizer; the chat is the
existing WebView → configured LEVI server. No cloud voice dependency of ours.

## What was added

| Component | File | Purpose |
|---|---|---|
| `AssistActivity` | `app/.../dev/levi/app/AssistActivity.kt` | Exported activity with `ASSIST` / `VOICE_COMMAND` intent-filters. Validates the action, **ignores all extras on external intents** (no intent-spoofing surface), then routes into `MainActivity` with a voice-input affordance. |
| `LeviVoiceInteractionService` | `app/.../dev/levi/app/voice/` | `VoiceInteractionService` the system binds. Declaring it is what lists LEVI in Settings → Apps → Default apps → Digital assistant app. |
| `LeviVoiceInteractionSessionService` | `.../voice/` | Vends the overlay session to the system. |
| `LeviVoiceSession` | `.../voice/` | Voice plate UI: mic state, one-utterance `SpeechRecognizer` capture, handoff of the transcript to `MainActivity`. RECORD_AUDIO gating with rationale; fails closed. |
| `AssistantStatus` | `.../voice/` | Reads `Settings.Secure` `assistant` and compares the flattened component to our package. Read-only — only the system picker can change the default. |
| `AssistantFragment` | `app/.../dev/levi/app/settings/` | Settings screen: honest default-assistant status, deep link to the system picker, microphone permission row. |
| `res/xml/voice_interaction_service.xml` | meta-data | `supportsAssist="true"`, keyguard voice launch **off**. |
| `MainActivity` extras | — | `EXTRA_VOICE_QUERY` → banner + documented `window.leviVoiceQuery(text)` JS hook; `EXTRA_START_VOICE` → system `RecognizerIntent`; toolbar mic action. |

Manifest: `RECORD_AUDIO` (runtime), `AssistActivity` (exported, `excludeFromRecents`, `noHistory`),
both voice services (`BIND_VOICE_INTERACTION`, exported), `HeyLeviService`
(not exported, `foregroundServiceType="microphone"`) with `FOREGROUND_SERVICE`,
`FOREGROUND_SERVICE_MICROPHONE`, and `USE_FULL_SCREEN_INTENT` (API 34+).
Cleartext posture unchanged (denied except loopback).

## How the user enables it

1. Install the APK.
2. LEVI → Settings → **Set as default assistant** → shows status; if not
   default, **Choose default assistant** opens system settings.
   (Or: system Settings → Apps → Default apps → Digital assistant app → LEVI.)
3. Grant the microphone when the voice plate asks (only needed for the
   hands-free plate; the toolbar mic uses the system recognizer and needs
   no permission).
4. Optional, same screen: **Hey LEVI hotword** (best-effort listener, costs
   stated on the toggle) and **Speak chat responses** (device TTS, off by
   default).

## Web UI contract (optional, for the Talk UI)

If the page defines `window.leviVoiceQuery(text)`, the app calls it with the
transcript after load. Until then the query stays visible in the dismissible
banner — the app never pretends the chat received it.

If the page wants spoken replies, it calls `window.leviSpeak.speak(text)`
with plain text (and `window.leviSpeak.stop()` to silence). Both are no-ops
unless the user enabled **Speak chat responses** in Settings — the page may
offer the affordance, but the user owns the switch. The voice is the
device's own TTS engine; no cloud voice service of ours.

## Honest limits

- **Hotword** ("Hey LEVI") is best-effort, not system-level: a third-party
  app can't register a DSP hotword, so the toggle in Settings runs a
  foreground service that keeps the device's own recognizer warm and
  matches transcripts. Costs are stated up front — mic indicator shows
  while listening, battery use rises, detection misses in noise, and the
  listener stops on reboot (re-enable in Settings).
- **Gesture behavior varies by OEM** (long-press home, swipe corner, power
  double-press): whatever the device maps to Assist opens LEVI once selected.
- **Spoken responses** need the web UI's cooperation: the app exposes the
  `leviSpeak` bridge and the device TTS engine, but the page decides what
  text to send. Silent by default; the user opts in.
- **App lock still gates the chat**: invoking the assistant on a locked phone
  lands on the lock screen, not the conversation.
- `VOICE_COMMAND` (Bluetooth / wired-headset button) routes to the same flow.
