"""Phone hardware bridge — LEVI's device-assistant body over Termux:API.

Sits above :mod:`levi.integrations.termux`'s :class:`TermuxBridge` and adds
the rest of the phone hardware surface: camera, microphone, sensors, wifi,
telephony info, contacts, call log, SMS, notifications. Still 100% stdlib.

Deny-closed capability model. Three capabilities, none granted by default:

- ``"sense"``    — read-only hardware state (sensors, location, wifi,
  device info, sms/call-log/contact reads). No data leaves the device.
- ``"actuate"``  — local device actions (notify, torch, TTS, camera photo,
  mic record, media play). Everything stays on the phone.
- ``"message"``  — off-device communication: SMS send, phone calls. The
  share sheet is user-mediated; sending SMS or placing a call additionally
  requires ``confirm=True`` on *every* call — a missing confirmation is
  refused, not defaulted.

Every call checks the binary exists first (:func:`shutil.which`), degrades
to an honest ``missing tool`` reading instead of raising, and carries a
timeout so a wedged device API can never block the daemon. Nothing here
assumes Termux exists: ``PhoneBridge.probe()`` tells the truth on any
machine. All calls are appended to ``bridge.audit`` for Sentinel to see.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

from levi.integrations.termux import DeviceReading, TermuxBridge

#: capabilities — deny-closed; grant() flips them on explicitly.
CAP_SENSE = "sense"
CAP_ACTUATE = "actuate"
CAP_MESSAGE = "message"
CAPABILITIES: tuple = (CAP_SENSE, CAP_ACTUATE, CAP_MESSAGE)

#: read-only hardware state; nothing leaves the device.
PHONE_SENSE_TOOLS: tuple = (
    "termux-sensor",
    "termux-wifi-scaninfo",
    "termux-wifi-connectioninfo",
    "termux-telephony-deviceinfo",
    "termux-telephony-cellinfo",
    "termux-camera-info",
    "termux-sms-list",
    "termux-call-log",
    "termux-contact-list",
    "termux-notification-list",
)

#: local device actions; everything stays on the phone.
PHONE_ACTUATE_TOOLS: tuple = (
    "termux-torch",
    "termux-camera-photo",
    "termux-microphone-record",
    "termux-notification-remove",
    "termux-media-player",
)

#: off-device communication — requires CAP_MESSAGE *and* explicit confirm.
PHONE_MESSAGE_TOOLS: tuple = (
    "termux-sms-send",
    "termux-telephony-call",
    "termux-share",
)

PHONE_TOOLS: tuple = PHONE_SENSE_TOOLS + PHONE_ACTUATE_TOOLS + PHONE_MESSAGE_TOOLS


def _capture_dir() -> str:
    base = os.environ.get("LEVI_HOME", os.path.join(os.path.expanduser("~"), ".levi"))
    return os.path.join(base, "phone", "captures")


class PhoneBridge(TermuxBridge):
    """Capability-gated bridge to the full Termux:API hardware surface.

    Construct with :meth:`probe` (never raw — probing is the point), then
    :meth:`grant` the capabilities the caller actually needs.
    """

    def __init__(self, tools: Dict[str, bool]):
        super().__init__(tools)
        self._caps: Dict[str, bool] = {cap: False for cap in CAPABILITIES}
        self.audit: List[Dict[str, Any]] = []

    # -- probing ---------------------------------------------------------

    @classmethod
    def probe(cls) -> "PhoneBridge":
        """Probe the base Termux surface plus every phone hardware tool."""
        tools = dict(TermuxBridge.probe().available)
        for tool in PHONE_TOOLS:
            tools[tool] = shutil.which(tool) is not None
        return cls(tools)

    # -- capabilities ----------------------------------------------------

    def grant(self, *caps: str) -> "PhoneBridge":
        """Grant one or more capabilities. Chainable."""
        for cap in caps:
            if cap not in self._caps:
                raise ValueError(f"unknown capability: {cap!r}")
            self._caps[cap] = True
        return self

    def revoke(self, *caps: str) -> "PhoneBridge":
        """Revoke one or more capabilities. Chainable."""
        for cap in caps:
            if cap not in self._caps:
                raise ValueError(f"unknown capability: {cap!r}")
            self._caps[cap] = False
        return self

    @property
    def granted(self) -> List[str]:
        return [c for c, on in self._caps.items() if on]

    def _gate(self, tool: str, cap: str) -> Optional[DeviceReading]:
        """Return a refusal reading when the capability is not granted."""
        if not self._caps.get(cap):
            reading = DeviceReading(
                ok=False,
                tool=tool,
                error=f"capability '{cap}' not granted — call grant('{cap}')",
            )
            self.audit.append({"tool": tool, "ok": False, "refused": True, "cap": cap})
            return reading
        return None

    def _refuse(self, tool: str, reason: str) -> DeviceReading:
        reading = DeviceReading(ok=False, tool=tool, error=reason)
        self.audit.append({"tool": tool, "ok": False, "refused": True})
        return reading

    def _run(
        self, tool: str, args: List[str], *, timeout: float = 10.0
    ) -> DeviceReading:
        reading = super()._run(tool, args, timeout=timeout)
        self.audit.append(
            {
                "tool": tool,
                "ok": reading.ok,
                "error": reading.error if not reading.ok else "",
            }
        )
        return reading

    # -- read-only sensing (CAP_SENSE) -----------------------------------

    def sensors(self) -> DeviceReading:
        """One-shot read of every device sensor (JSON)."""
        refused = self._gate("termux-sensor", CAP_SENSE)
        return refused or self._run("termux-sensor", ["-n", "1"], timeout=15.0)

    def wifi_scan(self) -> DeviceReading:
        """Scan nearby wifi access points (JSON)."""
        refused = self._gate("termux-wifi-scaninfo", CAP_SENSE)
        return refused or self._run("termux-wifi-scaninfo", [], timeout=20.0)

    def wifi_connection(self) -> DeviceReading:
        """Current wifi connection details (JSON)."""
        refused = self._gate("termux-wifi-connectioninfo", CAP_SENSE)
        return refused or self._run("termux-wifi-connectioninfo", [])

    def device_info(self) -> DeviceReading:
        """Telephony device info (JSON)."""
        refused = self._gate("termux-telephony-deviceinfo", CAP_SENSE)
        return refused or self._run("termux-telephony-deviceinfo", [])

    def cell_info(self) -> DeviceReading:
        """Cell tower info (JSON)."""
        refused = self._gate("termux-telephony-cellinfo", CAP_SENSE)
        return refused or self._run("termux-telephony-cellinfo", [])

    def camera_info(self) -> DeviceReading:
        """List device cameras (JSON)."""
        refused = self._gate("termux-camera-info", CAP_SENSE)
        return refused or self._run("termux-camera-info", [])

    def sms_list(self, limit: int = 20) -> DeviceReading:
        """List recent SMS messages (JSON). Read-only."""
        refused = self._gate("termux-sms-list", CAP_SENSE)
        if refused:
            return refused
        return self._run("termux-sms-list", ["-l", str(max(1, limit))])

    def call_log(self, limit: int = 20) -> DeviceReading:
        """List recent calls (JSON). Read-only."""
        refused = self._gate("termux-call-log", CAP_SENSE)
        if refused:
            return refused
        return self._run("termux-call-log", ["-l", str(max(1, limit))])

    def contact_list(self) -> DeviceReading:
        """List contacts (JSON). Read-only."""
        refused = self._gate("termux-contact-list", CAP_SENSE)
        return refused or self._run("termux-contact-list", [])

    def notification_list(self) -> DeviceReading:
        """List active LEVI notifications (JSON). Read-only."""
        refused = self._gate("termux-notification-list", CAP_SENSE)
        return refused or self._run("termux-notification-list", [])

    # -- local actuation (CAP_ACTUATE) -----------------------------------

    def torch(self, on: bool = True) -> DeviceReading:
        """Toggle the camera flashlight."""
        refused = self._gate("termux-torch", CAP_ACTUATE)
        return refused or self._run("termux-torch", ["on" if on else "off"])

    def camera_photo(
        self, path: Optional[str] = None, camera: int = 0
    ) -> DeviceReading:
        """Take a photo; stays on the device."""
        refused = self._gate("termux-camera-photo", CAP_ACTUATE)
        if refused:
            return refused
        if path is None:
            os.makedirs(_capture_dir(), exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(_capture_dir(), f"photo_{stamp}.jpg")
        return self._run("termux-camera-photo", ["-c", str(camera), path], timeout=30.0)

    def mic_record(
        self, path: Optional[str] = None, seconds: int = 10
    ) -> DeviceReading:
        """Record audio for ``seconds``; stays on the device."""
        refused = self._gate("termux-microphone-record", CAP_ACTUATE)
        if refused:
            return refused
        seconds = max(1, min(300, seconds))
        if path is None:
            os.makedirs(_capture_dir(), exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(_capture_dir(), f"rec_{stamp}.m4a")
        return self._run(
            "termux-microphone-record",
            ["-f", path, "-l", str(seconds)],
            timeout=float(seconds) + 20.0,
        )

    def notification_remove(self, nid: str) -> DeviceReading:
        """Dismiss a LEVI notification by id."""
        refused = self._gate("termux-notification-remove", CAP_ACTUATE)
        if refused:
            return refused
        if not nid:
            return self._refuse("termux-notification-remove", "id is required")
        return self._run("termux-notification-remove", [nid])

    def media_play(self, path: str) -> DeviceReading:
        """Play a local audio file via the device media player."""
        refused = self._gate("termux-media-player", CAP_ACTUATE)
        if refused:
            return refused
        if not path:
            return self._refuse("termux-media-player", "path is required")
        return self._run("termux-media-player", ["play", path])

    # -- off-device communication (CAP_MESSAGE + confirm) ----------------

    def sms_send(
        self, number: str, message: str, *, confirm: bool = False
    ) -> DeviceReading:
        """Send an SMS. Requires ``confirm=True`` on every call — no silent sends."""
        if not confirm:
            return self._refuse(
                "termux-sms-send",
                "confirmation required: pass confirm=True to send",
            )
        refused = self._gate("termux-sms-send", CAP_MESSAGE)
        if refused:
            return refused
        if not number or not message:
            return self._refuse("termux-sms-send", "number and message are required")
        return self._run("termux-sms-send", ["-n", number, message])

    def call(self, number: str, *, confirm: bool = False) -> DeviceReading:
        """Place a phone call. Requires ``confirm=True`` on every call."""
        if not confirm:
            return self._refuse(
                "termux-telephony-call",
                "confirmation required: pass confirm=True to call",
            )
        refused = self._gate("termux-telephony-call", CAP_MESSAGE)
        if refused:
            return refused
        if not number:
            return self._refuse("termux-telephony-call", "number is required")
        return self._run("termux-telephony-call", [number])

    def sense_card(self) -> Dict[str, Any]:
        """One honest snapshot: caps granted, tools reachable, battery."""
        return {
            "granted": self.granted,
            "on_termux": self.on_termux,
            "present": self.present,
            "missing": self.missing,
            "battery": self.battery().to_dict(),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {"tools": dict(self._tools), "granted": self.granted}


def _cli(argv: Optional[List[str]] = None) -> int:
    import argparse
    import json as _json

    ap = argparse.ArgumentParser(
        prog="levi.integrations.phone",
        description="Phone hardware bridge — probe the Termux:API surface.",
    )
    ap.add_argument(
        "action",
        nargs="?",
        default="probe",
        choices=["probe", "sensors", "photo", "torch"],
        help="action to run",
    )
    ap.add_argument("--caps", default="", help="comma-separated capabilities to grant")
    args = ap.parse_args(argv)

    bridge = PhoneBridge.probe()
    for cap in (c.strip() for c in args.caps.split(",") if c.strip()):
        bridge.grant(cap)

    if args.action == "probe":
        print(_json.dumps(bridge.sense_card(), indent=2, sort_keys=True))
    elif args.action == "sensors":
        print(_json.dumps(bridge.sensors().to_dict(), indent=2))
    elif args.action == "photo":
        print(_json.dumps(bridge.camera_photo().to_dict(), indent=2))
    elif args.action == "torch":
        print(_json.dumps(bridge.torch(True).to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
