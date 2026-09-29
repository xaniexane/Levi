/* google-drive cell — in-editor companion for the Drive plugin.
 *
 * Honest split (G6): the cell CANNOT reach the Drive API — the tricombs
 * contract has no exec capability (verified against caps.ts), and the
 * cell holds no tokens. What it really does:
 *   - stage-active: copies the active buffer into google-drive-outbox/
 *     via fs-write, then tells the user the exact engine command that
 *     completes the push.
 *   - drive-help: shows the engine command reference.
 * No network strings anywhere in this file.
 */

defineCellPlugin(function (cell) {
  var OUTBOX = "google-drive-outbox/";

  function baseName(path) {
    if (!path) return "untitled.txt";
    var parts = String(path).split("/");
    return parts[parts.length - 1] || "untitled.txt";
  }

  cell.registerCommand({
    id: "google-drive.stage-active",
    title: "Google Drive: stage active file for push",
    category: "Google",
  });
  cell.registerCommand({
    id: "google-drive.drive-help",
    title: "Google Drive: command reference",
    category: "Google",
  });

  cell.onCommand("google-drive.stage-active", function () {
    return cell.call("editor", "getActiveText", []).then(function (text) {
      if (text === null || text === undefined) {
        cell.notify("google-drive: no active buffer to stage.", "error");
        return { staged: false, reason: "no-active-buffer" };
      }
      return cell.call("editor", "getActivePath", []).then(function (path) {
        var name = baseName(path);
        var dest = OUTBOX + name;
        return cell.call("fs-write", "write", [dest, String(text)]).then(function () {
          cell.notify(
            "staged to " + dest + " — push it with: " +
            "python3 -m levi.si.plugins.google_drive push " + dest,
            "info"
          );
          return { staged: true, path: dest };
        });
      });
    });
  });

  cell.onCommand("google-drive.drive-help", function () {
    cell.notify(
      "drive engine: python3 -m levi.si.plugins.google_drive " +
      "ls [query] | pull <file-id> <local-path> | push <local-path> " +
      "[--name N] [--parent ID] [--update FILE_ID] — text/code files only, " +
      "no deletes, receipts on every transfer.",
      "info"
    );
    return { ok: true };
  });
});
