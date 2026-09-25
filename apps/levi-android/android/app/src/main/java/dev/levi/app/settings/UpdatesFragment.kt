package dev.levi.app.settings

import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import dev.levi.app.R

class UpdatesFragment : Fragment() {
    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        val ctx = requireContext()
        val scroll = SettingsUi.pageScroll(ctx)
        val content = SettingsUi.pageContent(scroll)
        val g = SettingsUi.group(ctx, null)
        val rows = SettingsUi.rows(g)

        rows.addView(
            SettingsUi.row(
                ctx,
                R.drawable.ic_info,
                getString(R.string.updates_installed),
                installedVersion(ctx),
            ),
        )

        rows.addView(SettingsUi.divider(ctx))
        rows.addView(
            SettingsUi.row(
                ctx,
                R.drawable.ic_download,
                getString(R.string.updates_check),
                getString(R.string.updates_check_desc),
            ) {
                startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(getString(R.string.updates_releases_url))))
            },
        )

        content.addView(g)
        content.addView(SettingsUi.note(ctx, getString(R.string.updates_note)))
        return scroll
    }

    private fun installedVersion(context: android.content.Context): String =
        try {
            val pm = context.packageManager
            val info = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                pm.getPackageInfo(context.packageName, PackageManager.PackageInfoFlags.of(0))
            } else {
                @Suppress("DEPRECATION")
                pm.getPackageInfo(context.packageName, 0)
            }
            info.versionName ?: "—"
        } catch (_: PackageManager.NameNotFoundException) {
            "—"
        }
}
