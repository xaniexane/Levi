package dev.levi.app.settings

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import androidx.activity.result.contract.ActivityResultContracts
import androidx.fragment.app.Fragment
import dev.levi.app.R

/**
 * The permissions LEVI uses, with their real runtime status.
 *
 * INTERNET, ACCESS_NETWORK_STATE and USE_BIOMETRIC are install-time (normal)
 * permissions; POST_NOTIFICATIONS is runtime on API 33+ and requestable from
 * here. Nothing else is declared or used by the app.
 */
class PermissionsFragment : Fragment() {

    private lateinit var content: LinearLayout

    private val requestNotifications =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) {
            // Granted or denied — re-render so the row shows the truth.
            render()
        }

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
        render()
    }

    private fun isGranted(permission: String): Boolean =
        requireContext().checkSelfPermission(permission) ==
            PackageManager.PERMISSION_GRANTED

    private fun render() {
        val ctx = requireContext()
        content.removeAllViews()

        val group = SettingsUi.group(ctx, getString(R.string.row_permissions))
        val rows = SettingsUi.rows(group)

        fun addRow(
            iconRes: Int,
            title: String,
            subtitle: String?,
            onClick: (() -> Unit)? = null,
        ) {
            if (rows.childCount > 0) rows.addView(SettingsUi.divider(ctx))
            rows.addView(SettingsUi.row(ctx, iconRes, title, subtitle, onClick = onClick))
        }

        addRow(
            R.drawable.ic_shield,
            getString(R.string.perm_internet_title),
            if (isGranted(Manifest.permission.INTERNET)) getString(R.string.perm_granted_install)
            else getString(R.string.perm_not_granted),
        )
        addRow(
            R.drawable.ic_shield,
            getString(R.string.perm_network_title),
            if (isGranted(Manifest.permission.ACCESS_NETWORK_STATE)) getString(R.string.perm_granted_install)
            else getString(R.string.perm_not_granted),
        )
        addRow(
            R.drawable.ic_shield,
            getString(R.string.perm_biometric_title),
            if (isGranted(Manifest.permission.USE_BIOMETRIC)) getString(R.string.perm_granted_install)
            else getString(R.string.perm_not_granted),
        )

        // POST_NOTIFICATIONS: runtime permission only on API 33+; below that
        // it behaves like an install-time permission.
        val notificationsGranted =
            Build.VERSION.SDK_INT < 33 || isGranted(Manifest.permission.POST_NOTIFICATIONS)
        addRow(
            R.drawable.ic_shield,
            getString(R.string.perm_notifications_title),
            if (notificationsGranted) getString(R.string.perm_granted)
            else getString(R.string.perm_not_granted),
            onClick = if (notificationsGranted || Build.VERSION.SDK_INT < 33) null else {
                { requestNotifications.launch(Manifest.permission.POST_NOTIFICATIONS) }
            },
        )

        addRow(
            R.drawable.ic_info,
            getString(R.string.perm_open_system),
            null,
            onClick = {
                val intent = Intent(
                    Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                    Uri.fromParts("package", ctx.packageName, null),
                )
                startActivity(intent)
            },
        )

        content.addView(group)
        content.addView(SettingsUi.note(ctx, getString(R.string.perm_note)))
    }
}
