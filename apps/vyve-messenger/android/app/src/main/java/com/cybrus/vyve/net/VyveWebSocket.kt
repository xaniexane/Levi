package com.cybrus.vyve.net

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import timber.log.Timber

// ══════════════════════════════════════════════════════════════════════════
// Real-time delivery channel — GET /ws/{user_id} on the messaging service.
//
// The contract (docs/openapi.yaml, x-websocket) mandates an auth-first-frame
// protocol: the FIRST frame sent MUST be {"type":"auth","token":"<JWT>"}.
// The server closes the socket when the token's sub differs from {user_id}.
// Close codes: 4001 (no/invalid auth frame), 4002 (invalid token),
//              4003 (token sub != user_id).
// ══════════════════════════════════════════════════════════════════════════

@Serializable
private data class AuthFrame(
    val type: String = "auth",
    val token: String,
)

@Serializable
private data class TypingFrame(
    val type: String = "typing",
    @SerialName("conversation_id") val conversationId: String,
)

@Serializable
private data class ReadReceiptFrame(
    val type: String = "read_receipt",
    @SerialName("message_id") val messageId: String,
)

@Serializable
private data class PingFrame(val type: String = "ping")

class VyveWebSocket(
    private val client: OkHttpClient,
    /** e.g. "http://10.0.2.2:8081" — the ws:// scheme is derived automatically. */
    private val messagingBaseUrl: String,
    private val userId: String,
    private val tokenProvider: () -> String?,
    private val listener: Listener,
) {
    interface Listener {
        fun onConnected(serverTime: String?)
        fun onQueuedMessages(messages: List<JsonObject>)
        fun onNewMessage(conversationId: String?, message: JsonObject?)
        fun onConversationCreated(conversation: JsonObject?)
        fun onTyping(conversationId: String?, fromUserId: String?)
        fun onPong()
        fun onAuthFailed(code: Int)
        fun onClosed(code: Int, reason: String)
        fun onFailure(t: Throwable)
    }

    companion object {
        const val CLOSE_NO_AUTH_FRAME = 4001
        const val CLOSE_INVALID_TOKEN = 4002
        const val CLOSE_SUB_MISMATCH = 4003
    }

    private var socket: WebSocket? = null
    private val json = VyveApiFactory.json

    fun connect() {
        disconnect()
        val wsUrl = (messagingBaseUrl.trimEnd('/') + "/ws/$userId")
            .replaceFirst("https://", "wss://")
            .replaceFirst("http://", "ws://")
        val request = Request.Builder().url(wsUrl).build()
        socket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                // Mandatory first frame: authenticate before anything else.
                val token = tokenProvider()
                if (token.isNullOrBlank()) {
                    Timber.w("No access token available for WebSocket auth")
                    webSocket.close(CLOSE_NO_AUTH_FRAME, "missing token")
                    return
                }
                webSocket.send(json.encodeToString(AuthFrame.serializer(), AuthFrame(token = token)))
            }

            override fun onMessage(webSocket: WebSocket, text: String) = handleFrame(text)

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                if (code in CLOSE_NO_AUTH_FRAME..CLOSE_SUB_MISMATCH) listener.onAuthFailed(code)
                listener.onClosed(code, reason)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                if (code in CLOSE_NO_AUTH_FRAME..CLOSE_SUB_MISMATCH) listener.onAuthFailed(code)
                listener.onClosed(code, reason)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Timber.w(t, "WebSocket failure")
                listener.onFailure(t)
            }
        })
    }

    fun sendTyping(conversationId: String) {
        socket?.send(json.encodeToString(TypingFrame.serializer(), TypingFrame(conversationId = conversationId)))
    }

    fun sendReadReceipt(messageId: String) {
        socket?.send(json.encodeToString(ReadReceiptFrame.serializer(), ReadReceiptFrame(messageId = messageId)))
    }

    fun ping() {
        socket?.send(json.encodeToString(PingFrame.serializer(), PingFrame()))
    }

    fun disconnect() {
        socket?.close(1000, "client disconnect")
        socket = null
    }

    private fun handleFrame(text: String) {
        val obj = runCatching { json.parseToJsonElement(text).jsonObject }.getOrNull() ?: return
        when (obj["type"]?.jsonPrimitive?.content) {
            "connected" -> listener.onConnected(obj["server_time"]?.jsonPrimitive?.content)
            "queued_messages" -> {
                val messages = obj["messages"]?.let { element ->
                    runCatching {
                        json.decodeFromJsonElement(ListSerializer(JsonObject.serializer()), element)
                    }.getOrNull()
                }.orEmpty()
                listener.onQueuedMessages(messages)
            }
            "new_message" -> listener.onNewMessage(
                obj["conversation_id"]?.jsonPrimitive?.content,
                obj["message"]?.jsonObject,
            )
            "conversation_created" -> listener.onConversationCreated(obj["conversation"]?.jsonObject)
            "typing" -> listener.onTyping(
                obj["conversation_id"]?.jsonPrimitive?.content,
                obj["user_id"]?.jsonPrimitive?.content,
            )
            "pong" -> listener.onPong()
            else -> Timber.d("Unhandled WS frame: %s", text.take(120))
        }
    }
}
