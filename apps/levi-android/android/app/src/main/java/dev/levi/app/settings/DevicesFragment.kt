package dev.levi.app.settings

import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.Toast
import androidx.fragment.app.Fragment
import dev.levi.app.R

/**
 * Device info: this device's real facts plus a linked-devices section.
 * Linking is not wired yet, so that row carries an honest PENDING badge.
 */
class DevicesFragment : Fragment() {

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        val ctx = requireContext()
        val scroll = SettingsUi.pageScroll(ctx)
        val content = SettingsUi.pageContent(scroll)

        val thisDevice = SettingsUi.group(ctx, getString(R.string.dev_this_device))
        val rows = SettingsUi.rows(thisDevice)
        fun staticRow(iconRes: Int, title: String, subtitle: String?) {
            if (rows.childCount > 0) rows.addView(SettingsUi.divider(ctx))
            rows.addView(SettingsUi.row(ctx, iconRes, title, subtitle))
        }

        staticRow(
            R.drawable.ic_devices,
            getString(R.string.dev_model),
            "${Build.MANUFACTURER} ${Build.MODEL}",
        )
        staticRow(
            R.drawable.ic_info,
            getString(R.string.dev_android),
            "${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})",
        )
        staticRow(
            R.drawable.ic_download,
            getString(R.string.dev_app_version),
            appVersion(),
        )
        staticRow(
            R.drawable.ic_key,
            getString(R.string.dev_device_id),
            Settings.Secure.getString(ctx.contentResolver, Settings.Secure.ANDROID_ID),
        )
        content.addView(thisDevice)

        val linked = SettingsUi.group(ctx, getString(R.string.dev_linked))
        val linkedRows = SettingsUi.rows(linked)
        linkedRows.addView(
            SettingsUi.row(
                ctx,
                R.drawable.ic_devices,
                getString(R.string.dev_link_new),
                badge = getString(R.string.badge_pending),
                onClick = {
                    Toast.makeText(
                        ctx,
                        R.string.dev_link_pending_toast,
                        Toast.LENGTH_SHORT,
                    ).show()
                },
            ),
        )
        content.addView(linked)

        content.addView(SettingsUi.note(ctx, getString(R.string.dev_note)))
        return scroll
    }

    /** versionName (versionCode), with API 33+ PackageInfoFlags and API 28+ longVersionCode guards. */
    private fun appVersion(): String {
        val ctx = requireContext()
        return try {
            val info =
                if (Build.VERSION.SDK_INT >= 33) {
                    ctx.packageManager.getPackageInfo(
                        ctx.packageName,
                        PackageManager.PackageInfoFlags.of(0),
                    )
                } else {
                    @Suppress("DEPRECATION")
                    ctx.packageManager.getPackageInfo(ctx.packageName, 0)
                }
            val code =
                if (Build.VERSION.SDK_INT >= 28) info.longVersionCode
                else @Suppress("DEPRECATION") info.versionCode.toLong()
            "${info.versionName} ($code)"
        } catch (e: PackageManager.NameNotFoundException) {
            "?"
        }
    }
}
