"""RT — Root Intelligence. Works while the machine sleeps.

A shutdown hook writes morning.md: what the day's classes observed, what
is queued for the offline morning. Honest scope: it is a script that runs
at shutdown (systemd unit / Termux boot-shutdown hook) and a reader at
boot. No dreaming, just bookkeeping — which is what you actually want.

Install hint: `rt_root.install_hint()` prints the hook setup.
"""

from __future__ import annotations

import time
from pathlib import Path


def write_morning_md(data_dir: str | Path, sections: dict[str, list[str]]) -> Path:
    """Compose morning.md from named sections. Called by the shutdown hook."""
    data_dir = Path(data_dir).expanduser()
    out_dir = data_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "morning.md"
    day = time.strftime("%Y-%m-%d")
    lines = [f"# Morning — {day}", ""]
    for title, items in sections.items():
        lines.append(f"## {title}")
        lines += [f"- {i}" for i in items] or ["- (nothing)"]
        lines.append("")
    path.write_text("\n".join(lines))
    return path


def install_hint() -> str:
    return """RT shutdown hook — pick your platform:

Linux (systemd):
  [Unit] Description=SOXI root nightly
  [Service] Type=oneshot
  ExecStart=/usr/bin/python3 -m levi.soxi.daemon --nightly
  [Install] WantedBy=shutdown.target
  → save as /etc/systemd/system/soxi-root.service, then
    systemctl enable soxi-root.service

Termux (Android):
  mkdir -p ~/.termux/boot
  # Termux:Boot runs scripts in ~/.termux/boot at boot; for shutdown,
  # schedule `python -m levi.soxi.daemon --nightly` via Termux:Tasker
  # or a cron-like job before your usual power-off.

The hook only writes local markdown. No network, no uploads."""


def collect_sections(data_dir: str | Path) -> dict[str, list[str]]:
    """Gather one line per class for the nightly write-up."""
    from .fr_friction import FrictionStore
    from .et_etch import EtchBoard
    from .sh_shadow import ShadowLog

    data_dir = Path(data_dir).expanduser()
    sections: dict[str, list[str]] = {}
    try:
        fr = FrictionStore(data_dir)
        sections["Friction"] = [f"{fr.count()} corrections on file"]
        fr.close()
    except Exception:
        pass
    try:
        et = EtchBoard(data_dir)
        sections["Etched laws"] = [r["text"] for r in et.laws()[-5:]]
    except Exception:
        pass
    try:
        sh = ShadowLog(data_dir)
        sections["Shadow"] = [f"{sh.count()} abandonments logged"]
        sh.close()
    except Exception:
        pass
    return sections
