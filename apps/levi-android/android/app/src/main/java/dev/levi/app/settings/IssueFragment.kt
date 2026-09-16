package dev.levi.app.settings

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.Toast
import androidx.core.content.FileProvider
import androidx.fragment.app.Fragment
import com.google.android.material.button.MaterialButton
import com.google.android.material.checkbox.MaterialCheckBox
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout
import dev.levi.app.R
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Generates a markdown issue report on the device and lets the user send it
 * wherever they choose. Nothing is uploaded by this screen.
 */
class IssueFragment : Fragment() {

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        val ctx = requireContext()
        val scroll = SettingsUi.pageScroll(ctx)
        val content = SettingsUi.pageContent(scroll)

        val group = SettingsUi.group(ctx, getString(R.string.issue_group))
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

        val titleLayout = TextInputLayout(ctx).apply {
            hint = getString(R.string.issue_title_hint)
        }
        val titleInput = TextInputEditText(ctx).apply {
            inputType = InputType.TYPE_CLASS_TEXT
        }
        titleLayout.addView(titleInput)

        val descLayout = TextInputLayout(ctx).apply {
            hint = getString(R.string.issue_desc_hint)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { topMargin = SettingsUi.dp(ctx, 12) }
        }
        val descInput = TextInputEditText(ctx).apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
            minLines = 4
            gravity = Gravity.TOP
        }
        descLayout.addView(descInput)

        val includeDevice = MaterialCheckBox(ctx).apply {
            text = getString(R.string.issue_include_device)
            isChecked = true
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { topMargin = SettingsUi.dp(ctx, 12) }
        }

        val generate = MaterialButton(ctx).apply {
            text = getString(R.string.issue_generate)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { topMargin = SettingsUi.dp(ctx, 16) }
            setOnClickListener {
                val title = titleInput.text?.toString().orEmpty().trim()
                if (title.isEmpty()) {
                    titleLayout.error = getString(R.string.issue_title_empty)
                    return@setOnClickListener
                }
                titleLayout.error = null
                buildAndShare(
                    ctx,
                    title,
                    descInput.text?.toString().orEmpty().trim(),
                    includeDevice.isChecked,
                )
            }
        }

        form.addView(titleLayout)
        form.addView(descLayout)
        form.addView(includeDevice)
        form.addView(generate)
        rows.addView(form)

        content.addView(group)
        content.addView(SettingsUi.note(ctx, getString(R.string.issue_note)))
        return scroll
    }

    private fun buildAndShare(ctx: Context, title: String, desc: String, includeDevice: Boolean) {
        val stamp = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date())
        val file = File(ctx.cacheDir, "levi-issue-$stamp.md")
        try {
            file.writeText(reportMarkdown(ctx, title, desc, includeDevice))
        } catch (e: Exception) {
            Toast.makeText(ctx, R.string.issue_write_failed, Toast.LENGTH_LONG).show()
            return
        }
        try {
            val uri = FileProvider.getUriForFile(ctx, ctx.packageName + ".fileprovider", file)
            val send = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_STREAM, uri)
                putExtra(Intent.EXTRA_SUBJECT, title)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            startActivity(Intent.createChooser(send, getString(R.string.issue_generate)))
        } catch (e: Exception) {
            Toast.makeText(ctx, R.string.issue_share_failed, Toast.LENGTH_LONG).show()
        }
    }

    private fun reportMarkdown(
        ctx: Context,
        title: String,
        desc: String,
        includeDevice: Boolean,
    ): String {
        val sb = StringBuilder()
        sb.append("# LEVI issue report\n\n")
        sb.append("**Title:** ").append(title.replace("\n", " ")).append("\n\n")
        sb.append("## Description\n\n")
        sb.append(if (desc.isBlank()) "_No description provided._" else desc).append("\n\n")
        if (includeDevice) {
            sb.append("## Device info\n\n")
            sb.append("- Model: ").append(Build.MANUFACTURER).append(" ").append(Build.MODEL).append("\n")
            sb.append("- Android: ").append(Build.VERSION.RELEASE)
                .append(" (API ").append(Build.VERSION.SDK_INT).append(")\n")
            val pm = ctx.packageManager
            val info = try {
                if (Build.VERSION.SDK_INT >= 33) {
                    pm.getPackageInfo(ctx.packageName, PackageManager.PackageInfoFlags.of(0))
                } else {
                    @Suppress("DEPRECATION")
                    pm.getPackageInfo(ctx.packageName, 0)
                }
            } catch (e: Exception) {
                null
            }
            val code = info?.let {
                if (Build.VERSION.SDK_INT >= 28) it.longVersionCode else @Suppress("DEPRECATION") it.versionCode.toLong()
            }
            sb.append("- App version: ").append(info?.versionName ?: "unknown")
                .append(" (").append(code ?: "?").append(")\n")
            sb.append("- Report time: ")
                .append(SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date()))
                .append("\n\n")
        }
        sb.append("_Generated locally by the LEVI Android app._\n")
        return sb.toString()
    }
}
