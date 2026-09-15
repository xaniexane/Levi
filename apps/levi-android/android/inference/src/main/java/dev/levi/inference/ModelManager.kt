package dev.levi.inference

import java.io.File
import java.io.IOException
import java.io.RandomAccessFile
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * Downloads GGUF models from Hugging Face into app-private storage.
 *
 * - Resume via HTTP Range; atomic publish via temp file + rename.
 * - SHA-256 verification when the catalog provides a digest (skipped
 *   honestly otherwise — see [ModelInfo.sha256]).
 * - No auth tokens anywhere: all catalog URLs are public.
 *
 * Network I/O only; pure helpers ([sha256Of], [parseContentRange],
 * [buildRangeHeader]) are JVM-testable.
 */
class ModelManager(private val modelsDir: File) {

    fun interface ProgressListener {
        fun onProgress(downloadedBytes: Long, totalBytes: Long)
    }

    init {
        if (!modelsDir.exists()) modelsDir.mkdirs()
    }

    fun modelFile(info: ModelInfo): File = File(modelsDir, info.file)

    fun isInstalled(info: ModelInfo): Boolean {
        val f = modelFile(info)
        return f.exists() && f.length() >= info.sizeBytes * 9 / 10
    }

    fun installedModels(): List<File> =
        modelsDir.listFiles { f -> f.isFile && f.name.endsWith(".gguf") }
            ?.sortedByDescending { it.lastModified() } ?: emptyList()

    /**
     * Download [info], resuming any partial file. Throws [IOException] on
     * network failure or hash mismatch. [isCancelled] is polled between
     * buffer writes.
     */
    @Throws(IOException::class)
    fun download(
        info: ModelInfo,
        listener: ProgressListener? = null,
        isCancelled: () -> Boolean = { false },
    ): File {
        if (!info.available) {
            throw IOException("${info.displayName} is not downloadable yet (${info.tagline})")
        }
        val url = info.downloadUrl
            ?: throw IOException("${info.displayName} has no download URL")
        val dest = modelFile(info)
        if (isInstalled(info)) {
            listener?.onProgress(dest.length(), dest.length())
            return dest
        }
        val tmp = File(modelsDir, info.file + ".part")
        var offset = if (tmp.exists()) tmp.length() else 0L

        val total = remoteSize(info, url, offset)
        var conn = openConnection(url, offset)
        try {
            val response = conn.responseCode
            // 416 has no HttpURLConnection constant; compare the literal.
            if (response == 416) {
                // Server says the range is done; treat tmp as complete.
                offset = tmp.length()
            } else if (response != HttpURLConnection.HTTP_OK &&
                response != HttpURLConnection.HTTP_PARTIAL
            ) {
                throw IOException("download failed: HTTP $response for $url")
            }
            if (response == HttpURLConnection.HTTP_OK && offset > 0) {
                // Server ignored Range — restart from scratch.
                tmp.delete()
                offset = 0
            }
            RandomAccessFile(tmp, "rw").use { raf ->
                raf.seek(offset)
                var downloaded = offset
                val buf = ByteArray(256 * 1024)
                conn.inputStream.use { input ->
                    while (true) {
                        if (isCancelled()) throw IOException("download cancelled")
                        val n = input.read(buf)
                        if (n < 0) break
                        raf.write(buf, 0, n)
                        downloaded += n
                        listener?.onProgress(downloaded, total ?: -1L)
                    }
                }
            }
        } finally {
            conn.disconnect()
        }

        if (info.sha256 != null) {
            val actual = sha256Of(tmp)
            if (!actual.equals(info.sha256, ignoreCase = true)) {
                throw IOException("SHA-256 mismatch for ${info.file}")
            }
        }
        if (!tmp.renameTo(dest)) throw IOException("failed to publish ${info.file}")
        listener?.onProgress(dest.length(), dest.length())
        return dest
    }

    private fun remoteSize(info: ModelInfo, url: String, offset: Long): Long? {
        // Prefer the catalog's declared size; confirm with a HEAD request.
        return try {
            val head = URL(url).openConnection() as HttpURLConnection
            head.requestMethod = "HEAD"
            head.connectTimeout = 15_000
            head.readTimeout = 15_000
            try {
                val len = head.getHeaderField("Content-Length")?.toLongOrNull()
                if (head.responseCode in 200..299 && len != null && len > 0) len else info.sizeBytes
            } finally {
                head.disconnect()
            }
        } catch (_: IOException) {
            info.sizeBytes
        }
    }

    private fun openConnection(url: String, offset: Long): HttpURLConnection {
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.connectTimeout = 20_000
        conn.readTimeout = 30_000
        conn.setRequestProperty("User-Agent", "levi-android/1.0")
        if (offset > 0) conn.setRequestProperty("Range", buildRangeHeader(offset))
        // Follow HF's redirect to the CDN.
        conn.instanceFollowRedirects = true
        return conn
    }

    companion object {
        /** "bytes 100-200/1000" -> 1000, or null when unparseable. */
        fun parseContentRange(header: String?): Long? {
            if (header == null) return null
            val slash = header.lastIndexOf('/')
            if (slash < 0) return null
            return header.substring(slash + 1).toLongOrNull()
        }

        fun buildRangeHeader(offset: Long): String = "bytes=$offset-"

        /** Hex SHA-256 of a file. */
        fun sha256Of(file: File): String {
            val digest = MessageDigest.getInstance("SHA-256")
            file.inputStream().use { input ->
                val buf = ByteArray(256 * 1024)
                while (true) {
                    val n = input.read(buf)
                    if (n < 0) break
                    digest.update(buf, 0, n)
                }
            }
            return digest.digest().joinToString("") { "%02x".format(it) }
        }
    }
}
