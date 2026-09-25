"""Termux device bridge — LEVI's connector to the Android pocket machine.

Chauncey develops on Android via Termux; this connector lets LEVI reach the
device beside the desk: battery, notifications, clipboard, location, the
share sheet. It is 100% stdlib and LEVI-native — no SDK, no paid APIs, no
cloud round-trip.

Every Termux API tool is *probed* with :func:`shutil.which` before use, and
every action degrades to an honest ``missing_tool`` reading instead of
raising. Nothing here assumes Termux exists: :meth:`TermuxBridge.probe`
tells the truth on any machine, and on a machine without the Termux API the
bridge simply reports everything unavailable.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

#: termux-api tools this bridge knows how to call.
TERMUX_TOOLS: tuple = (
    "termux-battery-status",
    "termux-clipboard-get",
    "termux-clipboard-set",
    "termux-notification",
    "termux-toast",
    "termux-vibrate",
    "termux-location",
    "termux-info",
    "termux-share",
    "termux-tts-speak",
)


@dataclass
class DeviceReading:
    """One probe/action result — honest about what happened."""

    ok: bool
    tool: str
    data: Any = None
    error: str = ""

    @property
    def missing_tool(self) -> bool:
        return not self.ok and self.error.startswith("missing tool:")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TermuxBridge:
    """A probed bridge to the Termux API on this machine.

    Construct with :meth:`probe` (never raw — probing is the point).
    """

    def __init__(self, tools: Dict[str, bool]):
        self._tools = dict(tools)

    # -- probing ------------------------------------------------------------

    @classmethod
    def probe(cls) -> "TermuxBridge":
        """Probe which termux-api tools exist on this machine."""
        return cls({tool: shutil.which(tool) is not None for tool in TERMUX_TOOLS})

    @property
    def available(self) -> Dict[str, bool]:
        return dict(self._tools)

    @property
    def present(self) -> List[str]:
        return [t for t, have in self._tools.items() if have]

    @property
    def missing(self) -> List[str]:
        return [t for t, have in self._tools.items() if not have]

    @property
    def on_termux(self) -> bool:
        """True when the Termux API surface is genuinely reachable."""
        return self._tools.get("termux-info", False)

    # -- actions ------------------------------------------------------------

    def _run(
        self, tool: str, args: List[str], *, timeout: float = 10.0
    ) -> DeviceReading:
        if not self._tools.get(tool):
            return DeviceReading(ok=False, tool=tool, error=f"missing tool: {tool}")
        try:
            proc = subprocess.run(
                [tool, *args],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return DeviceReading(ok=False, tool=tool, error=f"{tool} timed out")
        except OSError as exc:
            return DeviceReading(ok=False, tool=tool, error=f"{tool} failed: {exc}")
        if proc.returncode != 0:
            return DeviceReading(
                ok=False,
                tool=tool,
                error=(proc.stderr.strip() or f"{tool} exited {proc.returncode}"),
            )
        out = proc.stdout.strip()
        try:
            return DeviceReading(
                ok=True, tool=tool, data=json.loads(out) if out else None
            )
        except json.JSONDecodeError:
            return DeviceReading(ok=True, tool=tool, data=out)

    def info(self) -> DeviceReading:
        """Device info (termux-info)."""
        return self._run("termux-info", [])

    def battery(self) -> DeviceReading:
        """Battery status: percentage, plugged state, health."""
        return self._run("termux-battery-status", [])

    def notify(self, title: str, content: str = "") -> DeviceReading:
        """Fire a device notification."""
        if not title:
            return DeviceReading(
                ok=False, tool="termux-notification", error="title is required"
            )
        return self._run(
            "termux-notification", ["--title", title, "--content", content]
        )

    def toast(self, text: str) -> DeviceReading:
        """Show a short toast."""
        if not text:
            return DeviceReading(
                ok=False, tool="termux-toast", error="text is required"
            )
        return self._run("termux-toast", [text])

    def vibrate(self, duration_ms: int = 300) -> DeviceReading:
        """Vibrate the device for ``duration_ms`` milliseconds."""
        return self._run("termux-vibrate", ["-d", str(max(0, duration_ms))])

    def clipboard_get(self) -> DeviceReading:
        """Read the clipboard."""
        return self._run("termux-clipboard-get", [])

    def clipboard_set(self, text: str) -> DeviceReading:
        """Write the clipboard."""
        if not text:
            return DeviceReading(
                ok=False, tool="termux-clipboard-set", error="text is required"
            )
        return self._run("termux-clipboard-set", [text])

    def location(self) -> DeviceReading:
        """One-shot location fix (10s provider timeout)."""
        return self._run("termux-location", ["-p", "gps,network"], timeout=30.0)

    def share(self, path: str, *, title: str = "Share from LEVI") -> DeviceReading:
        """Open the Android share sheet for a file."""
        if not path:
            return DeviceReading(
                ok=False, tool="termux-share", error="path is required"
            )
        return self._run("termux-share", ["-a", "send", path, "-t", title])

    def speak(self, text: str) -> DeviceReading:
        """Speak text aloud via the device TTS engine."""
        if not text:
            return DeviceReading(
                ok=False, tool="termux-tts-speak", error="text is required"
            )
        return self._run("termux-tts-speak", [text])

    def status_card(self) -> Dict[str, Any]:
        """One honest snapshot: what is reachable and what is not."""
        return {
            "on_termux": self.on_termux,
            "present": self.present,
            "missing": self.missing,
            "battery": self.battery().to_dict(),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {"tools": dict(self._tools)}


def _cli(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="levi.integrations.termux",
        description="Termux device bridge — probe the Android pocket machine.",
    )
    ap.add_argument(
        "action",
        nargs="?",
        default="probe",
        choices=["probe", "battery", "notify", "toast", "info", "clipboard"],
        help="action to run",
    )
    ap.add_argument("--title", default="LEVI", help="notification title")
    ap.add_argument("--text", default="", help="notification/toast text")
    args = ap.parse_args(argv)

    bridge = TermuxBridge.probe()
    if args.action == "probe":
        print(json.dumps(bridge.status_card(), indent=2, sort_keys=True))
    elif args.action == "battery":
        print(json.dumps(bridge.battery().to_dict(), indent=2, sort_keys=True))
    elif args.action == "info":
        print(json.dumps(bridge.info().to_dict(), indent=2, sort_keys=True))
    elif args.action == "notify":
        print(json.dumps(bridge.notify(args.title, args.text).to_dict(), indent=2))
    elif args.action == "toast":
        print(json.dumps(bridge.toast(args.text or "ping").to_dict(), indent=2))
    elif args.action == "clipboard":
        print(json.dumps(bridge.clipboard_get().to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
