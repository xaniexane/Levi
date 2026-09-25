package dev.levi.inference

import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.Future
import java.util.concurrent.atomic.AtomicBoolean

/**
 * High-level on-device inference API. Owns the single-threaded execution
 * discipline (llama.cpp context is not thread-safe; the JNI layer also
 * serializes, but one caller thread keeps ordering sane).
 *
 * All results are honest about the native layer's absence: without
 * liblevi_llama.so every operation returns [EngineResult.Unavailable]
 * instead of throwing.
 */
class InferenceEngine(
    private val bridge: LlamaBridge = LlamaBridge,
    executor: ExecutorService = Executors.newSingleThreadExecutor { r ->
        Thread(r, "levi-inference").apply { isDaemon = true }
    },
) {
    sealed interface EngineResult<out T> {
        data class Ok<T>(val value: T) : EngineResult<T>
        data class Unavailable(val reason: String) : EngineResult<Nothing>
    }

    private val executor: ExecutorService = executor
    private val cancelled = AtomicBoolean(false)

    fun isNativeAvailable(): Boolean = bridge.nativeAvailable
    fun isLoaded(): Boolean = bridge.isLoaded()

    /** Load a GGUF model. Blocking — call off the UI thread or use [loadAsync]. */
    fun load(modelPath: String, params: GenerationParams = GenerationParams()): EngineResult<Unit> {
        if (!bridge.nativeAvailable) return EngineResult.Unavailable("native library not built")
        val threads = Runtime.getRuntime().availableProcessors().coerceIn(2, 8)
        val ok = bridge.nativeLoad(modelPath, params.contextSize, threads)
        return if (ok) EngineResult.Ok(Unit)
        else EngineResult.Unavailable("nativeLoad failed for $modelPath")
    }

    fun loadAsync(modelPath: String, params: GenerationParams = GenerationParams()): Future<EngineResult<Unit>> =
        executor.submit<EngineResult<Unit>> { load(modelPath, params) }

    fun unload() {
        if (bridge.isLoaded()) bridge.nativeUnload()
    }

    /** Blocking generation. */
    fun generate(prompt: String, params: GenerationParams = GenerationParams()): EngineResult<String> {
        if (!bridge.isLoaded()) return EngineResult.Unavailable("no model loaded")
        val text = bridge.nativeGenerate(prompt, params.maxTokens, params.temperature, params.seed)
            ?: return EngineResult.Unavailable("generation failed")
        return EngineResult.Ok(text)
    }

    fun generateAsync(prompt: String, params: GenerationParams = GenerationParams()): Future<EngineResult<String>> =
        executor.submit<EngineResult<String>> { generate(prompt, params) }

    /**
     * Streaming generation. [onToken] is invoked per piece on the inference
     * thread; return false from it (or call [cancel]) to stop early.
     */
    fun generateStream(
        prompt: String,
        params: GenerationParams = GenerationParams(),
        onToken: (String) -> Boolean,
    ): EngineResult<Unit> {
        if (!bridge.isLoaded()) return EngineResult.Unavailable("no model loaded")
        cancelled.set(false)
        val ok = bridge.nativeGenerateStream(
            prompt, params.maxTokens, params.temperature, params.seed,
            LlamaBridge.TokenCallback { piece ->
                if (cancelled.get()) false else onToken(piece)
            },
        )
        return if (ok) EngineResult.Ok(Unit)
        else EngineResult.Unavailable("streaming generation failed")
    }

    fun generateStreamAsync(
        prompt: String,
        params: GenerationParams = GenerationParams(),
        onToken: (String) -> Boolean,
    ): Future<EngineResult<Unit>> =
        executor.submit<EngineResult<Unit>> { generateStream(prompt, params, onToken) }

    /** Ask the in-flight stream to stop at the next token boundary. */
    fun cancel() {
        cancelled.set(true)
    }

    /** Throughput probe; negative tokensPerSecond means failure. */
    fun benchmark(prompt: String = "The quick brown fox", nTokens: Int = 32): EngineResult<BenchmarkResult> {
        if (!bridge.isLoaded()) return EngineResult.Unavailable("no model loaded")
        val tps = bridge.nativeBenchmark(prompt, nTokens)
        return if (tps < 0) EngineResult.Unavailable("benchmark failed")
        else EngineResult.Ok(BenchmarkResult(tps, prompt, nTokens))
    }

    fun contextSize(): Int = if (bridge.isLoaded()) bridge.nativeContextSize() else 0

    fun shutdown() {
        cancel()
        unload()
        executor.shutdownNow()
    }
}
