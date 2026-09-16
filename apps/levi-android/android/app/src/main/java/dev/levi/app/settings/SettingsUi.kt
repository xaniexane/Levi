package dev.levi.app.settings

import android.content.Context
import android.graphics.Typeface
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView
import androidx.appcompat.widget.SwitchCompat
import androidx.core.content.ContextCompat
import com.google.android.material.card.MaterialCardView
import dev.levi.app.R

/**
 * Tiny DSL for building the LEVI settings pages in code: grouped
 * Material cards with rows, switch rows, badges and notes — the look of
 * the reference screenshots, in LEVI's void theme.
 */
object SettingsUi {
    fun dp(context: Context, v: Int): Int =
        TypedValue.applyDimension(
            TypedValue.COMPLEX_UNIT_DIP,
            v.toFloat(),
            context.resources.displayMetrics,
        ).toInt()

    /** Scrollable page; add groups to [pageContent]. */
    fun pageScroll(context: Context): ScrollView =
        ScrollView(context).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.MATCH_PARENT,
            )
            isFillViewport = true
        }

    fun pageContent(scroll: ScrollView): LinearLayout {
        val c = LinearLayout(scroll.context).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT,
                ScrollView.LayoutParams.WRAP_CONTENT,
            )
            val d = dp(scroll.context, 0)
            setPadding(d, dp(scroll.context, 8), d, dp(scroll.context, 24))
        }
        scroll.addView(c)
        return c
    }

    /** Small section label shown above a card (e.g. "LEVI Account"). */
    fun sectionLabel(context: Context, text: String): TextView =
        TextView(context).apply {
            this.text = text
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            setTextColor(ContextCompat.getColor(context, R.color.text_dim))
            val m = dp(context, 16)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { setMargins(dp(context, 28), m, m, dp(context, 6)) }
        }

    /**
     * Rounded card; returns the inner vertical container to add rows to.
     * Pass [title] for the small label above the card, null for none.
     */
    fun group(context: Context, title: String?): LinearLayout {
        val outer = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            )
        }
        if (title != null) outer.addView(sectionLabel(context, title))
        val card = MaterialCardView(context).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply {
                val h = dp(context, 16)
                setMargins(h, dp(context, 4), h, dp(context, 4))
            }
            radius = dp(context, 24).toFloat()
            setCardBackgroundColor(ContextCompat.getColor(context, R.color.void_panel))
            cardElevation = 0f
        }
        val inner = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            )
            setPadding(dp(context, 8), dp(context, 8), dp(context, 8), dp(context, 8))
        }
        card.addView(inner)
        outer.addView(card)
        outer.setTag(R.id.tag_group_inner, inner)
        return outer
    }

    /** The row container inside a [group] — add rows here. */
    fun rows(group: LinearLayout): LinearLayout =
        group.getTag(R.id.tag_group_inner) as LinearLayout

    fun divider(context: Context): View =
        View(context).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(context, 1),
            ).apply {
                setMargins(dp(context, 56), 0, dp(context, 16), 0)
            }
            setBackgroundColor(ContextCompat.getColor(context, R.color.divider))
        }

    private fun baseRow(context: Context): LinearLayout =
        LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            )
            setPadding(dp(context, 16), dp(context, 14), dp(context, 16), dp(context, 14))
            isClickable = true
            isFocusable = true
            val out = TypedValue()
            context.theme.resolveAttribute(
                android.R.attr.selectableItemBackground,
                out,
                true,
            )
            setBackgroundResource(out.resourceId)
        }

    private fun iconView(context: Context, iconRes: Int): ImageView =
        ImageView(context).apply {
            layoutParams = LinearLayout.LayoutParams(dp(context, 24), dp(context, 24))
            setImageResource(iconRes)
            setColorFilter(ContextCompat.getColor(context, R.color.text_dim))
        }

    private fun textBlock(context: Context, title: String, subtitle: String?): LinearLayout {
        val block = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
                .apply { marginStart = dp(context, 16) }
        }
        block.addView(
            TextView(context).apply {
                text = title
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
                setTextColor(ContextCompat.getColor(context, R.color.text))
            },
        )
        if (subtitle != null) {
            block.addView(
                TextView(context).apply {
                    text = subtitle
                    setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
                    setTextColor(ContextCompat.getColor(context, R.color.text_dim))
                    setPadding(0, dp(context, 2), 0, 0)
                },
            )
        }
        return block
    }

    /** Amber "PENDING"-style badge shown at the row's end. */
    fun badge(context: Context, text: String): TextView =
        TextView(context).apply {
            this.text = text
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 10f)
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(ContextCompat.getColor(context, R.color.amber))
            background = ContextCompat.getDrawable(context, R.drawable.badge_pending)
            val h = dp(context, 8)
            val v = dp(context, 4)
            setPadding(h, v, h, v)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { marginStart = dp(context, 8) }
        }

    private fun chevron(context: Context): ImageView =
        ImageView(context).apply {
            layoutParams = LinearLayout.LayoutParams(dp(context, 20), dp(context, 20))
                .apply { marginStart = dp(context, 8) }
            setImageResource(R.drawable.ic_chevron_right)
            setColorFilter(ContextCompat.getColor(context, R.color.text_dim))
        }

    /**
     * Standard navigation row. [badge] marks honestly-pending destinations.
     * [onClick] null => static row (no chevron).
     */
    fun row(
        context: Context,
        iconRes: Int,
        title: String,
        subtitle: String? = null,
        badge: String? = null,
        onClick: (() -> Unit)? = null,
    ): View = baseRow(context).apply {
        addView(iconView(context, iconRes))
        addView(textBlock(context, title, subtitle))
        if (badge != null) addView(badge(context, badge))
        if (onClick != null) {
            addView(chevron(context))
            setOnClickListener { onClick() }
        } else {
            isClickable = false
            isFocusable = false
        }
    }

    /** Row with a trailing switch. */
    fun switchRow(
        context: Context,
        iconRes: Int,
        title: String,
        subtitle: String?,
        checked: Boolean,
        onChecked: (Boolean) -> Unit,
    ): View = baseRow(context).apply {
        // The whole row isn't clickable; only the switch toggles.
        isClickable = false
        isFocusable = false
        setBackgroundResource(0)
        addView(iconView(context, iconRes))
        addView(textBlock(context, title, subtitle))
        addView(
            SwitchCompat(context).apply {
                this.isChecked = checked
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                ).apply { marginStart = dp(context, 8) }
                setOnCheckedChangeListener { _, isChecked -> onChecked(isChecked) }
            },
        )
    }

    /** Small explanatory paragraph inside a page. */
    fun note(context: Context, text: String): TextView =
        TextView(context).apply {
            this.text = text
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            setTextColor(ContextCompat.getColor(context, R.color.text_dim))
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply {
                val h = dp(context, 28)
                setMargins(h, dp(context, 4), h, dp(context, 4))
            }
        }

    /** Big empty-state block: icon + title + body. */
    fun emptyState(context: Context, iconRes: Int, title: String, body: String): LinearLayout =
        LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(context, 32), dp(context, 48), dp(context, 32), dp(context, 32))
            addView(
                ImageView(context).apply {
                    layoutParams = LinearLayout.LayoutParams(dp(context, 56), dp(context, 56))
                    setImageResource(iconRes)
                    setColorFilter(ContextCompat.getColor(context, R.color.text_dim))
                },
            )
            addView(
                TextView(context).apply {
                    text = title
                    setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f)
                    typeface = Typeface.DEFAULT_BOLD
                    setTextColor(ContextCompat.getColor(context, R.color.text))
                    setPadding(0, dp(context, 16), 0, 0)
                },
            )
            addView(
                TextView(context).apply {
                    text = body
                    setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
                    setTextColor(ContextCompat.getColor(context, R.color.text_dim))
                    gravity = Gravity.CENTER
                    setPadding(0, dp(context, 8), 0, 0)
                },
            )
        }
}
