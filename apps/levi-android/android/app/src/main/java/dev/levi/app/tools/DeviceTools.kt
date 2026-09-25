package dev.levi.app.tools

import android.Manifest
import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.SearchManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.location.LocationManager
import android.net.Uri
import android.os.Build
import android.os.Looper
import android.provider.AlarmClock
import android.provider.CalendarContract
import android.provider.Settings
import android.webkit.MimeTypeMap
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import dev.levi.app.MainActivity
import dev.levi.app.R
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.URL
import java.time.Instant
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import javax.net.ssl.HttpsURLConnection

/**
 * Native implementations of LEVI's on-device tools.
 *
 * Every tool is explicit and fail-closed:
 * - tools that need an Android runtime permission check it first and
 *   return a `permission_denied` result instead of proceeding;
 * - tools that launch another app verify an activity can handle the
 *   intent and report `no_handler` otherwise;
 * - nothing collects data silently — location is read only when the
 *   `location_coarse` tool is invoked, and network fetch is HTTPS-only
 *   with strict size/time caps.
 *
 * All public entry points take an application context (never an
 * Activity) so they are safe to call from a background agent runtime.
 */
object DeviceTools {

    // ---- Tool names (stable, used by ToolStore keys and the manifest) ----

    const val NOTIFY = "notify"
    const val CALENDAR_EVENT = "calendar_event"
    const val ALARM = "alarm"
    const val LOCATION_COARSE = "location_coarse"
    const val OPEN_URL = "open_url"
    const val OPEN_FILE = "open_file"
    const val LOCAL_TIME = "local_time"
    const val WEB_SEARCH = "web_search"
    const val FETCH_URL = "fetch_url"

    val toolNames: List<String> = listOf(
        NOTIFY, CALENDAR_EVENT, ALARM, LOCATION_COARSE,
        OPEN_URL, OPEN_FILE, LOCAL_TIME, WEB_SEARCH, FETCH_URL,
    )

    private const val CHANNEL_TOOLS = "levi_device_tools"
    private const val FETCH_MAX_BYTES = 256 * 1024
    private const val USER_AGENT = "LEVI-Android/1.0 (device-tool)"

    // ---- Specs (UI + manifest contract source for titles/icons) ----

    /** Localized specs for the Tools screen. Names match [toolNames]. */
    @android.annotation.SuppressLint("InlinedApi") // POST_NOTIFICATIONS field needs API 33; declared in manifest
    fun specs(context: Context): List<ToolSpec> = listOf(
        ToolSpec(
            name = NOTIFY,
            titleRes = R.string.tool_notify_title,
            descriptionRes = R.string.tool_notify_desc,
            iconRes = R.drawable.ic_bell,
            permission = Manifest.permission.POST_NOTIFICATIONS,
            risk = RiskLevel.LOW,
            params = listOf(
                ParamSpec("title", "string", true, "Notification title (non-empty)."),
                ParamSpec("body", "string", true, "Notification body text (non-empty)."),
            ),
        ),
        ToolSpec(
            name = CALENDAR_EVENT,
            titleRes = R.string.tool_calendar_title,
            descriptionRes = R.string.tool_calendar_desc,
            iconRes = R.drawable.ic_devices,
            permission = null, // insert via system editor — user confirms on screen
            risk = RiskLevel.LOW,
            params = listOf(
                ParamSpec("title", "string", true, "Event title."),
                ParamSpec("description", "string", false, "Event notes."),
                ParamSpec("location", "string", false, "Event location text."),
                ParamSpec("start_millis", "integer", false, "Start time, epoch millis. Defaults to now."),
                ParamSpec("end_millis", "integer", false, "End time, epoch millis. Defaults to start + 1h."),
                ParamSpec("all_day", "boolean", false, "All-day event.", "false"),
            ),
            noteRes = R.string.tool_calendar_note,
        ),
        ToolSpec(
            name = ALARM,
            titleRes = R.string.tool_alarm_title,
            descriptionRes = R.string.tool_alarm_desc,
            iconRes = R.drawable.ic_bell,
            permission = null, // system clock app handles it — no permission needed
            risk = RiskLevel.LOW,
            params = listOf(
                ParamSpec("kind", "string", false, "\"alarm\" or \"timer\".", "alarm"),
                ParamSpec("hour", "integer", false, "Alarm hour 0-23 (kind=alarm)."),
                ParamSpec("minute", "integer", false, "Alarm minute 0-59 (kind=alarm)."),
                ParamSpec("length_seconds", "integer", false, "Timer length 1-86400s (kind=timer)."),
                ParamSpec("message", "string", false, "Label shown on the alarm/timer."),
                ParamSpec("skip_ui", "boolean", false, "Try to set without showing the clock UI.", "false"),
            ),
        ),
        ToolSpec(
            name = LOCATION_COARSE,
            titleRes = R.string.tool_location_title,
            descriptionRes = R.string.tool_location_desc,
            iconRes = R.drawable.ic_devices,
            permission = Manifest.permission.ACCESS_COARSE_LOCATION,
            risk = RiskLevel.HIGH,
            params = emptyList(),
            noteRes = R.string.tool_location_note,
        ),
        ToolSpec(
            name = OPEN_URL,
            titleRes = R.string.tool_open_url_title,
            descriptionRes = R.string.tool_open_url_desc,
            iconRes = R.drawable.ic_link,
            permission = null,
            risk = RiskLevel.MEDIUM,
            params = listOf(
                ParamSpec("url", "string", true, "http(s) URL to open in the default browser."),
            ),
        ),
        ToolSpec(
            name = OPEN_FILE,
            titleRes = R.string.tool_open_file_title,
            descriptionRes = R.string.tool_open_file_desc,
            iconRes = R.drawable.ic_doc,
            permission = null,
            risk = RiskLevel.MEDIUM,
            params = listOf(
                ParamSpec("path", "string", true, "Absolute path to a file inside the app's own storage."),
            ),
            noteRes = R.string.tool_open_file_note,
        ),
        ToolSpec(
            name = LOCAL_TIME,
            titleRes = R.string.tool_local_time_title,
            descriptionRes = R.string.tool_local_time_desc,
            iconRes = R.drawable.ic_devices,
            permission = null,
            risk = RiskLevel.LOW,
            params = emptyList(),
        ),
        ToolSpec(
            name = WEB_SEARCH,
            titleRes = R.string.tool_web_search_title,
            descriptionRes = R.string.tool_web_search_desc,
            iconRes = R.drawable.ic_chat,
            permission = null,
            risk = RiskLevel.LOW,
            params = listOf(
                ParamSpec("query", "string", true, "Search query (non-empty)."),
            ),
        ),
        ToolSpec(
            name = FETCH_URL,
            titleRes = R.string.tool_fetch_url_title,
            descriptionRes = R.string.tool_fetch_url_desc,
            iconRes = R.drawable.ic_download,
            permission = null, // INTERNET is an install-time permission
            risk = RiskLevel.MEDIUM,
            params = listOf(
                ParamSpec("url", "string", true, "HTTPS URL to fetch. Plain HTTP is refused."),
                ParamSpec("max_chars", "integer", false, "Body chars to return (100-100000).", "8000"),
                ParamSpec("timeout_ms", "integer", false, "Connect+read timeout (1000-30000).", "10000"),
            ),
            noteRes = R.string.tool_fetch_url_note,
        ),
    )

    fun specFor(name: String, context: Context): ToolSpec? =
        specs(context).firstOrNull { it.name == name }

    // ---- Dispatch ----

    /** Runs [name] with [params]. Assumes toggle + permission were checked by [ToolGateway]. */
    fun run(context: Context, name: String, params: JSONObject): JSONObject {
        val ctx = context.applicationContext
        return when (name) {
            NOTIFY -> runNotify(ctx, params)
            CALENDAR_EVENT -> runCalendarEvent(ctx, params)
            ALARM -> runAlarm(ctx, params)
            LOCATION_COARSE -> runLocationCoarse(ctx, params)
            OPEN_URL -> runOpenUrl(ctx, params)
            OPEN_FILE -> runOpenFile(ctx, params)
            LOCAL_TIME -> runLocalTime(ctx)
            WEB_SEARCH -> runWebSearch(ctx, params)
            FETCH_URL -> runFetchUrl(ctx, params)
            else -> fail("unknown_tool", "No such tool: $name")
        }
    }

    /** True when the runtime permission (if any) for [permission] is granted. */
    fun hasPermission(context: Context, permission: String?): Boolean {
        if (permission == null) return true
        if (permission == Manifest.permission.POST_NOTIFICATIONS &&
            Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU
        ) {
            return true // install-time on older Android
        }
        return ContextCompat.checkSelfPermission(context, permission) ==
            PackageManager.PERMISSION_GRANTED
    }

    // ---- Result helpers ----

    private fun ok(): JSONObject = JSONObject().put("ok", true)

    private fun fail(code: String, message: String): JSONObject =
        JSONObject().put("ok", false).put("error", code).put("message", message)

    private fun permissionDenied(permission: String): JSONObject =
        JSONObject()
            .put("ok", false)
            .put("error", "permission_denied")
            .put("permission", permission)
            .put(
                "message",
                "Android permission $permission is not granted. " +
                    "Grant it in system Settings (Apps > LEVI > Permissions), then retry.",
            )

    private fun noHandler(what: String): JSONObject =
        fail("no_handler", "No app on this device can handle $what.")

    private fun requiredString(params: JSONObject, name: String): String? {
        val v = params.optString(name, "").trim()
        return v.ifEmpty { null }
    }

    // ---- 1. notify ----

    // POST_NOTIFICATIONS is an API-33 field; the manifest declares it and
    // hasPermission() treats it as install-time below API 33.
    @android.annotation.SuppressLint("InlinedApi")
    private fun runNotify(context: Context, params: JSONObject): JSONObject {
        if (!hasPermission(context, Manifest.permission.POST_NOTIFICATIONS)) {
            return permissionDenied(Manifest.permission.POST_NOTIFICATIONS)
        }
        val nm = context.getSystemService(NotificationManager::class.java) ?: return fail(
            "unavailable",
            "Notification service unavailable.",
        )
        if (!nm.areNotificationsEnabled()) {
            return fail(
                "notifications_disabled",
                "Notifications are disabled for LEVI at the system level. " +
                    "Enable them in system Settings to use this tool.",
            )
        }
        val title = requiredString(params, "title")
            ?: return fail("missing_param", "Parameter 'title' is required and must be non-empty.")
        val body = requiredString(params, "body")
            ?: return fail("missing_param", "Parameter 'body' is required and must be non-empty.")
        ensureToolsChannel(context, nm)
        val tap = PendingIntent.getActivity(
            context,
            0,
            Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, CHANNEL_TOOLS)
            .setSmallIcon(R.drawable.ic_bell)
            .setContentTitle(title.take(120))
            .setContentText(body.take(400))
            .setStyle(NotificationCompat.BigTextStyle().bigText(body.take(2000)))
            .setContentIntent(tap)
            .setAutoCancel(true)
            .build()
        return try {
            nm.notify((System.currentTimeMillis() % Int.MAX_VALUE).toInt(), notification)
            ok().put("posted", true).put("channel", CHANNEL_TOOLS)
        } catch (e: SecurityException) {
            permissionDenied(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    private fun ensureToolsChannel(context: Context, nm: NotificationManager) {
        // NotificationChannel needs API 26 == minSdk; no version guard required.
        if (nm.getNotificationChannel(CHANNEL_TOOLS) == null) {
            nm.createNotificationChannel(
                NotificationChannel(
                    CHANNEL_TOOLS,
                    context.getString(R.string.tools_channel_name),
                    NotificationManager.IMPORTANCE_DEFAULT,
                ).apply { description = context.getString(R.string.tools_channel_desc) },
            )
        }
    }

    // ---- 2. calendar_event ----

    private fun runCalendarEvent(context: Context, params: JSONObject): JSONObject {
        val title = requiredString(params, "title")
            ?: return fail("missing_param", "Parameter 'title' is required and must be non-empty.")
        val now = System.currentTimeMillis()
        val start = params.optLong("start_millis", now)
        var end = params.optLong("end_millis", 0L)
        if (end <= 0L) end = start + 3_600_000L
        val intent = Intent(Intent.ACTION_INSERT)
            .setData(CalendarContract.Events.CONTENT_URI)
            .putExtra(CalendarContract.Events.TITLE, title)
            .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, start)
            .putExtra(CalendarContract.EXTRA_EVENT_END_TIME, end)
            .putExtra(
                CalendarContract.EXTRA_EVENT_ALL_DAY,
                params.optBoolean("all_day", false),
            )
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        params.optString("description", "").takeIf { it.isNotBlank() }?.let {
            intent.putExtra(CalendarContract.Events.DESCRIPTION, it)
        }
        params.optString("location", "").takeIf { it.isNotBlank() }?.let {
            intent.putExtra(CalendarContract.Events.EVENT_LOCATION, it)
        }
        if (intent.resolveActivity(context.packageManager) == null) {
            return noHandler("a calendar insert")
        }
        context.startActivity(intent)
        return ok().put("launched", true)
            .put("note", "The system calendar editor was opened; the user confirms the event there.")
    }

    // ---- 3. alarm / timer ----

    private fun runAlarm(context: Context, params: JSONObject): JSONObject {
        val kind = params.optString("kind", "alarm").lowercase()
        val message = params.optString("message", "").takeIf { it.isNotBlank() }
        val skipUi = params.optBoolean("skip_ui", false)
        val intent = when (kind) {
            "timer" -> {
                val len = params.optInt("length_seconds", 0)
                if (len < 1 || len > 86_400) {
                    return fail(
                        "bad_param",
                        "Parameter 'length_seconds' must be 1-86400 for kind=timer.",
                    )
                }
                Intent(AlarmClock.ACTION_SET_TIMER)
                    .putExtra(AlarmClock.EXTRA_LENGTH, len)
            }
            "alarm" -> {
                val hour = params.optInt("hour", -1)
                val minute = params.optInt("minute", -1)
                if (hour !in 0..23 || minute !in 0..59) {
                    return fail(
                        "bad_param",
                        "Parameters 'hour' (0-23) and 'minute' (0-59) are required for kind=alarm.",
                    )
                }
                Intent(AlarmClock.ACTION_SET_ALARM)
                    .putExtra(AlarmClock.EXTRA_HOUR, hour)
                    .putExtra(AlarmClock.EXTRA_MINUTES, minute)
            }
            else -> return fail("bad_param", "Parameter 'kind' must be \"alarm\" or \"timer\".")
        }
        message?.let { intent.putExtra(AlarmClock.EXTRA_MESSAGE, it) }
        intent.putExtra(AlarmClock.EXTRA_SKIP_UI, skipUi)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (intent.resolveActivity(context.packageManager) == null) {
            return noHandler("an alarm/timer request")
        }
        context.startActivity(intent)
        return ok().put("launched", true).put("kind", kind)
    }

    // ---- 4. location_coarse ----

    private fun runLocationCoarse(context: Context, params: JSONObject): JSONObject {
        if (!hasPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION)) {
            return permissionDenied(Manifest.permission.ACCESS_COARSE_LOCATION)
        }
        val lm = context.getSystemService(LocationManager::class.java)
            ?: return fail("unavailable", "Location service unavailable.")
        if (!lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
            return fail(
                "provider_disabled",
                "Network location is disabled on this device. Enable location services to use this tool.",
            )
        }
        val loc = try {
            lm.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
        } catch (e: SecurityException) {
            return permissionDenied(Manifest.permission.ACCESS_COARSE_LOCATION)
        }
        if (loc == null) {
            return fail(
                "location_unavailable",
                "No recent network-based fix. Open an app that uses location once, then retry.",
            )
        }
        return ok()
            .put("latitude", loc.latitude)
            .put("longitude", loc.longitude)
            .put("accuracy_m", loc.accuracy)
            .put("fix_time_millis", loc.time)
            .put("provider", loc.provider)
            .put(
                "note",
                "Coarse, network/IP-based estimate (ACCESS_COARSE_LOCATION). " +
                    "Accuracy is city-block level at best; never treat as precise.",
            )
    }

    // ---- 5. open_url ----

    private fun runOpenUrl(context: Context, params: JSONObject): JSONObject {
        val raw = requiredString(params, "url")
            ?: return fail("missing_param", "Parameter 'url' is required and must be non-empty.")
        val uri = try {
            Uri.parse(raw)
        } catch (e: Exception) {
            return fail("bad_param", "Parameter 'url' is not a valid URI.")
        }
        val scheme = uri.scheme?.lowercase()
        if (scheme != "http" && scheme != "https") {
            return fail("bad_param", "Only http and https URLs can be opened; got '$scheme'.")
        }
        val intent = Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (intent.resolveActivity(context.packageManager) == null) {
            return noHandler("a web URL")
        }
        context.startActivity(intent)
        return ok().put("launched", true).put("url", uri.toString())
    }

    // ---- 6. open_file ----

    private fun runOpenFile(context: Context, params: JSONObject): JSONObject {
        val raw = requiredString(params, "path")
            ?: return fail("missing_param", "Parameter 'path' is required and must be non-empty.")
        val file = File(raw)
        val canonical = try {
            file.canonicalPath
        } catch (e: Exception) {
            return fail("bad_param", "Path cannot be resolved: $raw")
        }
        // Fail-closed scope: only files inside the app's own storage.
        val roots = listOfNotNull(
            context.cacheDir, context.filesDir,
            context.externalCacheDir, context.getExternalFilesDir(null),
        ).mapNotNull { runCatching { it.canonicalPath }.getOrNull() }
        if (roots.none { canonical == it || canonical.startsWith(it + File.separator) }) {
            return fail(
                "path_outside_scope",
                "Only files inside the app's own storage can be opened.",
            )
        }
        if (!file.isFile) return fail("not_found", "No such file: $canonical")
        val ext = file.extension.lowercase()
        val mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext) ?: "*/*"
        val uri = try {
            FileProvider.getUriForFile(context, context.packageName + ".fileprovider", file)
        } catch (e: IllegalArgumentException) {
            return fail("not_shareable", "This file cannot be shared with another app.")
        }
        val intent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, mime)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (intent.resolveActivity(context.packageManager) == null) {
            return noHandler("this file type ($mime)")
        }
        context.startActivity(Intent.createChooser(intent, file.name))
        return ok().put("launched", true).put("mime", mime)
    }

    // ---- 7. local_time ----

    private fun runLocalTime(context: Context): JSONObject {
        val now = ZonedDateTime.now()
        val zone = ZoneId.systemDefault()
        return ok()
            .put("epoch_millis", System.currentTimeMillis())
            .put("iso", now.format(DateTimeFormatter.ISO_OFFSET_DATE_TIME))
            .put("timezone", zone.id)
            .put("utc_offset", now.offset.id)
    }

    // ---- 8. web_search ----

    private fun runWebSearch(context: Context, params: JSONObject): JSONObject {
        val query = requiredString(params, "query")
            ?: return fail("missing_param", "Parameter 'query' is required and must be non-empty.")
        val intent = Intent(Intent.ACTION_WEB_SEARCH)
            .putExtra(SearchManager.QUERY, query)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (intent.resolveActivity(context.packageManager) == null) {
            return noHandler("a web search")
        }
        context.startActivity(intent)
        return ok().put("launched", true)
            .put("note", "Handed to the device's default search handler; results stay in that app.")
    }

    // ---- 9. fetch_url ----

    private fun runFetchUrl(context: Context, params: JSONObject): JSONObject {
        if (Looper.myLooper() == Looper.getMainLooper()) {
            return fail(
                "main_thread",
                "fetch_url performs network I/O and must run off the main thread.",
            )
        }
        val raw = requiredString(params, "url")
            ?: return fail("missing_param", "Parameter 'url' is required and must be non-empty.")
        val maxChars = params.optInt("max_chars", 8000).coerceIn(100, 100_000)
        val timeoutMs = params.optInt("timeout_ms", 10_000).coerceIn(1_000, 30_000)

        var current = raw
        var status = -1
        var contentType = ""
        var redirects = 0
        try {
            while (true) {
                val url = URL(current)
                if (url.protocol.lowercase() != "https") {
                    return fail(
                        "insecure_scheme",
                        "Only https:// URLs are fetched; got '${url.protocol}'. " +
                            "This tool never sends agent traffic over cleartext.",
                    )
                }
                val conn = (url.openConnection() as HttpsURLConnection).apply {
                    instanceFollowRedirects = false
                    connectTimeout = timeoutMs
                    readTimeout = timeoutMs
                    setRequestProperty("User-Agent", USER_AGENT)
                    setRequestProperty("Accept", "text/*,application/json,*/*;q=0.1")
                }
                status = conn.responseCode
                if (status in 301..308 && redirects < 5) {
                    val loc = conn.getHeaderField("Location")
                        ?: return fail("fetch_failed", "Redirect ($status) with no Location header.")
                    conn.disconnect()
                    current = URL(url, loc).toString()
                    redirects++
                    continue
                }
                contentType = conn.getHeaderField("Content-Type").orEmpty()
                val charset = Regex("charset=([^;]+)", RegexOption.IGNORE_CASE)
                    .find(contentType)?.groupValues?.get(1)?.trim().orEmpty()
                    .ifEmpty { "UTF-8" }
                val stream = if (status in 200..299) conn.inputStream else conn.errorStream
                    ?: return fail("fetch_failed", "HTTP $status with no response body.")
                // Manual capped read: InputStream.readNBytes() needs API 33.
                val bytes = ByteArrayOutputStream().also { out ->
                    val buf = ByteArray(8192)
                    var total = 0
                    stream.use { input ->
                        while (total <= FETCH_MAX_BYTES) {
                            val n = input.read(buf)
                            if (n < 0) break
                            out.write(buf, 0, n)
                            total += n
                        }
                    }
                }.toByteArray()
                conn.disconnect()
                val truncated = bytes.size > FETCH_MAX_BYTES
                val body = bytes.take(FETCH_MAX_BYTES).toByteArray()
                    .toString(charset(charset))
                return ok()
                    .put("status", status)
                    .put("final_url", current)
                    .put("content_type", contentType)
                    .put("truncated", truncated || body.length > maxChars)
                    .put("body", if (body.length > maxChars) body.take(maxChars) else body)
            }
        } catch (e: SecurityException) {
            return fail("fetch_failed", "Blocked by device policy: ${e.message}")
        } catch (e: Exception) {
            return fail("fetch_failed", "Fetch failed: ${e.message}")
        }
    }
}
