package dev.levi.app.settings

import android.content.Context
import android.os.Bundle
import android.text.InputType
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.fragment.app.Fragment
import com.google.android.material.button.MaterialButton
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout
import dev.levi.app.R

/**
 * Secure credentials store: list/add/delete named secrets backed by
 * SettingsStore (EncryptedSharedPreferences). Everything works for real;
 * nothing here is a stub.
 */
class CredentialsFragment : Fragment() {

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

        val names = SettingsStore.credentialNames(ctx)
        val group = SettingsUi.group(ctx, getString(R.string.row_credentials))
        val rows = SettingsUi.rows(group)
        if (names.isEmpty()) {
            rows.addView(
                SettingsUi.emptyState(
                    ctx,
                    R.drawable.ic_key,
                    getString(R.string.creds_empty_title),
                    getString(R.string.creds_empty_body),
                ),
            )
        } else {
            names.forEachIndexed { i, name ->
                if (i > 0) rows.addView(SettingsUi.divider(ctx))
                rows.addView(
                    SettingsUi.row(ctx, R.drawable.ic_key, name) {
                        showCredential(ctx, name)
                    },
                )
            }
        }
        content.addView(group)

        val add = MaterialButton(ctx).apply {
            text = getString(R.string.creds_add)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply {
                val h = SettingsUi.dp(ctx, 16)
                setMargins(h, SettingsUi.dp(ctx, 12), h, 0)
            }
            setOnClickListener { showAddDialog(ctx) }
        }
        content.addView(add)
        content.addView(SettingsUi.note(ctx, getString(R.string.creds_note)))
    }

    /** Shows the secret in a non-editable TextView with Delete + Close. */
    private fun showCredential(ctx: Context, name: String) {
        val secret = SettingsStore.getCredential(ctx, name) ?: return
        val secretView = TextView(ctx).apply {
            text = secret
            textIsSelectable = true
            setTextColor(resources.getColor(R.color.text, null))
            setPadding(48, 24, 48, 8)
        }
        AlertDialog.Builder(ctx)
            .setTitle(name)
            .setView(secretView)
            .setPositiveButton(R.string.creds_delete) { _, _ ->
                confirmDelete(ctx, name)
            }
            .setNegativeButton(R.string.creds_close, null)
            .show()
    }

    private fun confirmDelete(ctx: Context, name: String) {
        AlertDialog.Builder(ctx)
            .setTitle(R.string.creds_delete_confirm_title)
            .setMessage(getString(R.string.creds_delete_confirm_body, name))
            .setPositiveButton(R.string.creds_delete) { _, _ ->
                SettingsStore.deleteCredential(ctx, name)
                Toast.makeText(ctx, R.string.creds_deleted, Toast.LENGTH_SHORT).show()
                render()
            }
            .setNegativeButton(R.string.creds_close, null)
            .show()
    }

    private fun showAddDialog(ctx: Context) {
        val pad = SettingsUi.dp(ctx, 24)
        val layout = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, SettingsUi.dp(ctx, 8), pad, 0)
        }
        val nameLayout = TextInputLayout(ctx).apply {
            hint = getString(R.string.creds_name_hint)
        }
        val nameInput = TextInputEditText(ctx).apply {
            inputType = InputType.TYPE_CLASS_TEXT
            setTextColor(resources.getColor(R.color.text, null))
        }
        nameLayout.addView(nameInput)
        val secretField = TextInputLayout(ctx).apply {
            hint = getString(R.string.creds_secret_hint)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { topMargin = SettingsUi.dp(ctx, 12) }
        }
        val secretInput = TextInputEditText(ctx).apply {
            inputType =
                InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            setTextColor(resources.getColor(R.color.text, null))
        }
        secretField.addView(secretInput)
        layout.addView(nameLayout)
        layout.addView(secretField)

        AlertDialog.Builder(ctx)
            .setTitle(R.string.creds_add)
            .setView(layout)
            .setPositiveButton(R.string.save, null)
            .setNegativeButton(android.R.string.cancel, null)
            .create()
            .also { dialog ->
                dialog.setOnShowListener {
                    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                        val name = nameInput.text.toString().trim()
                        val secret = secretInput.text.toString()
                        if (name.isBlank() || secret.isBlank()) {
                            nameLayout.error = getString(R.string.creds_blank)
                            return@setOnClickListener
                        }
                        nameLayout.error = null
                        try {
                            SettingsStore.putCredential(ctx, name, secret)
                        } catch (e: SettingsStore.SecureStorageException) {
                            Toast.makeText(
                                ctx,
                                R.string.secure_unavailable,
                                Toast.LENGTH_LONG,
                            ).show()
                            return@setOnClickListener
                        }
                        Toast.makeText(ctx, R.string.creds_saved, Toast.LENGTH_SHORT).show()
                        dialog.dismiss()
                        render()
                    }
                }
            }
            .show()
    }
}
