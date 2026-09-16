package dev.levi.app.settings

import android.app.AlertDialog
import android.content.Intent
import android.content.pm.ShortcutInfo
import android.content.pm.ShortcutManager
import android.graphics.drawable.Icon
import android.os.Bundle
import android.provider.Settings
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Toast
import androidx.fragment.app.Fragment
import dev.levi.app.MainActivity
import dev.levi.app.R
import dev.levi.app.SettingsActivity
import dev.levi.app.ServerConfig

/**
 * Root settings page: grouped cards mirroring the reference layout,
 * adapted to be LEVI-native. Rows that cannot work yet carry a visible
 * PENDING badge — nothing here pretends to work when it doesn't.
 */
class SettingsHomeFragment : Fragment() {

    private lateinit var scroll: ScrollView
    private lateinit var content: LinearLayout

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        scroll = SettingsUi.pageScroll(requireContext())
        content = SettingsUi.pageContent(scroll)
        render()
        return scroll
    }

    override fun onResume() {
        super.onResume()
        // Rebuild so subtitles (theme, lock state, profile) stay fresh.
        if (::content.isInitialized) render()
    }

    private fun open(fragment: Fragment, title: String) {
        (requireActivity() as SettingsActivity).open(fragment, title)
    }

    private fun render() {
        val ctx = requireContext()
        content.removeAllViews()

        // ---- Group 1: connections & device ----
        val g1 = SettingsUi.group(ctx, null)
        val r1 = SettingsUi.rows(g1)
        r1.addView(
            SettingsUi.row(
                ctx, R.drawable.ic_server,
                getString(R.string.row_server),
                ServerConfig.getUrl(ctx).ifBlank { getString(R.string.row_server_not_set) },
            ) { open(ServerFragment(), getString(R.string.row_server)) },
        )
        r1.addView(SettingsUi.divider(ctx))
        r1.addView(
            SettingsUi.row(ctx, R.drawable.ic_link, getString(R.string.row_connectors)) {
                open(ConnectorsFragment(), getString(R.string.row_connectors))
            },
        )
        r1.addView(SettingsUi.divider(ctx))
        r1.addView(
            SettingsUi.row(
                ctx, R.drawable.ic_wallet, getString(R.string.row_wallet),
                badge = getString(R.string.badge_pending),
            ) { open(WalletFragment(), getString(R.string.row_wallet)) },
        )
        r1.addView(SettingsUi.divider(ctx))
        r1.addView(
            SettingsUi.row(ctx, R.drawable.ic_key, getString(R.string.row_credentials)) {
                open(CredentialsFragment(), getString(R.string.row_credentials))
            },
        )
        r1.addView(SettingsUi.divider(ctx))
        r1.addView(
            SettingsUi.row(ctx, R.drawable.ic_shield, getString(R.string.row_permissions)) {
                open(PermissionsFragment(), getString(R.string.row_permissions))
            },
        )
        r1.addView(SettingsUi.divider(ctx))
        r1.addView(
            SettingsUi.row(ctx, R.drawable.ic_chat, getString(R.string.row_channels)) {
                open(ChannelsFragment(), getString(R.string.row_channels))
            },
        )
        r1.addView(SettingsUi.divider(ctx))
        r1.addView(
            SettingsUi.row(ctx, R.drawable.ic_devices, getString(R.string.row_devices)) {
                open(DevicesFragment(), getString(R.string.row_devices))
            },
        )
        content.addView(g1)

        // ---- Group 2: behavior ----
        val g2 = SettingsUi.group(ctx, null)
        val r2 = SettingsUi.rows(g2)
        r2.addView(
            SettingsUi.row(ctx, R.drawable.ic_bell, getString(R.string.row_notifications)) {
                open(NotificationsFragment(), getString(R.string.row_notifications))
            },
        )
        r2.addView(SettingsUi.divider(ctx))
        r2.addView(
            SettingsUi.row(
                ctx, R.drawable.ic_palette, getString(R.string.row_appearance),
                themeName(ctx),
            ) { open(AppearanceFragment(), getString(R.string.row_appearance)) },
        )
        r2.addView(SettingsUi.divider(ctx))
        r2.addView(
            SettingsUi.row(
                ctx, R.drawable.ic_lock, getString(R.string.row_applock),
                if (SettingsStore.isAppLockEnabled(ctx)) getString(R.string.state_on)
                else getString(R.string.state_off),
            ) { open(AppLockFragment(), getString(R.string.row_applock)) },
        )
        r2.addView(SettingsUi.divider(ctx))
        r2.addView(
            SettingsUi.row(ctx, R.drawable.ic_mic, getString(R.string.row_assistant)) {
                openAssistantSettings()
            },
        )
        r2.addView(SettingsUi.divider(ctx))
        r2.addView(
            SettingsUi.row(ctx, R.drawable.ic_home, getString(R.string.row_homescreen)) {
                pinShortcut()
            },
        )
        content.addView(g2)

        // ---- Group 3: data & help ----
        val g3 = SettingsUi.group(ctx, null)
        val r3 = SettingsUi.rows(g3)
        r3.addView(
            SettingsUi.row(ctx, R.drawable.ic_invite, getString(R.string.row_invite)) {
                open(InviteFragment(), getString(R.string.row_invite))
            },
        )
        r3.addView(SettingsUi.divider(ctx))
        r3.addView(
            SettingsUi.row(ctx, R.drawable.ic_database, getString(R.string.row_data)) {
                open(DataControlsFragment(), getString(R.string.row_data))
            },
        )
        r3.addView(SettingsUi.divider(ctx))
        r3.addView(
            SettingsUi.row(ctx, R.drawable.ic_flag, getString(R.string.row_issue)) {
                open(IssueFragment(), getString(R.string.row_issue))
            },
        )
        r3.addView(SettingsUi.divider(ctx))
        r3.addView(
            SettingsUi.row(ctx, R.drawable.ic_help, getString(R.string.row_help)) {
                open(HelpFragment(), getString(R.string.row_help))
            },
        )
        r3.addView(SettingsUi.divider(ctx))
        r3.addView(
            SettingsUi.row(ctx, R.drawable.ic_download, getString(R.string.row_updates)) {
                open(UpdatesFragment(), getString(R.string.row_updates))
            },
        )
        r3.addView(SettingsUi.divider(ctx))
        r3.addView(
            SettingsUi.row(ctx, R.drawable.ic_doc, getString(R.string.row_legal)) {
                open(LegalFragment(), getString(R.string.row_legal))
            },
        )
        content.addView(g3)

        // ---- Group 4: LEVI Account ----
        val g4 = SettingsUi.group(ctx, getString(R.string.section_account))
        val r4 = SettingsUi.rows(g4)
        val hasProfile = SettingsStore.hasProfile(ctx)
        r4.addView(
            SettingsUi.row(
                ctx, R.drawable.ic_person, getString(R.string.row_account),
                if (hasProfile) SettingsStore.profileName(ctx) else getString(R.string.row_account_setup),
            ) { open(AccountFragment(), getString(R.string.row_account)) },
        )
        if (hasProfile) {
            r4.addView(SettingsUi.divider(ctx))
            r4.addView(
                SettingsUi.row(ctx, R.drawable.ic_logout, getString(R.string.row_logout)) {
                    confirmLogout()
                },
            )
        }
        content.addView(g4)
    }

    private fun themeName(ctx: android.content.Context): String =
        when (SettingsStore.getTheme(ctx)) {
            SettingsStore.THEME_LIGHT -> getString(R.string.theme_light)
            SettingsStore.THEME_SYSTEM -> getString(R.string.theme_system)
            else -> getString(R.string.theme_void)
        }

    /** System voice-input settings — where the default assistant is chosen. */
    private fun openAssistantSettings() {
        try {
            startActivity(Intent(Settings.ACTION_VOICE_INPUT_SETTINGS))
        } catch (e: Exception) {
            Toast.makeText(
                requireContext(),
                getString(R.string.assistant_unavailable),
                Toast.LENGTH_SHORT,
            ).show()
        }
    }

    /** Pinned home-screen shortcut (Android 8+). */
    private fun pinShortcut() {
        val ctx = requireContext()
        val sm = ctx.getSystemService(ShortcutManager::class.java)
        if (sm == null || !sm.isRequestPinShortcutSupported) {
            Toast.makeText(ctx, getString(R.string.shortcut_unsupported), Toast.LENGTH_SHORT).show()
            return
        }
        val shortcut = ShortcutInfo.Builder(ctx, "levi_home")
            .setShortLabel("LEVI")
            .setLongLabel(getString(R.string.shortcut_label))
            .setIcon(Icon.createWithResource(ctx, R.mipmap.ic_launcher))
            .setIntent(Intent(ctx, MainActivity::class.java).setAction(Intent.ACTION_MAIN))
            .build()
        try {
            sm.requestPinShortcut(shortcut, null)
        } catch (e: Exception) {
            Toast.makeText(ctx, getString(R.string.shortcut_failed), Toast.LENGTH_SHORT).show()
        }
    }

    private fun confirmLogout() {
        val ctx = requireContext()
        AlertDialog.Builder(ctx)
            .setTitle(R.string.row_logout)
            .setMessage(R.string.logout_confirm)
            .setPositiveButton(R.string.row_logout) { _, _ ->
                SettingsStore.clearProfile(ctx)
                Toast.makeText(ctx, R.string.logged_out, Toast.LENGTH_SHORT).show()
                render()
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }
}
