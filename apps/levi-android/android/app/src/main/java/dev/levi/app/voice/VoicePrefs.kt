package dev.levi.app.voice

import android.content.Context

/** Non-sensitive voice feature toggles. The user owns every switch. */
object VoicePrefs {
    private const val PREFS = "levi_voice"
    private const val KEY_HEY_LEVI = "hey_levi_enabled"
    private const val KEY_SPEAK_REPLIES = "speak_replies"

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /** Whether the user wants the "Hey LEVI" listener on. */
    fun isHeyLeviEnabled(context: Context): Boolean =
        prefs(context).getBoolean(KEY_HEY_LEVI, false)

    fun setHeyLeviEnabled(context: Context, enabled: Boolean) {
        prefs(context).edit().putBoolean(KEY_HEY_LEVI, enabled).apply()
    }

    /** Whether chat replies are read aloud. Default off. */
    fun speakReplies(context: Context): Boolean =
        prefs(context).getBoolean(KEY_SPEAK_REPLIES, false)

    fun setSpeakReplies(context: Context, enabled: Boolean) {
        prefs(context).edit().putBoolean(KEY_SPEAK_REPLIES, enabled).apply()
    }
}
