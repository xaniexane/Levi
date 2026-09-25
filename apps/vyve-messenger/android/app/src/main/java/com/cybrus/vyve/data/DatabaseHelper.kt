package com.cybrus.vyve.data

import android.content.ContentValues
import android.content.Context
import androidx.sqlite.db.SupportSQLiteDatabase
import androidx.sqlite.db.SupportSQLiteOpenHelper
import net.zetetic.database.DefaultDatabaseErrorHandler
import net.zetetic.database.sqlcipher.SQLiteDatabase
import net.zetetic.database.sqlcipher.SQLiteOpenHelper
import timber.log.Timber

// ══════════════════════════════════════════════════════════════════════════
// SQLCipher-encrypted local store (net.zetetic:sqlcipher-android:4.9.0).
//
// 4.x API notes (verified against the 4.9.0 AAR bytecode — the old
// net.sqlcipher.* API this file was first written against does not exist
// here):
//   • SQLiteDatabase.loadLibs() is GONE. The AAR never loads its own .so,
//     so the host app must call System.loadLibrary("sqlcipher") once per
//     process (done in init below).
//   • The passphrase is constructor-injected (String overload → UTF-8 bytes
//     internally); getWritableDatabase()/getReadableDatabase() take no args.
//     Consequence: the key lives in the helper for its lifetime, so key
//     rotation means building a new DatabaseHelper instance.
//   • The androidx.sqlite.db.* supertypes need the explicit
//     androidx.sqlite:sqlite-android dep (see libs.versions.toml).
//   • SQLiteOpenHelper also implements SupportSQLiteOpenHelper, whose
//     getWritableDatabase()/getReadableDatabase() bridge methods collide with
//     the concrete ones (same name+arity, different return type) — Kotlin
//     cannot resolve the call. We go through the support interface instead;
//     the bridge delegates to the same keyed database, so behavior is
//     identical. (insertWithOnConflict → insert(table, CONFLICT_*, values),
//     rawQuery → query.)
// ══════════════════════════════════════════════════════════════════════════

data class StoredMessage(
    val messageId: String,
    val conversationId: String,
    val senderKeyId: String? = null,
    val senderId: String? = null,
    val ciphertext: String,
    val nonce: String,
    val ephemeralPubkey: String? = null,
    val signature: String? = null,
    val sentAt: String? = null,
    val status: String? = null,
)

data class StoredConversation(
    val conversationId: String,
    val conversationType: String? = null,
    val name: String? = null,
    /** JSON array of participant user-ids. */
    val participantsJson: String = "[]",
    val lastActivity: String? = null,
)

class DatabaseHelper(
    context: Context,
    passphraseProvider: () -> CharArray,
) : SQLiteOpenHelper(
    context,
    DATABASE_NAME,
    // 4.x takes the key at construction (String → UTF-8 bytes internally).
    // Resolved once here; rotating the key requires a new helper instance.
    passphraseProvider().concatToString(),
    null, // CursorFactory
    DATABASE_VERSION,
    0, // minimumSupportedVersion
    DefaultDatabaseErrorHandler(),
    null, // hook
    false, // enableWriteAheadLogging (library default)
) {

    companion object {
        private const val DATABASE_NAME = "vyve.db"
        private const val DATABASE_VERSION = 1
    }

    init {
        // 4.x removed SQLiteDatabase.loadLibs(); the AAR never loads its own
        // libsqlcipher.so, so the host app must load it once per process.
        System.loadLibrary("sqlcipher")
    }

    // Via the SupportSQLiteOpenHelper interface: the concrete no-arg
    // getWritableDatabase()/getReadableDatabase() are unresolvable from Kotlin
    // (bridge-method collision), and the interface bridges delegate to them.
    private fun writable(): SupportSQLiteDatabase =
        (this as SupportSQLiteOpenHelper).writableDatabase

    private fun readable(): SupportSQLiteDatabase =
        (this as SupportSQLiteOpenHelper).readableDatabase

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """
            CREATE TABLE messages (
                message_id      TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                sender_key_id   TEXT,
                sender_id       TEXT,
                ciphertext      TEXT NOT NULL,
                nonce           TEXT NOT NULL,
                ephemeral_pubkey TEXT,
                signature       TEXT,
                sent_at         TEXT,
                status          TEXT
            )
            """.trimIndent(),
        )
        db.execSQL("CREATE INDEX idx_messages_conversation ON messages(conversation_id)")

        db.execSQL(
            """
            CREATE TABLE conversations (
                conversation_id   TEXT PRIMARY KEY,
                conversation_type TEXT,
                name              TEXT,
                participants      TEXT NOT NULL DEFAULT '[]',
                last_activity     TEXT
            )
            """.trimIndent(),
        )
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        // v1 is the first shipped schema; add migrations here when v2 lands.
        Timber.w("Database upgrade %d -> %d: no migrations defined", oldVersion, newVersion)
    }

    // ── Messages ──────────────────────────────────────────────────────────

    fun insertMessage(message: StoredMessage) {
        val values = ContentValues().apply {
            put("message_id", message.messageId)
            put("conversation_id", message.conversationId)
            put("sender_key_id", message.senderKeyId)
            put("sender_id", message.senderId)
            put("ciphertext", message.ciphertext)
            put("nonce", message.nonce)
            put("ephemeral_pubkey", message.ephemeralPubkey)
            put("signature", message.signature)
            put("sent_at", message.sentAt)
            put("status", message.status)
        }
        writable().insert(
            "messages",
            SQLiteDatabase.CONFLICT_REPLACE,
            values,
        )
    }

    fun getMessages(conversationId: String, limit: Int = 50): List<StoredMessage> {
        val messages = mutableListOf<StoredMessage>()
        readable().query(
            "SELECT message_id, conversation_id, sender_key_id, sender_id, ciphertext," +
                " nonce, ephemeral_pubkey, signature, sent_at, status" +
                " FROM messages WHERE conversation_id = ? ORDER BY sent_at DESC LIMIT ?",
            arrayOf<Any>(conversationId, limit.toString()),
        ).use { cursor ->
            val idx = { name: String -> cursor.getColumnIndexOrThrow(name) }
            while (cursor.moveToNext()) {
                messages += StoredMessage(
                    messageId = cursor.getString(idx("message_id")),
                    conversationId = cursor.getString(idx("conversation_id")),
                    senderKeyId = cursor.getString(idx("sender_key_id")),
                    senderId = cursor.getString(idx("sender_id")),
                    ciphertext = cursor.getString(idx("ciphertext")),
                    nonce = cursor.getString(idx("nonce")),
                    ephemeralPubkey = cursor.getString(idx("ephemeral_pubkey")),
                    signature = cursor.getString(idx("signature")),
                    sentAt = cursor.getString(idx("sent_at")),
                    status = cursor.getString(idx("status")),
                )
            }
        }
        return messages
    }

    // ── Conversations ─────────────────────────────────────────────────────

    fun upsertConversation(conversation: StoredConversation) {
        val values = ContentValues().apply {
            put("conversation_id", conversation.conversationId)
            put("conversation_type", conversation.conversationType)
            put("name", conversation.name)
            put("participants", conversation.participantsJson)
            put("last_activity", conversation.lastActivity)
        }
        writable().insert(
            "conversations",
            SQLiteDatabase.CONFLICT_REPLACE,
            values,
        )
    }

    fun getConversations(): List<StoredConversation> {
        val conversations = mutableListOf<StoredConversation>()
        readable().query(
            "SELECT conversation_id, conversation_type, name, participants, last_activity" +
                " FROM conversations ORDER BY last_activity DESC",
        ).use { cursor ->
            val idx = { name: String -> cursor.getColumnIndexOrThrow(name) }
            while (cursor.moveToNext()) {
                conversations += StoredConversation(
                    conversationId = cursor.getString(idx("conversation_id")),
                    conversationType = cursor.getString(idx("conversation_type")),
                    name = cursor.getString(idx("name")),
                    participantsJson = cursor.getString(idx("participants")) ?: "[]",
                    lastActivity = cursor.getString(idx("last_activity")),
                )
            }
        }
        return conversations
    }

    fun deleteConversation(conversationId: String) {
        writable().delete("messages", "conversation_id = ?", arrayOf(conversationId))
        writable().delete("conversations", "conversation_id = ?", arrayOf(conversationId))
    }
}
