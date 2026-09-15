package dev.levi.inference

import java.io.File

/**
 * Plain data types for the on-device inference module. All pure Kotlin, no
 * Android framework dependency beyond java.io — unit-testable on the JVM.
 *
 * Product framing: the on-device weights are the LEVI family. LEVI is always
 * the headliner and the default selection; anything else is a selectable
 * source, never the headliner.
 */

/**
 * A downloadable on-device model. [baseModel] names the underlying base
 * weights honestly (e.g. "Qwen3-0.6B") whenever LEVI packages a remix;
 * [available] is false for announced-but-not-yet-shipped family members
 * (levi-tiny), which the manager refuses to download.
 */
data class ModelInfo(
    val id: String,
    /** Headliner UI name, e.g. "Levi 0.6B". */
    val displayName: String,
    /** UI subtitle, e.g. "Levi remix · Qwen3 base". */
    val tagline: String,
    /** Honest base-weights label, e.g. "Qwen3-0.6B" or "LEVI native". */
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

/** A non-LEVI provider the user may select as an alternative source.
 *  Never the headliner, never the default. */
data class ExternalSource(
    val id: String,
    val displayName: String,
    val note: String,
)

object ModelCatalog {
    /** LEVI's own native brain — on-device build in progress, not yet downloadable. */
    val LEVI_TINY = ModelInfo(
        id = "levi-tiny",
        displayName = "Levi Tiny",
        tagline = "LEVI's own native brain · coming to on-device soon",
        baseModel = "LEVI native",
        repo = "",
        file = "",
        sizeBytes = 0L,
        sha256 = null,
        minRamMb = 512,
        quantLabel = "native",
        available = false,
    )

    /** Levi remix: Qwen3-based GGUF base, LEVI-packaged. */
    val LEVI_0_6B = ModelInfo(
        id = "levi-0.6b",
        displayName = "Levi 0.6B",
        tagline = "Levi remix · Qwen3 base",
        baseModel = "Qwen3-0.6B",
        repo = "Qwen/Qwen3-0.6B-GGUF",
        file = "Qwen3-0.6B-Q8_0.gguf",
        sizeBytes = 640L * 1024 * 1024,
        sha256 = null, // not advertised by the publisher; verified on demand
        minRamMb = 1536,
        quantLabel = "Q8_0",
    )

    /** Levi remix: Qwen3-based GGUF base, LEVI-packaged. */
    val LEVI_4B = ModelInfo(
        id = "levi-4b",
        displayName = "Levi 4B",
        tagline = "Levi remix · Qwen3 base",
        baseModel = "Qwen3-4B",
        repo = "Qwen/Qwen3-4B-GGUF",
        file = "Qwen3-4B-Q4_K_M.gguf",
        sizeBytes = 2_684_354_560L, // ~2.5 GiB
        sha256 = null,
        minRamMb = 4096,
        quantLabel = "Q4_K_M",
    )

    /** The LEVI family, headliner order. */
    val leviFamily: List<ModelInfo> = listOf(LEVI_TINY, LEVI_0_6B, LEVI_4B)

    /** Backwards-compatible alias: the headliner list. */
    val models: List<ModelInfo> get() = leviFamily

    /** Selectable sources — alternatives, never the default. */
    val externalSources: List<ExternalSource> = listOf(
        ExternalSource(
            id = "ollama",
            displayName = "Ollama",
            note = "A local server on your network. A selectable source — LEVI stays the headliner.",
        ),
        ExternalSource(
            id = "openai-compatible",
            displayName = "OpenAI-compatible endpoint",
            note = "Any OpenAI-style API as a selectable source.",
        ),
    )

    /** LEVI is the default selected model. Always. */
    fun defaultModel(): ModelInfo = LEVI_0_6B

    /**
     * Largest downloadable LEVI-family model that fits [totalRamMb];
     * falls back to the default when nothing fits.
     */
    fun recommendedFor(totalRamMb: Long): ModelInfo =
        leviFamily
            .filter { it.available && totalRamMb >= it.minRamMb }
            .maxByOrNull { it.sizeBytes }
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
