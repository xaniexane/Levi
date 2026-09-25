package dev.levi.app.settings

import android.os.Bundle
import android.text.InputType
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import androidx.fragment.app.Fragment
import com.google.android.material.button.MaterialButton
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout
import dev.levi.app.R

/**
 * Invite code entry. Codes are format-validated locally and stored
 * encrypted on this device — the screen says so plainly, because there is
 * no redemption server to validate against yet.
 */
class InviteFragment : Fragment() {

    companion object {
        private val CODE_REGEX = Regex("^LEVI-[A-Z0-9]{4}-[A-Z0-9]{4}$")
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        val ctx = requireContext()
        val scroll = SettingsUi.pageScroll(ctx)
        val content = SettingsUi.pageContent(scroll)

        // Container for the saved-code card; refreshed in place after redeem.
        val savedSlot = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            )
        }
        content.addView(savedSlot)

        fun refreshSaved() {
            savedSlot.removeAllViews()
            val saved = SettingsStore.inviteCode(ctx)
            if (saved.isBlank()) return
            val savedGroup = SettingsUi.group(ctx, null)
            val savedRows = SettingsUi.rows(savedGroup)
            savedRows.addView(
                SettingsUi.row(
                    ctx,
                    R.drawable.ic_invite,
                    getString(R.string.invite_saved_code),
                    saved,
                ),
            )
            savedSlot.addView(savedGroup)
            savedSlot.addView(SettingsUi.note(ctx, getString(R.string.invite_saved_local)))
        }
        refreshSaved()

        val group = SettingsUi.group(ctx, getString(R.string.invite_group))
        val rows = SettingsUi.rows(group)
        rows.removeAllViews()
        val pad = SettingsUi.dp(ctx, 16)
        val form = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { setMargins(pad, SettingsUi.dp(ctx, 8), pad, pad) }
        }

        val codeLayout = TextInputLayout(ctx).apply {
            hint = getString(R.string.invite_code_hint)
        }
        val codeInput = TextInputEditText(ctx).apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS
            setText(SettingsStore.inviteCode(ctx))
        }
        codeLayout.addView(codeInput)

        val redeem = MaterialButton(ctx).apply {
            text = getString(R.string.invite_redeem)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { topMargin = SettingsUi.dp(ctx, 16) }
            setOnClickListener {
                val code = codeInput.text?.toString().orEmpty().trim().uppercase()
                if (!CODE_REGEX.matches(code)) {
                    codeLayout.error = getString(R.string.invite_error)
                    return@setOnClickListener
                }
                codeLayout.error = null
                try {
                    SettingsStore.setInviteCode(ctx, code)
                } catch (e: SettingsStore.SecureStorageException) {
                    codeLayout.error = getString(R.string.secure_unavailable)
                    return@setOnClickListener
                }
                codeInput.setText(code)
                refreshSaved()
            }
        }

        form.addView(codeLayout)
        form.addView(redeem)
        rows.addView(form)
        content.addView(group)

        content.addView(SettingsUi.note(ctx, getString(R.string.invite_note)))
        return scroll
    }
}
