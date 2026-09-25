package dev.levi.app.settings

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.Toast
import androidx.fragment.app.Fragment
import dev.levi.app.R
import dev.levi.app.ServerConfig
import dev.levi.app.SettingsActivity

class ConnectorsFragment : Fragment() {
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
        // The server URL can change in the ServerFragment behind us — rebuild.
        if (::content.isInitialized) {
            content.removeAllViews()
            render()
        }
    }

    private fun render() {
        val ctx = requireContext()
        val g = SettingsUi.group(ctx, null)
        val rows = SettingsUi.rows(g)

        val serverUrl = ServerConfig.getUrl(ctx).ifBlank { getString(R.string.connectors_server_unset) }
        rows.addView(
            SettingsUi.row(
                ctx,
                R.drawable.ic_server,
                getString(R.string.connectors_server),
                serverUrl,
            ) {
                (requireActivity() as SettingsActivity).open(ServerFragment(), getString(R.string.connectors_server))
            },
        )

        rows.addView(SettingsUi.divider(ctx))

        val pending = getString(R.string.badge_pending)
        rows.addView(
            SettingsUi.row(
                ctx,
                R.drawable.ic_chat,
                getString(R.string.connectors_messenger),
                null,
                pending,
            ) {
                Toast.makeText(ctx, R.string.connectors_pending_toast, Toast.LENGTH_SHORT).show()
            },
        )
        rows.addView(SettingsUi.divider(ctx))
        rows.addView(
            SettingsUi.row(
                ctx,
                R.drawable.ic_chat,
                getString(R.string.connectors_whatsapp),
                null,
                pending,
            ) {
                Toast.makeText(ctx, R.string.connectors_pending_toast, Toast.LENGTH_SHORT).show()
            },
        )

        content.addView(g)
        content.addView(SettingsUi.note(ctx, getString(R.string.connectors_note)))
    }
}
