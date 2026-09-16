package dev.levi.app.settings

import android.content.Context
import android.content.Intent
import android.text.InputType
import android.widget.EditText
import android.widget.LinearLayout
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import com.google.android.material.textfield.TextInputLayout
import dev.levi.app.LockActivity
import dev.levi.app.R

/**
 * App-lock state + biometric / PIN helpers.
 *
 * `unlocked` is process-local: killing the app re-arms the lock, which is
 * the safe default. The enabled flag and PIN hash live in the encrypted
 * store (SettingsStore).
 */
object AppLock {
    @Volatile
    var unlocked: Boolean = false

    /**
     * Launches [LockActivity] when app lock is enabled and this process has
     * not unlocked yet. Returns true when the lock screen was shown (the
     * caller should not continue setting up protected UI).
     *
     * Fail-closed: if the secure store cannot be read, the lock state is
     * unknown, so the lock screen is shown rather than letting anyone in.
     */
    fun requireUnlock(activity: AppCompatActivity): Boolean {
        val locked =
            try {
                SettingsStore.isAppLockEnabled(activity)
            } catch (e: SettingsStore.SecureStorageException) {
                true
            }
        if (!locked || unlocked) return false
        activity.startActivity(Intent(activity, LockActivity::class.java))
        return true
    }

    fun canUseBiometrics(context: Context): Boolean =
        BiometricManager.from(context).canAuthenticate(
            BiometricManager.Authenticators.BIOMETRIC_WEAK,
        ) == BiometricManager.BIOMETRIC_SUCCESS

    fun promptBiometric(
        activity: FragmentActivity,
        title: String,
        subtitle: String?,
        onSuccess: () -> Unit,
        onError: (String) -> Unit,
    ) {
        val executor = ContextCompat.getMainExecutor(activity)
        val prompt = BiometricPrompt(
            activity,
            executor,
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    onSuccess()
                }

                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    onError(errString.toString())
                }
            },
        )
        val info = BiometricPrompt.PromptInfo.Builder()
            .setTitle(title)
            .apply { subtitle?.let { setSubtitle(it) } }
            // Biometric-only authenticators require an explicit negative
            // button, otherwise authenticate() throws.
            .setNegativeButtonText(activity.getString(android.R.string.cancel))
            .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_WEAK)
            .build()
        prompt.authenticate(info)
    }

    /**
     * Two-entry PIN setup dialog. Calls [onPin] with the PIN when both
     * entries match and are 4+ digits.
     */
    fun pinSetupDialog(context: Context, onPin: (String) -> Unit) {
        val pad = 48
        val layout = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, 24, pad, 8)
        }
        fun pinField(hint: String): EditText {
            val til = TextInputLayout(context).apply { this.hint = hint }
            val et = EditText(context).apply {
                inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD
            }
            til.addView(et)
            layout.addView(til)
            return et
        }
        val first = pinField(context.getString(R.string.applock_pin_new))
        val second = pinField(context.getString(R.string.applock_pin_confirm))
        AlertDialog.Builder(context)
            .setTitle(R.string.applock_pin_title)
            .setView(layout)
            .setPositiveButton(R.string.save, null)
            .setNegativeButton(android.R.string.cancel, null)
            .create()
            .also { dialog ->
                dialog.setOnShowListener {
                    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                        val a = first.text.toString()
                        val b = second.text.toString()
                        when {
                            a.length < 4 -> first.error =
                                context.getString(R.string.applock_pin_too_short)
                            a != b -> second.error =
                                context.getString(R.string.applock_pin_mismatch)
                            else -> {
                                onPin(a)
                                dialog.dismiss()
                            }
                        }
                    }
                }
            }
            .show()
    }
}
