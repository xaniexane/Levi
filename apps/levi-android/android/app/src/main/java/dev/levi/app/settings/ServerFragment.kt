package dev.levi.app.settings

import android.os.Bundle
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
import dev.levi.app.ServerConfig

/**
 * The LEVI server URL configuration, moved from the old single-purpose
 * SettingsActivity into the settings page stack. Behavior is unchanged:
 * cleartext http:// is only accepted for loopback hosts (the network
 * security config denies it everywhere else).
 */
class ServerFragment : Fragment() {

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        val ctx = requireContext()
        val scroll = SettingsUi.pageScroll(ctx)
        val content = SettingsUi.pageContent(scroll)

        val group = SettingsUi.group(ctx, null)
        val rows = SettingsUi.rows(group)
        val pad = SettingsUi.dp(ctx, 16)

        val label = SettingsUi.note(ctx, getString(R.string.settings_server_label)).apply {
            setTextColor(resources.getColor(R.color.amber, null))
        }

        val urlLayout = TextInputLayout(ctx).apply {
            hint = getString(R.string.settings_url_hint)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { setMargins(pad, SettingsUi.dp(ctx, 8), pad, 0) }
        }
        val urlInput = TextInputEditText(ctx).apply {
            inputType = android.text.InputType.TYPE_TEXT_VARIATION_URI
            setTextColor(resources.getColor(R.color.text, null))
            setText(ServerConfig.getUrl(ctx))
        }
        urlLayout.addView(urlInput)

        val save = MaterialButton(ctx).apply {
            text = getString(R.string.save)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { setMargins(pad, SettingsUi.dp(ctx, 16), pad, 0) }
            setOnClickListener {
                val raw = urlInput.text.toString()
                if (ServerConfig.isInsecureHttp(raw)) {
                    urlLayout.error = getString(R.string.error_url_insecure)
                    return@setOnClickListener
                }
                val normalized = ServerConfig.normalize(raw)
                if (normalized == null) {
                    urlLayout.error = getString(R.string.error_url_invalid)
                    return@setOnClickListener
                }
                urlLayout.error = null
                ServerConfig.setUrl(ctx, normalized)
                Toast.makeText(
                    ctx,
                    if (normalized.isEmpty()) getString(R.string.url_cleared)
                    else getString(R.string.url_saved, normalized),
                    Toast.LENGTH_SHORT,
                ).show()
            }
        }

        val inner = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            addView(label)
            addView(urlLayout)
            addView(save)
        }
        // Rebuild the card content with the form (the DSL group ships an
        // empty row container; we use our own padded column instead).
        rows.removeAllViews()
        rows.addView(inner)
        content.addView(group)
        content.addView(SettingsUi.note(ctx, getString(R.string.settings_help)))
        return scroll
    }
}
