"""privacy_defaults — privacy-by-default where the settings describe reality.

Studied from: giant-patterns-hunt-20260916-0016/report.md [S2].

Load-bearing idea: a privacy setting is only honest if it describes what the
software actually does. Defaults are the most private option, and every
setting carries a truth probe — a callable that reports the real behavior —
so ``verify()`` can catch any setting whose description has drifted from
reality.

LEVI's take: ``PrivacyManifest`` holds ``Setting`` records. Each setting has
a private default, a plain-language description, a ``leaves_device`` flag, and
a probe returning the true value. Every data access is appended to an audit
log. ``describe()`` renders the whole manifest for a human; ``verify()``
reports mismatches between claims and probes.

Honest limits: probes are supplied by the integrator and only as good as the
code they wrap; this module cannot observe behavior it is not told about.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

ORIGIN = "levi-revival/privacy-defaults"


@dataclass
class Setting:
    """One privacy setting. The default is always the most private option."""

    name: str
    description: str
    default: Any
    value: Any
    leaves_device: bool
    probe: Optional[Callable[[], Any]] = field(default=None, repr=False)

    def claim(self) -> Dict[str, Any]:
        """What the settings screen tells the user."""
        return {
            "name": self.name,
            "description": self.description,
            "value": self.value,
            "leaves_device": self.leaves_device,
        }


@dataclass
class AccessRecord:
    """One entry in the data-access audit log."""

    when: str
    accessor: str
    data_kind: str
    destination: str


class PrivacyManifest:
    """A privacy manifest whose settings describe reality, verified by probes."""

    def __init__(self) -> None:
        self._settings: Dict[str, Setting] = {}
        self._audit: List[AccessRecord] = []

    def declare(
        self,
        name: str,
        description: str,
        default: Any,
        leaves_device: bool,
        probe: Optional[Callable[[], Any]] = None,
    ) -> Setting:
        """Declare a setting, initialized to its private default."""
        if name in self._settings:
            raise KeyError(f"setting already declared: {name!r}")
        setting = Setting(
            name=name,
            description=description,
            default=default,
            value=default,
            leaves_device=leaves_device,
            probe=probe,
        )
        self._settings[name] = setting
        return setting

    def set(self, name: str, value: Any) -> None:
        """Change a setting. The change itself is audited."""
        setting = self._settings[name]
        setting.value = value
        self.record_access("user", name, "settings store (local)")

    def get(self, name: str) -> Any:
        """Read the current value of a setting."""
        return self._settings[name].value

    def record_access(self, accessor: str, data_kind: str, destination: str) -> None:
        """Log one data access. Callers are expected to log honestly."""
        self._audit.append(
            AccessRecord(
                when=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                accessor=accessor,
                data_kind=data_kind,
                destination=destination,
            )
        )

    def audit_log(self) -> List[Dict[str, str]]:
        """Every recorded data access, oldest first."""
        return [
            {
                "when": r.when,
                "accessor": r.accessor,
                "data_kind": r.data_kind,
                "destination": r.destination,
            }
            for r in self._audit
        ]

    def never_leaves_device(self) -> bool:
        """True when no setting currently permits data to leave the device."""
        return not any(s.value for s in self._settings.values() if s.leaves_device)

    def verify(self) -> List[Dict[str, Any]]:
        """Check each probed setting: does the claim match the probe's reality?

        Returns one dict per mismatch. An empty list means every probed
        setting describes reality.
        """
        mismatches = []
        for setting in self._settings.values():
            if setting.probe is None:
                continue
            reality = setting.probe()
            if reality != setting.value:
                mismatches.append(
                    {
                        "name": setting.name,
                        "claimed": setting.value,
                        "actual": reality,
                        "description": setting.description,
                    }
                )
        return mismatches

    def describe(self) -> str:
        """A human-readable summary of the whole manifest."""
        lines = ["Privacy manifest (defaults are the most private option):"]
        for setting in self._settings.values():
            scope = "leaves device" if setting.leaves_device else "stays on device"
            lines.append(
                f"  - {setting.name}: {setting.value!r} "
                f"(default {setting.default!r}) — {scope}. {setting.description}"
            )
        return "\n".join(lines)
