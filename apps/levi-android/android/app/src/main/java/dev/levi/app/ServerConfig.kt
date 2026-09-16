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
        // Cleartext http:// is only ever acceptable for local hosts — the
        // network security config denies it everywhere else. Reject early
        // so the failure is legible instead of a silent WebView error.
        if (t.startsWith("http://") && !isLocalHost(t)) return null
        return t
    }

    /**
     * True when [raw] is an http:// URL whose host is NOT permitted
     * cleartext by the network security config — i.e. cleartext that
     * normalize() will refuse. Used by Settings to show a specific,
     * actionable error.
     */
    fun isInsecureHttp(raw: String): Boolean {
        val t = raw.trim().trimEnd('/')
        if (!t.startsWith("http://")) return false
        return !isLocalHost(t)
    }

    /**
     * Loopback or emulator-host loopback ONLY — exactly the hosts the
     * network security config allow-lists for cleartext. Everything else
     * (including RFC-1918 LAN addresses) must use HTTPS.
     */
    fun isLocalHost(url: String): Boolean {
        val host = url.substringAfter("://").substringBefore('/').substringBefore(':')
            .trim().lowercase().removeSuffix(".")
        if (host.isEmpty()) return false
        if (host == "localhost" || host == "10.0.2.2") return true
        val v4 = Regex("""^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$""").matchEntire(host)
            ?: return false
        val aN = v4.groupValues[1].toIntOrNull() ?: return false
        return aN == 127 // 127.0.0.0/8 loopback
    }
}
