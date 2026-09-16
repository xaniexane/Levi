package dev.levi.app.voice

import android.os.Bundle
import android.service.voice.VoiceInteractionService

/**
 * The service the system binds when LEVI is the default digital assistant.
 *
 * Declared with the BIND_VOICE_INTERACTION permission and
 * `android.voice_interaction` meta-data (see res/xml/voice_interaction_service.xml).
 * All interaction work happens in [LeviVoiceSession]; this service only
 * vends sessions. Declaring it is what makes LEVI appear in
 * Settings → Apps → Default apps → Digital assistant app.
 */
class LeviVoiceInteractionService : VoiceInteractionService() {

    override fun onReady() {
        super.onReady()
        // Nothing to warm up: sessions are created on demand.
    }

    override fun onShutdown() {
        super.onShutdown()
    }
}
