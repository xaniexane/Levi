package dev.levi.inference

/**
 * Builds chat prompts for the on-device model. Uses LEVI's chat template
 * (ChatML-style <|im_start|>/<|im_end|> markers). Pure logic — no Android
 * APIs, JVM-testable.
 */
object PromptBuilder {

    const val MAX_CHARS_DEFAULT = 6000

    fun build(
        persona: LeviPersona,
        history: List<ChatMessage>,
        userMessage: String,
        maxChars: Int = MAX_CHARS_DEFAULT,
    ): String {
        val sb = StringBuilder()
        sb.append("<|im_start|>system\n")
        sb.append(persona.systemPrompt)
        sb.append("<|im_end|>\n")

        // Oldest-first; drop whole turns from the front until we fit.
        val turns = ArrayDeque(history)
        while (turns.isNotEmpty() && estimateLength(persona, turns.toList(), userMessage) > maxChars) {
            turns.removeFirst()
        }
        for (msg in turns) {
            val role = if (msg.role == ChatMessage.ROLE_ASSISTANT) "assistant" else "user"
            sb.append("<|im_start|>").append(role).append('\n')
            sb.append(msg.content.trim())
            sb.append("<|im_end|>\n")
        }

        sb.append("<|im_start|>user\n")
        sb.append(userMessage.trim())
        sb.append("<|im_end|>\n")
        sb.append("<|im_start|>assistant\n")
        return sb.toString()
    }

    private fun estimateLength(
        persona: LeviPersona,
        history: List<ChatMessage>,
        userMessage: String,
    ): Int {
        // Rough char budget; the native layer re-truncates by tokens anyway.
        var n = persona.systemPrompt.length + userMessage.length + 128
        for (m in history) n += m.content.length + 32
        return n
    }

    /** Extract the assistant's reply from a raw generate() output that may
     *  echo the prompt tail. Returns the text after the last assistant marker. */
    fun stripEcho(raw: String): String {
        val marker = "<|im_start|>assistant\n"
        val idx = raw.lastIndexOf(marker)
        val body = if (idx >= 0) raw.substring(idx + marker.length) else raw
        return body.substringBefore("<|im_end|>").trim()
    }
}
