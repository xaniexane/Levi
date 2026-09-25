"""Companion: the keeper's on-device hands.

Optional on-device automation for Termux (Android), recreated LEVI-native
from the consolidated offline-first upload's device_tools. The upload's
version returned bare strings and let any caller fire an SMS. The LEVI
version enforces the standing law:

* NOTHING here runs on a timer or in a background thread. Every call is
  something the keeper explicitly triggered -- Plan->Preview->Permission->
  Execute->Verify, with the Permission step enforced in code.
* Reads and writes are different permission classes. A write action
  (sending an SMS) requires `confirmed=True` -- the explicit permission
  token from the keeper's side -- and refuses malformed recipients and
  overlong messages before touching the subprocess.
* Results are structured (`ToolResult`), not bare strings, so callers can
  distinguish "the phone said no" from "Termux:API isn't installed".
* Missing `termux-*` binaries (i.e. not on a Termux phone) fail cleanly
  via `shutil.which`, never with a traceback.

On a normal machine every tool reports "unavailable" and does nothing.

stdlib-only.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

PHONE_RE = re.compile(r"^\+?[0-9][0-9\-.\s()]{5,20}$")
MAX_SMS_CHARS = 500
MAX_SCREEN_TEXT_CHARS = 1500

_TERMUX_BINARIES = ("termux-sms-list", "termux-sms-send", "termux-screenshot")


@dataclass
class ToolResult:
    """Structured outcome of one companion tool call."""

    ok: bool
    tool: str
    detail: str
    data: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "tool": self.tool,
            "detail": self.detail,
            "data": self.data,
        }


def _which(name: str):
    """Indirection for shutil.which so tests can simulate off-device."""
    return shutil.which(name)


def available() -> Dict[str, bool]:
    """Which Termux:API binaries exist on PATH. All False off-device."""
    return {name: _which(name) is not None for name in _TERMUX_BINARIES}


def on_device() -> bool:
    """True only when at least one Termux:API binary is present."""
    return any(available().values())


def _run(cmd: List[str], timeout: int = 15) -> subprocess.CompletedProcess:
    if _which(cmd[0]) is None:
        raise FileNotFoundError(f"{cmd[0]} is not installed (Termux:API missing)")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def read_sms(limit: int = 5) -> ToolResult:
    """Read recent inbox SMS. Read-class: no confirmation needed."""
    limit = max(1, min(int(limit), 50))
    try:
        result = _run(["termux-sms-list", "-t", "inbox", "-l", str(limit)])
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
        return ToolResult(False, "read_sms", f"unavailable: {exc}")
    if result.returncode != 0:
        err = result.stderr.strip() or "Termux:API call failed"
        return ToolResult(False, "read_sms", err)
    try:
        messages = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        return ToolResult(
            False, "read_sms", f"could not parse Termux:API output: {exc}"
        )
    items = [
        {"from": m.get("address", "?"), "body": str(m.get("body", ""))[:160]}
        for m in (messages or [])
    ]
    return ToolResult(
        True,
        "read_sms",
        f"{len(items)} message(s)" if items else "no SMS found",
        {"messages": items},
    )


def send_sms(number: str, message: str, *, confirmed: bool = False) -> ToolResult:
    """Send one SMS. Write-class: requires confirmed=True (the Permission step).

    `confirmed` must come from the keeper's explicit yes for THIS send --
    a standing "sure, text people" is not enough. This is the dual-key
    idea: policy (this module exists) AND per-action permission.
    """
    number = (number or "").strip()
    message = (message or "").strip()
    if not confirmed:
        return ToolResult(
            False,
            "send_sms",
            "refused: no per-action confirmation (confirmed=True required)",
        )
    if not PHONE_RE.match(number):
        return ToolResult(False, "send_sms", "refused: recipient looks malformed")
    if not message:
        return ToolResult(False, "send_sms", "refused: message is empty")
    if len(message) > MAX_SMS_CHARS:
        return ToolResult(
            False,
            "send_sms",
            f"refused: message too long ({len(message)} > {MAX_SMS_CHARS})",
        )
    try:
        result = _run(["termux-sms-send", "-n", number, message])
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
        return ToolResult(False, "send_sms", f"unavailable: {exc}")
    if result.returncode != 0:
        return ToolResult(
            False, "send_sms", result.stderr.strip() or "Termux:API call failed"
        )
    return ToolResult(True, "send_sms", f"SMS sent to {number}", {"to": number})


_ORGANIZE_CATEGORIES: Dict[str, List[str]] = {
    "Images": [".jpg", ".jpeg", ".png", ".webp", ".gif"],
    "Documents": [".pdf", ".txt", ".md", ".docx"],
    "Audio": [".mp3", ".flac", ".wav", ".m4a"],
    "Video": [".mp4", ".mkv", ".mov"],
    "Archives": [".zip", ".tar", ".gz", ".rar"],
}


def organize(directory: str, *, dry_run: bool = False) -> ToolResult:
    """Sort files into category folders. Preview with dry_run first.

    Never touches dotfiles, never overwrites an existing destination,
    never deletes anything.
    """
    path = Path(directory).expanduser()
    if not path.exists() or not path.is_dir():
        return ToolResult(False, "organize", f"directory not found: {directory}")
    planned = []
    for item in sorted(path.iterdir()):
        if not item.is_file() or item.name.startswith("."):
            continue
        for category, extensions in _ORGANIZE_CATEGORIES.items():
            if item.suffix.lower() in extensions:
                planned.append((item, category))
                break
    if dry_run:
        moves = [{"file": src.name, "to": cat} for src, cat in planned]
        return ToolResult(
            True,
            "organize",
            f"dry run: {len(moves)} file(s) would move",
            {"moves": moves},
        )
    moved = 0
    for item, category in planned:
        dest_dir = path / category
        dest_dir.mkdir(exist_ok=True)
        dest = dest_dir / item.name
        if dest.exists():
            continue
        item.rename(dest)
        moved += 1
    return ToolResult(True, "organize", f"moved {moved} file(s)", {"moved": moved})


def read_screen(max_chars: int = MAX_SCREEN_TEXT_CHARS) -> ToolResult:
    """Screenshot + OCR the current screen (needs Termux:API and tesseract)."""
    shot_path = os.path.join(tempfile.gettempdir(), "levi_screen.png")
    try:
        shot = _run(["termux-screenshot", shot_path], timeout=10)
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
        return ToolResult(False, "read_screen", f"unavailable: {exc}")
    if shot.returncode != 0:
        return ToolResult(
            False, "read_screen", shot.stderr.strip() or "screenshot failed"
        )
    if _which("tesseract") is None:
        return ToolResult(
            False, "read_screen", "screenshot saved, but tesseract is not installed"
        )
    try:
        ocr = subprocess.run(
            ["tesseract", shot_path, "stdout"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return ToolResult(False, "read_screen", f"OCR failed: {exc}")
    text = (ocr.stdout or "").strip()[:max_chars]
    return ToolResult(
        True,
        "read_screen",
        "screen text captured" if text else "no text detected",
        {"text": text},
    )


def tools() -> Dict[str, str]:
    """Capability manifest: what this module can do, and each tool's class."""
    return {
        "read_sms": "read -- recent inbox SMS",
        "send_sms": "write -- send one SMS (requires confirmed=True)",
        "organize": "write -- sort a directory into category folders (dry_run available)",
        "read_screen": "read -- screenshot + OCR current screen",
    }
