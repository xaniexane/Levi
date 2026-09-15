package dev.levi.inference

/**
 * Thin JNI boundary over liblevi_llama.so (llama.cpp + llama_jni.cpp).
 *
 * The native library is optional: if it is absent (module built without
 * running native/build-android.sh) every call site must check
 * [nativeAvailable]/[isLoaded] first and degrade gracefully. Calling an
 * external function without the library throws UnsatisfiedLinkError — the
 * [InferenceEngine] guards all of these.
 */
object LlamaBridge {

    val nativeAvailable: Boolean

    init {
        var ok = false
        try {
            System.loadLibrary("levi_llama")
            ok = true
        } catch (_: UnsatisfiedLinkError) {
            ok = false
        } catch (_: SecurityException) {
            ok = false
        }
        nativeAvailable = ok
    }

    /** Callback for streaming generation. Return false to cancel. */
    fun interface TokenCallback {
        fun onToken(token: String): Boolean
    }

    external fun nativeLoad(modelPath: String, nCtx: Int, nThreads: Int): Boolean
    external fun nativeUnload()
    external fun nativeIsLoaded(): Boolean

    /** Blocking generation; returns null on failure. Call off the UI thread. */
    external fun nativeGenerate(
        prompt: String,
        maxTokens: Int,
        temperature: Float,
        seed: Int,
    ): String?

    /** Streaming generation; returns false when the model is not loaded. */
    external fun nativeGenerateStream(
        prompt: String,
        maxTokens: Int,
        temperature: Float,
        seed: Int,
        callback: TokenCallback,
    ): Boolean

    /** Generation throughput in tokens/sec, or a negative value on failure. */
    external fun nativeBenchmark(prompt: String, nTokens: Int): Float

    external fun nativeContextSize(): Int

    fun isLoaded(): Boolean = nativeAvailable && nativeIsLoaded()
}
