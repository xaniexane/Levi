"""Terminal UX effects for LEVI: color, banners, spinners, progress bars,
tables, typing effects, status lines, sparklines, meters, menus, prompts.

**Pipe-safety (structural).** Every function consults :func:`effects_enabled`
before emitting anything: when stdout is not a TTY or the ``NO_COLOR``
environment variable is set, there are no ANSI escape codes, no cursor
movement and no animation — only plain readable text.  Terminal width is
read via :func:`shutil.get_terminal_size` with an 80-column fallback, and
glyph selection probes ``sys.stdout.encoding`` so a ``UnicodeEncodeError``
can never crash output: glyphs that cannot be represented degrade to
ASCII-safe alternatives.

Only the standard library is used.  No ``curses``, no third-party deps.
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
import time

__all__ = [
    "ProgressBar",
    "Spinner",
    "Table",
    "banner",
    "color",
    "confirm",
    "effects_enabled",
    "menu",
    "meter",
    "pause_for_key",
    "rule",
    "sparkline",
    "status_line",
    "typing_print",
]

# ---------------------------------------------------------------------------
# Structural gates
# ---------------------------------------------------------------------------


def effects_enabled() -> bool:
    """Return True only when rich terminal effects are safe to emit.

    Effects are enabled when stdout is a real TTY **and** the ``NO_COLOR``
    environment variable is unset (a non-empty value disables effects, per
    the NO_COLOR convention).  Every effect in this module consults this
    gate, so pipe-safe degradation is structural, not per-callsite luck.
    """
    try:
        if os.environ.get("NO_COLOR"):
            return False
        return bool(sys.stdout.isatty())
    except Exception:
        # A broken stdout (closed, exotic) must never crash the caller.
        return False


def _terminal_width() -> int:
    """Best-effort terminal width; never raises, falls back to 80."""
    try:
        width = shutil.get_terminal_size(fallback=(80, 24)).columns
        return width if width and width > 0 else 80
    except Exception:
        return 80


def _unicode_ok() -> bool:
    """True when stdout's encoding can render this module's Unicode glyphs."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        "⠋─┌█…▁".encode(encoding)
        return True
    except Exception:
        return False


def _rich() -> bool:
    """True when BOTH effects are enabled AND Unicode glyphs are encodable.

    Static glyphs (rules, banners, tables, sparklines, meters) follow this:
    degraded output is fully ASCII.  Animation itself only needs
    :func:`effects_enabled` (a latin-1 TTY still animates, with ASCII
    spinner glyphs).
    """
    return effects_enabled() and _unicode_ok()


def _safe_write(text: str) -> None:
    """Write to stdout, degrading glyphs on UnicodeEncodeError; never raises."""
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except UnicodeEncodeError:
        # Degrade the *content*, not the call: strip to ASCII approximations.
        degraded = (
            text.replace("…", "...")
            .replace("─", "-")
            .replace("│", "|")
            .replace("┌", "+")
            .replace("┐", "+")
            .replace("└", "+")
            .replace("┘", "+")
            .replace("█", "#")
            .replace("░", "-")
        )
        try:
            sys.stdout.write(degraded.encode("ascii", "replace").decode("ascii"))
            sys.stdout.flush()
        except Exception:
            pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Color / rules / banners
# ---------------------------------------------------------------------------

_FG_CODES = {
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "white": 37,
    "gray": 90,
}


def color(
    text: str, fg: str | None = None, bold: bool = False, dim: bool = False
) -> str:
    """Wrap *text* in ANSI SGR codes, or return it unchanged when degraded.

    ``fg`` is one of red/green/yellow/blue/magenta/cyan/white/gray (unknown
    names are ignored, not errors).  When :func:`effects_enabled` is False
    the input is returned verbatim — callers never need their own branch.
    """
    if not effects_enabled():
        return text
    codes: list[str] = []
    if bold:
        codes.append("1")
    if dim:
        codes.append("2")
    if fg is not None and fg in _FG_CODES:
        codes.append(str(_FG_CODES[fg]))
    if not codes:
        return text
    return f"\x1b[{';'.join(codes)}m{text}\x1b[0m"


def rule(char: str | None = None) -> str:
    """A full-width horizontal rule line, returned as a string.

    The rule is drawn with ``─`` when rich, ``-`` when degraded.  It is
    returned (not printed) so tests and non-stdout writers can reuse it;
    callers typically do ``print(rule())``.
    """
    glyph = char if char else ("─" if _rich() else "-")
    return glyph * _terminal_width()


def banner(title: str, subtitle: str = "") -> str:
    """Render a panel box around *title* (and optional *subtitle*).

    Rich mode uses box-drawing characters; degraded mode uses a plain ASCII
    ``+---+``/``|`` panel.  Returns the rendered string — callers print it.
    Never emits ANSI codes.
    """
    lines = [title]
    if subtitle:
        lines.append(subtitle)
    inner = max((len(line) for line in lines), default=0)
    pad = 2  # spaces each side
    if _rich():
        top = "┌" + "─" * (inner + pad * 2) + "┐"
        bottom = "└" + "─" * (inner + pad * 2) + "┘"
        body = [f"│{' ' * pad}{line.ljust(inner)}{' ' * pad}│" for line in lines]
        return "\n".join([top, *body, bottom])
    top = "+" + "-" * (inner + pad * 2) + "+"
    bottom = top
    body = [f"|{' ' * pad}{line.ljust(inner)}{' ' * pad}|" for line in lines]
    return "\n".join([top, *body, bottom])


# ---------------------------------------------------------------------------
# Spinner
# ---------------------------------------------------------------------------

_BRAILLE = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_ASCII_SPIN = ["-", "\\", "|", "/"]


class Spinner:
    """Context-managed animated spinner for a long-running step.

    TTY: animates braille dots (ASCII ``-\\|/`` when the encoding cannot do
    braille) on one rewritten line.  Degraded: prints a single static
    ``... label`` line on entry.  On exit the line is always restored
    cleanly (rewritten line cleared in TTY mode; nothing dangling in pipe
    mode).  Example::

        with Spinner("Training brain"):
            train()
    """

    def __init__(self, label: str, interval: float = 0.08) -> None:
        self.label = label
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._rich = False

    def __enter__(self) -> "Spinner":
        self._rich = _rich()
        if not self._rich:
            # Degraded: one static line, no animation, no cursor tricks.
            print(f"... {self.label}")
            return self
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._spin, name="levi-ux-spinner", daemon=True
        )
        self._thread.start()
        return self

    def _spin(self) -> None:
        glyphs = _BRAILLE if _unicode_ok() else _ASCII_SPIN
        i = 0
        while not self._stop.wait(self.interval):
            _safe_write(f"\r{glyphs[i % len(glyphs)]} {self.label}")
            i += 1

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        if self._thread is not None:
            self._stop.set()
            self._thread.join(timeout=2.0)
            self._thread = None
            # Restore the line cleanly: clear the spinner row.
            try:
                _safe_write("\r" + " " * _terminal_width() + "\r")
            except Exception:
                pass
        return False


# ---------------------------------------------------------------------------
# Progress bar
# ---------------------------------------------------------------------------


def _fmt_duration(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m{secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


class ProgressBar:
    """A progress bar with %, rate and ETA.

    TTY: single rewritten line, e.g. ``label [██████░░░░] 60% 3.2/s ETA 8s``.
    Degraded: prints one plain line each time a 25% boundary is crossed, so
    logs stay readable.  When *total* is unknown (``None`` or ``<= 0``) the
    TTY view becomes a counter with rate; degraded mode prints just the
    final count on :meth:`finish`.

    ``update(n=1)`` advances the count by *n*; ``set(n)`` jumps to *n*.
    """

    def __init__(self, total: int | None, label: str = "", width: int = 30) -> None:
        self.total = total if total and total > 0 else None
        self.label = label
        self.width = width
        self.current = 0
        self._start = time.monotonic()
        self._last_reported_quarter = -1
        self._finished = False

    # -- state ------------------------------------------------------------
    def update(self, n: int = 1) -> None:
        """Advance the counter by *n* (negative values are allowed)."""
        self.current = max(0, self.current + n)
        self._render()

    def set(self, n: int) -> None:
        """Jump the counter to *n*."""
        self.current = max(0, n)
        self._render()

    def finish(self) -> None:
        """Mark complete: final render, then release the line."""
        if self._finished:
            return
        self._finished = True
        if self.total is not None:
            self.current = max(self.current, self.total)
        self._render(final=True)
        if _rich():
            sys.stdout.write("\n")
            sys.stdout.flush()
        elif not effects_enabled():
            # Degraded: one summary line so the outcome is in the log.
            if self.total is not None:
                if self._last_reported_quarter < 4:
                    print(f"{self._label_prefix()}done ({self.current}/{self.total})")
            else:
                print(f"{self._label_prefix()}done ({self.current} items)")

    # -- rendering ---------------------------------------------------------
    def _label_prefix(self) -> str:
        return f"{self.label}: " if self.label else ""

    def _rate_eta(self) -> str:
        elapsed = max(time.monotonic() - self._start, 1e-9)
        rate = self.current / elapsed
        parts = [f"{rate:.1f}/s"]
        if self.total is not None and rate > 0:
            remaining = max(self.total - self.current, 0)
            parts.append(f"ETA {_fmt_duration(remaining / rate)}")
        return " ".join(parts)

    def _render(self, final: bool = False) -> None:
        if _rich():
            self._render_tty()
        elif not effects_enabled():
            self._render_degraded()

    def _render_tty(self) -> None:
        if self.total is not None:
            frac = min(self.current / self.total, 1.0)
            fill = "█" if _rich() else "#"
            empty = "░" if _rich() else "-"
            filled = int(frac * self.width)
            bar = fill * filled + empty * (self.width - filled)
            line = (
                f"\r{self._label_prefix()}[{bar}] {frac * 100:5.1f}% {self._rate_eta()}"
            )
        else:
            line = f"\r{self._label_prefix()}{self.current} items {self._rate_eta()}"
        _safe_write(line[: _terminal_width()])

    def _render_degraded(self) -> None:
        if self.total is None:
            return  # pipe mode with unknown total: just counts at finish()
        frac = min(self.current / self.total, 1.0)
        quarter = int(frac * 4)
        if quarter > self._last_reported_quarter:
            self._last_reported_quarter = quarter
            print(
                f"{self._label_prefix()}{quarter * 25}% ({self.current}/{self.total})"
            )


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


class Table:
    """Aligned-column table renderer.

    Columns are sized to their content, capped by the terminal width, and
    long cells are truncated with an ellipsis (``…`` rich, ``~`` degraded).
    Degraded output is plain aligned text — no ANSI, no box art.  Example::

        print(Table(["name", "score"], [["levi", 98], ["kai", 3]]).render())
    """

    def __init__(
        self,
        headers: list[str],
        rows: list[list[object]],
        max_width: int | None = None,
    ) -> None:
        self.headers = [str(h) for h in headers]
        self.rows = [[str(c) for c in row] for row in rows]
        self.max_width = max_width or _terminal_width()

    def _truncate(self, cell: str, width: int) -> str:
        if len(cell) <= width:
            return cell
        if width <= 1:
            return cell[:width]
        ellipsis = "…" if _rich() else "~"
        return cell[: width - 1] + ellipsis

    def render(self) -> str:
        """Return the rendered table as a string (no trailing newline)."""
        cols = len(self.headers)
        widths = [len(h) for h in self.headers]
        for row in self.rows:
            for i in range(cols):
                cell = row[i] if i < len(row) else ""
                widths[i] = max(widths[i], len(cell))

        # Shrink columns proportionally to fit max_width (2-space gutters).
        total = sum(widths) + 2 * (cols - 1)
        min_col = 4
        while total > self.max_width and any(w > min_col for w in widths):
            i = max(range(cols), key=lambda j: widths[j])
            if widths[i] <= min_col:
                break
            widths[i] -= 1
            total = sum(widths) + 2 * (cols - 1)

        def fmt(cells: list[str]) -> str:
            return "  ".join(
                self._truncate(cells[i] if i < len(cells) else "", widths[i]).ljust(
                    widths[i]
                )
                for i in range(cols)
            )

        lines = [fmt(self.headers), fmt(["-" * w for w in widths])]
        lines.extend(fmt(row) for row in self.rows)
        return "\n".join(lines)

    def print(self) -> None:
        """Print the rendered table."""
        print(self.render())


# ---------------------------------------------------------------------------
# Typing effect / status line
# ---------------------------------------------------------------------------


def typing_print(text: str, delay: float = 0.02) -> None:
    """Print *text* one character at a time in TTY mode; instantly otherwise.

    Degraded mode prints the whole string at once.  A terminal that cannot
    encode a character falls back to plain ``print`` rather than crashing.
    """
    if not effects_enabled():
        print(text)
        return
    try:
        for ch in text:
            _safe_write(ch)
            time.sleep(max(delay, 0.0))
        _safe_write("\n")
    except Exception:
        print(text)


_status_last: str = ""
_status_last_len: int = 0


def status_line(text: str) -> None:
    """Show a live single-line status.

    TTY: rewrites the current line via carriage return (padded to erase
    leftovers from longer previous text).  Degraded: prints only when
    *text* changes, so logs are not spammed with repeats.
    """
    global _status_last, _status_last_len
    if _rich():
        width = _terminal_width()
        shown = text[:width].ljust(max(_status_last_len, len(text[:width])))
        _status_last_len = len(text[:width])
        _safe_write("\r" + shown)
        _status_last = text
    elif not effects_enabled():
        if text != _status_last:
            print(text)
            _status_last = text


def clear_status_line() -> None:
    """Erase the current TTY status line; a no-op when degraded."""
    global _status_last, _status_last_len
    if _rich():
        _safe_write("\r" + " " * _status_last_len + "\r")
    _status_last = ""
    _status_last_len = 0


# ---------------------------------------------------------------------------
# Sparklines / meters
# ---------------------------------------------------------------------------

_BLOCKS = "▁▂▃▄▅▆▇█"
_ASCII_LEVELS = " .:-=+*#"


def sparkline(values: list[float]) -> str:
    """Render *values* as a compact sparkline string.

    Uses block characters (``▁``–``█``) when encodable, ASCII levels
    (`` .:-=+*#``) otherwise.  Empty input returns ``""``; a constant
    series renders as the middle block for every value; a single value
    renders one character.
    """
    if not values:
        return ""
    chars = _BLOCKS if _rich() else _ASCII_LEVELS
    lo, hi = min(values), max(values)
    if hi == lo:
        mid = chars[len(chars) // 2]
        return mid * len(values)
    span = hi - lo
    out = []
    for v in values:
        idx = int(round((v - lo) / span * (len(chars) - 1)))
        out.append(chars[max(0, min(idx, len(chars) - 1))])
    return "".join(out)


def meter(value: float, max_value: float, width: int = 20) -> str:
    """Render a horizontal meter: ``[██████░░░░░░] 60%``.

    *value* is clamped to ``[0, max_value]``; a non-positive *max_value*
    yields an empty bar.  Rich mode uses ``█``/``░`` (or ``#``/``-`` when
    the encoding cannot do blocks); degraded mode always uses ``#``/``-``
    with no ANSI.
    """
    width = max(width, 1)
    if max_value <= 0:
        frac = 0.0
    else:
        frac = min(max(value, 0.0) / max_value, 1.0)
    if _rich():
        fill, empty = "█", "░"
    else:
        fill, empty = "#", "-"
    filled = int(round(frac * width))
    bar = fill * filled + empty * (width - filled)
    return f"[{bar}] {frac * 100:3.0f}%"


# ---------------------------------------------------------------------------
# Interactive prompts (no curses)
# ---------------------------------------------------------------------------


def menu(
    options: list[str], prompt: str = "Choose", allow_quit: bool = True
) -> int | None:
    """Show a numbered interactive menu; return the chosen index or None.

    Reads one line at a time via :func:`input` (no curses), so it works
    even when stdin is not a TTY.  Accepts the option number (``1``-based)
    or its letter (``a``, ``b``, …); ``q``/``quit``, EOF or Ctrl-C returns
    ``None``.  Empty *options* returns ``None`` immediately.
    """
    if not options:
        return None
    letters = "abcdefghijklmnopqrstuvwxyz"
    for i, option in enumerate(options):
        tag = letters[i] if i < len(letters) else "?"
        print(f"  {i + 1}) {option}  [{tag}]")
    suffix = ", q=quit" if allow_quit else ""
    while True:
        try:
            raw = input(f"{prompt} [1-{len(options)}{suffix}]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        if allow_quit and raw in {"q", "quit", "exit"}:
            return None
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return idx
        elif len(raw) == 1 and raw in letters[: len(options)]:
            return letters.index(raw)
        print(f"Please enter 1-{len(options)}" + (" or q" if allow_quit else "") + ".")


def confirm(prompt: str, default: bool = False) -> bool:
    """Ask a yes/no question; return True for an affirmative answer.

    EOF or Ctrl-C counts as the default (normally ``False``).  The prompt
    suffix shows the default: ``[y/N]`` or ``[Y/n]``.
    """
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        raw = input(f"{prompt} {suffix} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return default
    if not raw:
        return default
    return raw in {"y", "yes"}


def pause_for_key(message: str = "Press Enter to continue") -> None:
    """Print *message* and wait for Enter.  A no-op on EOF/Ctrl-C."""
    try:
        input(f"{message} ")
    except (EOFError, KeyboardInterrupt):
        pass
