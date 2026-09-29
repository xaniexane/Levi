"""LEVI bot sundown — the evening card, composed not typed.

``compose_sundown`` takes named zero-argument *providers* — each returns
a list of plain-text lines for one section — and renders the card through
``levi.bot.brief.render_brief`` so the card never exceeds its line budget.
A provider that raises is reported as SILENT (name + error class, never a
traceback); a malformed provider table is refused with a named error,
never coerced.

Same providers, same answers → same card, every time.

Default providers (local-only, stdlib, never network):

- ``shipped`` — commits landed today in the LEVI repo checkout
- ``handoffs`` — handoff packets written today under ~/.levi/bot/handoffs
- ``ledger`` — daemon-ledger samples recorded today

Run it: ``python3 -m levi.bot.sundown``
"""

from __future__ import annotations

import argparse
import datetime
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from levi.bot.brief import BriefResult, render_brief


class SundownError(ValueError):
    """Raised when the sundown request itself is malformed."""


Provider = Callable[[], Sequence[str]]


def _validate_providers(providers: Mapping[str, Provider]) -> Dict[str, Provider]:
    if not isinstance(providers, Mapping):
        raise SundownError("sundown: providers must be a mapping of name -> callable")
    if not providers:
        raise SundownError("sundown: at least one provider is required")
    clean: Dict[str, Provider] = {}
    for name, fn in providers.items():
        if not isinstance(name, str) or not name.strip():
            raise SundownError("sundown: provider names must be non-empty strings")
        if not callable(fn):
            raise SundownError(f"sundown: provider '{name}' is not callable")
        if name in clean:
            raise SundownError(f"sundown: duplicate provider '{name}'")
        clean[name] = fn
    return clean


def _validate_title(title: object) -> str:
    if not isinstance(title, str) or not title.strip():
        raise SundownError("sundown: title must be a non-empty string")
    return title.strip()


def compose_sundown(
    title: str,
    providers: Mapping[str, Provider],
    max_lines: int = 24,
) -> BriefResult:
    """Compose the sundown card from provider sections.

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
        lines = [str(line) for line in raw] if raw else ["(quiet)"]
        sections.append((name, lines))
    return render_brief(clean_title, sections, max_lines=max_lines)


# ---------------------------------------------------------------------------
# Default providers — local-only, stdlib, never network
# ---------------------------------------------------------------------------

_MAX_SECTION_LINES = 10


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def shipped_provider() -> List[str]:
    """Commits landed today in this LEVI checkout."""
    root = _repo_root()
    today = datetime.date.today().isoformat()
    proc = subprocess.run(
        ["git", "log", "--since", f"{today} 00:00", "--format=%h %s"],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise SundownError(f"git log failed: {proc.stderr.strip()[:80]}")
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    shown = lines[:_MAX_SECTION_LINES]
    extra = len(lines) - len(shown)
    if extra > 0:
        shown.append(f"+{extra} more commit(s)")
    return shown or ["no commits today"]


def _files_written_today(directory: Path, limit: int) -> Tuple[List[str], int]:
    today = datetime.date.today()
    names: List[str] = []
    total = 0
    if not directory.is_dir():
        return names, 0
    for child in sorted(directory.iterdir(), key=lambda p: p.name):
        if not child.is_file():
            continue
        try:
            mtime = datetime.date.fromtimestamp(child.stat().st_mtime)
        except OSError:
            continue
        if mtime == today:
            total += 1
            if len(names) < limit:
                names.append(child.name)
    return names, total


def handoffs_provider() -> List[str]:
    """Handoff packets written today."""
    names, total = _files_written_today(
        Path.home() / ".levi" / "bot" / "handoffs", _MAX_SECTION_LINES
    )
    if total == 0:
        return ["no handoffs written today"]
    lines = [f"- {name}" for name in names]
    if total > len(names):
        lines.append(f"+{total - len(names)} more packet(s)")
    return lines


def ledger_provider() -> List[str]:
    """Daemon-ledger samples recorded today."""
    # ledger lives as ledger.jsonl inside the daemon dir; count its
    # today's entries by prefix match on the ISO date, bounded tail read.
    ledger = Path.home() / ".levi" / "daemon" / "ledger.jsonl"
    if not ledger.is_file():
        return ["no ledger file yet"]
    today = datetime.date.today().isoformat()
    count = 0
    try:
        with ledger.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 256 * 1024))
            tail = fh.read().decode("utf-8", errors="replace")
        for line in tail.splitlines():
            if line.startswith(today):
                count += 1
    except OSError:
        return ["ledger unreadable"]
    return [f"{count} ledger sample(s) today"]


def default_providers() -> Dict[str, Provider]:
    """The standard local-only sundown provider table."""
    return {
        "shipped": shipped_provider,
        "handoffs": handoffs_provider,
        "ledger": ledger_provider,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point: ``python -m levi.bot.sundown [--max-lines N]``."""
    parser = argparse.ArgumentParser(description="Compose the evening sundown card.")
    parser.add_argument("--max-lines", type=int, default=24)
    args = parser.parse_args(argv)
    card = compose_sundown(
        "Evening sundown", default_providers(), max_lines=args.max_lines
    )
    print(card.text)
    return 0


def _declare_to_interop() -> None:
    try:
        from levi.interop.registry import register
    except Exception:  # pragma: no cover - registry substrate mid-edit
        return
    try:
        register(
            "bot-sundown",
            provides=("bot.sundown.compose", "bot.sundown.cli"),
            requires=("bot-brief",),
        )
    except Exception:  # deny-closed: duplicate / malformed never half-runs
        pass


_declare_to_interop()


if __name__ == "__main__":
    raise SystemExit(main())
