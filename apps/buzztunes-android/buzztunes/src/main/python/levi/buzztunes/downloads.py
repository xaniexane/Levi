"""Download lane — offline-capable, honest.

What downloads actually are: direct HTTP(S) audio files fetched with
stdlib ``urllib`` (no new dependencies in the Chaquopy env) and saved
into ``<store>/downloads/``. A ``downloads.json`` manifest records
source URL, bytes, sha256, and timestamp per track. Downloads persist
on-device across launches.

What downloads are NOT:
  * YouTube rips. There is no linked YouTube access and no extraction
    tooling; a youtube.com / youtu.be URL is refused with a plain-speech
    explanation. The YouTube seam (youtube.py) stays honest.
  * Anything that isn't a direct audio file. URLs whose path doesn't end
    in a known audio suffix are refused — the lane never guesses at
    HTML pages or playlists.

Integrity: files stream to ``.part`` then atomically rename; sha256 is
recorded; manifest entries whose file went missing are reported with
``"missing": True`` — never pretended present.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .providers import AUDIO_SUFFIXES

CHUNK = 65536
_TIMEOUT = 60
_UA = {"User-Agent": "BuzzTunes/0.2.0 (offline-downloads; +local-first)"}

_FILENAME_BAD = re.compile(r"[^A-Za-z0-9._ -]+")


class DownloadError(RuntimeError):
    """A download was refused or failed. Message is plain speech."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sanitize_filename(name: str) -> str:
    name = _FILENAME_BAD.sub("_", name).strip(" .")
    return name or "download"


def _is_youtube_url(url: str) -> bool:
    host = urllib.request.urlparse(url).netloc.lower()
    return host in (
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
        "music.youtube.com",
    )


class DownloadStore:
    """On-device download lane backed by a JSON manifest."""

    def __init__(self, directory: str | Path) -> None:
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.dir / "downloads.json"
        self._manifest: Dict[str, Dict] = self._load()

    # -- manifest ------------------------------------------------------
    def _load(self) -> Dict[str, Dict]:
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save(self) -> None:
        tmp = self.manifest_path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(self._manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
        tmp.replace(self.manifest_path)

    # -- public --------------------------------------------------------
    def download(
        self,
        url: str,
        title: Optional[str] = None,
        artist: Optional[str] = None,
        timeout: int = _TIMEOUT,
    ) -> Dict:
        """Fetch a direct audio URL into the downloads dir.

        Raises DownloadError (plain speech) for anything that isn't a
        direct HTTP(S) audio file, and on network failure.
        """
        url = (url or "").strip()
        parsed = urllib.request.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise DownloadError(
                f"refusing {url!r}: downloads need a direct http(s) audio "
                "file URL (mp3/wav/ogg/flac/m4a/opus/aac)."
            )
        if _is_youtube_url(url):
            raise DownloadError(
                "refusing YouTube URL: there's no linked YouTube access and "
                "BuzzTunes doesn't rip YouTube. Paste a direct audio file "
                "URL instead — the YouTube seam stays honest."
            )
        suffix = Path(parsed.path).suffix.lower()
        if suffix not in AUDIO_SUFFIXES:
            raise DownloadError(
                f"refusing {url!r}: the URL doesn't point at a direct audio "
                f"file (need one of: {', '.join(AUDIO_SUFFIXES)})."
            )

        base = _sanitize_filename(Path(parsed.path).name) or "download"
        if not base.lower().endswith(suffix):
            base += suffix
        target = self.dir / base
        n = 1
        while target.exists():
            target = self.dir / f"{target.stem}-{n}{suffix}"
            n += 1

        req = urllib.request.Request(url, headers=_UA)
        part = target.with_suffix(target.suffix + ".part")
        digest = hashlib.sha256()
        total = 0
        try:
            with (
                urllib.request.urlopen(req, timeout=timeout) as resp,
                open(part, "wb") as fh,
            ):
                while True:
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    fh.write(chunk)
                    digest.update(chunk)
                    total += len(chunk)
        except Exception as exc:  # noqa: BLE001 - network truth, plain speech
            try:
                part.unlink()
            except OSError:
                pass
            raise DownloadError(
                f"download failed for {url!r}: {type(exc).__name__}: {exc}"
            ) from exc
        if total == 0:
            try:
                part.unlink()
            except OSError:
                pass
            raise DownloadError(f"download failed for {url!r}: empty body.")
        part.replace(target)

        stem_title = target.stem
        rec = {
            "id": f"downloads:{target.name}",
            "title": title or stem_title,
            "artist": artist or "unknown artist",
            "provider": "downloads",
            "ref": str(target),
            "url": url,
            "file": target.name,
            "bytes": total,
            "sha256": digest.hexdigest(),
            "downloaded_at": _utcnow(),
        }
        self._manifest[rec["id"]] = rec
        self._save()
        return dict(rec)

    def list(self) -> List[Dict]:
        """Manifest records; entries whose file is gone are marked missing."""
        out = []
        for rec in self._manifest.values():
            rec = dict(rec)
            rec["missing"] = not (self.dir / rec["file"]).is_file()
            out.append(rec)
        return sorted(out, key=lambda r: r.get("downloaded_at", ""))

    def get(self, track_id: str) -> Dict:
        try:
            rec = dict(self._manifest[track_id])
        except KeyError:
            raise KeyError(f"no download {track_id!r}") from None
        rec["missing"] = not (self.dir / rec["file"]).is_file()
        return rec

    def path_for(self, track_id: str) -> Path:
        """Local file path for a download. Raises KeyError if unknown,
        DownloadError if the file went missing."""
        rec = self.get(track_id)
        path = self.dir / rec["file"]
        if not path.is_file():
            raise DownloadError(
                f"downloaded file for {track_id!r} is missing from the "
                "device — re-download it while online."
            )
        return path

    # No remove(): Chauncey's no-deletion law (2026-09-27/28) — downloads
    # stay on the device once fetched. Nothing here deletes user files.
