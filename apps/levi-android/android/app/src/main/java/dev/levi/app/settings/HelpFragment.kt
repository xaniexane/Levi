package dev.levi.app.settings

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.fragment.app.Fragment
import dev.levi.app.R

/**
 * Bundled FAQ answered entirely from static text, plus links to the GitHub
 * repo and the Android app docs. There is no support chat in this build —
 * the notes say so honestly.
 */
class HelpFragment : Fragment() {

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        val ctx = requireContext()
        val scroll = SettingsUi.pageScroll(ctx)
        val content = SettingsUi.pageContent(scroll)

        content.addView(SettingsUi.note(ctx, faqBlock(ctx)))
        content.addView(SettingsUi.note(ctx, faqBlock2(ctx)))

        val group = SettingsUi.group(ctx, null)
        val rows = SettingsUi.rows(group)
        rows.addView(
            SettingsUi.row(
                ctx,
                R.drawable.ic_link,
                getString(R.string.help_github),
                getString(R.string.help_github_sub),
            ) { openUrl("https://github.com/xaniexane/Levi") },
        )
        rows.addView(SettingsUi.divider(ctx))
        rows.addView(
            SettingsUi.row(
                ctx,
                R.drawable.ic_doc,
                getString(R.string.help_docs),
                getString(R.string.help_docs_sub),
            ) { openUrl("https://github.com/xaniexane/Levi/blob/main/docs/ANDROID_APP.md") },
        )
        content.addView(group)

        content.addView(SettingsUi.note(ctx, getString(R.string.help_note)))
        return scroll
    }

    private fun faqBlock(ctx: Context): String =
        "Q: " + ctx.getString(R.string.help_faq_server_q) + "\n" +
            "A: " + ctx.getString(R.string.help_faq_server_a) + "\n\n" +
            "Q: " + ctx.getString(R.string.help_faq_http_q) + "\n" +
            "A: " + ctx.getString(R.string.help_faq_http_a)

    private fun faqBlock2(ctx: Context): String =
        "Q: " + ctx.getString(R.string.help_faq_applock_q) + "\n" +
            "A: " + ctx.getString(R.string.help_faq_applock_a) + "\n\n" +
            "Q: " + ctx.getString(R.string.help_faq_data_q) + "\n" +
            "A: " + ctx.getString(R.string.help_faq_data_a)

    private fun openUrl(url: String) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        } catch (e: Exception) {
            Toast.makeText(requireContext(), R.string.help_open_failed, Toast.LENGTH_LONG).show()
        }
    }
}
