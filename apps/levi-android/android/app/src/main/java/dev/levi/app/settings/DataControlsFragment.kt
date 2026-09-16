package dev.levi.app.settings

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.core.content.FileProvider
import androidx.fragment.app.Fragment
import dev.levi.app.R
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * Storage usage, data export and full wipe. Everything here is honest and
 * local: export zips what is actually on disk, and wipe uses the platform
 * clearApplicationUserData() — there is no hidden "delete but keep a copy".
 */
class DataControlsFragment : Fragment() {

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        val ctx = requireContext()
        val scroll = SettingsUi.pageScroll(ctx)
        val content = SettingsUi.pageContent(scroll)

        val group = SettingsUi.group(ctx, null)
        val rows = SettingsUi.rows(group)

        rows.addView(
            SettingsUi.row(
                ctx,
                R.drawable.ic_database,
                getString(R.string.data_storage_used),
                humanSize(dirSize(ctx.filesDir) + dirSize(ctx.cacheDir)),
            ),
        )
        rows.addView(SettingsUi.divider(ctx))
        rows.addView(
            SettingsUi.row(
                ctx,
                R.drawable.ic_download,
                getString(R.string.data_export),
                getString(R.string.data_export_sub),
            ) { exportData(ctx) },
        )
        rows.addView(SettingsUi.divider(ctx))
        rows.addView(
            SettingsUi.row(
                ctx,
                R.drawable.ic_info,
                getString(R.string.data_wipe),
                getString(R.string.data_wipe_sub),
            ) { confirmWipe(ctx) },
        )

        content.addView(group)
        content.addView(SettingsUi.note(ctx, getString(R.string.data_note)))
        return scroll
    }

    // ---- Storage size ----

    private fun dirSize(dir: File?): Long {
        if (dir == null || !dir.exists()) return 0L
        var total = 0L
        val stack = ArrayDeque<File>()
        stack.add(dir)
        while (stack.isNotEmpty()) {
            val f = stack.removeLast()
            if (f.isDirectory) {
                f.listFiles()?.let { stack.addAll(it) }
            } else {
                total += f.length()
            }
        }
        return total
    }

    private fun humanSize(bytes: Long): String {
        if (bytes < 1024) return "$bytes B"
        val kb = bytes / 1024.0
        if (kb < 1024) return "%.1f KB".format(Locale.US, kb)
        val mb = kb / 1024.0
        if (mb < 1024) return "%.1f MB".format(Locale.US, mb)
        return "%.2f GB".format(Locale.US, mb / 1024.0)
    }

    // ---- Export ----

    private fun exportData(ctx: Context) {
        val stamp = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date())
        val zip = File(ctx.cacheDir, "levi-export-$stamp.zip")
        Thread {
            try {
                zip.parentFile?.mkdirs()
                ZipOutputStream(BufferedOutputStream(FileOutputStream(zip))).use { zos ->
                    // filesDir itself (not cacheDir — that's where the zip lives).
                    addTree(zos, ctx.filesDir, "files", setOf(zip.canonicalPath))
                    // SharedPreferences store lives in <dataDir>/shared_prefs.
                    val prefsDir = File(ctx.applicationInfo.dataDir, "shared_prefs")
                    addTree(zos, prefsDir, "shared_prefs", setOf(zip.canonicalPath))
                }
                // The fragment may be gone by the time the zip is ready.
                activity?.runOnUiThread { shareZip(ctx, zip) }
            } catch (e: Exception) {
                activity?.runOnUiThread {
                    Toast.makeText(ctx, R.string.data_export_failed, Toast.LENGTH_LONG).show()
                }
            }
        }.start()
    }

    private fun addTree(zos: ZipOutputStream, root: File, prefix: String, skip: Set<String>) {
        if (!root.exists()) return
        val stack = ArrayDeque<Pair<File, String>>()
        stack.add(root to prefix)
        val buf = ByteArray(8192)
        while (stack.isNotEmpty()) {
            val (f, name) = stack.removeLast()
            if (f.canonicalPath in skip) continue
            if (f.isDirectory) {
                zos.putNextEntry(ZipEntry("$name/"))
                zos.closeEntry()
                f.listFiles()?.forEach { child ->
                    stack.add(child to "$name/${child.name}")
                }
            } else {
                zos.putNextEntry(ZipEntry(name))
                FileInputStream(f).use { input ->
                    var n = input.read(buf)
                    while (n > 0) {
                        zos.write(buf, 0, n)
                        n = input.read(buf)
                    }
                }
                zos.closeEntry()
            }
        }
    }

    private fun shareZip(ctx: Context, zip: File) {
        try {
            val uri = FileProvider.getUriForFile(ctx, ctx.packageName + ".fileprovider", zip)
            val send = Intent(Intent.ACTION_SEND).apply {
                type = "application/zip"
                putExtra(Intent.EXTRA_STREAM, uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            Toast.makeText(ctx, R.string.data_export_ready, Toast.LENGTH_SHORT).show()
            startActivity(Intent.createChooser(send, getString(R.string.data_export)))
        } catch (e: Exception) {
            Toast.makeText(ctx, R.string.data_share_failed, Toast.LENGTH_LONG).show()
        }
    }

    // ---- Wipe ----

    private fun confirmWipe(ctx: Context) {
        AlertDialog.Builder(ctx)
            .setTitle(R.string.data_wipe_title)
            .setMessage(R.string.data_wipe_message)
            .setNeutralButton(R.string.data_export_first) { _, _ -> exportData(ctx) }
            .setNegativeButton(R.string.data_cancel, null)
            .setPositiveButton(R.string.data_wipe_confirm) { _, _ -> reallyWipe(ctx) }
            .show()
    }

    private fun reallyWipe(ctx: Context) {
        AlertDialog.Builder(ctx)
            .setTitle(R.string.data_really_wipe_title)
            .setMessage(R.string.data_really_wipe_message)
            .setNegativeButton(R.string.data_cancel, null)
            .setPositiveButton(R.string.data_wipe_confirm) { _, _ ->
                wipeDeviceData(ctx)
            }
            .show()
    }

    private fun wipeDeviceData(ctx: Context) {
        if (Build.VERSION.SDK_INT >= 28) {
            (ctx.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager)
                .clearApplicationUserData()
            return
        }
        // Pre-P fallback (minSdk 26): the platform API doesn't exist, so
        // delete the app's own files and prefs manually, then exit.
        try {
            ctx.filesDir.deleteRecursively()
            ctx.cacheDir.deleteRecursively()
            File(ctx.applicationInfo.dataDir, "shared_prefs").deleteRecursively()
        } catch (e: Exception) {
            // Best effort; the user can also clear data from system settings.
        }
        android.os.Process.killProcess(android.os.Process.myPid())
    }
}
