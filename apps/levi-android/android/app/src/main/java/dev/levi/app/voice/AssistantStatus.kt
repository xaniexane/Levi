package dev.levi.app.voice

import android.content.Context
import android.provider.Settings

/**
 * Default-assistant status: is LEVI the system's chosen assistant?
 *
 * Reads [Settings.Secure] `assistant` (the flattened ComponentName of the
 * current default assistant) and checks whether it belongs to our package.
 * Read-only — this never changes the setting; only the system picker can.
 */
object AssistantStatus {

    /**
     * Flattened component of the current default assistant, or null.
     *
     * Note: there is no public Settings.Secure constant for this key, so the
     * literal "assistant" is used (it is the documented Settings.Secure key).
     */
    fun currentAssistant(context: Context): String? =
        Settings.Secure.getString(context.contentResolver, "assistant")

    /** True when the default assistant component belongs to this app. */
    fun isDefaultAssistant(context: Context): Boolean {
        val current = currentAssistant(context) ?: return false
        // Flattened form is "package/class".
        return current.startsWith(context.packageName + "/")
    }

    /** Our VoiceInteractionService flattened the way the system reports it. */
    fun ourServiceComponent(context: Context): String =
        context.packageName + "/" + LeviVoiceInteractionService::class.java.name
}
