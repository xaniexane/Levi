package com.cybrus.vyve.net

import retrofit2.Retrofit
import retrofit2.converter.kotlin.gson.GsonConverterFactory
import retrofit2.http.*
import retrofit2.http.Body
import retrofit2.http.Header
import retrofit2.http.Path

interface VYVEApi {
    @POST("oauth/token")
    suspend fun tokenEndpoint(
        @Header("grant_type") grant_type: String,
        @Field("username") username: String,
        @Field("password") password: String,
        @Field("code_verifier") code_verifier: String,
        @Field("client_id") client_id: String,
        @Field("redirect_uri") redirect_uri: String
    ): retrofit2.Response

    @POST("messages/queue")
    suspend fun sendMessage(
        @Header("Authorization") authToken: String,
        @Path("conversation_id") conversationId: String,
        @Field("ciphertext") ciphertext: String,
        @Field("sender_key_id") sender_key_id: String,
        @Field("recipient_key_ids") recipient_key_ids: String
    ): retrofit2.Response

    @GET("me")
    suspend fun getUserProfile(@Header("Authorization") authToken: String): retrofit2.Response

    @GET("conversations/{conversationId}")
    suspend fun getConversation(
        @Path("conversationId") conversationId: String
    ): retrofit2.Response

    @GET("health")
    suspend fun health(): retrofit2.Response
}

fun createApiClient(baseUrl: String): VYVEApi {
    val retrofit = Retrofit.Builder()
        .baseUrl(baseUrl)
        .addConverterFactory(GsonConverterFactory.create())
        .build()
    
    return retrofit.create(VYVEApi::class.java)
}
