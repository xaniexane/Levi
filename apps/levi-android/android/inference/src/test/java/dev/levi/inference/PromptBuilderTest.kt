package dev.levi.inference

import org.junit.Assert.*
import org.junit.Test

class PromptBuilderTest {

    @Test
    fun `prompt contains persona system prompt and user message`() {
        val prompt = PromptBuilder.build(LeviPersona.WARM, emptyList(), "hello there")
        assertTrue(prompt.contains(LeviPersona.WARM.systemPrompt))
        assertTrue(prompt.contains("hello there"))
        assertTrue(prompt.endsWith("<|im_start|>assistant\n"))
    }

    @Test
    fun `history turns are wrapped with role markers`() {
        val history = listOf(
            ChatMessage(ChatMessage.ROLE_USER, "what is 2+2?"),
            ChatMessage(ChatMessage.ROLE_ASSISTANT, "4"),
        )
        val prompt = PromptBuilder.build(LeviPersona.CALM, history, "and 3+3?")
        assertTrue(prompt.contains("<|im_start|>user\nwhat is 2+2?<|im_end|>"))
        assertTrue(prompt.contains("<|im_start|>assistant\n4<|im_end|>"))
        // Newest user message comes after history.
        assertTrue(prompt.indexOf("and 3+3?") > prompt.indexOf("what is 2+2?"))
    }

    @Test
    fun `long history is truncated from the front to fit budget`() {
        val history = (1..50).map {
            ChatMessage(ChatMessage.ROLE_USER, "filler message number $it ".repeat(20))
        }
        val prompt = PromptBuilder.build(LeviPersona.BOLD, history, "final question", maxChars = 2000)
        assertTrue(prompt.length <= 2000 + 512) // markers + tail overhead
        assertTrue(prompt.contains("final question"))
        // Oldest filler should be gone, newest kept.
        assertFalse(prompt.contains("filler message number 1 "))
        assertTrue(prompt.contains("filler message number 50 "))
    }

    @Test
    fun `all personas produce distinct prompts`() {
        val prompts = LeviPersona.entries.map {
            PromptBuilder.build(it, emptyList(), "hi")
        }
        assertEquals(prompts.size, prompts.toSet().size)
    }

    @Test
    fun `stripEcho removes prompt echo`() {
        val raw = "<|im_start|>assistant\nHello! How can I help?<|im_end|>"
        assertEquals("Hello! How can I help?", PromptBuilder.stripEcho(raw))
    }

    @Test
    fun `stripEcho passes through plain text`() {
        assertEquals("just text", PromptBuilder.stripEcho("just text"))
    }
}
