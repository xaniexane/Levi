package dev.levi.inference

import org.junit.Assert.*
import org.junit.Test

/**
 * Contract tests for the JNI boundary that need no native library and no
 * emulator: they pin the degradation behavior every caller must rely on.
 */
class LlamaBridgeContractTest {

    @Test
    fun `nativeAvailable is a plain boolean, never throws`() {
        val available: Boolean = LlamaBridge.nativeAvailable
        // In unit tests (and in builds without native/build-android.sh)
        // the library is absent; the flag must simply report that.
        assertFalse(available)
    }

    @Test
    fun `engine reports unavailable without native lib`() {
        val engine = InferenceEngine()
        try {
            assertFalse(engine.isNativeAvailable())
            assertFalse(engine.isLoaded())

            val load = engine.load("/nonexistent.gguf")
            assertTrue(load is InferenceEngine.EngineResult.Unavailable)

            val gen = engine.generate("hello")
            assertTrue(gen is InferenceEngine.EngineResult.Unavailable)

            val stream = engine.generateStream("hello") { true }
            assertTrue(stream is InferenceEngine.EngineResult.Unavailable)

            val bench = engine.benchmark()
            assertTrue(bench is InferenceEngine.EngineResult.Unavailable)

            // Unload/shutdown must be safe no-ops.
            engine.unload()
            assertEquals(0, engine.contextSize())
        } finally {
            engine.shutdown()
        }
    }

    @Test
    fun `cancel before generation is harmless`() {
        val engine = InferenceEngine()
        try {
            engine.cancel() // no stream running; must not throw
        } finally {
            engine.shutdown()
        }
    }
}
