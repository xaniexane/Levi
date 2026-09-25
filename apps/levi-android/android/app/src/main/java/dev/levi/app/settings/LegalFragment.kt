package dev.levi.app.settings

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import dev.levi.app.R

/**
 * Copyright, embedded-library attribution and the honest privacy summary.
 * Static text only — nothing here needs a control.
 */
class LegalFragment : Fragment() {

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        val ctx = requireContext()
        val scroll = SettingsUi.pageScroll(ctx)
        val content = SettingsUi.pageContent(scroll)

        content.addView(SettingsUi.note(ctx, getString(R.string.legal_copyright)))
        content.addView(SettingsUi.note(ctx, getString(R.string.legal_licenses)))
        content.addView(SettingsUi.note(ctx, getString(R.string.legal_privacy)))
        return scroll
    }
}
