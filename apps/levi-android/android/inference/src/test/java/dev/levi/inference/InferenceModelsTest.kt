package dev.levi.inference

import org.junit.Assert.*
import org.junit.Test

class InferenceModelsTest {

    @Test
    fun `levi is the default selected model`() {
        assertEquals(ModelCatalog.LEVI_0_6B, ModelCatalog.defaultModel())
        assertEquals("levi-0.6b", ModelCatalog.defaultModel().id)
    }

    @Test
    fun `headliner list leads with the levi family`() {
        val ids = ModelCatalog.leviFamily.map { it.id }
        assertEquals(listOf("levi-tiny", "levi-0.6b", "levi-4b"), ids)
        assertEquals(ModelCatalog.leviFamily, ModelCatalog.models)
    }

    @Test
    fun `remixes label their base honestly`() {
        assertEquals("Qwen3-0.6B", ModelCatalog.LEVI_0_6B.baseModel)
        assertEquals("Qwen3-4B", ModelCatalog.LEVI_4B.baseModel)
        assertTrue(ModelCatalog.LEVI_0_6B.tagline.contains("Qwen3"))
        assertTrue(ModelCatalog.LEVI_4B.tagline.contains("Qwen3"))
        assertTrue(ModelCatalog.LEVI_0_6B.displayName.startsWith("Levi"))
    }

    @Test
    fun `levi-tiny is announced but not downloadable`() {
        assertFalse(ModelCatalog.LEVI_TINY.available)
        assertNull(ModelCatalog.LEVI_TINY.downloadUrl)
        assertEquals("LEVI native", ModelCatalog.LEVI_TINY.baseModel)
    }

    @Test
    fun `external sources are never the headliner`() {
        assertTrue(ModelCatalog.externalSources.isNotEmpty())
        val ids = ModelCatalog.externalSources.map { it.id }
        assertTrue(ids.contains("ollama"))
        assertFalse(ModelCatalog.leviFamily.any { it.id in ids })
    }

    @Test
    fun `recommendedFor picks the largest fitting levi model`() {
        assertEquals(ModelCatalog.LEVI_4B, ModelCatalog.recommendedFor(8192))
        assertEquals(ModelCatalog.LEVI_0_6B, ModelCatalog.recommendedFor(2048))
        // Falls back to the default when nothing fits.
        assertEquals(ModelCatalog.defaultModel(), ModelCatalog.recommendedFor(256))
    }

    @Test
    fun `persona labels match the app UI`() {
        val labels = LeviPersona.entries.map { it.label }.toSet()
        assertTrue(labels.contains("Warm"))
        assertTrue(labels.contains("Bold"))
        assertTrue(labels.contains("Calm"))
    }

    @Test
    fun `generation params carry sane defaults`() {
        val p = GenerationParams()
        assertTrue(p.maxTokens > 0)
        assertTrue(p.temperature in 0.0f..2.0f)
        assertTrue(p.contextSize >= 512)
    }

    @Test
    fun `download url points at huggingface resolve`() {
        assertEquals(
            "https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q8_0.gguf",
            ModelCatalog.LEVI_0_6B.downloadUrl,
        )
        assertEquals(
            "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf",
            ModelCatalog.LEVI_4B.downloadUrl,
        )
    }
}
