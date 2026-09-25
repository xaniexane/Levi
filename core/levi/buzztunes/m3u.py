"""M3U — the universal playlist bridge.

Buzz Tunes reads and writes M3U playlists (plain M3U + M3U8/Unicode) so
any queue or thread interoperates with every other player.

Honest parsing:
  * ``#EXTM3U`` header recognized (not required).
  * ``#EXTINF:<duration>,<artist> - <title>`` metadata preserved.
    Duration ``-1`` means unknown. A missing comma or non-numeric
    duration does not kill the parse — the line is skipped and logged.
  * Relative paths resolve against the playlist's directory (or a
    caller-supplied base); absolute paths and http(s) URLs pass through.
  * Anything unparseable — blank lines, stray comments, garbage — is
    skipped and recorded in ``skipped`` with a reason. The parse never
    raises on malformed input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .providers import Track


@dataclass
class ParsedPlaylist:
    tracks: List[Track]
    skipped: List[Dict] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.tracks)


def _split_artist_title(display: str) -> Tuple[str, str]:
    if " - " in display:
        artist, title = (p.strip() for p in display.split(" - ", 1))
        return artist or "unknown artist", title or display.strip()
    return "unknown artist", display.strip()


def parse_m3u(text: str, base_dir: Optional[str | Path] = None,
              source_name: str = "m3u") -> ParsedPlaylist:
    """Parse M3U/M3U8 text. Never raises on malformed lines."""
    tracks: List[Track] = []
    skipped: List[Dict] = []
    base = Path(base_dir) if base_dir else None

    pending_duration: Optional[float] = None
    pending_display: str = ""
    lineno = 0

    def _ref_for(entry: str) -> Tuple[str, str]:
        # returns (provider, ref)
        e = entry.strip()
        if e.lower().startswith(("http://", "https://")):
            return "url", e
        p = Path(e)
        if not p.is_absolute() and base is not None:
            p = base / p
        return "local", str(p)

    for raw in text.splitlines():
        lineno += 1
        line = raw.strip()
        if not line:
            continue
        if line.upper() == "#EXTM3U":
            continue
        if line.upper().startswith("#EXTINF:"):
            payload = line[len("#EXTINF:"):]
            if "," in payload:
                dur_s, display = payload.split(",", 1)
            else:
                skipped.append({"line": lineno, "text": raw,
                                "reason": "EXTINF missing comma"})
                pending_duration, pending_display = None, ""
                continue
            try:
                dur = float(dur_s.strip())
                pending_duration = None if dur < 0 else dur
            except ValueError:
                skipped.append({"line": lineno, "text": raw,
                                "reason": "EXTINF bad duration"})
                pending_duration, pending_display = None, ""
                continue
            pending_display = display.strip()
            continue
        if line.startswith("#"):
            # Other comments/directives: not playable, not an error.
            skipped.append({"line": lineno, "text": raw,
                            "reason": "non-EXTINF directive"})
            pending_duration, pending_display = None, ""
            continue

        # Media entry.
        provider, ref = _ref_for(line)
        if provider == "local":
            artist, title = _split_artist_title(
                pending_display or Path(ref).stem.replace("_", " "))
            track_id = f"m3u:{ref}"
        else:
            artist, title = _split_artist_title(pending_display or ref)
            track_id = f"m3u:{ref}"
        tracks.append(Track(
            id=track_id,
            title=title,
            artist=artist,
            duration=pending_duration,
            provider=source_name if provider == "local" else "url",
            ref=ref,
            meta={"m3u_line": lineno,
                  "m3u_display": pending_display},
        ))
        pending_duration, pending_display = None, ""

    return ParsedPlaylist(tracks=tracks, skipped=skipped)


def write_m3u(tracks: List[Track]) -> str:
    """Serialize tracks to M3U text. Round-trips through parse_m3u."""
    lines = ["#EXTM3U"]
    for t in tracks:
        dur = "-1" if t.duration is None else str(int(t.duration))
        display = f"{t.artist} - {t.title}" if t.artist else t.title
        lines.append(f"#EXTINF:{dur},{display}")
        lines.append(t.ref)
    return "\n".join(lines) + "\n"


def read_playlist(path: str | Path) -> ParsedPlaylist:
    """Read a .m3u or .m3u8 file (BOM-tolerant)."""
    p = Path(path)
    text = p.read_bytes().decode("utf-8-sig")
    return parse_m3u(text, base_dir=p.parent, source_name="m3u")


def write_playlist(path: str | Path, tracks: List[Track]) -> int:
    """Write tracks to a .m3u file. Returns track count."""
    p = Path(path)
    p.write_text(write_m3u(tracks), encoding="utf-8")
    return len(tracks)
