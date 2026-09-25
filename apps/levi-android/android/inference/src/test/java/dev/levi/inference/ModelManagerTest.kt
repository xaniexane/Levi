package dev.levi.inference

import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.nio.file.Files

class ModelManagerTest {

    @Test
    fun `parseContentRange extracts total`() {
        assertEquals(1000L, ModelManager.parseContentRange("bytes 100-200/1000"))
        assertEquals(640L * 1024 * 1024, ModelManager.parseContentRange("bytes 0-99/671088640"))
    }

    @Test
    fun `parseContentRange returns null for junk`() {
        assertNull(ModelManager.parseContentRange(null))
        assertNull(ModelManager.parseContentRange("bytes 0-99"))
        assertNull(ModelManager.parseContentRange("garbage"))
    }

    @Test
    fun `buildRangeHeader formats resume offset`() {
        assertEquals("bytes=12345-", ModelManager.buildRangeHeader(12345))
        assertEquals("bytes=0-", ModelManager.buildRangeHeader(0))
    }

    @Test
    fun `sha256Of matches known digest`() {
        val dir = Files.createTempDirectory("levi-mm-test").toFile()
        try {
            val f = File(dir, "a.bin")
            f.writeBytes("levi".toByteArray())
            // sha256("levi"), verified with sha256sum on the host.
            assertEquals(
                "c3c0a114bf9769f107003aca3157da439936a06b03e2d6f0e05965e742453bf2",
                ModelManager.sha256Of(f),
            )
            // Deterministic across calls.
            assertEquals(ModelManager.sha256Of(f), ModelManager.sha256Of(f))
        } finally {
            dir.deleteRecursively()
        }
    }

    @Test
    fun `catalog urls are well-formed https`() {
        for (m in ModelCatalog.models) {
            if (!m.available) continue
            val url = m.downloadUrl!!
            assertTrue(url.startsWith("https://huggingface.co/"))
            assertTrue(url.endsWith(".gguf"))
            assertTrue(m.sizeBytes > 0)
            assertTrue(m.minRamMb > 0)
        }
    }

    @Test
    fun `download refuses models that are not available yet`() {
        val dir = Files.createTempDirectory("levi-mm-test3").toFile()
        try {
            val mgr = ModelManager(dir)
            try {
                mgr.download(ModelCatalog.LEVI_TINY)
                fail("expected IOException for levi-tiny")
            } catch (e: java.io.IOException) {
                assertTrue(e.message!!.contains("Levi Tiny"))
            }
        } finally {
            dir.deleteRecursively()
        }
    }

    @Test
    fun `installedModels lists gguf files only`() {
        val dir = Files.createTempDirectory("levi-mm-test2").toFile()
        try {
            File(dir, "a.gguf").writeBytes(ByteArray(8))
            File(dir, "b.gguf.part").writeBytes(ByteArray(8))
            File(dir, "notes.txt").writeBytes(ByteArray(8))
            val mgr = ModelManager(dir)
            val installed = mgr.installedModels()
            assertEquals(1, installed.size)
            assertEquals("a.gguf", installed[0].name)
        } finally {
            dir.deleteRecursively()
        }
    }
}
