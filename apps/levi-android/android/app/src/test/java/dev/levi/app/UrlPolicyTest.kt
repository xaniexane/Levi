package dev.levi.app

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for [ServerConfig.isSameServerHost] — the WebView navigation
 * policy (extracted verbatim from MainActivity.isConfiguredHost).
 *
 * The authority (host[:port]) is compared whole: a different port is a
 * different host. That is the historical behavior, pinned here.
 */
class UrlPolicyTest {

    @Test
    fun sameSchemeAndHostDifferentPathIsTrue() {
        assertTrue(
            ServerConfig.isSameServerHost(
                "https://levi.example.com/chat",
                "https://levi.example.com/settings",
            ),
        )
    }

    @Test
    fun sameSchemeAndHostWithQueryIsTrue() {
        assertTrue(
            ServerConfig.isSameServerHost(
                "https://levi.example.com/chat?x=1",
                "https://levi.example.com",
            ),
        )
    }

    @Test
    fun differentHostIsFalse() {
        assertFalse(
            ServerConfig.isSameServerHost(
                "https://evil.example.com/",
                "https://levi.example.com/",
            ),
        )
    }

    @Test
    fun differentSchemeIsFalse() {
        assertFalse(
            ServerConfig.isSameServerHost(
                "http://levi.example.com/",
                "https://levi.example.com/",
            ),
        )
    }

    @Test
    fun httpsVsHttpIsFalse() {
        assertFalse(
            ServerConfig.isSameServerHost(
                "https://levi.example.com/",
                "http://levi.example.com/",
            ),
        )
    }

    @Test
    fun blankConfiguredIsFalse() {
        assertFalse(ServerConfig.isSameServerHost("https://levi.example.com/", ""))
        assertFalse(ServerConfig.isSameServerHost("https://levi.example.com/", "   "))
    }

    @Test
    fun hostComparisonIsCaseInsensitive() {
        assertTrue(
            ServerConfig.isSameServerHost(
                "HTTPS://LEVI.EXAMPLE.COM/chat",
                "https://levi.example.com/settings",
            ),
        )
    }

    @Test
    fun portDifferenceIsFalse_pinnedBehavior() {
        // hostOf keeps the raw authority (host[:port]); a different port is
        // a different host. Pinned, not changed.
        assertFalse(
            ServerConfig.isSameServerHost(
                "http://127.0.0.1:8080/chat",
                "http://127.0.0.1:9090/chat",
            ),
        )
    }

    @Test
    fun samePortIsTrue() {
        assertTrue(
            ServerConfig.isSameServerHost(
                "http://127.0.0.1:8080/chat",
                "http://127.0.0.1:8080/settings",
            ),
        )
    }

    @Test
    fun subdomainIsFalse() {
        assertFalse(
            ServerConfig.isSameServerHost(
                "https://sub.levi.example.com/",
                "https://levi.example.com/",
            ),
        )
    }
}
