"""Provider plugins — the provider-universal media layer (L1).

A provider is anything that can name tracks: local files today, YouTube
or PeerTube tomorrow. The core never imports a provider SDK; providers
register themselves here and the engine only speaks this interface.

Ships with:
  * ``local`` — file-based provider: scans a directory for audio files.
  * ``fake``  — deterministic fake catalog. The whole test suite runs
    the engine against this; if the engine works on fake, L1 holds.

No network provider ships yet. That is the queued follow-up, not a
stub pretending otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Iterator, List, Optional

if TYPE_CHECKING:
    # downloads.py imports AUDIO_SUFFIXES from this module, so this
    # import stays under TYPE_CHECKING to avoid a runtime cycle.
    from .downloads import DownloadStore

AUDIO_SUFFIXES = (".mp3", ".wav", ".ogg", ".oga", ".flac", ".m4a", ".opus", ".aac")


@dataclass
class Track:
    """One playable item, provider-agnostic."""

    id: str
    title: str
    artist: str = "unknown artist"
    duration: Optional[float] = None  # seconds
    provider: str = ""
    ref: str = ""  # provider-local reference: path, id, or URL
    meta: Dict = field(default_factory=dict)

    def to_record(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "duration": self.duration,
            "provider": self.provider,
            "ref": self.ref,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_record(cls, rec: Dict) -> "Track":
        return cls(
            id=str(rec.get("id", "")),
            title=str(rec.get("title", "")),
            artist=str(rec.get("artist", "unknown artist")),
            duration=rec.get("duration"),
            provider=str(rec.get("provider", "")),
            ref=str(rec.get("ref", "")),
            meta=dict(rec.get("meta", {})),
        )


class ProviderPlugin:
    """Interface every provider implements. Core speaks only this."""

    name: str = "base"

    def search(self, query: str, limit: int = 25) -> List[Track]:
        raise NotImplementedError

    def resolve(self, ref: str) -> Track:
        """Turn a provider-local ref into a Track. Raises KeyError if unknown."""
        raise NotImplementedError

    def describe(self) -> Dict:
        return {"name": self.name, "kind": self.__class__.__name__}


class ProviderRegistry:
    """Name -> provider. Registration is explicit; unknown names refuse."""

    def __init__(self) -> None:
        self._providers: Dict[str, ProviderPlugin] = {}

    def register(self, provider: ProviderPlugin) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> ProviderPlugin:
        try:
            return self._providers[name]
        except KeyError:
            raise KeyError(
                f"unknown provider {name!r}; registered: {sorted(self._providers)}"
            ) from None

    def names(self) -> List[str]:
        return sorted(self._providers)

    def search_all(self, query: str, limit: int = 25) -> List[Track]:
        out: List[Track] = []
        for name in self.names():
            out.extend(self._providers[name].search(query, limit=limit))
        return out[:limit]


class LocalFileProvider(ProviderPlugin):
    """File-based provider: a directory of audio files is the library."""

    name = "local"

    def __init__(self, library_dir: str | Path) -> None:
        self.library_dir = Path(library_dir)

    def _iter_files(self) -> Iterator[Path]:
        if not self.library_dir.is_dir():
            return
        for path in sorted(self.library_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES:
                yield path

    def _track_for(self, path: Path) -> Track:
        stem = path.stem
        artist, title = "unknown artist", stem
        if " - " in stem:
            artist, title = (part.strip() for part in stem.split(" - ", 1))
        return Track(
            id=f"local:{path.relative_to(self.library_dir)}",
            title=title,
            artist=artist,
            provider=self.name,
            ref=str(path),
        )

    def search(self, query: str, limit: int = 25) -> List[Track]:
        q = query.lower()
        hits = [self._track_for(p) for p in self._iter_files() if q in p.stem.lower()]
        return hits[:limit]

    def resolve(self, ref: str) -> Track:
        path = Path(ref)
        if not path.is_file():
            raise KeyError(f"local: no such file {ref!r}")
        return self._track_for(path)


class DownloadsProvider(LocalFileProvider):
    """The download lane as a provider: downloaded audio files are the
    offline-capable library. Track ids are namespaced ``downloads:``
    and carry the download manifest metadata (source_url, sha256,
    downloaded_at) when present. Files dropped in by hand still scan;
    only manifest-backed entries carry provenance."""

    name = "downloads"

    def __init__(self, store: "DownloadStore") -> None:
        self._store = store
        super().__init__(store.dir)

    def _track_for(self, path: Path) -> Track:
        track_id = f"downloads:{path.name}"
        meta: Dict = {}
        title = artist = None
        try:
            rec = self._store.get(track_id)
            meta = {
                "source_url": rec.get("url", ""),
                "sha256": rec.get("sha256", ""),
                "downloaded_at": rec.get("downloaded_at", ""),
                "bytes": rec.get("bytes", 0),
            }
            title, artist = rec.get("title"), rec.get("artist")
        except KeyError:
            pass
        if title is None:
            stem = path.stem
            artist, title = "unknown artist", stem
            if " - " in stem:
                artist, title = (p.strip() for p in stem.split(" - ", 1))
        return Track(
            id=track_id,
            title=title or path.stem,
            artist=artist or "unknown artist",
            provider=self.name,
            ref=str(path),
            meta=meta,
        )

    def search(self, query: str, limit: int = 25) -> List[Track]:
        """File-stem search like the parent, but also matches the
        manifest title/artist/id — a download renamed at fetch time
        stays findable under the name the user gave it."""
        q = query.lower().strip()
        hits = []
        for p in self._iter_files():
            track = self._track_for(p)
            if (
                not q
                or q in p.stem.lower()
                or q in track.title.lower()
                or q in track.artist.lower()
                or q in track.id.lower()
            ):
                hits.append(track)
            if len(hits) >= limit:
                break
        return hits

    def describe(self) -> Dict:
        d = super().describe()
        d["note"] = (
            "on-device downloads: direct audio files only, "
            "persisted across launches, playable offline"
        )
        return d


class FakeProvider(ProviderPlugin):
    """Deterministic fake catalog. The law L1 prover: the engine must
    run identically against this as against any real provider."""

    name = "fake"

    _CATALOG = (
        ("fake:001", "Midnight Static", "The Frequencies", 187.0),
        ("fake:002", "Copper Skyline", "Analog Bloom", 243.0),
        ("fake:003", "Glasswing", "The Frequencies", 201.0),
        ("fake:004", "Low Orbit Lullaby", "Night Cartographer", 176.0),
        ("fake:005", "Paper Satellites", "Analog Bloom", 220.0),
        ("fake:006", "Vantablack Heart", "The Frequencies", 198.0),
        ("fake:007", "Signal Bloom", "Night Cartographer", 232.0),
        ("fake:008", "Tape Ghost", "Analog Bloom", 189.0),
    )

    def search(self, query: str, limit: int = 25) -> List[Track]:
        q = query.lower()
        hits = [
            Track(
                id=tid,
                title=title,
                artist=artist,
                duration=dur,
                provider=self.name,
                ref=tid,
            )
            for tid, title, artist, dur in self._CATALOG
            if q in title.lower() or q in artist.lower() or not q.strip()
        ]
        return hits[:limit]

    def resolve(self, ref: str) -> Track:
        for tid, title, artist, dur in self._CATALOG:
            if tid == ref:
                return Track(
                    id=tid,
                    title=title,
                    artist=artist,
                    duration=dur,
                    provider=self.name,
                    ref=tid,
                )
        raise KeyError(f"fake: unknown ref {ref!r}")

    def describe(self) -> Dict:
        d = super().describe()
        d["note"] = "test double; no network, no audio"
        return d


def default_registry(library_dir: Optional[str | Path] = None) -> ProviderRegistry:
    reg = ProviderRegistry()
    reg.register(FakeProvider())
    if library_dir is not None:
        reg.register(LocalFileProvider(library_dir))
    return reg
