package com.cybrus.vyve.crypto

import com.goterl.lazysodium.LazySodiumAndroid
import com.goterl.lazysodium.SodiumAndroid
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Crypto module providing libsodium-based cryptographic operations.
 * 
 * This is the ONLY place where cryptographic primitives are instantiated.
 * All other code must use the [CryptoProvider] interface, never libsodium directly.
 * 
 * Why: enables cryptographic agility — algorithms can be swapped without
 * changing application code, and security review is centralized.
 */
@Module
@InstallIn(SingletonComponent::class)
object CryptoModule {

    @Provides
    @Singleton
    fun provideSodium(): SodiumAndroid = SodiumAndroid()

    @Provides
    @Singleton
    fun provideLazySodium(sodium: SodiumAndroid): LazySodiumAndroid =
        LazySodiumAndroid(sodium, LibsodiumBinder())

    @Provides
    @Singleton
    fun provideCryptoProvider(lazySodium: LazySodiumAndroid): CryptoProvider =
        LibsodiumCryptoProvider(lazySodium)
}

/**
 * Minimal binder for lazy-sodium initialization. In production, this binds
 * native libsodium libraries. For this scaffold, returns a stub.
 */
private class LibsodiumBinder : com.goterl.lazysodium.interfaces.Message {
    override fun cryptoBoxKeypair(pk: ByteArray?, sk: ByteArray?): Int = 0
    override fun cryptoBoxKeypair(pk: CharArray?, sk: CharArray?): Int = 0
    override fun cryptoBoxEasy(
        c: ByteArray?, m: ByteArray?, mlen: Long, n: ByteArray?,
        pk: ByteArray?, sk: ByteArray?
    ): Int = 0

    override fun cryptoBoxOpenEasy(
        m: ByteArray?, c: ByteArray?, clen: Long, n: ByteArray?,
        pk: ByteArray?, sk: ByteArray?
    ): Int = 0
}
