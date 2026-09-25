package dev.levi.app.settings

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import dev.levi.app.R

/**
 * The app's notification channels — the "Messaging channels" surface.
 * Created at app start (LeviApp); per-channel toggles delete + recreate
 * the channel with IMPORTANCE_NONE / restored importance, which is the
 * only programmatic way to change a channel's importance after creation.
 */
object LeviChannels {
    const val MESSAGES = "levi_messages"
    const val UPDATES = "levi_updates"

    private data class Spec(val id: String, val nameRes: Int, val descRes: Int, val importance: Int)

    private fun specs(context: Context) = listOf(
        Spec(MESSAGES, R.string.channel_messages, R.string.channel_messages_desc, NotificationManager.IMPORTANCE_DEFAULT),
        Spec(UPDATES, R.string.channel_updates, R.string.channel_updates_desc, NotificationManager.IMPORTANCE_LOW),
    )

    private fun manager(context: Context): NotificationManager =
        context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

    /** Creates any missing channels. Safe to call repeatedly. */
    fun ensure(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = manager(context)
        for (s in specs(context)) {
            if (nm.getNotificationChannel(s.id) == null) {
                nm.createNotificationChannel(
                    NotificationChannel(s.id, context.getString(s.nameRes), s.importance).apply {
                        description = context.getString(s.descRes)
                    },
                )
            }
        }
        if (!SettingsStore.notificationsOn(context)) setAllEnabled(context, false)
    }

    fun channels(context: Context): List<NotificationChannel> {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return emptyList()
        val nm = manager(context)
        return specs(context).mapNotNull { nm.getNotificationChannel(it.id) }
    }

    fun isEnabled(context: Context, id: String): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return false
        return manager(context).getNotificationChannel(id)?.importance
            ?.let { it != NotificationManager.IMPORTANCE_NONE } ?: false
    }

    /** Enables/disables one channel by recreating it with new importance. */
    fun setEnabled(context: Context, id: String, enabled: Boolean) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val spec = specs(context).firstOrNull { it.id == id } ?: return
        val nm = manager(context)
        nm.deleteNotificationChannel(id)
        nm.createNotificationChannel(
            NotificationChannel(
                id,
                context.getString(spec.nameRes),
                if (enabled) spec.importance else NotificationManager.IMPORTANCE_NONE,
            ).apply { description = context.getString(spec.descRes) },
        )
    }

    fun setAllEnabled(context: Context, enabled: Boolean) {
        for (s in specs(context)) setEnabled(context, s.id, enabled)
    }

    /** Deep-link target: the system screen for one channel. */
    fun channelSettingsIntent(context: Context, id: String) =
        android.content.Intent(android.provider.Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS)
            .putExtra(android.provider.Settings.EXTRA_APP_PACKAGE, context.packageName)
            .putExtra(android.provider.Settings.EXTRA_CHANNEL_ID, id)
}
