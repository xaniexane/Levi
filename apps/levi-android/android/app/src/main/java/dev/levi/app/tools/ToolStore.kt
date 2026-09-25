package dev.levi.app.tools

import android.content.Context

/**
 * Per-tool on/off toggles: the user gate for the agent runtime.
 *
 * These are plain (non-encrypted) SharedPreferences in their own file —
 * toggles are UI preferences, not secrets, following the same pattern as
 * [dev.levi.app.settings.SettingsStore]'s plain prefs. They are read by
 * [ToolGateway] before every invocation: a disabled tool can never run,
 * regardless of what the agent asks for. Defaults are ON; the permission
 * gate (fail-closed) is what keeps sensitive tools inert until granted.
 */
object ToolStore {
    private const val PREFS = "levi_device_tools"
    private const val KEY_PREFIX = "tool:"

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /** True unless the user explicitly turned this tool off. */
    fun isEnabled(context: Context, toolName: String): Boolean =
        prefs(context).getBoolean(KEY_PREFIX + toolName, true)

    fun setEnabled(context: Context, toolName: String, enabled: Boolean) {
        prefs(context).edit().putBoolean(KEY_PREFIX + toolName, enabled).apply()
    }

    /** Number of tools the user has switched off (for subtitles). */
    fun disabledCount(context: Context): Int =
        DeviceTools.toolNames.count { !isEnabled(context, it) }
}
