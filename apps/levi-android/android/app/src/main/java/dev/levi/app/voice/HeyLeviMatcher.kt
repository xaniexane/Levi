package dev.levi.app.voice

/**
 * Decides whether a speech-recognition transcript is the user saying
 * "Hey LEVI".
 *
 * Pure function — no Android dependencies — so the trigger logic is unit
 * tested on the JVM ([HeyLeviMatcherTest]). The recognizer's transcripts
 * are noisy, so matching is deliberately forgiving: any "hey"-family head
 * word within two tokens before a "levi"-family token fires. A bare
 * "levi" with no head word never fires, which keeps ordinary conversation
 * about LEVI from waking the listener.
 *
 * Honest scope: this is transcript matching, not acoustic wake-word
 * detection. It is only as good as the device's speech recognizer, and it
 * runs while the [HeyLeviService] foreground service holds the mic — not
 * at DSP level like a system hotword.
 */
object HeyLeviMatcher {

    /** Words that can introduce the trigger ("hey levi", "a levi", …). */
    private val HEADS = setOf("hey", "hay", "ay", "a", "ok", "okay")

    /**
     * True when [transcript] contains a head word followed (within two
     * tokens) by a "levi"-family token.
     */
    fun isTrigger(transcript: String): Boolean {
        val tokens = transcript
            .lowercase()
            .split(Regex("[^a-z']+"))
            .map { it.trim('\'') }
            .filter { it.isNotBlank() }
        if (tokens.isEmpty()) return false
        for (i in tokens.indices) {
            if (!isLeviToken(tokens[i])) continue
            val window = tokens.subList(maxOf(0, i - 2), i)
            if (window.any { it in HEADS }) return true
        }
        return false
    }

    /**
     * "levi" plus the mis-hearings speech recognizers actually produce
     * ("levy", "livy", …), with one-edit tolerance for the rest. Kept
     * tight: "leave" is three edits away and does not match.
     */
    private fun isLeviToken(token: String): Boolean {
        if (token == "levi" || token == "levy" || token == "livy") return true
        return token.length in 3..6 && editDistance(token, "levi") <= 1
    }

    private fun editDistance(a: String, b: String): Int {
        val dp = Array(a.length + 1) { IntArray(b.length + 1) }
        for (i in 0..a.length) dp[i][0] = i
        for (j in 0..b.length) dp[0][j] = j
        for (i in 1..a.length) {
            for (j in 1..b.length) {
                dp[i][j] = minOf(
                    dp[i - 1][j] + 1,
                    dp[i][j - 1] + 1,
                    dp[i - 1][j - 1] + if (a[i - 1] == b[j - 1]) 0 else 1,
                )
            }
        }
        return dp[a.length][b.length]
    }
}
