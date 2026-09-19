package dev.levi.app.voice

import android.webkit.JavascriptInterface

/**
 * The `window.leviSpeak` bridge for the configured LEVI web UI (Talk UI).
 *
 * Contract:
 * - `leviSpeak.speak(text)` — reads [text] aloud with the device voice.
 * - `leviSpeak.stop()` — silences the current utterance.
 *
 * Both are no-ops unless the user enabled "Speak chat replies" in
 * Settings: the page may offer the affordance, but the user owns the
 * switch. The page should pass plain text (no markdown); overlong input
 * is truncated, never rejected.
 *
 * Exposure: this bridge is attached to the app's WebView, which loads the
 * user's configured LEVI server and nothing else — so only that origin
 * can call it.
 */
class SpeakBridge(
    private val tts: LeviTts,
    private val isEnabled: () -> Boolean,
) {
    @JavascriptInterface
    fun speak(text: String?) {
        if (!isEnabled()) return
        if (!text.isNullOrBlank()) tts.speak(text)
    }

    @JavascriptInterface
    fun stop() {
        tts.stop()
    }
}
