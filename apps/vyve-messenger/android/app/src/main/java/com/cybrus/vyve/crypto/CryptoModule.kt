package com.cybrus.vyve.crypto

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.inject.Singleton

// ══════════════════════════════════════════════════════════════════════════
// WHY JCA INSTEAD OF LAZY-SODIUM
//
// The previous CryptoModule imported com.goterl.lazysodium, which was never
// declared as a dependency (so the file could not compile) — and even if it
// had been, lazy-sodium is abandoned (last release 2021), distributed only
// via JitPack, and its native bindings are incompatible with the current
// AGP/R8 toolchain. It is not a viable dependency in 2026.
//
// This module uses javax.crypto (JCA) with AndroidKeyStore-backed
// AES-256-GCM for local secret storage — zero extra dependencies, hardware
// backing where the device offers it.
//
// NOTE: the backend message envelope is XChaCha20-Poly1305 (libsodium).
// JCA on Android does NOT provide XChaCha20. When E2EE send/receive is
// actually implemented, add com.google.crypto.tink:tink-android and provide
// the envelope crypto through Tink — do NOT pull lazy-sodium back in.
// ══════════════════════════════════════════════════════════════════════════

data class EncryptedPayload(
    val iv: ByteArray,
    val ciphertext: ByteArray,
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is EncryptedPayload) return false
        return iv.contentEquals(other.iv) && ciphertext.contentEquals(other.ciphertext)
    }

    override fun hashCode(): Int = 31 * iv.contentHashCode() + ciphertext.contentHashCode()
}

/**
 * The ONLY crypto surface the rest of the app may use. Implementations are
 * provided by [CryptoModule]; application code never touches JCA directly.
 */
interface CryptoProvider {
    /** Creates an AES-256 key in the AndroidKeyStore (no-op if it exists). */
    fun generateLocalKey(alias: String)

    fun encrypt(alias: String, plaintext: ByteArray): EncryptedPayload

    fun decrypt(alias: String, payload: EncryptedPayload): ByteArray

    fun deleteKey(alias: String)
}

class AndroidKeyStoreCryptoProvider : CryptoProvider {
    private val keyStore: KeyStore =
        KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }

    private fun getOrCreateKey(alias: String): SecretKey {
        (keyStore.getEntry(alias, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        val keyGenerator = KeyGenerator.getInstance("AES", ANDROID_KEYSTORE)
        keyGenerator.init(
            KeyGenParameterSpec.Builder(
                alias,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .setRandomizedEncryptionRequired(true)
                .build(),
        )
        return keyGenerator.generateKey()
    }

    override fun generateLocalKey(alias: String) {
        getOrCreateKey(alias)
    }

    override fun encrypt(alias: String, plaintext: ByteArray): EncryptedPayload {
        val cipher = Cipher.getInstance(AES_GCM_NOPADDING).apply {
            init(Cipher.ENCRYPT_MODE, getOrCreateKey(alias))
        }
        return EncryptedPayload(iv = cipher.iv, ciphertext = cipher.doFinal(plaintext))
    }

    override fun decrypt(alias: String, payload: EncryptedPayload): ByteArray {
        val cipher = Cipher.getInstance(AES_GCM_NOPADDING).apply {
            init(Cipher.DECRYPT_MODE, getOrCreateKey(alias), GCMParameterSpec(128, payload.iv))
        }
        return cipher.doFinal(payload.ciphertext)
    }

    override fun deleteKey(alias: String) {
        keyStore.deleteEntry(alias)
    }

    companion object {
        private const val ANDROID_KEYSTORE = "AndroidKeyStore"
        private const val AES_GCM_NOPADDING = "AES/GCM/NoPadding"
    }
}

@Module
@InstallIn(SingletonComponent::class)
object CryptoModule {
    @Provides
    @Singleton
    fun provideCryptoProvider(): CryptoProvider = AndroidKeyStoreCryptoProvider()
}
