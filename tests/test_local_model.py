"""Hermetic tests for levi.agent.local_model (the ``levi-local`` provider).

No real network, no real model weights, no real llama.cpp binary: the
runner is a fake executable script, the download source is a loopback
HTTP server, and HOME/MODEL_DIR are isolated per test. Spawned fake
servers are shut down by an autouse fixture (atexit is the backstop).
"""

import json
import os
import stat
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from levi.agent import local_model
from levi.agent.local_model import LocalModelProvider, PullError
from levi.agent.providers import LocalProvider, select_provider

ROOT = Path(__file__).resolve().parents[1]

FAKE_SERVER_SCRIPT = """\
#!/usr/bin/env python3
import json, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

port = None
argv = sys.argv[1:]
i = 0
while i < len(argv):
    if argv[i] == "--port" and i + 1 < len(argv):
        port = int(argv[i + 1]); i += 2
    elif argv[i] == "-m" and i + 1 < len(argv):
        i += 2
    else:
        i += 1

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()
    def do_POST(self):
        if self.path == "/v1/chat/completions":
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            tools = payload.get("tools") or []
            name = tools[0]["function"]["name"] if tools else "file_read"
            msg = {"role": "assistant", "content": "fake-model reply",
                   "tool_calls": [{"id": "call-1", "type": "function",
                                   "function": {"name": name, "arguments": "{}"}}]}
            body = json.dumps({"choices": [{"message": msg}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
"""

FAKE_RUNNER_DIES = """\
#!/usr/bin/env python3
import sys
sys.exit(1)
"""


@pytest.fixture(autouse=True)
def _clean_servers():
    yield
    local_model.shutdown_servers()


@pytest.fixture()
def model_home(tmp_path, monkeypatch):
    """Isolated model dir + HOME; no runner on the fake PATH."""
    home = tmp_path / "home"
    mdir = home / ".levi" / "models"
    mdir.mkdir(parents=True)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("LEVI_MODEL_DIR", str(mdir))
    # Fake bindir first (so no real llama-server shadows the fake), but keep
    # the rest of PATH: the fake runner scripts use `#!/usr/bin/env python3`.
    monkeypatch.setenv(
        "PATH", os.pathsep.join([str(bindir), os.environ.get("PATH", "")])
    )
    monkeypatch.delenv("LEVI_LLAMA_SERVER", raising=False)
    monkeypatch.delenv("LEVI_LOCAL_MODEL", raising=False)
    monkeypatch.delenv("LEVI_PROVIDER", raising=False)
    return mdir


def _write_executable(path: Path, content: str) -> Path:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _install_fake_stack(mdir: Path, monkeypatch, script=FAKE_SERVER_SCRIPT):
    weights = mdir / "test-model.gguf"
    weights.write_bytes(b"GGUF-fake-weights")
    runner = _write_executable(mdir / "fake-llama-server", script)
    monkeypatch.setenv("LEVI_LLAMA_SERVER", str(runner))
    return weights, runner


# ---------------------------------------------------------------------------
# Discovery / availability
# ---------------------------------------------------------------------------


def test_unavailable_with_empty_model_dir(model_home):
    assert local_model.find_weights() is None
    assert local_model.find_runner() is None
    assert not LocalModelProvider().is_available()
    report = local_model.status_report()
    assert report["available"] is False
    assert report["weights"] is None
    assert report["runner"] is None


def test_unavailable_weights_only(model_home, monkeypatch):
    (model_home / "a.gguf").write_bytes(b"x")
    assert not LocalModelProvider().is_available()
    report = local_model.status_report()
    assert report["weights"] is not None
    assert report["runner"] is None


def test_unavailable_runner_only(model_home, monkeypatch):
    _write_executable(model_home / "llama-server-bin", "#!/bin/sh\n")
    # file exists but is not named llama-server and not on a searched path
    assert not LocalModelProvider().is_available()


def test_available_with_weights_and_runner(model_home, monkeypatch):
    _install_fake_stack(model_home, monkeypatch)
    assert LocalModelProvider().is_available()
    report = local_model.status_report()
    assert report["available"] is True
    assert report["weights"].endswith("test-model.gguf")


def test_find_weights_env_override(model_home, monkeypatch):
    (model_home / "a.gguf").write_bytes(b"a")
    (model_home / "b.gguf").write_bytes(b"b")
    monkeypatch.setenv("LEVI_LOCAL_MODEL", "b.gguf")
    assert local_model.find_weights().name == "b.gguf"
    monkeypatch.setenv("LEVI_LOCAL_MODEL", "missing.gguf")
    assert local_model.find_weights() is None


def test_provider_name_is_levi_local():
    assert LocalModelProvider.name == "levi-local"


# ---------------------------------------------------------------------------
# select_provider chain
# ---------------------------------------------------------------------------


def test_select_default_falls_back_to_local_when_unset_up(model_home):
    p = select_provider()
    assert isinstance(p, LocalProvider)


def test_select_env_levi_local_falls_back_when_unset_up(model_home, monkeypatch):
    monkeypatch.setenv("LEVI_PROVIDER", "levi-local")
    assert isinstance(select_provider(), LocalProvider)


def test_select_levi_local_when_available(model_home, monkeypatch):
    # levi-local is LEGACY and explicit-only: even fully set up, it no
    # longer wins the default chain — only an explicit selection does.
    _install_fake_stack(model_home, monkeypatch)
    monkeypatch.delenv("LEVI_PROVIDER", raising=False)
    p = select_provider()
    assert isinstance(p, LocalProvider)
    monkeypatch.setenv("LEVI_PROVIDER", "levi-local")
    p = select_provider()
    assert isinstance(p, LocalModelProvider)
    assert p.name == "levi-local"


def test_select_explicit_flag_wins_over_env(model_home, monkeypatch):
    _install_fake_stack(model_home, monkeypatch)
    monkeypatch.setenv("LEVI_PROVIDER", "levi-local")
    p = select_provider("local")
    assert isinstance(p, LocalProvider)


# ---------------------------------------------------------------------------
# Server lifecycle against the fake runner
# ---------------------------------------------------------------------------


def test_chat_through_fake_server(model_home, monkeypatch):
    _install_fake_stack(model_home, monkeypatch)
    provider = LocalModelProvider()
    tools = [
        {
            "name": "file_read",
            "description": "Read a file",
            "parameters": {"type": "object"},
        }
    ]
    resp = provider.chat(
        [local_model.ChatMessage(role="user", content="read x.txt")], tools
    )
    assert resp.error is None, resp.error
    assert resp.provider == "levi-local"
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "file_read"


def test_server_is_shared_across_provider_instances(model_home, monkeypatch):
    _install_fake_stack(model_home, monkeypatch)
    tools = [
        {"name": "file_read", "description": "d", "parameters": {"type": "object"}}
    ]
    LocalModelProvider().chat(
        [local_model.ChatMessage(role="user", content="a")], tools
    )
    LocalModelProvider().chat(
        [local_model.ChatMessage(role="user", content="b")], tools
    )
    assert len(local_model._servers) == 1


def test_server_shutdown_kills_process(model_home, monkeypatch):
    _install_fake_stack(model_home, monkeypatch)
    tools = [
        {"name": "file_read", "description": "d", "parameters": {"type": "object"}}
    ]
    LocalModelProvider().chat(
        [local_model.ChatMessage(role="user", content="a")], tools
    )
    assert len(local_model._servers) == 1
    proc = next(iter(local_model._servers.values())).proc
    assert proc.poll() is None
    local_model.shutdown_servers()
    assert local_model._servers == {}
    assert proc.poll() is not None


def test_dying_runner_reports_honest_error(model_home, monkeypatch):
    _install_fake_stack(model_home, monkeypatch, script=FAKE_RUNNER_DIES)
    monkeypatch.setenv("LEVI_LOCAL_READY_TIMEOUT", "2")
    provider = LocalModelProvider()
    # is_available() only checks files, so it is True even though the
    # runner dies on spawn — the failure surfaces at chat() time.
    assert provider.is_available()
    resp = provider.chat([local_model.ChatMessage(role="user", content="hi")], [])
    assert resp.error is not None
    assert "levi-local" in resp.error
    assert not resp.tool_calls


def test_chat_without_setup_reports_missing_plainly(model_home):
    provider = LocalModelProvider()
    resp = provider.chat([local_model.ChatMessage(role="user", content="hi")], [])
    assert resp.error is not None
    assert "no .gguf weights" in resp.error
    assert "model pull" in resp.error


# ---------------------------------------------------------------------------
# Download helper against a loopback HTTP server
# ---------------------------------------------------------------------------


class _FileHandler(BaseHTTPRequestHandler):
    payload = b""
    requests = 0

    def log_message(self, *a):
        pass

    def do_GET(self):
        type(self).requests += 1
        if self.path == "/missing.gguf":
            self.send_response(404)
            self.end_headers()
            return
        body = type(self).payload
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def file_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _FileHandler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:%d" % srv.server_address[1]
    srv.shutdown()
    srv.server_close()


@pytest.fixture()
def fake_models(monkeypatch, file_server):
    """MODELS registry pointing at the loopback server."""
    _FileHandler.payload = bytes(range(256)) * 256  # 64 KiB
    _FileHandler.requests = 0
    models = {
        "test-tiny": {
            "display": "Test Tiny",
            "file": "test-tiny.gguf",
            "url": file_server + "/test-tiny.gguf",
            "approx_bytes": len(_FileHandler.payload),
            "sha256": None,
            "blurb": "test fixture",
        },
    }
    monkeypatch.setattr(local_model, "MODELS", models)
    return models


def test_download_success_records_manifest(model_home, fake_models):
    progress_calls = []
    dest = local_model.download_weights(
        "test-tiny", progress=lambda d, t: progress_calls.append((d, t))
    )
    assert dest.is_file()
    assert dest.read_bytes() == _FileHandler.payload
    assert progress_calls, "progress callback was never called"
    manifest = json.loads((model_home / "manifest.json").read_text())
    entry = manifest["test-tiny.gguf"]
    assert entry["url"].endswith("/test-tiny.gguf")
    assert len(entry["sha256"]) == 64
    # Second call re-verifies against the manifest without re-downloading.
    before = _FileHandler.requests
    dest2 = local_model.download_weights("test-tiny")
    assert dest2 == dest
    assert _FileHandler.requests == before


def test_download_sha_mismatch_cleans_up(model_home, fake_models, monkeypatch):
    fake_models["test-tiny"]["sha256"] = "0" * 64
    with pytest.raises(PullError, match="[Ss][Hh][Aa].*mismatch"):
        local_model.download_weights("test-tiny")
    dest = model_home / "test-tiny.gguf"
    assert not dest.exists()
    leftovers = [p for p in model_home.iterdir() if p.suffix == ".part"]
    assert leftovers == []


def test_download_http_error_cleans_up(model_home, fake_models):
    fake_models["test-tiny"]["url"] = fake_models["test-tiny"]["url"].replace(
        "test-tiny.gguf", "missing.gguf"
    )
    fake_models["test-tiny"]["file"] = "missing.gguf"
    with pytest.raises(PullError, match="HTTP 404"):
        local_model.download_weights("test-tiny")
    assert not (model_home / "missing.gguf").exists()
    assert [p for p in model_home.iterdir() if p.suffix == ".part"] == []


def test_download_unknown_model(model_home):
    with pytest.raises(PullError, match="unknown model"):
        local_model.download_weights("nope")


# ---------------------------------------------------------------------------
# Runner asset picker (pure function — no network)
# ---------------------------------------------------------------------------


def test_pick_runner_asset_prefers_plain_cpu_build():
    assets = [
        {
            "name": "llama-b9999-bin-ubuntu-x64-cuda-12-4.zip",
            "browser_download_url": "http://x/cuda.zip",
        },
        {
            "name": "llama-b9999-bin-ubuntu-x64.zip",
            "browser_download_url": "http://x/plain.zip",
        },
        {
            "name": "llama-b9999-bin-macos-arm64.zip",
            "browser_download_url": "http://x/macos.zip",
        },
    ]
    picked = local_model._pick_runner_asset(assets, ("ubuntu", "x64"))
    assert picked["browser_download_url"] == "http://x/plain.zip"
    assert local_model._pick_runner_asset(assets, ("win", "x64")) is None


# ---------------------------------------------------------------------------
# CLI: `levi agent model status` (subprocess, hermetic env)
# ---------------------------------------------------------------------------


def _cli_env(tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "core"), *sys.path])
    env["HOME"] = str(tmp_path / "cli-home")
    env["LEVI_MODEL_DIR"] = str(tmp_path / "cli-home" / ".levi" / "models")
    env["PATH"] = str(tmp_path / "cli-bin")  # empty: no llama-server
    env.pop("LEVI_LLAMA_SERVER", None)
    env.pop("LEVI_LOCAL_MODEL", None)
    env.pop("LEVI_PROVIDER", None)
    return env


def _run_model_status(tmp_path):
    return subprocess.run(
        [sys.executable, "-m", "levi.cli.main", "agent", "model", "status"],
        cwd=ROOT,
        env=_cli_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_cli_model_status_reports_missing_pieces(tmp_path):
    proc = _run_model_status(tmp_path)
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "levi-tiny" in out
    assert "Weights   : MISSING" in out
    assert "Runner    : MISSING" in out
    assert "no LEVI weight available" in out


def test_cli_model_status_reports_ready(tmp_path):
    env = _cli_env(tmp_path)
    bin_dir = Path(env["PATH"])
    bin_dir.mkdir(parents=True)
    mdir = Path(env["LEVI_MODEL_DIR"])
    mdir.mkdir(parents=True)
    (mdir / "Qwen3-0.6B-Q8_0.gguf").write_bytes(b"GGUF")
    runner = _write_executable(bin_dir / "llama-server", "#!/bin/sh\nexit 0\n")
    assert runner.exists()
    proc = subprocess.run(
        [sys.executable, "-m", "levi.cli.main", "agent", "model", "status"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Weights   : PRESENT" in proc.stdout
    assert "Runner    : PRESENT" in proc.stdout
    assert "levi-0.6b" in proc.stdout
    assert "* levi-0.6b" in proc.stdout  # active default marker


# ---------------------------------------------------------------------------
# GGUF context metadata + clamping
# ---------------------------------------------------------------------------


def _gguf_blob(arch: str = "qwen3", context_length: int | None = 40960) -> bytes:
    """Minimal valid GGUF header with general.architecture (+ optional
    <arch>.context_length)."""
    import struct

    def kv_str(key: str, value: str) -> bytes:
        kb, vb = key.encode(), value.encode()
        return (
            struct.pack("<Q", len(kb))
            + kb
            + struct.pack("<I", 8)
            + struct.pack("<Q", len(vb))
            + vb
        )

    def kv_u32(key: str, value: int) -> bytes:
        kb = key.encode()
        return (
            struct.pack("<Q", len(kb))
            + kb
            + struct.pack("<I", 4)
            + struct.pack("<I", value)
        )

    kvs = [kv_str("general.architecture", arch)]
    if context_length is not None:
        kvs.append(kv_u32(f"{arch}.context_length", context_length))
    return b"GGUF" + struct.pack("<IQQ", 3, 0, len(kvs)) + b"".join(kvs)


def test_parse_gguf_context_length():
    assert local_model._parse_gguf_context_length(_gguf_blob()) == 40960
    assert (
        local_model._parse_gguf_context_length(
            _gguf_blob(arch="llama", context_length=8192)
        )
        == 8192
    )


def test_parse_gguf_context_length_missing():
    assert (
        local_model._parse_gguf_context_length(_gguf_blob(context_length=None)) is None
    )
    assert local_model._parse_gguf_context_length(b"not a gguf") is None
    assert local_model._parse_gguf_context_length(b"GGUF" + b"\x00" * 4) is None


def test_ctx_size_clamps_to_native(tmp_path, monkeypatch):
    weights = tmp_path / "m.gguf"
    weights.write_bytes(_gguf_blob())
    monkeypatch.setenv("LEVI_LOCAL_CTX_SIZE", "131072")
    assert local_model.ctx_size(weights) == 40960
    monkeypatch.setenv("LEVI_LOCAL_CTX_SIZE", "8192")
    assert local_model.ctx_size(weights) == 8192
    monkeypatch.setenv("LEVI_LOCAL_CTX_SIZE", "not-a-number")
    assert local_model.ctx_size(weights) == local_model.DEFAULT_CTX_SIZE
    # No readable metadata -> requested size stands.
    plain = tmp_path / "plain.gguf"
    plain.write_bytes(b"\x00" * 64)
    monkeypatch.setenv("LEVI_LOCAL_CTX_SIZE", "20000")
    assert local_model.ctx_size(plain) == 20000


def test_server_spawn_passes_ctx_flag(tmp_path, monkeypatch):
    """_start_server passes -c <clamped ctx> to the runner."""
    weights = tmp_path / "m.gguf"
    weights.write_bytes(_gguf_blob())
    monkeypatch.setenv("LEVI_LOCAL_CTX_SIZE", "131072")

    seen = {}

    class _FakeProc:
        def poll(self):
            return None

    def _fake_popen(args, **kwargs):
        seen["args"] = list(args)
        return _FakeProc()

    monkeypatch.setattr(local_model.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(local_model, "_wait_ready", lambda base_url: True)
    base_url, error = local_model._start_server("/fake/runner", weights)
    assert error is None
    args = seen["args"]
    assert "-c" in args
    assert args[args.index("-c") + 1] == "40960"


# ---------------------------------------------------------------------------
# Managed runner discovery + safe release extraction
# ---------------------------------------------------------------------------


def test_find_runner_prefers_managed_bin_dir(model_home, monkeypatch):
    """A runner installed by fetch_runner() into <model_dir>/bin is found
    without LEVI_LLAMA_SERVER or PATH."""
    monkeypatch.delenv("LEVI_LLAMA_SERVER", raising=False)
    bindir = model_home / "bin"
    bindir.mkdir(exist_ok=True)
    runner = _write_executable(bindir / "llama-server", "#!/bin/sh\n")
    # PATH here contains only the test bindir (no llama-server in it).
    assert local_model.find_runner() == str(runner)


def test_find_runner_env_override_still_wins(model_home, monkeypatch):
    bindir = model_home / "bin"
    bindir.mkdir(exist_ok=True)
    _write_executable(bindir / "llama-server", "#!/bin/sh\n")
    other = _write_executable(model_home / "custom-runner", "#!/bin/sh\n")
    monkeypatch.setenv("LEVI_LLAMA_SERVER", str(other))
    assert local_model.find_runner() == str(other)


def _make_release_zip(members: dict) -> "Path":
    import tempfile
    import zipfile

    tmp = Path(tempfile.mkdtemp()) / "rel.zip"
    with zipfile.ZipFile(tmp, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return tmp


def test_extract_runner_takes_server_and_sibling_libs(tmp_path):
    import zipfile

    zpath = _make_release_zip(
        {
            "build/bin/llama-server": b"ELF-binary",
            "build/bin/libggml.so": b"shared-lib",
            "build/bin/libfoo.so.1.2": b"versioned-lib",
            "build/bin/llama-cli": b"other-tool",  # not extracted
            "other/libbar.so": b"elsewhere-lib",  # wrong dir: skipped
            "../evil.sh": b"zip-slip",  # skipped
            "/abs/path.sh": b"zip-slip",  # skipped
        }
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    with zipfile.ZipFile(zpath) as zf:
        target = local_model._extract_runner_files(zf, bin_dir)
    assert target == bin_dir / "llama-server"
    assert (bin_dir / "llama-server").read_bytes() == b"ELF-binary"
    assert (bin_dir / "libggml.so").read_bytes() == b"shared-lib"
    assert (bin_dir / "libfoo.so.1.2").read_bytes() == b"versioned-lib"
    assert not (bin_dir / "llama-cli").exists()
    assert not (bin_dir / "libbar.so").exists()
    assert not (bin_dir / "evil.sh").exists()
    assert not (bin_dir / "path.sh").exists()


def test_extract_runner_none_without_server(tmp_path):
    import zipfile

    zpath = _make_release_zip({"build/bin/llama-cli": b"x"})
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    with zipfile.ZipFile(zpath) as zf:
        assert local_model._extract_runner_files(zf, bin_dir) is None
    assert list(bin_dir.iterdir()) == []


# ---------------------------------------------------------------------------
# Authoritative weight hashes
# ---------------------------------------------------------------------------


def test_models_carry_pinned_authoritative_sha256():
    """Both production models pin the Hugging Face Git-LFS SHA-256
    (content hash) and a commit-pinned download URL, so downloads are
    verified against an authoritative upstream value."""
    import re

    for key, spec in local_model.MODELS.items():
        sha = spec.get("sha256")
        assert re.fullmatch(r"[0-9a-f]{64}", sha or ""), (
            "model %r has no pinned SHA-256" % key
        )
        url = spec.get("url") or ""
        assert re.search(r"/resolve/[0-9a-f]{40}/", url), (
            "model %r URL is not pinned to an exact commit" % key
        )
        assert spec["file"] in url


def test_pinned_hash_is_enforced_on_download(model_home, monkeypatch):
    """A download whose bytes don't match the pinned sha256 is rejected
    and the partial file is removed."""
    import hashlib
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    payload = b"not the real weights"

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = payload
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        models = {
            "pinned": {
                "display": "Pinned",
                "file": "pinned.gguf",
                "url": "http://127.0.0.1:%d/pinned.gguf" % srv.server_address[1],
                "approx_bytes": len(payload),
                # sha256 of something else -> must fail
                "sha256": hashlib.sha256(b"something else").hexdigest(),
                "blurb": "test",
            },
        }
        monkeypatch.setattr(local_model, "MODELS", models)
        with pytest.raises(local_model.PullError, match="SHA-256 mismatch"):
            local_model.download_weights("pinned")
        assert not (model_home / "pinned.gguf").exists()
        assert not list(model_home.glob("pinned.gguf.*.part"))
    finally:
        srv.shutdown()
        srv.server_close()
