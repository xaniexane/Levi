package dev.levi.app.settings

import android.content.Context
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.fragment.app.Fragment
import dev.levi.app.R

/**
 * App lock: require biometrics or PIN to open the app.
 *
 * The switch is re-rendered after every branch so it always reflects the
 * stored state — toggling it is only an *intent*; the flows below (or their
 * cancellation) decide what actually sticks.
 */
class AppLockFragment : Fragment() {

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
        render()
    }

    private fun render() {
        val ctx = requireContext()
        content.removeAllViews()

        val group = SettingsUi.group(ctx, getString(R.string.row_applock))
        val rows = SettingsUi.rows(group)
        rows.addView(
            SettingsUi.switchRow(
                ctx,
                R.drawable.ic_lock,
                getString(R.string.applock_switch_title),
                getString(R.string.applock_switch_sub),
                SettingsStore.isAppLockEnabled(ctx),
            ) { on -> onToggle(ctx, on) },
        )
        content.addView(group)
        content.addView(SettingsUi.note(ctx, getString(R.string.applock_note)))
    }

    private fun onToggle(ctx: Context, on: Boolean) {
        if (on) {
            if (!SettingsStore.secureAvailable(ctx)) {
                Toast.makeText(ctx, R.string.secure_unavailable, Toast.LENGTH_LONG).show()
                render()
                return
            }
            if (AppLock.canUseBiometrics(ctx)) {
                // requireActivity() is an AppCompatActivity (a FragmentActivity),
                // which is what promptBiometric needs.
                AppLock.promptBiometric(
                    requireActivity(),
                    getString(R.string.applock_prompt_title),
                    getString(R.string.applock_prompt_sub),
                    onSuccess = {
                        // Offer a PIN as fallback too.
                        AppLock.pinSetupDialog(ctx) { pin ->
                            SettingsStore.setPin(ctx, pin)
                            SettingsStore.setAppLockEnabled(ctx, true)
                            render()
                        }
                    },
                    onError = { msg ->
                        Toast.makeText(ctx, msg, Toast.LENGTH_SHORT).show()
                        render()
                    },
                )
            } else {
                AppLock.pinSetupDialog(ctx) { pin ->
                    SettingsStore.setPin(ctx, pin)
                    SettingsStore.setAppLockEnabled(ctx, true)
                    render()
                }
            }
            // The biometric / PIN dialogs are async. Until one of them
            // commits the change, the stored state is still "off" — re-render
            // now so the switch flips back off if the user cancels.
            render()
        } else {
            AlertDialog.Builder(ctx)
                .setTitle(R.string.applock_off_title)
                .setMessage(R.string.applock_off_body)
                .setPositiveButton(R.string.applock_off_confirm) { _, _ ->
                    SettingsStore.setAppLockEnabled(ctx, false)
                    render()
                }
                .setNegativeButton(android.R.string.cancel) { _, _ -> render() }
                .setOnCancelListener { render() }
                .show()
        }
    }
}
