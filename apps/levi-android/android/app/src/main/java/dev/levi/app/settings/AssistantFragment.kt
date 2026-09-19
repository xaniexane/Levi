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
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.fragment.app.Fragment
import dev.levi.app.R
import dev.levi.app.voice.AssistantStatus
import dev.levi.app.voice.HeyLeviService
import dev.levi.app.voice.VoicePrefs

/**
 * "Set as default assistant" screen.
 *
 * - Shows the honest truth: whether LEVI is currently the system's default
 *   digital assistant (read from Settings.Secure; we can never set it
 *   ourselves — only the system picker can).
 * - If not default, offers the system screens where the user picks it.
 * - Microphone permission row: needed for the assistant voice plate.
 *   Requested here with a rationale, fails closed without it.
 */
class AssistantFragment : Fragment() {

    private lateinit var content: LinearLayout

    /** Set when the user flips the hotword toggle before mic is granted. */
    private var pendingHeyLeviStart = false

    private val requestMic =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) {
            if (pendingHeyLeviStart && isMicGranted()) {
                pendingHeyLeviStart = false
                enableHeyLevi(true)
            }
            render() // Granted or denied — show the truth.
        }

    /**
     * Android 13+: the hotword trigger's "tap to talk" pop-up needs this
     * to be seen. The listener itself works without it.
     */
    private val requestNotifs =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) {
            // Granted or denied — the toggle already reflects the truth.
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
        if (::content.isInitialized) render()
    }

    private fun isMicGranted(): Boolean =
        requireContext().checkSelfPermission(Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    private fun render() {
        val ctx = requireContext()
        content.removeAllViews()

        val group = SettingsUi.group(ctx, getString(R.string.row_assistant))
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

        val isDefault = AssistantStatus.isDefaultAssistant(ctx)
        addRow(
            R.drawable.ic_mic,
            getString(R.string.assistant_status_title),
            if (isDefault) getString(R.string.assistant_is_default)
            else getString(R.string.assistant_not_default),
        )

        if (!isDefault) {
            addRow(
                R.drawable.ic_devices,
                getString(R.string.assistant_choose_title),
                getString(R.string.assistant_choose_sub),
                onClick = { openDefaultAppsSettings() },
            )
        }

        addRow(
            R.drawable.ic_mic,
            getString(R.string.perm_mic_title),
            if (isMicGranted()) getString(R.string.perm_granted)
            else getString(R.string.perm_mic_sub),
            onClick = if (isMicGranted()) null else {
                { requestMic.launch(Manifest.permission.RECORD_AUDIO) }
            },
        )

        // "Hey LEVI" hotword: the switch shows the actual listener state,
        // not just the wish — if the service died, the toggle reads off.
        if (rows.childCount > 0) rows.addView(SettingsUi.divider(ctx))
        rows.addView(
            SettingsUi.switchRow(
                ctx,
                R.drawable.ic_mic,
                getString(R.string.hey_levi_title),
                getString(R.string.hey_levi_sub),
                HeyLeviService.running,
                onChecked = { checked ->
                    if (checked) {
                        if (!isMicGranted()) {
                            pendingHeyLeviStart = true
                            requestMic.launch(Manifest.permission.RECORD_AUDIO)
                        } else {
                            enableHeyLevi(true)
                        }
                    } else {
                        pendingHeyLeviStart = false
                        enableHeyLevi(false)
                    }
                    // The service starts asynchronously; re-render shortly
                    // so the switch shows the true state.
                    content.postDelayed({ render() }, 600)
                },
            ),
        )

        // Spoken read-back of chat replies (device TTS, off by default).
        if (rows.childCount > 0) rows.addView(SettingsUi.divider(ctx))
        rows.addView(
            SettingsUi.switchRow(
                ctx,
                R.drawable.ic_mic,
                getString(R.string.speak_replies_title),
                getString(R.string.speak_replies_sub),
                VoicePrefs.speakReplies(ctx),
                onChecked = { checked ->
                    VoicePrefs.setSpeakReplies(ctx, checked)
                },
            ),
        )

        content.addView(group)
        content.addView(
            SettingsUi.note(ctx, getString(R.string.assistant_note)),
        )
    }

    /**
     * Turns the "Hey LEVI" listener on or off. The preference records the
     * wish; [HeyLeviService.running] is the truth the toggle displays.
     */
    private fun enableHeyLevi(enabled: Boolean) {
        val ctx = requireContext()
        VoicePrefs.setHeyLeviEnabled(ctx, enabled)
        if (enabled) {
            HeyLeviService.start(ctx)
            // Android 13+: without this the trigger pop-up can't be seen.
            if (Build.VERSION.SDK_INT >= 33 &&
                ctx.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
                PackageManager.PERMISSION_GRANTED
            ) {
                requestNotifs.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        } else {
            HeyLeviService.stop(ctx)
        }
    }

    /**
     * Best-effort path to where the default assistant is chosen.
     * Stock Android: voice-input settings. Fallback: the default-apps
     * screen (API 24+). Last resort: this app's system details page.
     */
    private fun openDefaultAppsSettings() {
        val ctx = requireContext()
        val candidates = listOf(
            Intent(Settings.ACTION_VOICE_INPUT_SETTINGS),
            Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS)
                .takeIf { Build.VERSION.SDK_INT >= 24 },
            Intent(
                Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                Uri.fromParts("package", ctx.packageName, null),
            ),
        ).filterNotNull()
        for (intent in candidates) {
            try {
                startActivity(intent)
                return
            } catch (e: Exception) {
                // Try the next candidate.
            }
        }
        Toast.makeText(
            ctx,
            getString(R.string.assistant_unavailable),
            Toast.LENGTH_SHORT,
        ).show()
    }
}
