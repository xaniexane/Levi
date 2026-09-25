package dev.levi.app.tools

import android.content.Context
import org.json.JSONObject

/**
 * The agent runtime's front door to on-device tools.
 *
 * Contract: `execute(context, toolName, paramsJson) -> resultJson`.
 *
 * Every call passes three gates in order:
 *  1. **Known tool** — unknown names fail with `unknown_tool`.
 *  2. **User toggle** — [ToolStore] must have the tool enabled, else
 *     `tool_disabled`. The toggle is the user's standing consent.
 *  3. **Android permission** — the tool's declared runtime permission must
 *     be granted right now, else `permission_denied` (fail-closed; the
 *     tool never runs partially).
 *
 * Results are JSON objects: `{"ok": true, ...}` on success,
 * `{"ok": false, "error": "<code>", "message": "<human text>", ...}` on
 * failure. Callers must treat any non-`ok` result as "the action did not
 * happen".
 *
 * Threading: safe to call from any thread, but tools that do network I/O
 * ([DeviceTools.FETCH_URL]) refuse to run on the main thread — call this
 * from a background thread or coroutine in the agent runtime.
 *
 * Dependency-light by design: stdlib + AndroidX core only, org.json for
 * the JSON contract (built into Android).
 */
object ToolGateway {

    /** Machine-readable list of tools for the agent (mirrors assets/levi_tools.json). */
    fun listTools(context: Context): List<ToolSpec> = DeviceTools.specs(context)

    fun isEnabled(context: Context, toolName: String): Boolean =
        ToolStore.isEnabled(context.applicationContext, toolName)

    /**
     * Runs [toolName] with [paramsJson] (a JSON object string; may be blank
     * for parameterless tools) and returns the result as a JSON string.
     */
    fun execute(context: Context, toolName: String, paramsJson: String): String {
        val ctx = context.applicationContext
        val spec = DeviceTools.specFor(toolName, ctx)
            ?: return err("unknown_tool", "No such tool: $toolName")
        if (!ToolStore.isEnabled(ctx, toolName)) {
            return err(
                "tool_disabled",
                "The '${spec.name}' tool is turned off in LEVI Settings > Device tools. " +
                    "Ask the user to enable it.",
            )
        }
        if (!DeviceTools.hasPermission(ctx, spec.permission)) {
            return err(
                "permission_denied",
                "Android permission ${spec.permission} is not granted for '${spec.name}'. " +
                    "Grant it in system Settings (Apps > LEVI > Permissions), then retry.",
                spec.permission,
            )
        }
        val params = try {
            if (paramsJson.isBlank()) JSONObject() else JSONObject(paramsJson)
        } catch (e: Exception) {
            return err("bad_params", "paramsJson is not a valid JSON object: ${e.message}")
        }
        return try {
            DeviceTools.run(ctx, spec.name, params).toString()
        } catch (e: SecurityException) {
            err("permission_denied", "SecurityException running '${spec.name}': ${e.message}", spec.permission)
        } catch (e: Exception) {
            err("internal", "Tool '${spec.name}' failed: ${e.message}")
        }
    }

    private fun err(code: String, message: String, permission: String? = null): String =
        JSONObject()
            .put("ok", false)
            .put("error", code)
            .put("message", message)
            .apply { if (permission != null) put("permission", permission) }
            .toString()
}
