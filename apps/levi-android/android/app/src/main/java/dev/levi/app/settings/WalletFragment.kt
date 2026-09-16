package dev.levi.app.settings

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.fragment.app.Fragment
import dev.levi.app.R

/**
 * Honestly empty: there is no wallet in this build. The empty state and
 * the PENDING row say so instead of faking balances.
 */
class WalletFragment : Fragment() {

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        val ctx = requireContext()
        val scroll = SettingsUi.pageScroll(ctx)
        val content = SettingsUi.pageContent(scroll)

        content.addView(
            SettingsUi.emptyState(
                ctx,
                R.drawable.ic_wallet,
                getString(R.string.wallet_empty_title),
                getString(R.string.wallet_empty_body),
            ),
        )

        val group = SettingsUi.group(ctx, null)
        val rows = SettingsUi.rows(group)
        rows.addView(
            SettingsUi.row(
                ctx,
                R.drawable.ic_wallet,
                getString(R.string.wallet_balances),
                null,
                getString(R.string.badge_pending),
            ) { Toast.makeText(ctx, R.string.wallet_balances_toast, Toast.LENGTH_SHORT).show() },
        )
        content.addView(group)

        content.addView(SettingsUi.note(ctx, getString(R.string.wallet_note)))
        return scroll
    }
}
