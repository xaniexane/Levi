package dev.levi.app.tools

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.activity.result.contract.ActivityResultContracts
import androidx.fragment.app.Fragment
import dev.levi.app.R
import dev.levi.app.settings.SettingsUi

/**
 * Device tools screen: one toggle per on-device capability.
 *
 * The toggle is the user's standing consent for the agent runtime —
 * [ToolGateway] refuses to run a disabled tool no matter who asks.
 * Tools that need an Android runtime permission show a permission row
 * underneath; execution stays fail-closed until the permission is
 * actually granted, so a toggle ON is never enough by itself.
 */
class ToolsFragment : Fragment() {

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) {
            render()
        }

    private var content: ViewGroup? = null

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
        render() // permission state may have changed in system Settings
    }

    private fun render() {
        val ctx = requireContext()
        val root = content ?: return
        root.removeAllViews()

        root.addView(SettingsUi.note(ctx, getString(R.string.tools_note)))

        val group = SettingsUi.group(ctx, getString(R.string.tools_group))
        val rows = SettingsUi.rows(group)

        val specs = DeviceTools.specs(ctx)
        specs.forEachIndexed { index, spec ->
            if (index > 0) rows.addView(SettingsUi.divider(ctx))
            rows.addView(
                SettingsUi.switchRow(
                    ctx,
                    spec.iconRes,
                    getString(spec.titleRes),
                    subtitle(ctx, spec),
                    ToolStore.isEnabled(ctx, spec.name),
                ) { on -> ToolStore.setEnabled(ctx, spec.name, on) },
            )
            permissionRow(ctx, spec)?.let { rows.addView(it) }
        }

        root.addView(group)
        root.addView(SettingsUi.note(ctx, getString(R.string.tools_note2)))
    }

    private fun subtitle(ctx: android.content.Context, spec: ToolSpec): String {
        val perm = permissionLabel(spec.permission)
        val risk = when (spec.risk) {
            RiskLevel.LOW -> getString(R.string.tools_risk_low)
            RiskLevel.MEDIUM -> getString(R.string.tools_risk_medium)
            RiskLevel.HIGH -> getString(R.string.tools_risk_high)
        }
        val desc = getString(spec.descriptionRes)
        val base = if (perm != null) "$desc\n$perm · $risk" else "$desc\n$risk"
        val note = spec.noteRes?.let { "\n${getString(it)}" }.orEmpty()
        return base + note
    }

    private fun permissionLabel(permission: String?): String? = when (permission) {
        android.Manifest.permission.POST_NOTIFICATIONS -> getString(R.string.tools_perm_notifications)
        android.Manifest.permission.ACCESS_COARSE_LOCATION -> getString(R.string.tools_perm_location)
        else -> null
    }

    /**
     * Permission state row for tools that need a runtime permission.
     * Null when the tool needs none (or the permission is install-time on
     * this OS version).
     */
    private fun permissionRow(ctx: android.content.Context, spec: ToolSpec): View? {
        val permission = spec.permission ?: return null
        if (permission == android.Manifest.permission.POST_NOTIFICATIONS &&
            Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU
        ) {
            return null // install-time permission below Android 13
        }
        val granted = DeviceTools.hasPermission(ctx, permission)
        return SettingsUi.row(
            ctx,
            R.drawable.ic_shield,
            getString(R.string.tools_permission_title),
            if (granted) getString(R.string.tools_permission_granted)
            else getString(R.string.tools_permission_not_granted),
            badge = if (granted) null else getString(R.string.tools_permission_badge),
        ) {
            if (!granted) {
                permissionLauncher.launch(permission)
            } else {
                openAppSettings(ctx)
            }
        }
    }

    private fun openAppSettings(ctx: android.content.Context) {
        try {
            startActivity(
                Intent(
                    Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                    Uri.fromParts("package", ctx.packageName, null),
                ),
            )
        } catch (e: Exception) {
            // No-op: the row is informational at this point.
        }
    }
}
