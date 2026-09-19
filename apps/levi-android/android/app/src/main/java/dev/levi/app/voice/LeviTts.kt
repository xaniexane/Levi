package dev.levi.app.voice

import android.content.Context
import android.speech.tts.TextToSpeech
import java.util.Locale

/**
 * Spoken read-back of LEVI's replies using the device's own
 * text-to-speech engine — no cloud voice service of ours. The user picks
 * the voice in system settings; on-device voices keep it fully offline.
 *
 * Fails silent, never loud: if the TTS engine isn't ready, [speak] is a
 * no-op rather than an error. The Settings toggle ("Speak chat replies")
 * is the only on/off switch — this class never decides on its own.
 */
class LeviTts(context: Context) {

    companion object {
        /** Longest single utterance; the web UI should pass plain text. */
        const val MAX_CHARS = 4000
    }

    @Volatile private var ready = false
    private var tts: TextToSpeech? = null

    init {
        tts = TextToSpeech(context.applicationContext) { status ->
            ready = status == TextToSpeech.SUCCESS
            if (ready) {
                val engine = tts
                val locale = Locale.getDefault()
                if (engine != null &&
                    engine.isLanguageAvailable(locale) >= TextToSpeech.LANG_AVAILABLE
                ) {
                    engine.language = locale
                }
            }
        }
    }

    /** Reads [text] aloud, replacing anything currently spoken. */
    fun speak(text: String) {
        if (!ready) return
        val clean = text.trim().take(MAX_CHARS)
        if (clean.isEmpty()) return
        try {
            tts?.speak(clean, TextToSpeech.QUEUE_FLUSH, null, "levi-reply")
        } catch (e: Exception) {
            // Engine gone mid-flight: stay quiet, don't crash the chat.
        }
    }

    fun stop() {
        try {
            tts?.stop()
        } catch (e: Exception) {
            // Best effort.
        }
    }

    fun shutdown() {
        try {
            tts?.stop()
            tts?.shutdown()
        } catch (e: Exception) {
            // Best effort.
        }
        tts = null
        ready = false
    }
}
