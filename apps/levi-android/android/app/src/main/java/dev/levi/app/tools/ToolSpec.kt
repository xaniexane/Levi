package dev.levi.app.tools

import dev.levi.app.R

/**
 * Machine + UI contract for one on-device tool.
 *
 * The agent runtime invokes tools by [name] through [ToolGateway]; the
 * Tools settings screen renders one toggle row per spec.
 *
 * - [permission]: the Android runtime permission the implementation needs,
 *   or null when none is required. Execution is fail-closed when denied.
 * - [risk]: LOW (local, no data leaves the device and nothing launches),
 *   MEDIUM (launches another app / performs network I/O), HIGH
 *   (sensitive data — location — even though it stays on-device).
 */
enum class RiskLevel { LOW, MEDIUM, HIGH }

data class ParamSpec(
    val name: String,
    /** "string" | "integer" | "boolean" */
    val type: String,
    val required: Boolean,
    val description: String,
    val default: String? = null,
)

data class ToolSpec(
    /** Stable machine name, e.g. "notify". Never localized. */
    val name: String,
    val titleRes: Int,
    val descriptionRes: Int,
    val iconRes: Int,
    val permission: String?,
    val risk: RiskLevel,
    val params: List<ParamSpec>,
    /** Optional extra usage note shown under the toggle. */
    val noteRes: Int? = null,
)
