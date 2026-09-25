package dev.levi.app.settings

import android.content.Intent
import android.os.Bundle
import android.provider.Settings as AndroidSettings
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import androidx.fragment.app.Fragment
import dev.levi.app.R

class NotificationsFragment : Fragment() {
    private lateinit var content: LinearLayout

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        val ctx = requireContext()
        val scroll = SettingsUi.pageScroll(ctx)
        content = SettingsUi.pageContent(scroll)
        render()
        return scroll
    }

    override fun onResume() {
        super.onResume()
        if (::content.isInitialized) {
            content.removeAllViews()
            render()
        }
    }

    private fun refresh() {
        content.removeAllViews()
        render()
    }

    private fun render() {
        val ctx = requireContext()
        val g = SettingsUi.group(ctx, null)
        val rows = SettingsUi.rows(g)

        rows.addView(
            SettingsUi.switchRow(
                ctx,
                R.drawable.ic_bell,
                getString(R.string.notifications_master),
                getString(R.string.notifications_master_desc),
                SettingsStore.notificationsOn(ctx),
            ) { on ->
                SettingsStore.setNotificationsOn(ctx, on)
                refresh()
            },
        )

        val channels = LeviChannels.channels(ctx)
        for (channel in channels) {
            rows.addView(SettingsUi.divider(ctx))
            rows.addView(
                SettingsUi.switchRow(
                    ctx,
                    R.drawable.ic_chat,
                    channel.name.toString(),
                    channel.description,
                    LeviChannels.isEnabled(ctx, channel.id),
                ) { enabled ->
                    LeviChannels.setEnabled(ctx, channel.id, enabled)
                    refresh()
                },
            )
        }

        rows.addView(SettingsUi.divider(ctx))
        rows.addView(
            SettingsUi.row(
                ctx,
                R.drawable.ic_info,
                getString(R.string.notifications_open_system),
                getString(R.string.notifications_open_system_desc),
            ) {
                val intent = Intent(AndroidSettings.ACTION_APP_NOTIFICATION_SETTINGS)
                    .putExtra(AndroidSettings.EXTRA_APP_PACKAGE, ctx.packageName)
                startActivity(intent)
            },
        )

        content.addView(g)
    }
}
