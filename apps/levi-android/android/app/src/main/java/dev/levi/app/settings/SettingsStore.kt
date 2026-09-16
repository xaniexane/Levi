package dev.levi.app.settings

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.appcompat.app.AppCompatDelegate
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.security.MessageDigest

/**
 * All settings persistence.
 *
 * Non-sensitive UI preferences live in plain SharedPreferences.
 * Anything sensitive (app-lock state, PIN hash, profile, invite code,
 * credential secrets) lives in EncryptedSharedPreferences. If the encrypted
 * store cannot be created (very old / broken keystore), we fall back to
 * plain prefs rather than crashing — the data stays on-device either way.
 */
object SettingsStore {
    private const val TAG = "SettingsStore"
    private const val PREFS = "levi_settings"
    private const val SECURE_PREFS = "levi_secure"

    // Keys (plain)
    private const val KEY_THEME = "theme" // "void" | "light" | "system"
    private const val KEY_NOTIFICATIONS = "notifications_enabled"

    // Keys (encrypted)
    private const val KEY_APPLOCK = "applock_enabled"
    private const val KEY_PIN_HASH = "pin_hash"
    private const val KEY_PROFILE_NAME = "profile_name"
    private const val KEY_PROFILE_HANDLE = "profile_handle"
    private const val KEY_INVITE = "invite_code"
    private const val KEY_CRED_PREFIX = "cred:"

    const val THEME_VOID = "void"
    const val THEME_LIGHT = "light"
    const val THEME_SYSTEM = "system"

    private fun prefs(context: Context): SharedPreferences =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private var secureCache: SharedPreferences? = null

    @Synchronized
    private fun secure(context: Context): SharedPreferences {
        secureCache?.let { return it }
        val created = try {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            EncryptedSharedPreferences.create(
                context,
                SECURE_PREFS,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            )
        } catch (e: Exception) {
            Log.w(TAG, "Encrypted prefs unavailable, falling back to plain prefs", e)
            context.getSharedPreferences(SECURE_PREFS, Context.MODE_PRIVATE)
        }
        secureCache = created
        return created
    }

    // ---- Appearance ----

    fun getTheme(context: Context): String =
        prefs(context).getString(KEY_THEME, THEME_VOID) ?: THEME_VOID

    fun setTheme(context: Context, theme: String) {
        prefs(context).edit().putString(KEY_THEME, theme).apply()
        applyTheme(context)
    }

    /** Maps the saved theme to an AppCompat night mode. Call before activities start. */
    fun applyTheme(context: Context) {
        val mode = when (getTheme(context)) {
            THEME_LIGHT -> AppCompatDelegate.MODE_NIGHT_NO
            THEME_SYSTEM -> AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM
            else -> AppCompatDelegate.MODE_NIGHT_YES // void: always dark
        }
        AppCompatDelegate.setDefaultNightMode(mode)
    }

    // ---- Notifications ----

    fun notificationsOn(context: Context): Boolean =
        prefs(context).getBoolean(KEY_NOTIFICATIONS, true)

    fun setNotificationsOn(context: Context, on: Boolean) {
        prefs(context).edit().putBoolean(KEY_NOTIFICATIONS, on).apply()
        LeviChannels.setAllEnabled(context, on)
    }

    // ---- App lock ----

    fun isAppLockEnabled(context: Context): Boolean =
        secure(context).getBoolean(KEY_APPLOCK, false)

    fun setAppLockEnabled(context: Context, enabled: Boolean) {
        secure(context).edit().putBoolean(KEY_APPLOCK, enabled).apply()
        if (!enabled) clearPin(context)
    }

    fun hasPin(context: Context): Boolean =
        secure(context).getString(KEY_PIN_HASH, null) != null

    fun setPin(context: Context, pin: String) {
        secure(context).edit().putString(KEY_PIN_HASH, sha256(pin)).apply()
    }

    fun checkPin(context: Context, pin: String): Boolean {
        val stored = secure(context).getString(KEY_PIN_HASH, null) ?: return false
        return stored == sha256(pin)
    }

    fun clearPin(context: Context) {
        secure(context).edit().remove(KEY_PIN_HASH).apply()
    }

    private fun sha256(s: String): String {
        val bytes = MessageDigest.getInstance("SHA-256").digest(s.toByteArray())
        return bytes.joinToString("") { "%02x".format(it) }
    }

    // ---- Local profile (LEVI Account) ----

    fun profileName(context: Context): String =
        secure(context).getString(KEY_PROFILE_NAME, "").orEmpty()

    fun setProfileName(context: Context, v: String) {
        secure(context).edit().putString(KEY_PROFILE_NAME, v.trim()).apply()
    }

    fun profileHandle(context: Context): String =
        secure(context).getString(KEY_PROFILE_HANDLE, "").orEmpty()

    fun setProfileHandle(context: Context, v: String) {
        secure(context).edit().putString(KEY_PROFILE_HANDLE, v.trim()).apply()
    }

    fun hasProfile(context: Context): Boolean = profileName(context).isNotBlank()

    fun clearProfile(context: Context) {
        secure(context).edit()
            .remove(KEY_PROFILE_NAME)
            .remove(KEY_PROFILE_HANDLE)
            .apply()
    }

    // ---- Invite code ----

    fun inviteCode(context: Context): String =
        secure(context).getString(KEY_INVITE, "").orEmpty()

    fun setInviteCode(context: Context, v: String) {
        secure(context).edit().putString(KEY_INVITE, v.trim().uppercase()).apply()
    }

    // ---- Secure credentials store ----

    fun credentialNames(context: Context): List<String> =
        secure(context).all.keys
            .filter { it.startsWith(KEY_CRED_PREFIX) }
            .map { it.removePrefix(KEY_CRED_PREFIX) }
            .sorted()

    fun putCredential(context: Context, name: String, secret: String) {
        secure(context).edit().putString(KEY_CRED_PREFIX + name.trim(), secret).apply()
    }

    fun getCredential(context: Context, name: String): String? =
        secure(context).getString(KEY_CRED_PREFIX + name, null)

    fun deleteCredential(context: Context, name: String) {
        secure(context).edit().remove(KEY_CRED_PREFIX + name).apply()
    }
}
