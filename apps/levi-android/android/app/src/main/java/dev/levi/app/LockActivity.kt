package dev.levi.app

import android.content.Intent
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.button.MaterialButton
import dev.levi.app.databinding.ActivityLockBinding
import dev.levi.app.settings.AppLock
import dev.levi.app.settings.SettingsStore

/**
 * App-lock gate. Shown by [AppLock.requireUnlock] when the lock is enabled
 * and this process has not unlocked yet. Biometrics when enrolled, PIN
 * otherwise (or as a fallback). Success sets the process-local unlocked
 * flag and returns to the app's main screen; killing the app re-arms the
 * lock.
 *
 * Fail-closed: if the secure store cannot be opened, no verification is
 * possible, so the app stays locked behind an honest error screen.
 */
class LockActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLockBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!SettingsStore.secureAvailable(this)) {
            showBrokenStore()
            return
        }
        binding = ActivityLockBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val bioAvailable = AppLock.canUseBiometrics(this)
        binding.biometricButton.visibility = if (bioAvailable) View.VISIBLE else View.GONE
        binding.biometricButton.setOnClickListener { runBiometric() }

        binding.unlockButton.setOnClickListener {
            val pin = binding.pinInput.text.toString()
            try {
                if (SettingsStore.checkPin(this, pin)) {
                    unlock()
                } else {
                    binding.pinLayout.error = getString(R.string.applock_pin_wrong)
                }
            } catch (e: SettingsStore.SecureStorageException) {
                showBrokenStore()
            }
        }

        // Offer biometrics immediately when available.
        if (bioAvailable) runBiometric()
    }

    override fun onBackPressed() {
        // The lock cannot be dismissed with back — it guards the app.
        // (Deliberately not calling super.)
    }

    private fun runBiometric() {
        AppLock.promptBiometric(
            activity = this,
            title = getString(R.string.applock_biometric_title),
            subtitle = getString(R.string.applock_biometric_subtitle),
            onSuccess = { unlock() },
            onError = { msg ->
                Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
            },
        )
    }

    private fun unlock() {
        AppLock.unlocked = true
        // The protected activity finished itself when it launched the lock;
        // return the user to the app instead of stranding them at the
        // launcher.
        startActivity(Intent(this, MainActivity::class.java))
        finish()
    }

    /** Honest dead-end: verification is impossible, so the app stays locked. */
    private fun showBrokenStore() {
        val pad = (24 * resources.displayMetrics.density).toInt()
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(pad, pad, pad, pad)
        }
        layout.addView(
            TextView(this).apply {
                text = getString(R.string.applock_store_broken_title)
                textSize = 20f
                gravity = Gravity.CENTER
            },
        )
        layout.addView(
            TextView(this).apply {
                text = getString(R.string.applock_store_broken_body)
                gravity = Gravity.CENTER
                setPadding(0, pad / 2, 0, pad)
            },
        )
        layout.addView(
            MaterialButton(this).apply {
                text = getString(R.string.applock_store_broken_close)
                setOnClickListener { finishAffinity() }
            },
        )
        setContentView(layout)
    }
}
