package dev.levi.app.settings

import android.os.Bundle
import android.text.InputType
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.Toast
import androidx.fragment.app.Fragment
import com.google.android.material.button.MaterialButton
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout
import dev.levi.app.R

/**
 * The local LEVI profile. Display name + handle persist through
 * SettingsStore (encrypted, on-device). Cloud sync is visibly PENDING —
 * the badge is honest, the row does not pretend to sync.
 */
class AccountFragment : Fragment() {

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        val ctx = requireContext()
        val scroll = SettingsUi.pageScroll(ctx)
        val content = SettingsUi.pageContent(scroll)

        val group = SettingsUi.group(ctx, getString(R.string.account_group))
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

        val nameLayout = TextInputLayout(ctx).apply {
            hint = getString(R.string.account_name_hint)
        }
        val nameInput = TextInputEditText(ctx).apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PERSON_NAME
            setText(SettingsStore.profileName(ctx))
        }
        nameLayout.addView(nameInput)

        val handleLayout = TextInputLayout(ctx).apply {
            hint = getString(R.string.account_handle_hint)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { topMargin = SettingsUi.dp(ctx, 12) }
        }
        val handleInput = TextInputEditText(ctx).apply {
            inputType = InputType.TYPE_CLASS_TEXT
            setText(SettingsStore.profileHandle(ctx))
        }
        handleLayout.addView(handleInput)

        val save = MaterialButton(ctx).apply {
            text = getString(R.string.account_save)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { topMargin = SettingsUi.dp(ctx, 16) }
            setOnClickListener {
                try {
                    SettingsStore.setProfileName(ctx, nameInput.text?.toString().orEmpty())
                    SettingsStore.setProfileHandle(ctx, handleInput.text?.toString().orEmpty())
                } catch (e: SettingsStore.SecureStorageException) {
                    Toast.makeText(ctx, R.string.secure_unavailable, Toast.LENGTH_LONG).show()
                    return@setOnClickListener
                }
                Toast.makeText(ctx, R.string.account_saved, Toast.LENGTH_SHORT).show()
            }
        }

        form.addView(nameLayout)
        form.addView(handleLayout)
        form.addView(save)
        rows.addView(form)
        content.addView(group)

        val syncGroup = SettingsUi.group(ctx, null)
        val syncRows = SettingsUi.rows(syncGroup)
        syncRows.addView(
            SettingsUi.row(
                ctx,
                R.drawable.ic_info,
                getString(R.string.account_cloud_sync),
                getString(R.string.account_cloud_sync_sub),
                getString(R.string.badge_pending),
            ) { Toast.makeText(ctx, R.string.account_cloud_sync_toast, Toast.LENGTH_SHORT).show() },
        )
        content.addView(syncGroup)

        content.addView(SettingsUi.note(ctx, getString(R.string.account_note)))
        return scroll
    }
}
