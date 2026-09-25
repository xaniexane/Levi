package dev.levi.inference

import org.junit.Assert.*
import org.junit.Test

class InferenceModelsTest {

    @Test
    fun `levi is the default selected model`() {
        assertEquals(ModelCatalog.LEVI_TINY, ModelCatalog.defaultModel())
        assertEquals("levi-tiny", ModelCatalog.defaultModel().id)
    }

    @Test
    fun `headliner list is the levi family only`() {
        val ids = ModelCatalog.leviFamily.map { it.id }
        assertEquals(listOf("levi-tiny"), ids)
        assertEquals(ModelCatalog.leviFamily, ModelCatalog.models)
    }

    @Test
    fun `every family model is levi native - no third-party bases, no masks`() {
        for (model in ModelCatalog.leviFamily) {
            assertEquals("LEVI native", model.baseModel)
            assertTrue(model.displayName.startsWith("Levi"))
        }
    }

    @Test
    fun `open-source alternatives wear their own names, never levi's`() {
        assertTrue(ModelCatalog.openSourceModels.isNotEmpty())
        for (model in ModelCatalog.openSourceModels) {
            assertFalse(model.displayName.startsWith("Levi"))
            assertFalse(model.id.startsWith("levi-"))
            assertNotEquals("LEVI native", model.baseModel)
            assertTrue(model.tagline.contains("Open source"))
        }
        assertEquals("Qwen3-0.6B", ModelCatalog.OPEN_QWEN_0_6B.baseModel)
        assertEquals("Qwen3-4B", ModelCatalog.OPEN_QWEN_4B.baseModel)
    }

    @Test
    fun `levi-tiny is announced but not downloadable`() {
        assertFalse(ModelCatalog.LEVI_TINY.available)
        assertNull(ModelCatalog.LEVI_TINY.downloadUrl)
        assertEquals("LEVI native", ModelCatalog.LEVI_TINY.baseModel)
    }

    @Test
    fun `cloud is purely Levi — no third-party provider endpoints`() {
        val ids = ModelCatalog.externalSources.map { it.id }
        assertEquals(listOf("levi-si-cloud"), ids)
        assertFalse(ModelCatalog.leviFamily.any { it.id in ids })
    }

    @Test
    fun `recommendedFor picks the largest downloadable that fits`() {
        assertEquals(ModelCatalog.OPEN_QWEN_4B, ModelCatalog.recommendedFor(8192))
        assertEquals(ModelCatalog.OPEN_QWEN_0_6B, ModelCatalog.recommendedFor(2048))
        // Falls back to the default when nothing downloadable fits.
        assertEquals(ModelCatalog.defaultModel(), ModelCatalog.recommendedFor(256))
    }

    @Test
    fun `downloadable excludes announced-but-not-shipped models`() {
        val ids = ModelCatalog.downloadable.map { it.id }
        assertFalse(ids.contains("levi-tiny"))
        assertTrue(ids.contains("open-qwen3-0.6b"))
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
    fun `open-source download urls point at huggingface resolve`() {
        assertEquals(
            "https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q8_0.gguf",
            ModelCatalog.OPEN_QWEN_0_6B.downloadUrl,
        )
        assertEquals(
            "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf",
            ModelCatalog.OPEN_QWEN_4B.downloadUrl,
        )
    }
}
