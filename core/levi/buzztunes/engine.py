"""Engine — queue, play, curate. The working core.

Honest boundary: the engine orders, queues, receipts, and scores. It
does NOT render audio. ``play()`` returns a play order describing what
would sound; the open follow-up is a real output sink (phone audio).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .curation import curate
from .demand import DemandLog
from .m3u import ParsedPlaylist, parse_m3u, read_playlist, write_playlist
from .providers import ProviderRegistry, Track, default_registry
from .receipts import ReceiptLog
from .stack import CuratorPool


class BuzzEngine:
    def __init__(self, store_dir: str | Path,
                 registry: Optional[ProviderRegistry] = None,
                 library_dir: Optional[str | Path] = None) -> None:
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.registry = registry or default_registry(library_dir)
        self.receipts = ReceiptLog(self.store_dir)
        self.demand = DemandLog(self.store_dir)
        self.curators = CuratorPool(self.store_dir / "curators")
        self._queue: List[Track] = []
        self._now_playing: Optional[Track] = None

    # -- queue ---------------------------------------------------------
    def queue_add(self, track: Track, actor: str = "owner") -> Dict:
        self._queue.append(track)
        self.demand.record("queue", track.id)
        return self.receipts.emit("queue.add", actor=actor, details={
            "track": track.to_record(), "position": len(self._queue)})

    def queue_list(self) -> List[Track]:
        return list(self._queue)

    def queue_clear(self, actor: str = "owner") -> Dict:
        n = len(self._queue)
        self._queue.clear()
        return self.receipts.emit("queue.clear", actor=actor,
                                  details={"removed": n})

    # -- play ----------------------------------------------------------
    def play(self, track_id: str, actor: str = "owner") -> Dict:
        track = next((t for t in self._queue if t.id == track_id), None)
        if track is None:
            track = self.registry.search_all(track_id, limit=1)
            track = track[0] if track else None
        if track is None:
            raise KeyError(f"nothing to play for {track_id!r}")
        self._now_playing = track
        self.demand.record("play", track.id)
        receipt = self.receipts.emit("play", actor=actor, details={
            "track": track.to_record(),
            "playback": "ordered-not-rendered",
            "note": "audio rendering is the open follow-up; the order is real"})
        return {"now_playing": track.to_record(), "receipt": receipt}

    def skip(self, track_id: str, actor: str = "owner",
             curator_index: int = 0) -> Dict:
        self.demand.record("skip", track_id)
        curator = self.curators.get(curator_index)
        learned = curator.learn(track_id, "curation", success=False,
                                tried_what=f"queued {track_id}",
                                note="listener skipped the pick")
        self._queue = [t for t in self._queue if t.id != track_id]
        return self.receipts.emit("skip", actor=actor, details={
            "track_id": track_id, "composted_by": curator.name,
            "genome": learned})

    def complete(self, track_id: str, actor: str = "owner",
                 curator_index: int = 0) -> Dict:
        self.demand.record("complete", track_id)
        curator = self.curators.get(curator_index)
        learned = curator.learn(track_id, "curation", success=True,
                                tried_what=f"queued {track_id}",
                                note="listener played it through")
        return self.receipts.emit("complete", actor=actor, details={
            "track_id": track_id, "learned_by": curator.name,
            "genome": learned})

    # -- curate --------------------------------------------------------
    def curate(self, query: str, provider: str = "fake",
               curator_index: int = 0, actor: str = "owner") -> Dict:
        prov = self.registry.get(provider)
        candidates = prov.search(query)
        curator = self.curators.get(curator_index)
        result = curate(
            candidates, seed=query, demand_log=self.demand,
            receipts=self.receipts,
            genome_consult=lambda pid: curator.consult(pid, "curation"),
            echo_explore=lambda t: curator.explore_variants(
                f"{t.artist} {t.title}"),
            actor=f"{actor}:{curator.name}")
        self.demand.record("curate", result["queue"][0].id if result["queue"]
                           else query, {"query": query})
        return result

    # -- m3u bridge ----------------------------------------------------
    def import_m3u(self, path: str | Path, actor: str = "owner") -> Dict:
        parsed = read_playlist(path)
        for t in parsed.tracks:
            self._queue.append(t)
        receipt = self.receipts.emit("m3u.import", actor=actor, details={
            "path": str(path), "imported": len(parsed.tracks),
            "skipped": parsed.skipped})
        return {"parsed": parsed, "receipt": receipt}

    def export_m3u(self, path: str | Path, actor: str = "owner") -> Dict:
        n = write_playlist(path, self._queue)
        return self.receipts.emit("m3u.export", actor=actor, details={
            "path": str(path), "tracks": n})

    def now_playing(self) -> Optional[Dict]:
        return self._now_playing.to_record() if self._now_playing else None
