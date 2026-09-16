package dev.levi.app.settings

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import dev.levi.app.R

class AppearanceFragment : Fragment() {
    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        val ctx = requireContext()
        val scroll = SettingsUi.pageScroll(ctx)
        val content = SettingsUi.pageContent(scroll)
        val g = SettingsUi.group(ctx, null)
        val rows = SettingsUi.rows(g)

        val current = SettingsStore.getTheme(ctx)
        val on = getString(R.string.state_on)

        val options = listOf(
            Triple(SettingsStore.THEME_VOID, getString(R.string.theme_void), getString(R.string.appearance_void_desc)),
            Triple(SettingsStore.THEME_LIGHT, getString(R.string.theme_light), getString(R.string.appearance_light_desc)),
            Triple(SettingsStore.THEME_SYSTEM, getString(R.string.theme_system), getString(R.string.appearance_system_desc)),
        )

        options.forEachIndexed { index, (value, title, desc) ->
            if (index > 0) rows.addView(SettingsUi.divider(ctx))
            val subtitle = if (value == current) {
                getString(R.string.appearance_selected_suffix, on).let { "$desc $it" }
            } else {
                desc
            }
            rows.addView(
                SettingsUi.row(
                    ctx,
                    R.drawable.ic_palette,
                    title,
                    subtitle,
                ) {
                    if (SettingsStore.getTheme(ctx) != value) {
                        SettingsStore.setTheme(ctx, value)
                        requireActivity().recreate()
                    }
                },
            )
        }

        content.addView(g)
        content.addView(SettingsUi.note(ctx, getString(R.string.appearance_note)))
        return scroll
    }
}
