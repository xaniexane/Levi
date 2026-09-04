package com.cybrus.vyve.data

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import net.sqlcipher.database.SQLiteDatabase
import net.sqlcipher.database.SQLiteException
import java.security.Security

class DatabaseHelper(private val context: Context) : SQLiteOpenHelper(context, "vyve_db", null, 1) {
    private var db: SQLiteDatabase? = null

    override fun onCreate(db: SQLiteDatabase) {
        try {
            // Enable encryption
            val cipher = Security.getProvider("SQLCipher")
            if (cipher == null) {
                throw SQLiteException("SQLCipher provider not found")
            }
            db = SQLiteDatabase.openOrCreateDatabase(
                context.filesDir?.absolutePath + "/vyve_db",
                cipher
            )
            db.enableWriteAheadLogging(true)
            
            // Create tables
            db.execSQL("CREATE TABLE messages (
                message_id TEXT PRIMARY KEY,
                conversation_id TEXT,
                sender_key_id TEXT,
                ciphertext BLOB,
                nonce BLOB,
                sent_at INTEGER,
                read_receipts TEXT,
                size_bucket TEXT,
                UNIQUE (conversation_id, sender_key_id)
            )")
            
            db.execSQL("CREATE TABLE conversations (
                conversation_id TEXT PRIMARY KEY,
                participants TEXT,
                created_at INTEGER,
                last_message_id TEXT,
                last_seen_at INTEGER,
                unread_count INTEGER DEFAULT 0
            )")
            
            db.execSQL("CREATE TABLE devices (
                device_id TEXT PRIMARY KEY,
                user_id TEXT,
                device_name TEXT,
                device_type TEXT,
                signing_key BLOB,
                encryption_key BLOB,
                registered_at INTEGER,
                trusted BOOLEAN DEFAULT 1,
                last_seen_at INTEGER,
                revoked_at INTEGER
            )")
            
        } catch (e: Exception) {
            throw SQLiteException("Database creation failed:", e)
        }
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        // Simplified — in production, handle migrations gracefully
        db.execSQL("DROP TABLE IF EXISTS messages")
        db.execSQL("DROP TABLE IF EXISTS conversations")
        onCreate(db)
    }

    fun insertMessage(
        conversationId: String,
        senderKeyId: String,
        ciphertext: String,
        nonce: String,
        sentAt: Long
    ): Long {
        val writable = db?.writableDatabase
        if (writable == null) return -1
        
        val stmt = writable.rawQuery("INSERT INTO messages (
            message_id,
            conversation_id,
            sender_key_id,
            ciphertext,
            nonce,
            sent_at,
            read_receipts,
            size_bucket
        ) VALUES (?,?,?,?,?,?,?,?)")
        
        val messageId = writable.insertWithOnConflict(
            null,
            null,
            "",
            conversationId,
            senderKeyId,
            ciphertext,
            nonce,
            sentAt,
            ""
        )
        return messageId
    }

    fun getMessages(conversationId: String): List<MessageEntity> {
        val readable = db?.readableDatabase
        if (readable == null) return emptyList()
        val cursor = readable.rawQuery(
            "SELECT * FROM messages WHERE conversation_id = ?",
            arrayOf(conversationId)
        )
        val messages = mutableListOf<MessageEntity>()
        while (cursor.moveToNext()) {
            val msg = MessageEntity(
                id = cursor.getLong(cursor.getColumnIndex("message_id")),
                conversationId = cursor.getString(cursor.getColumnIndex("conversation_id")),
                senderKeyId = cursor.getString(cursor.getColumnIndex("sender_key_id")),
                ciphertext = cursor.getString(cursor.getColumnIndex("ciphertext")),
                nonce = cursor.getString(cursor.getColumnIndex("nonce")),
                sentAt = cursor.getLong(cursor.getColumnIndex("sent_at")),
                readReceipts = cursor.getString(cursor.getColumnIndex("read_receipts")),
                sizeBucket = cursor.getString(cursor.getColumnIndex("size_bucket"))
            )
            messages.add(msg)
        }
        cursor.close()
        return messages
    }

    data class MessageEntity(
        val id: Long,
        val conversationId: String,
        val senderKeyId: String,
        val ciphertext: String,
        val nonce: String,
        val sentAt: Long,
        val readReceipts: String,
        val sizeBucket: String
    )
}
