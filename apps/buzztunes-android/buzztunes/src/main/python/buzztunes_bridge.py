"""BuzzTunes Android bridge.

JSON in/out wrappers over the on-device engine:
  - engine : play / queue / curate / forge / m3u / receipts / demand
  - dj     : the SI DJ — picks with why-lines, honest catalog
  - threads: Bloome listening threads — agents curate, members share
  - youtube: the playback seam — honest "not linked" state, never fakes audio
  - connectivity: online-default state, pushed from Android's
    ConnectivityManager via set_online(); the engine defaults to ONLINE
    until the first real report arrives
  - downloads: direct-audio-file downloads persisted on-device for
    offline playback; YouTube URLs are refused honestly

Every function returns a JSON string. The Java side never touches
Python objects directly. Chauncey's rulings baked in:
  * YouTube, NOT Spotify (2026-09-27)
  * Bloome + Metrolist MIX in one product
  * Online connection default, offline capable with downloads (2026-09-28)
  * play() shows and queues; downloaded tracks play their real local
    file; nothing else fakes audio
"""

from __future__ import annotations

import json
from pathlib import Path

from levi.buzztunes.engine import BuzzEngine
from levi.buzztunes.providers import Track, default_registry
from levi.buzztunes.threads import ThreadStore
from levi.buzztunes import youtube as youtube_mod
from levi.buzztunes.dj import pick_song
from levi.buzztunes.forge import forge_playlists
from levi.buzztunes.stack import check_stack

_ENGINE: BuzzEngine | None = None
_THREADS: ThreadStore | None = None
_STORE: Path | None = None


def _err(exc: BaseException) -> str:
    return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def _track_rec(t: Track) -> dict:
    rec = t.to_record()
    try:
        avail = _engine().availability(t)
        rec["downloaded"] = avail["downloaded"]
        rec["availability"] = avail["state"]
        rec["availability_reason"] = avail["reason"]
    except Exception:
        pass
    return rec


def _coerce(obj):
    """Serialize engine results: Tracks -> records, recursively."""
    if isinstance(obj, Track):
        return obj.to_record()
    if hasattr(obj, "to_record") and callable(obj.to_record):
        try:
            return _coerce(obj.to_record())
        except Exception:
            pass
    if isinstance(obj, dict):
        return {str(k): _coerce(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_coerce(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def _ok(**kw) -> str:
    return json.dumps({"ok": True, **_coerce(kw)})


def set_store(path: str) -> str:
    """Point the engine at its on-device store dir. Call once at launch."""
    global _ENGINE, _THREADS, _STORE
    try:
        _STORE = Path(path)
        _STORE.mkdir(parents=True, exist_ok=True)
        reg = default_registry()
        _ENGINE = BuzzEngine(str(_STORE), reg)
        _THREADS = ThreadStore(_ENGINE, str(_STORE / "threads"))
        return _ok(store=str(_STORE))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def _engine() -> BuzzEngine:
    if _ENGINE is None:
        raise RuntimeError("store not set — call set_store first")
    return _ENGINE


def _threads() -> ThreadStore:
    if _THREADS is None:
        raise RuntimeError("store not set — call set_store first")
    return _THREADS


def _catalog() -> list:
    tracks = []
    seen = set()
    for name in _engine().registry.names():
        for t in _engine().registry.get(name).search("", limit=10000):
            if t.id not in seen:
                seen.add(t.id)
                tracks.append(t)
    return tracks


def catalog() -> str:
    """The real catalog. Never invented — straight from providers."""
    try:
        return _ok(tracks=[_track_rec(t) for t in _catalog()])
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def dj_pick(mood: str, activity: str, energy: str = "", era: str = "") -> str:
    """Ask the SI DJ. Returns track + concept + voice line + why + path."""
    try:
        pick = pick_song(
            mood,
            activity,
            _catalog(),
            energy=energy or None,
            era=era or None,
            receipts=_engine().receipts,
            actor="dj:app",
        )
        return _ok(
            track=_track_rec(pick.track),
            concept=pick.concept,
            voice_line=pick.voice_line,
            reason=pick.reason,
            voice_path=pick.voice_path,
            axes=pick.axes,
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def curate(query: str) -> str:
    """KFX² curation over the real catalog."""
    try:
        res = _engine().curate(query, actor="owner:app")
        return _ok(result=res)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def forge(count: int, seed: str) -> str:
    """Forge deterministic playlists from the real catalog."""
    try:
        pls = forge_playlists(int(count), _catalog(), seed=seed or "buzz")
        return _ok(playlists=[p.to_record() for p in pls])
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def _find_track(track_id: str) -> Track:
    for t in _catalog():
        if t.id == track_id:
            return t
    for t in _engine().queue_list():
        if t.id == track_id:
            return t
    raise KeyError(f"unknown track {track_id!r}")


def queue_add(track_id: str) -> str:
    try:
        rec = _engine().queue_add(_find_track(track_id), actor="owner:app")
        return _ok(receipt=rec)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def queue_list() -> str:
    try:
        return _ok(tracks=[_track_rec(t) for t in _engine().queue_list()])
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def queue_clear() -> str:
    try:
        rec = _engine().queue_clear(actor="owner:app")
        return _ok(receipt=rec)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def play(track_id: str) -> str:
    """Play = order + show + honest route. Downloaded tracks return their
    real local file for the phone's audio sink; nothing else fakes audio."""
    try:
        res = _engine().play(track_id, actor="owner:app")
        yt = youtube_mod.status()
        route = res.get("route", {})
        return _ok(
            now_playing=res.get("now_playing"),
            playback=res.get("receipt", {})
            .get("details", {})
            .get("playback", "ordered-not-rendered"),
            route=route,
            availability=res.get("availability", {}),
            youtube=yt,
            note=route.get("note")
            or route.get("reason")
            or ("YouTube not linked — order shown, rendering is the open follow-up"),
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def set_online(online: str) -> str:
    """Record the phone's network state. Java passes "1"/"0"."""
    try:
        val = str(online).strip().lower() in ("1", "true", "yes", "on")
        return _ok(
            status=_engine().set_online(val, source="android", actor="owner:app")
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def connectivity() -> str:
    """Last-known connectivity state (online by default)."""
    try:
        return _ok(status=_engine().connectivity_status())
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def download_add(url: str, title: str = "", artist: str = "") -> str:
    """Download a direct audio URL for offline playback. Refuses
    non-audio and YouTube URLs honestly — never a fake download."""
    try:
        res = _engine().download_url(
            url, title=title or None, artist=artist or None, actor="owner:app"
        )
        return _ok(download=res["download"], receipt=res["receipt"])
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def downloads_list() -> str:
    """On-device downloads with honest availability."""
    try:
        return _ok(downloads=_engine().downloads_list())
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# No download_remove: Chauncey's no-deletion law — downloads stay on the
# device once fetched. Storage management is his call, not a UI action.


def youtube_status() -> str:
    try:
        return _ok(status=youtube_mod.status())
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def threads_list() -> str:
    try:
        return _ok(threads=_threads().list())
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def thread_create(name: str) -> str:
    try:
        t = _threads().create(name, actor="owner:app")
        return _ok(thread={"id": t.id, "name": t.name})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def thread_join(thread_id: str, member: str) -> str:
    try:
        rec = _threads().get(thread_id).join(member or "owner")
        return _ok(receipt=rec)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def thread_curate(thread_id: str, agent_name: str, query: str) -> str:
    """An agent curates into the thread — the Bloome half of the mix."""
    try:
        th = _threads().get(thread_id)
        res = _engine().curate(query, actor=f"agent:{agent_name}")
        tracks = res.get("queue", [])
        rec = th.add_curation(agent_name, tracks)
        return _ok(receipt=rec, tracks=[_track_rec(t) for t in tracks])
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def thread_queue(thread_id: str) -> str:
    try:
        return _ok(queue=_threads().get(thread_id).shared_queue())
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def stack() -> str:
    """The engine's own honest wiring report."""
    try:
        return _ok(report=check_stack())
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def laws() -> str:
    return _ok(
        laws=[
            "L1 provider-universal — core runs against any provider plugin; "
            "no provider SDK imports in core.",
            "L2 clean-room — no GPLv3-derived or target-derived code.",
            "L3 honest receipts — every play, queue, curation, skip, and "
            "thread action emits a receipt to the append-only log.",
            "L4 money 70/30 fail-closed — paid flows move ONLY through a "
            "Cybrus-marked rail; with no rail, every charge refuses.",
            "L5 thread surface — agent curation reaches a queue ONLY through "
            "a listening thread; no agent-inject backdoor.",
            "YouTube, not Spotify — Chauncey 2026-09-27. The seam reports "
            "honest not-linked state; audio is never faked.",
        ]
    )
