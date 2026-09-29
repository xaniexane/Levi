"""LEVI bot standup — the morning card, composed not typed.

``compose_standup`` takes named zero-argument *providers* — each returns
a list of plain-text lines for one section — and renders the card through
``levi.bot.brief.render_brief`` so the card never exceeds its line budget.
A provider that raises is reported as SILENT (name + error class, never a
traceback); a malformed provider table is refused with a named error,
never coerced.

Same providers, same answers → same card, every time.

Default providers (local-only, stdlib, never network):

- ``crashes`` — the coroner digest of perpetual-supervisor crashes
- ``disk`` — one band line for home-directory disk usage

Run it: ``python3 -m levi.bot.standup``
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence

from levi.bot.brief import BriefResult, render_brief


class StandupError(ValueError):
    """Raised when the standup request itself is malformed."""


Provider = Callable[[], Sequence[str]]


def _validate_providers(providers: Mapping[str, Provider]) -> Dict[str, Provider]:
    if not isinstance(providers, Mapping):
        raise StandupError("standup: providers must be a mapping of name -> callable")
    if not providers:
        raise StandupError("standup: at least one provider is required")
    clean: Dict[str, Provider] = {}
    for name, fn in providers.items():
        if not isinstance(name, str) or not name.strip():
            raise StandupError("standup: provider names must be non-empty strings")
        if not callable(fn):
            raise StandupError(f"standup: provider '{name}' is not callable")
        if name in clean:
            raise StandupError(f"standup: duplicate provider '{name}'")
        clean[name] = fn
    return clean


def _validate_title(title: object) -> str:
    if not isinstance(title, str) or not title.strip():
        raise StandupError("standup: title must be a non-empty string")
    return title.strip()


def compose_standup(
    title: str,
    providers: Mapping[str, Provider],
    max_lines: int = 24,
) -> BriefResult:
    """Compose the standup card from provider sections.

    Each provider is pinged in mapping order; exceptions become a single
    ``SILENT`` line naming the provider and the error class. Returns the
    :class:`BriefResult` from ``render_brief`` (``.text`` is the card,
    ``.dropped`` counts held-back lines).
    """
    clean_title = _validate_title(title)
    clean_providers = _validate_providers(providers)
    sections: List[tuple] = []
    for name, fn in clean_providers.items():
        try:
            raw = fn()
        except Exception as exc:  # noqa: BLE001 — a provider must not kill the card
            sections.append((name, [f"SILENT ({type(exc).__name__})"]))
            continue
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            sections.append((name, ["SILENT (bad provider shape)"]))
            continue
        lines = [str(line) for line in raw if str(line).strip()]
        sections.append((name, lines or ["(nothing to report)"]))
    return render_brief(clean_title, sections, max_lines=max_lines)


# ---------------------------------------------------------------------------
# Default providers — local-only, stdlib, never network
# ---------------------------------------------------------------------------


def crash_provider() -> List[str]:
    """Coroner digest lines for the standup card."""
    from levi.daemon.coroner import DEFAULT_CRASH_DIR, digest_reports, load_reports

    try:
        reports, skipped = load_reports(DEFAULT_CRASH_DIR)
    except Exception:  # noqa: BLE001 — no crash dir yet is not a crash
        return ["no crash directory yet"]
    digest = digest_reports(reports, skipped)
    lines = [
        f"{digest.total_reports} report(s), {digest.skipped_files} skipped file(s)"
    ]
    for name in sorted(digest.services):
        svc = digest.services[name]
        lines.append(f"- {name}: {svc.crashes} crash(es), last {svc.last_exc}")
    if digest.repeat_offenders:
        lines.append("repeat offenders: " + ", ".join(digest.repeat_offenders))
    return lines


def disk_provider(root: Optional[str] = None) -> List[str]:
    """One band line for disk usage under the given root (default: home)."""

    def _probe() -> List[str]:
        target = Path(root).expanduser() if root else Path.home()
        usage = shutil.disk_usage(target)
        pct = usage.used / usage.total * 100 if usage.total else 0.0
        band = "ok" if pct < 80 else "warn" if pct < 90 else "crit"
        return [f"disk {band}: {pct:.0f}% used on {target}"]

    return _probe()


def default_providers() -> Dict[str, Provider]:
    """The standard local-only standup provider table."""
    return {
        "crashes": crash_provider,
        "disk": lambda: disk_provider(),
    }


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point: ``python -m levi.bot.standup [--max-lines N]``."""
    parser = argparse.ArgumentParser(description="Compose the morning standup card.")
    parser.add_argument("--max-lines", type=int, default=24)
    args = parser.parse_args(argv)
    card = compose_standup(
        "Morning standup", default_providers(), max_lines=args.max_lines
    )
    print(card.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
