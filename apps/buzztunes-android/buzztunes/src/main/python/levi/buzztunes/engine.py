"""Engine — queue, play, curate. The working core.

Honest boundary: the engine orders, queues, receipts, and scores. Audio
rendering: downloaded (on-device) tracks carry a real local file the
phone's audio sink can play; everything else is ordered-and-shown.
``play()`` returns the honest playback route — never faked audio.

Connectivity (Chauncey 2026-09-28: online default, offline capable with
downloads): the engine defaults to ONLINE; the Android shell pushes the
real network state in via ``set_online()``. A downloaded copy always
wins over the network; offline + not-downloaded refuses honestly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .connectivity import Connectivity
from .curation import curate
from .demand import DemandLog
from .downloads import DownloadStore
from .m3u import read_playlist, write_playlist
from .providers import (
    DownloadsProvider,
    ProviderRegistry,
    Track,
    default_registry,
)
from .receipts import ReceiptLog
from .stack import CuratorPool


class BuzzEngine:
    def __init__(
        self,
        store_dir: str | Path,
        registry: Optional[ProviderRegistry] = None,
        library_dir: Optional[str | Path] = None,
    ) -> None:
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.registry = registry or default_registry(library_dir)
        self.receipts = ReceiptLog(self.store_dir)
        self.demand = DemandLog(self.store_dir)
        self.curators = CuratorPool(self.store_dir / "curators")
        # Connectivity: online by default (Chauncey 2026-09-28); the
        # Android shell pushes the real state via set_online().
        self.connectivity = Connectivity()
        # Download lane: direct audio files persisted on-device, always
        # registered so the catalog honestly shows offline availability.
        self.downloads = DownloadStore(self.store_dir / "downloads")
        self.registry.register(DownloadsProvider(self.downloads))
        self._queue: List[Track] = []
        self._now_playing: Optional[Track] = None

    # -- connectivity --------------------------------------------------
    def set_online(
        self, online: bool, source: str = "android", actor: str = "owner"
    ) -> Dict:
        """Record the phone's network state (pushed from Java).

        Connectivity is system state, not listener demand, so it is not
        demand-logged — the transitions counter + changed_at carry it."""
        return self.connectivity.set_online(bool(online), source=source)

    def connectivity_status(self) -> Dict:
        return self.connectivity.to_record()

    # -- downloads -----------------------------------------------------
    def download_url(
        self,
        url: str,
        title: Optional[str] = None,
        artist: Optional[str] = None,
        actor: str = "owner",
    ) -> Dict:
        """Download a direct audio URL for offline playback. Honest
        refusals (non-audio URL, YouTube URL, network failure) raise
        DownloadError with plain speech — never a fake download."""
        rec = self.downloads.download(url, title=title, artist=artist)
        receipt = self.receipts.emit(
            "download.add",
            actor=actor,
            details={
                "track_id": rec["id"],
                "url": rec["url"],
                "bytes": rec["bytes"],
                "sha256": rec["sha256"],
            },
        )
        return {"download": rec, "receipt": receipt}

    def downloads_list(self) -> List[Dict]:
        return self.downloads.list()

    # -- availability + playback routing --------------------------------
    def _find_any(self, track_id: str) -> Optional[Track]:
        """Resolve a track id honestly: queue first, then a full catalog
        scan for an exact id match (same approach as the bridge's
        _find_track). Never text-searches by id."""
        for t in self._queue:
            if t.id == track_id:
                return t
        for t in self.registry.search_all("", limit=1000):
            if t.id == track_id:
                return t
        return None

    def _local_path(self, track: Track) -> Optional[Path]:
        """On-device audio file for this track, if one truly exists."""
        if track.provider == "downloads":
            try:
                return self.downloads.path_for(track.id)
            except (KeyError, Exception):
                return None
        if track.provider == "local":
            p = Path(track.ref)
            return p if p.is_file() else None
        return None

    def availability(self, track: Track) -> Dict:
        """Honest availability for one track: what is actually playable,
        online and offline. Never claims more than exists."""
        local = self._local_path(track)
        if local is not None:
            return {
                "track_id": track.id,
                "downloaded": True,
                "offline_playable": True,
                "online_playable": True,
                "state": "offline-ready",
                "reason": "on this device — plays with or without network",
            }
        if track.provider == "youtube":
            from . import youtube as youtube_mod

            if youtube_mod.configured():
                return {
                    "track_id": track.id,
                    "downloaded": False,
                    "offline_playable": False,
                    "online_playable": True,
                    "state": "online-only",
                    "reason": "streams while online; download it for offline",
                }
            return {
                "track_id": track.id,
                "downloaded": False,
                "offline_playable": False,
                "online_playable": False,
                "state": "catalog-only",
                "reason": (
                    "YouTube isn't linked yet — shown and queued, no audio faked"
                ),
            }
        if track.provider == "fake":
            return {
                "track_id": track.id,
                "downloaded": False,
                "offline_playable": False,
                "online_playable": False,
                "state": "catalog-only",
                "reason": "catalog entry — no audio source to play or fetch",
            }
        return {
            "track_id": track.id,
            "downloaded": False,
            "offline_playable": False,
            "online_playable": self.connectivity.is_online(),
            "state": (
                "online-only"
                if self.connectivity.is_online()
                else "unavailable-offline"
            ),
            "reason": (
                "needs a network connection"
                if self.connectivity.is_online()
                else "offline and not downloaded"
            ),
        }

    def playback_route(self, track_id: str) -> Dict:
        """Decide how a track would actually sound. A downloaded copy
        always wins; offline + not-downloaded refuses honestly."""
        track = self._find_any(track_id)
        if track is None:
            raise KeyError(f"nothing to play for {track_id!r}")
        local = self._local_path(track)
        if local is not None:
            return {
                "mode": "local",
                "path": str(local),
                "track_id": track.id,
                "note": "playing the on-device download",
            }
        if not self.connectivity.is_online():
            return {
                "mode": "unavailable",
                "track_id": track.id,
                "reason": (
                    "offline and not downloaded — download it "
                    "while online to play it offline"
                ),
            }
        if track.provider == "youtube":
            from . import youtube as youtube_mod

            if youtube_mod.configured():
                return {
                    "mode": "online",
                    "track_id": track.id,
                    "note": "streaming via the YouTube seam",
                }
        return {
            "mode": "ordered",
            "track_id": track.id,
            "note": (
                "YouTube not linked — order shown, rendering is "
                "the open follow-up; no audio faked"
            ),
        }

    # -- queue ---------------------------------------------------------
    def queue_add(self, track: Track, actor: str = "owner") -> Dict:
        self._queue.append(track)
        self.demand.record("queue", track.id)
        return self.receipts.emit(
            "queue.add",
            actor=actor,
            details={"track": track.to_record(), "position": len(self._queue)},
        )

    def queue_list(self) -> List[Track]:
        return list(self._queue)

    def queue_clear(self, actor: str = "owner") -> Dict:
        n = len(self._queue)
        self._queue.clear()
        return self.receipts.emit("queue.clear", actor=actor, details={"removed": n})

    # -- play ----------------------------------------------------------
    def play(self, track_id: str, actor: str = "owner") -> Dict:
        track = self._find_any(track_id)
        if track is None:
            raise KeyError(f"nothing to play for {track_id!r}")
        self._now_playing = track
        self.demand.record("play", track.id)
        route = self.playback_route(track.id)
        avail = self.availability(track)
        receipt = self.receipts.emit(
            "play",
            actor=actor,
            details={
                "track": track.to_record(),
                "playback": (
                    "local-file" if route["mode"] == "local" else "ordered-not-rendered"
                ),
                "route": route,
                "note": route.get("note") or route.get("reason", ""),
            },
        )
        return {
            "now_playing": track.to_record(),
            "receipt": receipt,
            "route": route,
            "availability": avail,
        }

    def skip(self, track_id: str, actor: str = "owner", curator_index: int = 0) -> Dict:
        self.demand.record("skip", track_id)
        curator = self.curators.get(curator_index)
        learned = curator.learn(
            track_id,
            "curation",
            success=False,
            tried_what=f"queued {track_id}",
            note="listener skipped the pick",
        )
        self._queue = [t for t in self._queue if t.id != track_id]
        return self.receipts.emit(
            "skip",
            actor=actor,
            details={
                "track_id": track_id,
                "composted_by": curator.name,
                "genome": learned,
            },
        )

    def complete(
        self, track_id: str, actor: str = "owner", curator_index: int = 0
    ) -> Dict:
        self.demand.record("complete", track_id)
        curator = self.curators.get(curator_index)
        learned = curator.learn(
            track_id,
            "curation",
            success=True,
            tried_what=f"queued {track_id}",
            note="listener played it through",
        )
        return self.receipts.emit(
            "complete",
            actor=actor,
            details={
                "track_id": track_id,
                "learned_by": curator.name,
                "genome": learned,
            },
        )

    # -- curate --------------------------------------------------------
    def curate(
        self,
        query: str,
        provider: str = "fake",
        curator_index: int = 0,
        actor: str = "owner",
    ) -> Dict:
        prov = self.registry.get(provider)
        candidates = prov.search(query)
        curator = self.curators.get(curator_index)
        result = curate(
            candidates,
            seed=query,
            demand_log=self.demand,
            receipts=self.receipts,
            genome_consult=lambda pid: curator.consult(pid, "curation"),
            echo_explore=lambda t: curator.explore_variants(f"{t.artist} {t.title}"),
            actor=f"{actor}:{curator.name}",
        )
        self.demand.record(
            "curate",
            result["queue"][0].id if result["queue"] else query,
            {"query": query},
        )
        return result

    # -- m3u bridge ----------------------------------------------------
    def import_m3u(self, path: str | Path, actor: str = "owner") -> Dict:
        parsed = read_playlist(path)
        for t in parsed.tracks:
            self._queue.append(t)
        receipt = self.receipts.emit(
            "m3u.import",
            actor=actor,
            details={
                "path": str(path),
                "imported": len(parsed.tracks),
                "skipped": parsed.skipped,
            },
        )
        return {"parsed": parsed, "receipt": receipt}

    def export_m3u(self, path: str | Path, actor: str = "owner") -> Dict:
        n = write_playlist(path, self._queue)
        return self.receipts.emit(
            "m3u.export", actor=actor, details={"path": str(path), "tracks": n}
        )

    def now_playing(self) -> Optional[Dict]:
        return self._now_playing.to_record() if self._now_playing else None
