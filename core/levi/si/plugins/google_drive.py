"""Google Drive plugin — engine half.

Real Drive IO for code files through the existing connected
``hatch_gws_cli`` session (G7: the plugin never touches tokens).
The Hicomb cell (cells/google-drive/) is the in-editor companion: it
stages buffers to the outbox via fs caps and names the engine command
that completes the transfer (G6).

G1: no delete/trash/permissions methods exist on DriveSession.
G2: constructing a session makes no network calls.
G3: every transfer returns a receipt {file_id, name, sha256, bytes, ts}.
G4: text only; >1MB refused; undecodable bytes raise.

CLI (additive — no core CLI touched):
    python3 -m levi.si.plugins.google_drive ls [query]
    python3 -m levi.si.plugins.google_drive pull <file-id> <local-path>
    python3 -m levi.si.plugins.google_drive push <local-path> [--name N] [--parent ID] [--update FILE_ID]
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .glaws import GLAWS  # noqa: F401

CLI = "hatch_gws_cli"
MAX_TEXT_BYTES = 1_000_000

# Drive search scoped to code/text files (G1, G4)
CODE_QUERY = (
    "trashed = false and ("
    "mimeType contains 'text/' or "
    "name contains '.py' or name contains '.js' or name contains '.ts' or "
    "name contains '.md' or name contains '.json' or name contains '.html' or "
    "name contains '.css' or name contains '.sh'"
    ")"
)

_LIST_FIELDS = "files(id,name,mimeType,modifiedTime,size),nextPageToken"


class DriveError(RuntimeError):
    """A Drive operation failed. The CLI's stderr/api error is preserved."""


@dataclass(frozen=True)
class DriveReceipt:
    file_id: str
    name: str
    sha256: str
    bytes: int
    ts: str
    direction: str  # "pull" | "push"

    def to_dict(self) -> Dict:
        return {
            "file_id": self.file_id,
            "name": self.name,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "ts": self.ts,
            "direction": self.direction,
        }


class DriveSession:
    """Explicit-only Drive IO (G2). No calls happen before a method runs."""

    def __init__(self, cli: str = CLI, timeout: int = 60) -> None:
        self._cli = cli
        self._timeout = timeout
        # G2: __init__ does not call _run. (Proven by test.)

    # -- low-level -----------------------------------------------------
    def _run(self, *args: str, output: Optional[str] = None) -> Dict:
        exe = shutil.which(self._cli)
        if not exe:
            raise DriveError(f"{self._cli} not found on PATH")
        cmd = [exe, "drive", *args]
        if output:
            cmd += ["-o", output]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self._timeout
            )
        except subprocess.TimeoutExpired as exc:
            raise DriveError(f"drive call timed out: {' '.join(args[:3])}") from exc
        text = proc.stdout.strip()
        try:
            payload = json.loads(text) if text else {}
        except json.JSONDecodeError as exc:
            raise DriveError(
                f"drive call returned non-JSON: {text[:200]}"
            ) from exc
        if isinstance(payload, dict) and "error" in payload:
            err = payload["error"]
            msg = err.get("message", err) if isinstance(err, dict) else err
            raise DriveError(f"drive API error: {msg}")
        if proc.returncode != 0:
            raise DriveError(
                f"drive call failed (rc={proc.returncode}): "
                f"{proc.stderr.strip()[:300] or text[:300]}"
            )
        return payload if isinstance(payload, dict) else {}

    # -- reads ---------------------------------------------------------
    def list(self, query: str = "", limit: int = 25) -> List[Dict]:
        """List code/text files. Extra query terms ANDed with CODE_QUERY."""
        q = CODE_QUERY if not query.strip() else f"{CODE_QUERY} and ({query})"
        payload = self._run(
            "files", "list",
            "--params", json.dumps({
                "q": q,
                "fields": _LIST_FIELDS,
                "pageSize": max(1, min(100, limit)),
            }),
        )
        return [
            {
                "id": f.get("id", ""),
                "name": f.get("name", ""),
                "mimeType": f.get("mimeType", ""),
                "modifiedTime": f.get("modifiedTime", ""),
                "size": f.get("size"),
            }
            for f in payload.get("files", [])
            if isinstance(f, dict)
        ]

    def read_text(self, file_id: str) -> str:
        """Download a file and decode as text (G4 guards)."""
        if not file_id.strip():
            raise DriveError("read_text needs a file id")
        with tempfile.NamedTemporaryFile(
            prefix="levi-drive-", suffix=".bin", delete=False
        ) as tmp:
            tmp_path = tmp.name
        try:
            self._run(
                "files", "download",
                "--params", json.dumps({"fileId": file_id}),
                output=tmp_path,
            )
            raw = Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        if len(raw) > MAX_TEXT_BYTES:
            raise DriveError(
                f"refusing to decode {len(raw)} bytes as text "
                f"(cap {MAX_TEXT_BYTES})"
            )
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DriveError(
                "downloaded bytes are not UTF-8 text; refusing to guess"
            ) from exc

    def export_doc(self, file_id: str, mime: str = "text/plain") -> str:
        """Export a Google Workspace doc (Docs/Sheets) to text. Labeled."""
        with tempfile.NamedTemporaryFile(
            prefix="levi-drive-", suffix=".bin", delete=False
        ) as tmp:
            tmp_path = tmp.name
        try:
            self._run(
                "files", "export",
                "--params", json.dumps({"fileId": file_id, "mimeType": mime}),
                output=tmp_path,
            )
            raw = Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        if len(raw) > MAX_TEXT_BYTES:
            raise DriveError("exported doc exceeds text cap")
        return raw.decode("utf-8", errors="replace")

    # -- writes --------------------------------------------------------
    def _receipt(self, file_id: str, name: str, raw: bytes, direction: str) -> DriveReceipt:
        return DriveReceipt(
            file_id=file_id,
            name=name,
            sha256=hashlib.sha256(raw).hexdigest(),
            bytes=len(raw),
            ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            direction=direction,
        )

    def push_new(
        self, local_path: str, name: Optional[str] = None,
        parent: Optional[str] = None,
    ) -> DriveReceipt:
        """Upload a local text file as a new Drive file (G3 receipt)."""
        raw = Path(local_path).read_bytes()
        if len(raw) > MAX_TEXT_BYTES:
            raise DriveError("refusing to upload >1MB via this plugin")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DriveError("push_new takes UTF-8 text files only") from exc
        args = ["+upload", local_path]
        if name:
            args += ["--name", name]
        if parent:
            args += ["--parent", parent]
        payload = self._run(*args)
        file_id = str(payload.get("id", ""))
        if not file_id:
            raise DriveError(f"upload returned no file id: {str(payload)[:200]}")
        return self._receipt(file_id, name or Path(local_path).name, raw, "push")

    def push_update(self, file_id: str, local_path: str) -> DriveReceipt:
        """Replace the content of an existing Drive file (G3 receipt)."""
        if not file_id.strip():
            raise DriveError("push_update needs a file id")
        raw = Path(local_path).read_bytes()
        if len(raw) > MAX_TEXT_BYTES:
            raise DriveError("refusing to upload >1MB via this plugin")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DriveError("push_update takes UTF-8 text files only") from exc
        payload = self._run(
            "files", "update",
            "--params", json.dumps({"fileId": file_id}),
            "--upload", local_path,
            "--upload-content-type", "text/plain",
        )
        return self._receipt(
            str(payload.get("id", file_id)), str(payload.get("name", "")),
            raw, "push",
        )

    def pull(
        self, file_id: str, local_path: str
    ) -> DriveReceipt:
        """Download a Drive file to a local path (G3 receipt)."""
        text = self.read_text(file_id)
        raw = text.encode("utf-8")
        out = Path(local_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        meta = self._run(
            "files", "get",
            "--params", json.dumps({"fileId": file_id, "fields": "id,name"}),
        )
        return self._receipt(
            str(meta.get("id", file_id)), str(meta.get("name", out.name)),
            raw, "pull",
        )


__all__ = ["DriveSession", "DriveReceipt", "DriveError", "CODE_QUERY", "MAX_TEXT_BYTES"]


def _main(argv: List[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    sess = DriveSession()
    cmd = argv[0]
    try:
        if cmd == "ls":
            for f in sess.list(argv[1] if len(argv) > 1 else ""):
                print(f"{f['id']}  {f['name']}  [{f['mimeType']}]")
        elif cmd == "pull":
            if len(argv) != 3:
                print("usage: pull <file-id> <local-path>", file=sys.stderr)
                return 2
            r = sess.pull(argv[1], argv[2])
            print(json.dumps(r.to_dict(), indent=2))
        elif cmd == "push":
            # push <local-path> [--name N] [--parent ID] [--update FILE_ID]
            rest = argv[1:]
            if not rest:
                print("usage: push <local-path> [--name N] [--parent ID] [--update FILE_ID]",
                      file=sys.stderr)
                return 2
            name = parent = update = None
            path = rest[0]
            i = 1
            while i < len(rest):
                if rest[i] == "--name" and i + 1 < len(rest):
                    name = rest[i + 1]; i += 2
                elif rest[i] == "--parent" and i + 1 < len(rest):
                    parent = rest[i + 1]; i += 2
                elif rest[i] == "--update" and i + 1 < len(rest):
                    update = rest[i + 1]; i += 2
                else:
                    i += 1
            r = sess.push_update(update, path) if update else sess.push_new(path, name, parent)
            print(json.dumps(r.to_dict(), indent=2))
        else:
            print(f"unknown command {cmd!r}", file=sys.stderr)
            return 2
    except DriveError as exc:
        print(f"drive error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
