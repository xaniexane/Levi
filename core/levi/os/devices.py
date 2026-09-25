"""Device awareness — enumerate paired/surfaced devices, route by capability.

LAW 5: steps route only to devices with declared capabilities. Every
device carries an honest ``status``: ``real`` (present and usable),
``stubbed`` (the surface exists in the repo but is not live here), or
``unpaired`` (known but not connected in this build). Nothing pretends.

v0.1 builtin surfaces:
- ``local`` — this machine. Real.
- ``termux`` — the Termux Android package (ships at
  ``~/workspace/your_files/levi-termux/``). Stubbed: the tarball exists,
  it is not installed in this build.
- ``android-app`` — the Android scaffolds (cybrus/creator/hicomb/quetta-pan
  under ``apps/``). Stubbed: scaffolds only, no device connected.

Callers may pass their own :class:`Device` entries (e.g. a live pairing
registry later); builtins are the fallback, clearly labeled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Optional

__all__ = [
    "Device",
    "builtin_devices",
    "enumerate_devices",
    "required_capabilities",
    "route_step",
]

#: Backend flag -> capability a step needs before it may run.
_BACKEND_CAPS: Dict[str, FrozenSet[str]] = {
    "platform-native": frozenset({"local-compute"}),
    "playbook-only": frozenset({"local-compute"}),
    # Honest: needs-wiring skills name real connectors/credentials/devices.
    # v0.1 has no network device, so these steps stay blocked, never faked.
    "needs-wiring": frozenset({"network"}),
}


@dataclass(frozen=True)
class Device:
    id: str
    name: str
    kind: str  # workstation | phone | ...
    capabilities: FrozenSet[str]
    status: str  # "real" | "stubbed" | "unpaired"
    notes: str


def builtin_devices() -> List[Device]:
    """The device surfaces this build knows about, honestly labeled."""
    return [
        Device(
            id="local",
            name="This machine",
            kind="workstation",
            capabilities=frozenset({"local-compute", "filesystem", "shell"}),
            status="real",
            notes="The machine LEVI OS is running on.",
        ),
        Device(
            id="termux",
            name="Termux on Android",
            kind="phone",
            capabilities=frozenset({"local-compute", "shell", "android"}),
            status="stubbed",
            notes=(
                "Package ships at ~/workspace/your_files/levi-termux/ "
                "(tarball + setup.sh, smoke-tested from clean HOME). "
                "Not installed in this build — no live Termux session."
            ),
        ),
        Device(
            id="android-app",
            name="Android app scaffolds",
            kind="phone",
            capabilities=frozenset({"android-ui"}),
            status="stubbed",
            notes=(
                "Scaffolds only (apps/cybrus-android, apps/creator-android, "
                "apps/hicomb-android, apps/quetta-pan-android). "
                "No device connected, nothing installed."
            ),
        ),
    ]


def enumerate_devices(
    extra: Optional[Iterable[Device]] = None,
) -> List[Device]:
    """All known devices: caller-supplied first, then builtins."""
    devices = list(extra) if extra else []
    seen = {d.id for d in devices}
    for d in builtin_devices():
        if d.id not in seen:
            devices.append(d)
    return devices


def required_capabilities(backend: str) -> FrozenSet[str]:
    """Capabilities a step needs, from its skill's backend flag."""
    try:
        return _BACKEND_CAPS[backend]
    except KeyError:
        raise ValueError(f"unknown backend flag {backend!r}") from None


def route_step(
    capabilities: Iterable[str],
    devices: Optional[List[Device]] = None,
) -> Optional[Device]:
    """First device covering every required capability.

    Real devices win; a stubbed covering device is returned as intent
    (the runner defers it honestly); None when nothing covers the caps.
    """
    need = set(capabilities)
    pool = devices if devices is not None else enumerate_devices()
    fallback: Optional[Device] = None
    for d in pool:
        if need <= set(d.capabilities):
            if d.status == "real":
                return d
            if fallback is None:
                fallback = d
    return fallback
