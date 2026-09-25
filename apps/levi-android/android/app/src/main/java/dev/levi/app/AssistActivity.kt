package dev.levi.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity

/**
 * The activity the system fires when LEVI is the default assistant and the
 * user triggers Assist (long-press home / assistant gesture) on a path that
 * resolves to an activity rather than the [dev.levi.app.voice] session.
 *
 * Security posture:
 * - Only ASSIST and VOICE_COMMAND actions are honored. Anything else (when
 *   not an explicit internal call) finishes immediately.
 * - Extras on *external* intents are ignored wholesale — no intent-spoofing
 *   surface, no internal data is ever read from or written to them.
 * - The internal mic-permission flow (EXTRA_REQUEST_MIC) is honored only on
 *   explicit intents addressed to this app's own package.
 *
 * Behavior: routes straight into [MainActivity] with a voice-input
 * affordance. No UI of its own — it never stays on screen.
 */
class AssistActivity : AppCompatActivity() {

    companion object {
        /** Internal: ask for RECORD_AUDIO, then finish. Explicit intents only. */
        const val EXTRA_REQUEST_MIC = "dev.levi.app.extra.REQUEST_MIC"

        private val ALLOWED_ACTIONS = setOf(
            Intent.ACTION_ASSIST,
            Intent.ACTION_VOICE_COMMAND,
        )
    }

    private val requestMic =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            Toast.makeText(
                this,
                if (granted) R.string.voice_mic_granted else R.string.voice_mic_denied,
                Toast.LENGTH_SHORT,
            ).show()
            finish()
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val intent = intent
        val isInternal = intent?.component?.packageName == packageName

        if (isInternal && intent.getBooleanExtra(EXTRA_REQUEST_MIC, false)) {
            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) ==
                PackageManager.PERMISSION_GRANTED
            ) {
                finish() // Already granted; nothing to do.
            } else {
                requestMic.launch(Manifest.permission.RECORD_AUDIO)
            }
            return
        }

        // External entry: validate the action, ignore every extra.
        val action = intent?.action
        if (action != null && action !in ALLOWED_ACTIONS) {
            finish()
            return
        }

        // Route into the chat with a voice-input affordance.
        val main = Intent(this, MainActivity::class.java)
            .setAction(Intent.ACTION_MAIN)
            .putExtra(MainActivity.EXTRA_START_VOICE, true)
        startActivity(main)
        finish()
    }
}
