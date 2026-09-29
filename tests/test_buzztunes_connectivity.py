"""BuzzTunes 0.2.0 connectivity laws (Chauncey 2026-09-28):
"Should be online connection default but offline capable with downloads."

Laws under test:
  1. ONLINE is the default — no manual toggle needed to be online.
  2. Connectivity flips are recorded with source + timestamp.
  3. A downloaded copy always wins over the network; offline + a
     download on-device still routes local.
  4. Offline + not downloaded refuses honestly — no crash, no fake audio.
  5. Downloads persist on-device across engine restarts (manifest + file).
  6. The download lane refuses non-audio URLs and YouTube URLs with
     plain speech — never a fake download.
  7. A failed download leaves no manifest entry and no partial file.
  8. A manifest entry whose file went missing is marked missing, never
     pretended present.

Hermetic: the "server" is a localhost HTTP server on 127.0.0.1 —
no external network, per tests/conftest.py.
"""

import hashlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from levi.buzztunes import engine as engine_mod
from levi.buzztunes.connectivity import Connectivity
from levi.buzztunes.downloads import DownloadError, DownloadStore


PAYLOAD = b"RIFF" + b"\x00" * 100 + b"fake-audio-bytes-for-tests"


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/track.mp3":
            body = PAYLOAD
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture()
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def make_engine(tmp_path):
    return engine_mod.BuzzEngine(store_dir=str(tmp_path / "store"))


# -- law 1: online default ---------------------------------------------
def test_online_is_default(tmp_path):
    eng = make_engine(tmp_path)
    status = eng.connectivity_status()
    assert status["online"] is True
    assert status["state"] == "online"
    assert status["source"] == "default"


def test_connectivity_object_defaults_online():
    c = Connectivity()
    assert c.is_online() is True


# -- law 2: flips recorded ----------------------------------------------
def test_connectivity_roundtrip(tmp_path):
    eng = make_engine(tmp_path)
    off = eng.set_online(False, source="test", actor="owner")
    assert off["online"] is False
    assert off["state"] == "offline"
    on = eng.set_online(True, source="android", actor="owner")
    assert on["online"] is True
    assert on["source"] == "android"
    assert on["transitions"] >= 2


# -- law 5: downloads persist -------------------------------------------
def test_download_persists_across_restart(tmp_path, server):
    store_dir = str(tmp_path / "store")
    eng = make_engine(tmp_path)
    res = eng.download_url(
        f"{server}/track.mp3", title="Test Track", artist="Test Artist"
    )
    rec = res["download"]
    assert rec["bytes"] == len(PAYLOAD)
    assert rec["sha256"] == hashlib.sha256(PAYLOAD).hexdigest()
    assert res["receipt"]["action"] == "download.add"
    assert Path(rec["ref"]).is_file()

    # restart: new engine over the same store dir
    eng2 = engine_mod.BuzzEngine(store_dir=store_dir)
    dl = eng2.downloads_list()
    assert len(dl) == 1
    assert dl[0]["id"] == rec["id"]
    assert dl[0]["missing"] is False
    assert dl[0]["sha256"] == hashlib.sha256(PAYLOAD).hexdigest()

    # the downloads provider exposes it in the catalog
    hits = eng2.registry.search_all("Test Track")
    assert any(t.id == rec["id"] and t.provider == "downloads" for t in hits)


# -- law 3: downloaded copy wins, even offline ---------------------------
def test_downloaded_copy_wins_over_network(tmp_path, server):
    eng = make_engine(tmp_path)
    rec = eng.download_url(f"{server}/track.mp3", title="Offline Song")["download"]
    eng.set_online(False, source="test")
    route = eng.playback_route(rec["id"])
    assert route["mode"] == "local"
    assert Path(route["path"]).is_file()


def test_offline_ready_availability(tmp_path, server):
    eng = make_engine(tmp_path)
    rec = eng.download_url(f"{server}/track.mp3")["download"]
    track = eng._find_any(rec["id"])
    avail = eng.availability(track)
    assert avail["state"] == "offline-ready"
    assert avail["downloaded"] is True
    assert avail["offline_playable"] is True


def test_play_returns_local_route_for_download(tmp_path, server):
    eng = make_engine(tmp_path)
    rec = eng.download_url(f"{server}/track.mp3")["download"]
    res = eng.play(rec["id"])
    assert res["route"]["mode"] == "local"
    assert res["receipt"]["details"]["playback"] == "local-file"


# -- law 4: offline refusal, honest ---------------------------------------
def test_offline_refuses_not_downloaded(tmp_path):
    eng = make_engine(tmp_path)
    fake = eng.registry.search_all("frequencies")[0]
    eng.set_online(False, source="test")
    route = eng.playback_route(fake.id)
    assert route["mode"] == "unavailable"
    assert "offline" in route["reason"]
    # no crash through play() either
    res = eng.play(fake.id)
    assert res["route"]["mode"] == "unavailable"


def test_online_fake_track_stays_catalog_only(tmp_path):
    eng = make_engine(tmp_path)
    fake = eng.registry.search_all("frequencies")[0]
    avail = eng.availability(fake)
    assert avail["state"] == "catalog-only"
    assert avail["offline_playable"] is False


# -- law 6: honest refusals -------------------------------------------------
def test_download_refuses_non_audio_url(tmp_path):
    eng = make_engine(tmp_path)
    with pytest.raises(DownloadError) as exc:
        eng.download_url("https://example.com/some-page.html")
    assert "direct" in str(exc.value).lower()
    assert eng.downloads_list() == []


def test_download_refuses_youtube_url(tmp_path):
    eng = make_engine(tmp_path)
    with pytest.raises(DownloadError) as exc:
        eng.download_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert "youtube" in str(exc.value).lower()
    assert eng.downloads_list() == []


def test_download_refuses_non_http_scheme(tmp_path):
    eng = make_engine(tmp_path)
    with pytest.raises(DownloadError):
        eng.download_url("ftp://example.com/track.mp3")


# -- law 7: failed download leaves nothing fake -----------------------------
def test_failed_download_leaves_no_state(tmp_path):
    store = DownloadStore(tmp_path / "dl")
    with pytest.raises(DownloadError):
        store.download("http://127.0.0.1:1/track.mp3", timeout=2)
    assert store.list() == []
    assert list(store.dir.glob("*.part")) == []
    assert store._manifest == {}
    assert not store.manifest_path.exists()


def test_404_download_leaves_no_state(tmp_path, server):
    store = DownloadStore(tmp_path / "dl")
    with pytest.raises(DownloadError):
        store.download(f"{server}/nope.mp3")
    assert store.list() == []


# -- law 8: missing file marked, never pretended ----------------------------
def test_missing_file_marked_missing(tmp_path, server):
    store = DownloadStore(tmp_path / "dl")
    rec = store.download(f"{server}/track.mp3")
    Path(rec["ref"]).unlink()
    listed = store.list()
    assert listed[0]["missing"] is True
    with pytest.raises(DownloadError):
        store.path_for(rec["id"])


# (no remove test: the no-deletion law means downloads stay on-device —
# there is no deletion capability to test)
