# VYVE Cryptography Specification

**Document version:** 1.0.0  
**Status:** Engineering Reference  
**Last updated:** 2026-09-04  

---

## 1. Guiding Principles

1. **No homemade crypto.** Every algorithm used is published, independently reviewed, and widely deployed.
2. **No AES-256-CBC without HMAC.** Authenticated encryption only.
3. **Keys never leave the trust boundary.** Master keys stay on the user's device (or hardware security module for server-side).
4. **Forward secrecy by default.** Session keys are ephemeral; long-term keys are never used to encrypt messages.
5. **Key separation.** Every key has one purpose. Signing keys are separate from encryption keys.

---

## 2. Algorithms in Use

| Purpose | Algorithm | Parameters | Standard |
|---------|-----------|-----------|---------|
| Authenticated encryption | XChaCha20-Poly1305 | 256-bit key, 192-bit nonce | RFC 8439 |
| Key exchange | X25519 | 255-bit curve | RFC 7748 |
| Digital signatures | Ed25519 | 256-bit | RFC 8032 |
| Hashing | BLAKE2b | 512-bit output | RFC 7693 |
| Key derivation | Argon2id | 64MB RAM, 3 iterations | RFC 9106 |
| HMAC | HMAC-SHA512 | 512-bit | FIPS 198-1 |
| Random | System CSPRNG | /dev/urandom (Linux/Android) | OS provided |

**NO USE OF:**
- MD5 or SHA-1 (except in HMAC where specifically allowed)
- DES or 3DES
- RSA (for new keys; existing keys may be migrated)
- ECB mode
- CBC mode without HMAC
- ECB-then-CBC constructs without authenticated encryption

---

## 3. Key Hierarchy

```
User Master Key (UMK)
│
├── Identity Signing Key (Ed25519)         — signs messages, posts, social graph
├── Identity Encryption Key (X25519)      — encrypts stored vault items
│
├── Message Encryption Key (MEK)          — encrypts message content
│   └── Derived per-conversation via HKDF
│
└── Device Keys (one per device)
    ├── Device Signing Key (Ed25519)      — signs device registration
    └── Device Encryption Key (X25519)    — encrypts per-device local DB
        └── Derived per-file via HKDF
```

### 3.1 Key Generation
```
UMK = Argon2id(
    password: user_password,
    salt: 32_bytes_random,
    opslimit: 3,
    memlimit: 67108864,  # 64MB
    parallelism: 4
)

[identity_signing_priv, identity_signing_pub] = Ed25519.keygen(UMK)
[identity_enc_priv, identity_enc_pub] = X25519.keygen(UMK)

[device_signing_priv, device_signing_pub] = Ed25519.keygen(device_entropy)
[device_enc_priv, device_enc_pub] = X25519.keygen(device_entropy)
```

### 3.2 Key Storage
| Key | Where | Protection |
|-----|-------|-----------|
| UMK | Android Keystore (hardware-backed) | Biometric or PIN gate |
| Identity signing key | Derived, kept in memory only while app is unlocked | Cleared on lock/screen-off |
| Identity encryption key | Android Keystore (exportable=false) | Biometric or PIN gate |
| Device keys | Android Keystore | Device-bound |
| Conversation MEKs | Derived via HKDF, not stored | Derived fresh each session |

---

## 4. End-to-End Encryption Protocol

### 4.1 Message Encryption (sender side)
```python
def encrypt_message(plaintext: bytes, sender_device_key: KeyPair,
                    recipient_device_key: PublicKey) -> EncryptedMessage:
    # Step 1: Generate ephemeral key for forward secrecy
    ephemeral_keypair = X25519.keygen()

    # Step 2: Compute shared secret
    shared_secret = X25519.compute_shared_key(
        ephemeral_keypair.priv,
        recipient_device_key.pub
    )

    # Step 3: Derive message key
    message_key = HKDF_BLAKE2b(
        ikm=shared_secret,
        salt=sender_device_key.id,
        info=b"VYVE-MESSAGE-v1",
        length=32
    )

    # Step 4: Authenticate additional data
    aad = (
        sender_device_key.id          # who sent it
        + recipient_device_key.id      # intended recipient
        + timestamp                    # prevent replay
    )

    # Step 5: Encrypt
    nonce = random(24)  # XChaCha20 uses 24-byte nonce
    ciphertext = XChaCha20_Poly1305.encrypt(
        key=message_key,
        nonce=nonce,
        plaintext=plaintext,
        aad=aad
    )

    return EncryptedMessage(
        ephemeral_pubkey=ephemeral_keypair.pub,
        sender_key_id=sender_device_key.id,
        recipient_key_id=recipient_device_key.id,
        nonce=nonce,
        ciphertext=ciphertext,
        timestamp=rounded_timestamp
    )
```

### 4.2 Message Decryption (recipient side)
```python
def decrypt_message(msg: EncryptedMessage,
                    recipient_device_key: KeyPair) -> bytes:
    # Step 1: Compute shared secret
    shared_secret = X25519.compute_shared_key(
        recipient_device_key.priv,
        msg.ephemeral_pubkey
    )

    # Step 2: Derive message key
    message_key = HKDF_BLAKE2b(
        ikm=shared_secret,
        salt=msg.sender_key_id,
        info=b"VYVE-MESSAGE-v1",
        length=32
    )

    # Step 3: Decrypt and verify
    aad = (
        msg.sender_key_id
        + recipient_device_key.id
        + msg.timestamp
    )

    plaintext = XChaCha20_Poly1305.decrypt(
        key=message_key,
        nonce=msg.nonce,
        ciphertext=msg.ciphertext,
        aad=aad
    )

    return plaintext
```

### 4.3 Multi-Device Encryption
- Message is encrypted separately for each recipient device
- Each ciphertext uses a different ephemeral key pair
- Server stores N ciphertexts (one per device)
- Recipient device selects the ciphertext addressed to its key ID

### 4.4 Rekeying
- Maximum message key lifetime: 1,000 messages or 7 days (whichever is first)
- After expiry: new ephemeral key pair generated, new MEK derived
- Old message keys securely wiped from memory

---

## 5. Authentication

### 5.1 Message Authentication
Every message carries a cryptographic signature using Ed25519:
```
signature = Ed25519.sign(
    key=sender_identity_signing_key,
    message=ciphertext + metadata
)
```
The signature is verified by the recipient using the sender's known public key. Known public keys are exchanged during the initial key agreement and cached locally.

### 5.2 Device Attestation
```
device_registration = {
    device_id: uuid,
    public_signing_key: Ed25519Pub,
    public_encryption_key: X25519Pub,
    user_id: hashed_user_id,
    signature: Ed25519.sign(
        key=device_signing_key,
        message=device_id + public_keys + user_id
    ),
    registered_at: unix_timestamp
}
```

---

## 6. Local Storage Encryption

### 6.1 Database Encryption
- SQLCipher with XChaCha20-Poly1305
- Database key derived from UMK via Argon2id
- Key stored in Android Keystore with `SetUserAuthenticationRequired(true)`
- Automatic lock on screen-off (configurable: immediate, 1min, 5min, 15min)

### 6.2 File Encryption
- Each attachment encrypted with unique file key
- File key wrapped with device encryption key
- Stored as: `{wrapped_file_key, nonce, ciphertext, file_hash}`

---

## 7. What the Server Actually Has

| Data | Can Decrypt? | Can Modify? | Can Forge? |
|------|-------------|-------------|------------|
| Ciphertext | ❌ No | ❌ No (Poly1305 auth fails) | ❌ No |
| Sender key ID | ✅ Yes | ✅ Yes | ❌ No |
| Recipient key IDs | ✅ Yes | ✅ Yes | ❌ No |
| Ephemeral pubkey | ✅ Yes | ✅ Yes | ❌ No |
| Timestamp (rounded) | ✅ Yes | ✅ Yes | ✅ Yes |
| Nonce | ✅ Yes | ✅ Yes | ❌ No |
| Signatures | ✅ Yes (but not spoof) | ❌ No | ❌ No |

---

## 8. Cryptographic Agility

VYVE implements cryptographic agility: the ability to upgrade algorithms without breaking existing data or requiring users to re-enroll.

| Upgrade Trigger | Migration Path |
|----------------|---------------|
| Algorithm discovered weak | Deprecate old algorithm, require new for new keys |
| Post-quantum need | X25519 → ML-KEM (Kyber) hybrid (future) |
| Key size increase | Derive new keys from master, keep old for decryption |
| Library vulnerability | Hot-patch library, regenerate session keys |

All cryptographic operations are behind a `CryptoProvider` interface:
```kotlin
interface CryptoProvider {
    fun encrypt(plaintext: ByteArray, key: ByteArray, nonce: ByteArray): ByteArray
    fun decrypt(ciphertext: ByteArray, key: ByteArray, nonce: ByteArray): ByteArray
    fun sign(message: ByteArray, privateKey: ByteArray): ByteArray
    fun verify(message: ByteArray, signature: ByteArray, publicKey: ByteArray): Boolean
    fun deriveKey(master: ByteArray, context: ByteArray): ByteArray
}
```

The concrete implementation is injected at runtime, allowing library upgrades or algorithm swaps without application code changes.

---

## 9. Random Number Generation

| Platform | RNG Source |
|----------|-----------|
| Android | `java.security.SecureRandom` backed by `/dev/urandom` |
| Server | `secrets.SystemRandom()` backed by OS CSPRNG |
| Key Generation | `libsodium.randombytes_buf()` |

All random values are verified for minimum entropy before use:
- Key generation: 256-bit entropy minimum
- Nonces: 192-bit random (XChaCha20 requires 24 bytes)
- Salt: 128-bit random minimum
