package dev.levi.app.voice

import android.os.Bundle
import android.service.voice.VoiceInteractionSession
import android.service.voice.VoiceInteractionSessionService

/**
 * Vends [LeviVoiceSession] to the system. Bound only by the system
 * (BIND_VOICE_INTERACTION); never started by the app itself.
 */
class LeviVoiceInteractionSessionService : VoiceInteractionSessionService() {

    override fun onNewSession(args: Bundle): VoiceInteractionSession =
        LeviVoiceSession(this)
}
