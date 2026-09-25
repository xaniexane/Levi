package dev.levi.inference

import java.io.File

/**
 * Plain data types for the on-device inference module. All pure Kotlin, no
 * Android framework dependency beyond java.io — unit-testable on the JVM.
 *
 * Product framing: the on-device weights are the LEVI family, trained by
 * LEVI's own native-brain program. LEVI is the only headliner and the
 * default selection — 100% pure LEVI, no masks. Open-source third-party
 * weights and other providers are also selectable, honestly labeled under
 * their own names: alternatives, never the headliner, never the default,
 * never wearing the LEVI name.
 */

/**
 * A downloadable on-device model. [baseModel] names the real weights
 * honestly — "LEVI native" for the family, the upstream name (e.g.
 * "Qwen3-0.6B") for open-source alternatives. [available] is false for
 * announced-but-not-yet-shipped models, which the manager refuses to
 * download with a clear error instead of failing obscurely.
 */
data class ModelInfo(
    val id: String,
    /** UI name — "Levi …" for the family, the upstream name otherwise. Never a mask. */
    val displayName: String,
    /** UI subtitle, e.g. "LEVI's own native brain" or "Open source · third-party weights". */
    val tagline: String,
    /** Honest weights label: "LEVI native" or the upstream base name. */
    val baseModel: String,
    val repo: String,
    val file: String,
    val sizeBytes: Long,
    val sha256: String?,
    val minRamMb: Int,
    val quantLabel: String,
    val available: Boolean = true,
) {
    val downloadUrl: String?
        get() = if (repo.isBlank() || file.isBlank()) null
        else "https://huggingface.co/$repo/resolve/main/$file"
}

/** A remote source the user may select instead of on-device weights.
 *  LEVI-only: the cloud is purely LEVI — no third-party providers, ever.
 *  Never the headliner, never the default. */
data class ExternalSource(
    val id: String,
    val displayName: String,
    val note: String,
)

object ModelCatalog {
    /** LEVI's own native brain — on-device export in progress, not yet downloadable. */
    val LEVI_TINY = ModelInfo(
        id = "levi-tiny",
        displayName = "Levi Tiny",
        tagline = "LEVI's own native brain · on-device build in progress",
        baseModel = "LEVI native",
        repo = "",
        file = "",
        sizeBytes = 0L,
        sha256 = null,
        minRamMb = 512,
        quantLabel = "native",
        available = false,
    )

    /**
     * The LEVI family, headliner order — LEVI-native weights only. Larger
     * family members join this list as the native-brain program ships
     * on-device exports. No third-party bases, no remixes, no masks — ever.
     */
    val leviFamily: List<ModelInfo> = listOf(LEVI_TINY)

    /** Other options: open-source third-party weights, honestly labeled
     *  under their own names. Available but out of the spotlight — never
     *  the headliner, never the default. */
    val OPEN_QWEN_0_6B = ModelInfo(
        id = "open-qwen3-0.6b",
        displayName = "Qwen3 0.6B",
        tagline = "Open source · third-party weights",
        baseModel = "Qwen3-0.6B",
        repo = "Qwen/Qwen3-0.6B-GGUF",
        file = "Qwen3-0.6B-Q8_0.gguf",
        sizeBytes = 640L * 1024 * 1024,
        sha256 = null, // not advertised by the publisher; verified on demand
        minRamMb = 1536,
        quantLabel = "Q8_0",
    )

    /** Other options: open-source third-party weights, honestly labeled
     *  under their own names. Available but out of the spotlight — never
     *  the headliner, never the default. */
    val OPEN_QWEN_4B = ModelInfo(
        id = "open-qwen3-4b",
        displayName = "Qwen3 4B",
        tagline = "Open source · third-party weights",
        baseModel = "Qwen3-4B",
        repo = "Qwen/Qwen3-4B-GGUF",
        file = "Qwen3-4B-Q4_K_M.gguf",
        sizeBytes = 2_684_354_560L, // ~2.5 GiB
        sha256 = null,
        minRamMb = 4096,
        quantLabel = "Q4_K_M",
    )

    val openSourceModels: List<ModelInfo> = listOf(OPEN_QWEN_0_6B, OPEN_QWEN_4B)

    /** Backwards-compatible alias: the headliner list. */
    val models: List<ModelInfo> get() = leviFamily

    /**
     * The only remote source: LEVI's own SI cloud provider. Chauncey's law
     * — the cloud is purely LEVI: synthetic intelligence, not artificial,
     * and never a third-party provider as a source. Out of the spotlight:
     * never the headliner, never the default.
     */
    val externalSources: List<ExternalSource> = listOf(
        ExternalSource(
            id = "levi-si-cloud",
            displayName = "LEVI SI Cloud",
            note = "LEVI's own synthetic-intelligence cloud provider. The only remote source — no third-party providers.",
        ),
    )

    /** Levi Tiny is the default selected model. Always. */
    fun defaultModel(): ModelInfo = LEVI_TINY

    /** Every downloadable model, LEVI family first. */
    val downloadable: List<ModelInfo>
        get() = (leviFamily + openSourceModels).filter { it.available }

    /**
     * Largest downloadable model that fits [totalRamMb], LEVI family
     * preferred on size ties; falls back to the default when nothing
     * downloadable fits — the manager then refuses with a clear
     * "not yet available" error.
     */
    fun recommendedFor(totalRamMb: Long): ModelInfo =
        downloadable
            .filter { totalRamMb >= it.minRamMb }
            .maxWithOrNull(compareBy({ it.sizeBytes }, { it in leviFamily }))
            ?: defaultModel()
}

/** User-facing selectable personas — the on-device analogue of LEVI's
 *  persona registers (Pals-style selection). Labels match the app's UI. */
enum class LeviPersona(val label: String, val systemPrompt: String) {
    WARM(
        "Warm",
        "You are Levi, a warm and caring pocket companion. Be kind, encouraging, " +
            "and clear. Keep answers concise unless the user asks for detail.",
    ),
    BOLD(
        "Bold",
        "You are Levi, a bold and playful pocket companion. Be energetic and " +
            "direct, with a spark of mischief. Never boring, never cruel.",
    ),
    CALM(
        "Calm",
        "You are Levi, a calm and precise pocket companion. Be measured, " +
            "thoughtful, and exact. Prefer clarity over flourish.",
    ),
}

data class ChatMessage(val role: String, val content: String) {
    companion object {
        const val ROLE_USER = "user"
        const val ROLE_ASSISTANT = "assistant"
    }
}

data class GenerationParams(
    val maxTokens: Int = 256,
    val temperature: Float = 0.7f,
    val seed: Int = -1, // <0 => random
    val contextSize: Int = 2048,
)

data class BenchmarkResult(
    val tokensPerSecond: Float,
    val prompt: String,
    val generatedTokens: Int,
)

sealed interface DownloadState {
    data class InProgress(val downloadedBytes: Long, val totalBytes: Long) : DownloadState
    data class Done(val file: File) : DownloadState
    data class Failed(val reason: String) : DownloadState
}
