package com.cybrus.vyve.net

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import java.util.concurrent.TimeUnit

// ══════════════════════════════════════════════════════════════════════════
// VYVE Messenger API — Retrofit interfaces.
//
// Mirrors apps/vyve-messenger/docs/openapi.yaml (generated from the backend
// code, spec<->code verified 23:23):
//   * OAuth provider on :8080, messaging service on :8081 — NO /v1 prefix.
//   * RS256 JWT bearer auth; PKCE S256; exact-match redirect_uri.
//   * POST /conversations and POST /conversations/{id}/messages return the
//     created object with 201 (NOT wrapped).
//   * Timestamps are ISO-8601 UTC strings.
// kotlinx-serialization is the ONE JSON converter used in this app.
// ══════════════════════════════════════════════════════════════════════════

// ── OAuth provider (:8080) ────────────────────────────────────────────────

@Serializable
data class DiscoveryDocument(
    val issuer: String? = null,
    @SerialName("authorization_endpoint") val authorizationEndpoint: String? = null,
    @SerialName("token_endpoint") val tokenEndpoint: String? = null,
    @SerialName("userinfo_endpoint") val userinfoEndpoint: String? = null,
    @SerialName("jwks_uri") val jwksUri: String? = null,
    @SerialName("response_types_supported") val responseTypesSupported: List<String> = emptyList(),
    @SerialName("grant_types_supported") val grantTypesSupported: List<String> = emptyList(),
    @SerialName("scopes_supported") val scopesSupported: List<String> = emptyList(),
    @SerialName("code_challenge_methods_supported") val codeChallengeMethodsSupported: List<String> = emptyList(),
)

@Serializable
data class Jwk(
    val kty: String? = null,
    val alg: String? = null,
    val use: String? = null,
    val kid: String? = null,
    val n: String? = null,
    val e: String? = null,
)

@Serializable
data class Jwks(val keys: List<Jwk> = emptyList())

@Serializable
data class TokenResponse(
    @SerialName("access_token") val accessToken: String,
    @SerialName("token_type") val tokenType: String,
    @SerialName("expires_in") val expiresIn: Int,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("id_token") val idToken: String? = null,
    val scope: String,
)

@Serializable
data class UserInfo(
    val sub: String,
    val username: String,
    val name: String? = null,
    val email: String? = null,
    val role: String? = null,
    val tier: String? = null,
)

@Serializable
data class UserProfile(
    val sub: String,
    val username: String,
    val email: String,
    @SerialName("display_name") val displayName: String,
    val role: String,
    val tier: String,
    val scopes: List<String> = emptyList(),
)

@Serializable
data class DeviceRegistration(
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_name") val deviceName: String,
    @SerialName("device_type") val deviceType: String,
    @SerialName("signing_key") val signingKey: String,
    @SerialName("encryption_key") val encryptionKey: String,
)

@Serializable
data class Device(
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_name") val deviceName: String? = null,
    @SerialName("device_type") val deviceType: String? = null,
    @SerialName("signing_key") val signingKey: String? = null,
    @SerialName("encryption_key") val encryptionKey: String? = null,
    @SerialName("registered_at") val registeredAt: String? = null,
    val trusted: Boolean? = null,
)

@Serializable
data class DeviceList(val devices: List<Device> = emptyList())

@Serializable
data class StatusResponse(val status: String)

@Serializable
data class DeviceRegisteredResponse(
    val status: String,
    @SerialName("device_id") val deviceId: String,
)

@Serializable
data class OAuthHealth(
    val status: String? = null,
    val service: String? = null,
    val version: String? = null,
    val issuer: String? = null,
    @SerialName("users_registered") val usersRegistered: Int? = null,
    @SerialName("tokens_issued") val tokensIssued: Int? = null,
    @SerialName("refresh_tokens_active") val refreshTokensActive: Int? = null,
)

/** OAuth2 / OIDC provider — base URL http://<host>:8080/ */
interface OAuthService {
    @GET(".well-known/openid-configuration")
    suspend fun discovery(): Response<DiscoveryDocument>

    @GET("oauth/jwks")
    suspend fun jwks(): Response<Jwks>

    /**
     * Token endpoint. grant_type=authorization_code needs code, code_verifier
     * (+ optional redirect_uri, client_id, client_secret); grant_type=
     * refresh_token needs refresh_token (+ client_id, client_secret).
     */
    @FormUrlEncoded
    @POST("oauth/token")
    suspend fun token(
        @Field("grant_type") grantType: String,
        @Field("code") code: String? = null,
        @Field("code_verifier") codeVerifier: String? = null,
        @Field("redirect_uri") redirectUri: String? = null,
        @Field("refresh_token") refreshToken: String? = null,
        @Field("client_id") clientId: String? = null,
        @Field("client_secret") clientSecret: String? = null,
    ): Response<TokenResponse>

    @GET("oauth/userinfo")
    suspend fun userinfo(@Header("Authorization") bearer: String): Response<UserInfo>

    /** RFC 7009 — always 200 on a well-formed request. */
    @FormUrlEncoded
    @POST("oauth/revoke")
    suspend fun revoke(
        @Field("token") token: String,
        @Field("token_type_hint") tokenTypeHint: String? = null,
    ): Response<StatusResponse>

    @GET("me")
    suspend fun me(@Header("Authorization") bearer: String): Response<UserProfile>

    @GET("me/devices")
    suspend fun listDevices(@Header("Authorization") bearer: String): Response<DeviceList>

    @POST("me/devices")
    suspend fun registerDevice(
        @Header("Authorization") bearer: String,
        @Body registration: DeviceRegistration,
    ): Response<DeviceRegisteredResponse>

    @DELETE("me/devices/{device_id}")
    suspend fun revokeDevice(
        @Header("Authorization") bearer: String,
        @Path("device_id") deviceId: String,
    ): Response<StatusResponse>

    @GET("health")
    suspend fun health(): Response<OAuthHealth>
}

// ── Messaging service (:8081) ─────────────────────────────────────────────

@Serializable
data class ConversationCreate(
    @SerialName("conversation_type") val conversationType: String,
    @SerialName("participant_ids") val participantIds: List<String>,
    val name: String? = null,
)

@Serializable
data class Conversation(
    @SerialName("conversation_id") val conversationId: String,
    @SerialName("conversation_type") val conversationType: String? = null,
    val participants: List<String> = emptyList(),
    val name: String? = null,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("last_activity") val lastActivity: String? = null,
    @SerialName("unread_count") val unreadCount: Map<String, Int> = emptyMap(),
)

@Serializable
data class ConversationList(val conversations: List<Conversation> = emptyList())

@Serializable
data class EncryptedMessageUpload(
    @SerialName("recipient_key_ids") val recipientKeyIds: List<String>,
    @SerialName("ephemeral_pubkey") val ephemeralPubkey: String,
    val nonce: String,
    val ciphertext: String,
    val signature: String,
    @SerialName("size_bucket") val sizeBucket: String? = null, // accepted but IGNORED server-side
    @SerialName("attachment_ids") val attachmentIds: List<String> = emptyList(),
    @SerialName("reply_to") val replyTo: String? = null,
    @SerialName("forward_policy") val forwardPolicy: String? = null,
)

@Serializable
data class Message(
    @SerialName("message_id") val messageId: String,
    @SerialName("conversation_id") val conversationId: String,
    @SerialName("sender_key_id") val senderKeyId: String? = null, // derived server-side
    @SerialName("sender_id") val senderId: String? = null,
    @SerialName("recipient_key_ids") val recipientKeyIds: List<String> = emptyList(),
    @SerialName("ephemeral_pubkey") val ephemeralPubkey: String? = null,
    val nonce: String? = null,
    val ciphertext: String? = null,
    val signature: String? = null,
    @SerialName("size_bucket") val sizeBucket: String? = null, // recomputed server-side
    @SerialName("sent_at") val sentAt: String? = null, // server clock
    val status: String? = null, // "queued" -> "delivered"
    @SerialName("attachment_ids") val attachmentIds: List<String> = emptyList(),
    @SerialName("reply_to") val replyTo: String? = null,
    @SerialName("delivery_receipts") val deliveryReceipts: Map<String, String> = emptyMap(),
    @SerialName("read_receipts") val readReceipts: Map<String, String> = emptyMap(),
)

@Serializable
data class MessageTombstone(
    @SerialName("message_id") val messageId: String,
    @SerialName("conversation_id") val conversationId: String,
    val status: String,
    @SerialName("deleted_at") val deletedAt: String? = null,
    @SerialName("sender_id") val senderId: String? = null,
)

/**
 * GET /conversations/{id}/messages — the list items are oneOf
 * Message|MessageTombstone, so they are decoded leniently as raw JSON and
 * classified by the caller via [isTombstone].
 */
@Serializable
data class MessageList(
    val messages: List<JsonObject> = emptyList(),
    val total: Int = 0,
)

@Serializable
data class QueueResponse(
    val messages: List<Message> = emptyList(),
    val count: Int = 0,
)

@Serializable
data class DeliverResponse(
    val status: String,
    @SerialName("delivered_at") val deliveredAt: String? = null,
)

@Serializable
data class MessagingHealth(
    val status: String? = null,
    val service: String? = null,
    val version: String? = null,
    val conversations: Int? = null,
    val messages: Int? = null,
    @SerialName("queued_messages") val queuedMessages: Int? = null,
    @SerialName("active_connections") val activeConnections: Int? = null,
)

/** VYVE messaging service — base URL http://<host>:8081/ */
interface MessagingService {
    @GET("conversations")
    suspend fun listConversations(@Header("Authorization") bearer: String): Response<ConversationList>

    /** 201 — returns the created conversation directly (NOT wrapped). */
    @POST("conversations")
    suspend fun createConversation(
        @Header("Authorization") bearer: String,
        @Body request: ConversationCreate,
    ): Response<Conversation>

    @GET("conversations/{conversation_id}")
    suspend fun getConversation(
        @Header("Authorization") bearer: String,
        @Path("conversation_id") conversationId: String,
    ): Response<Conversation>

    /** Leave a conversation — 204, empty body. */
    @DELETE("conversations/{conversation_id}")
    suspend fun leaveConversation(
        @Header("Authorization") bearer: String,
        @Path("conversation_id") conversationId: String,
    ): Response<Unit>

    @GET("conversations/{conversation_id}/messages")
    suspend fun listMessages(
        @Header("Authorization") bearer: String,
        @Path("conversation_id") conversationId: String,
        @Query("limit") limit: Int? = null,
        @Query("before") before: String? = null,
    ): Response<MessageList>

    /** 201 — returns the stored message envelope directly (NOT wrapped). */
    @POST("conversations/{conversation_id}/messages")
    suspend fun sendMessage(
        @Header("Authorization") bearer: String,
        @Path("conversation_id") conversationId: String,
        @Body message: EncryptedMessageUpload,
    ): Response<Message>

    /** 200 — envelope, or tombstone if soft-deleted (decoded as raw JSON). */
    @GET("messages/{message_id}")
    suspend fun getMessage(
        @Header("Authorization") bearer: String,
        @Path("message_id") messageId: String,
    ): Response<JsonObject>

    /** Soft delete (sender only) — 204, empty body. */
    @DELETE("messages/{message_id}")
    suspend fun deleteMessage(
        @Header("Authorization") bearer: String,
        @Path("message_id") messageId: String,
    ): Response<Unit>

    /** Delivery receipt — GET (per the contract), 200. */
    @GET("messages/{message_id}/deliver")
    suspend fun recordDelivery(
        @Header("Authorization") bearer: String,
        @Path("message_id") messageId: String,
    ): Response<DeliverResponse>

    /** Drains the caller's offline queue (read-once) — 200. */
    @GET("queue")
    suspend fun drainQueue(@Header("Authorization") bearer: String): Response<QueueResponse>

    @GET("health")
    suspend fun health(): Response<MessagingHealth>
}

// ── Shared ────────────────────────────────────────────────────────────────

@Serializable
data class ErrorBody(val detail: String? = null)

/** True when a raw message-list item is a soft-delete tombstone. */
fun isTombstone(item: JsonObject): Boolean =
    item["status"]?.toString()?.trim('"') == "deleted"

/** Builds both Retrofit services. baseUrl must end with '/', e.g. "http://10.0.2.2:8080/". */
object VyveApiFactory {
    val json: Json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        encodeDefaults = true
    }

    private val jsonMediaType = "application/json".toMediaType()

    fun okHttpClient(debug: Boolean): OkHttpClient =
        OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .apply {
                if (debug) {
                    addInterceptor(
                        HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC },
                    )
                }
            }
            .build()

    private fun retrofit(baseUrl: String, debug: Boolean): Retrofit =
        Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(okHttpClient(debug))
            .addConverterFactory(json.asConverterFactory(jsonMediaType))
            .build()

    fun oauthService(baseUrl: String, debug: Boolean): OAuthService =
        retrofit(baseUrl, debug).create(OAuthService::class.java)

    fun messagingService(baseUrl: String, debug: Boolean): MessagingService =
        retrofit(baseUrl, debug).create(MessagingService::class.java)
}
