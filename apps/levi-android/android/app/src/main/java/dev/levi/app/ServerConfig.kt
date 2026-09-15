package dev.levi.app

import android.content.Context
import android.content.SharedPreferences

/** Server URL persistence. Empty = not configured yet. */
object ServerConfig {
    private const val PREFS = "levi_server"
    private const val KEY_URL = "server_url"

    private fun prefs(context: Context): SharedPreferences =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun getUrl(context: Context): String =
        prefs(context).getString(KEY_URL, "").orEmpty().trim()

    fun setUrl(context: Context, url: String) {
        prefs(context).edit().putString(KEY_URL, url.trim()).apply()
    }

    /** Normalize user input: require a scheme, strip trailing slash. */
    fun normalize(raw: String): String? {
        val t = raw.trim().trimEnd('/')
        if (t.isEmpty()) return ""
        if (!t.startsWith("http://") && !t.startsWith("https://")) return null
        if (t.length < 10) return null
        return t
    }
}
