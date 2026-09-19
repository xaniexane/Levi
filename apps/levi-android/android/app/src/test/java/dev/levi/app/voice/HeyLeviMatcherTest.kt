package dev.levi.app.voice

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for [HeyLeviMatcher]'s trigger logic — the decision behind
 * the "Hey LEVI" hotword listener. Pure JVM, no Android needed.
 *
 * The contract under test: a "hey"-family head word near a "levi"-family
 * token fires; a bare "levi" with no head word never does.
 */
class HeyLeviMatcherTest {

    // ---- fires ----

    @Test
    fun trigger_plainHeyLevi() {
        assertTrue(HeyLeviMatcher.isTrigger("hey levi"))
    }

    @Test
    fun trigger_caseAndPunctuationIgnored() {
        assertTrue(HeyLeviMatcher.isTrigger("Hey, Levi!"))
    }

    @Test
    fun trigger_recognizerMishearingLevy() {
        assertTrue(HeyLeviMatcher.isTrigger("hey levy"))
    }

    @Test
    fun trigger_headWordVariants() {
        assertTrue(HeyLeviMatcher.isTrigger("a levi what time is it"))
        assertTrue(HeyLeviMatcher.isTrigger("okay levi"))
    }

    @Test
    fun trigger_insideLongerUtterance() {
        assertTrue(
            HeyLeviMatcher.isTrigger(
                "i was wondering hey levi can you set a timer",
            ),
        )
    }

    // ---- stays quiet ----

    @Test
    fun quiet_bareLeviNeverFires() {
        assertFalse(HeyLeviMatcher.isTrigger("levi"))
        assertFalse(HeyLeviMatcher.isTrigger("levi is a great name"))
    }

    @Test
    fun quiet_unrelatedUtterance() {
        assertFalse(HeyLeviMatcher.isTrigger("hey siri"))
        assertFalse(HeyLeviMatcher.isTrigger("play some music"))
        assertFalse(HeyLeviMatcher.isTrigger(""))
    }

    @Test
    fun quiet_lookalikeWordsDoNotFire() {
        // "leave" is three edits from "levi" — must not trigger.
        assertFalse(HeyLeviMatcher.isTrigger("hey leave a message"))
        assertFalse(HeyLeviMatcher.isTrigger("hey level up"))
    }

    @Test
    fun quiet_headAfterLeviDoesNotFire() {
        assertFalse(HeyLeviMatcher.isTrigger("levi hey"))
    }
}
