package dev.levi.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for [ServerConfig]'s pure URL helpers — the policy behind the
 * app's cleartext rejection and the network security config allow-list.
 *
 * Loopback-only means loopback-only: 127.0.0.0/8, "localhost", and the
 * emulator host 10.0.2.2. RFC-1918 LAN addresses must NOT cleartext.
 */
class ServerConfigTest {

    // ---- normalize() ----

    @Test
    fun normalize_httpsUnchanged() {
        assertEquals("https://example.com", ServerConfig.normalize("https://example.com"))
    }

    @Test
    fun normalize_stripsTrailingSlashes() {
        assertEquals("https://example.com", ServerConfig.normalize("https://example.com/"))
        assertEquals("https://example.com", ServerConfig.normalize("https://example.com///"))
    }

    @Test
    fun normalize_trimsWhitespace() {
        assertEquals("https://example.com", ServerConfig.normalize("  https://example.com/  "))
    }

    @Test
    fun normalize_missingSchemeRejected() {
        assertNull(ServerConfig.normalize("example.com"))
        assertNull(ServerConfig.normalize("ftp://example.com"))
    }

    @Test
    fun normalize_tooShortRejected() {
        assertNull(ServerConfig.normalize("http://"))
        assertNull(ServerConfig.normalize("https://a"))
    }

    @Test
    fun normalize_emptyIsEmptyNotNull() {
        assertEquals("", ServerConfig.normalize(""))
        assertEquals("", ServerConfig.normalize("   "))
    }

    @Test
    fun normalize_httpRejectedForNonLocalHost() {
        assertNull(ServerConfig.normalize("http://example.com"))
        assertNull(ServerConfig.normalize("http://192.168.1.10/"))
        assertNull(ServerConfig.normalize("http://10.0.0.5:8080/"))
    }

    @Test
    fun normalize_httpAllowedForLoopback() {
        assertEquals("http://127.0.0.1:8080", ServerConfig.normalize("http://127.0.0.1:8080/"))
        assertEquals("http://127.0.0.1", ServerConfig.normalize("http://127.0.0.1"))
        assertEquals("http://localhost", ServerConfig.normalize("http://localhost/"))
    }

    @Test
    fun normalize_httpAllowedForEmulatorHost() {
        assertEquals("http://10.0.2.2:8080", ServerConfig.normalize("http://10.0.2.2:8080"))
    }

    // ---- isInsecureHttp() ----

    @Test
    fun isInsecureHttp_trueForNonLocalCleartext() {
        assertTrue(ServerConfig.isInsecureHttp("http://example.com"))
        assertTrue(ServerConfig.isInsecureHttp("http://192.168.1.10/"))
    }

    @Test
    fun isInsecureHttp_falseForLocalCleartext() {
        assertFalse(ServerConfig.isInsecureHttp("http://127.0.0.1"))
        assertFalse(ServerConfig.isInsecureHttp("http://localhost/"))
        assertFalse(ServerConfig.isInsecureHttp("http://10.0.2.2:8080"))
    }

    @Test
    fun isInsecureHttp_falseForHttpsOrSchemaless() {
        assertFalse(ServerConfig.isInsecureHttp("https://example.com"))
        assertFalse(ServerConfig.isInsecureHttp("example.com"))
    }

    // ---- isLocalHost() ----

    @Test
    fun isLocalHost_loopbackTrue() {
        assertTrue(ServerConfig.isLocalHost("http://127.0.0.1/"))
        assertTrue(ServerConfig.isLocalHost("http://127.0.0.1:8080/path"))
    }

    @Test
    fun isLocalHost_loopbackRangeTrue() {
        assertTrue(ServerConfig.isLocalHost("http://127.5.6.7/"))
        assertTrue(ServerConfig.isLocalHost("http://127.255.255.255/"))
    }

    @Test
    fun isLocalHost_localhostAndEmulatorHostTrue() {
        assertTrue(ServerConfig.isLocalHost("http://localhost/"))
        assertTrue(ServerConfig.isLocalHost("http://10.0.2.2/"))
    }

    @Test
    fun isLocalHost_trailingDotHostTrue() {
        assertTrue(ServerConfig.isLocalHost("http://localhost./"))
        assertTrue(ServerConfig.isLocalHost("http://127.0.0.1./"))
    }

    @Test
    fun isLocalHost_uppercaseHostTrue() {
        assertTrue(ServerConfig.isLocalHost("HTTP://LOCALHOST/"))
        assertTrue(ServerConfig.isLocalHost("http://127.0.0.1/"))
    }

    @Test
    fun isLocalHost_rfc1918LanFalse() {
        assertFalse(ServerConfig.isLocalHost("http://192.168.1.1/"))
        assertFalse(ServerConfig.isLocalHost("http://192.168.0.1:8080/"))
        assertFalse(ServerConfig.isLocalHost("http://10.0.0.5/"))
        assertFalse(ServerConfig.isLocalHost("http://172.16.0.1/"))
    }

    @Test
    fun isLocalHost_publicHostFalse() {
        assertFalse(ServerConfig.isLocalHost("http://example.com/"))
        assertFalse(ServerConfig.isLocalHost("https://levi.example.com/path"))
    }

    @Test
    fun isLocalHost_emptyOrGarbageHostFalse() {
        assertFalse(ServerConfig.isLocalHost("http://"))
        assertFalse(ServerConfig.isLocalHost("http:///path"))
        assertFalse(ServerConfig.isLocalHost("http://not-an-ip/"))
    }
}
