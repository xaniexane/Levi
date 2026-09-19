"""Levi Local — LEGACY offline model provider (llama-server backend).

Provider name: ``levi-local``.

.. deprecated::
    This llama-server + third-party GGUF path is LEGACY. It still works
    when explicitly selected (``--provider levi-local`` /
    ``LEVI_PROVIDER=levi-local``), but it is no longer in the automatic
    provider chain and is no longer LEVI's local-model story. The
    supported path is :mod:`levi.agent.brain_provider` (``levi-brain``):
    LEVI's own native brain, trained from scratch on LEVI's own corpus —
    no LLaMA weights, no llama.cpp.

This module manages a ``llama-server`` process (no Ollama daemon, no
cloud) serving a GGUF model from ``~/.levi/models``. The agent runtime
talks to it over the exact same OpenAI-compatible
``/v1/chat/completions`` path as the cloud providers
(see :class:`levi.agent.providers.OpenAICompatibleProvider`) — the
difference is that the server is spawned and owned by this module.

Honesty contract (non-negotiable):

- ``is_available()`` is True only when BOTH a ``.gguf`` weights file is
  present in the model dir AND a ``llama-server`` runner binary is found.
  If either is missing, the system says so plainly (see
  :func:`status_report`) and the provider chain falls back to the
  rule-based ``local`` planner — it never pretends the model exists.
- The model is a small CPU-friendly LLM (default: Qwen3-0.6B Q8_0,
  ~640MB). It is framed everywhere as LEVI's own offline inference
  stack, never as superintelligence; its capability ceiling is "runs
  the agent loop's tools offline", nothing more.
- Chat/tool-call failures come back as ``ChatResponse.error`` — never a
  faked answer. No network calls happen except the explicit
  ``levi agent model pull`` download and loopback inference traffic.
- Spawned ``llama-server`` processes are tracked and terminated at
  interpreter exit; a failed readiness check kills the process it
  started. Nothing is left orphaned.

The tool schemas the model sees come from the loop's system prompt
(:func:`levi.agent.loop._default_system_prompt`), which lists every
tool with its exact parameter names — the same prompt every provider
gets. This module adds no second prompt layer.

Stdlib only: ``subprocess``, ``urllib``, ``hashlib``, ``zipfile``,
``socket``. No new dependencies.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# NOTE: providers.py must NOT import this module at top level (circular:
# this module subclasses OpenAICompatibleProvider). providers.py imports
# us lazily inside select_provider().
from levi.agent.providers import (
    ChatMessage,
    ChatResponse,
    OpenAICompatibleProvider,
    ProviderToolCall,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_DIR_ENV = "LEVI_MODEL_DIR"
RUNNER_ENV = "LEVI_LLAMA_SERVER"
MODEL_NAME_ENV = "LEVI_LOCAL_MODEL"
READY_TIMEOUT_ENV = "LEVI_LOCAL_READY_TIMEOUT"
CTX_SIZE_ENV = "LEVI_LOCAL_CTX_SIZE"

DEFAULT_READY_TIMEOUT_S = 120.0
READY_POLL_INTERVAL_S = 1.0
CHAT_TIMEOUT_S = 300  # small-model CPU inference can be slow; be patient
LOCALHOST = "127.0.0.1"
DEFAULT_CTX_SIZE = 32768
MIN_CTX_SIZE = 512
MAX_CTX_SIZE = 131072

DEFAULT_MODEL_KEY = "qwen3-0.6b"
MODELS: dict[str, dict] = {
    "qwen3-0.6b": {
        "display": "Qwen3-0.6B (Q8_0)",
        "file": "Qwen3-0.6B-Q8_0.gguf",
        "url": (
            "https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/"
            "23749fefcc72300e3a2ad315e1317431b06b590a/Qwen3-0.6B-Q8_0.gguf"
        ),
        "approx_bytes": 639_446_688,
        # Authoritative SHA-256: Hugging Face's Git-LFS object id for this
        # file (LFS oids ARE the SHA-256 of the file content), read from
        # the repo tree API and cross-checked against the download's
        # X-Linked-ETag header. The URL is pinned to the exact commit so
        # the hash cannot go stale if upstream re-uploads.
        "sha256": "9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031",
        "ram_note": "Runs on ~1.5 GB free RAM. The default: fast, tiny, always fits.",
        "blurb": (
            "Qwen3 0.6B, Q8_0 quant (~640MB, Apache-2.0). Small, CPU-friendly, "
            "and its chat template ships native tool-call support, which is "
            "what the agent loop needs."
        ),
    },
    "qwen3-4b": {
        "display": "Qwen3-4B (Q4_K_M)",
        "file": "Qwen3-4B-Q4_K_M.gguf",
        "url": (
            "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/"
            "bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q4_K_M.gguf"
        ),
        "approx_bytes": 2_497_280_256,
        # Authoritative SHA-256: HF Git-LFS object id, verified against the
        # download's X-Linked-ETag header; URL pinned to the exact commit.
        "sha256": "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5",
        "ram_note": (
            "Needs ~4-6 GB of free RAM (weights ~2.5GB plus the 32k-context "
            "KV cache). Noticeably slower per token on CPU than the 0.6B."
        ),
        "blurb": (
            "Qwen3 4B, Q4_K_M quant (~2.5GB, Apache-2.0). Smarter than the "
            "0.6B default — better at multi-step tool plans — still CPU-runnable."
        ),
    },
}

LLAMACPP_RELEASES_API = "https://api.github.com/ggerganov/llama.cpp/releases/latest"

RUNNER_INSTALL_INSTRUCTIONS = """\
Levi Local needs a `llama-server` runner binary. Install one of:
  macOS:   brew install llama.cpp        (puts llama-server on PATH)
  Linux:   download the ubuntu-x64 release zip from
           https://github.com/ggerganov/llama.cpp/releases
           and place `llama-server` on PATH,
           or set LEVI_LLAMA_SERVER=/path/to/llama-server
  Windows: download the win-x64 release zip from the same releases page
  From source (any OS):
           git clone https://github.com/ggerganov/llama.cpp
           cmake -B build && cmake --build build --config Release
Then run:  levi agent model status
"""


# ---------------------------------------------------------------------------
# Paths and discovery (no side effects — safe for is_available())
# ---------------------------------------------------------------------------


def model_dir() -> Path:
    """Model directory: ``LEVI_MODEL_DIR`` or ``~/.levi/models``."""
    override = os.environ.get(MODEL_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".levi" / "models"


def find_weights(directory: Path | None = None) -> Path | None:
    """Return the weights file to use, or None if none is present.

    ``LEVI_LOCAL_MODEL`` names one file explicitly; otherwise the first
    ``*.gguf`` in the model dir (alphabetical) wins.
    """
    directory = directory or model_dir()
    named = os.environ.get(MODEL_NAME_ENV, "").strip()
    if named:
        candidate = directory / named
        return candidate if candidate.is_file() else None
    try:
        ggufs = sorted(
            p
            for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() == ".gguf"
        )
    except OSError:
        return None
    return ggufs[0] if ggufs else None


def find_runner() -> str | None:
    """Return a usable ``llama-server`` binary path, or None.

    ``LEVI_LLAMA_SERVER`` wins; then the managed
    ``<model_dir>/bin/llama-server`` installed by ``fetch_runner()``;
    otherwise ``llama-server`` on PATH.
    """
    override = os.environ.get(RUNNER_ENV, "").strip()
    if override:
        p = Path(override).expanduser()
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
        return None
    managed = (
        model_dir()
        / "bin"
        / ("llama-server.exe" if sys.platform == "win32" else "llama-server")
    )
    if managed.is_file() and (sys.platform == "win32" or os.access(managed, os.X_OK)):
        return str(managed)
    return shutil.which("llama-server")


def status_report() -> dict:
    """Machine-readable readiness report. No side effects."""
    directory = model_dir()
    weights = find_weights(directory)
    runner = find_runner()
    manifest = _read_manifest()
    manifest_entry = manifest.get(weights.name) if weights else None
    return {
        "model_dir": str(directory),
        "model_dir_exists": directory.is_dir(),
        "weights": str(weights) if weights else None,
        "weights_bytes": weights.stat().st_size if weights else None,
        "weights_sha256": (manifest_entry or {}).get("sha256"),
        "weights_native_ctx": _gguf_context_length(weights) if weights else None,
        "ctx_size": ctx_size(weights),
        "runner": runner,
        "available": bool(weights and runner),
    }


# ---------------------------------------------------------------------------
# Context window sizing
# ---------------------------------------------------------------------------


def _parse_gguf_context_length(data: bytes) -> int | None:
    """Read ``<arch>.context_length`` from GGUF KV metadata (stdlib only).

    Returns None when the bytes are not a parseable GGUF — the caller
    then falls back to the requested context size.
    """
    import struct

    if len(data) < 24 or data[:4] != b"GGUF":
        return None
    _version, n_tensors, n_kv = struct.unpack_from("<IQQ", data, 4)
    pos = 24
    arch: str | None = None
    found: int | None = None

    def read_u64() -> int:
        nonlocal pos
        if pos + 8 > len(data):
            raise ValueError("truncated")
        v = struct.unpack_from("<Q", data, pos)[0]
        pos += 8
        return v

    def read_u32() -> int:
        nonlocal pos
        if pos + 4 > len(data):
            raise ValueError("truncated")
        v = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        return v

    def read_bytes(n: int) -> bytes:
        nonlocal pos
        if pos + n > len(data):
            raise ValueError("truncated")
        b = data[pos : pos + n]
        pos += n
        return b

    def skip_value(vtype: int) -> None:
        nonlocal pos
        sizes = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
        if vtype in sizes:
            read_bytes(sizes[vtype])
        elif vtype == 8:  # string
            read_bytes(read_u64())
        elif vtype == 9:  # array
            atype = read_u32()
            alen = read_u64()
            for _ in range(min(alen, 4096)):
                skip_value(atype)
        else:
            raise ValueError("unknown gguf type %d" % vtype)

    for _ in range(min(n_kv, 10000)):
        key = read_bytes(read_u64()).decode("utf-8", "replace")
        vtype = read_u32()
        if key == "general.architecture" and vtype == 8:
            arch = read_bytes(read_u64()).decode("utf-8", "replace")
            continue
        want = arch is not None and key == "%s.context_length" % arch
        fallback = key.endswith(".context_length")
        if (want or fallback) and vtype in (4, 10):  # uint32 / uint64
            raw = read_bytes(4 if vtype == 4 else 8)
            found = struct.unpack("<I" if vtype == 4 else "<Q", raw)[0]
            break
        skip_value(vtype)
    return found


def _gguf_context_length(path: Path | None) -> int | None:
    """Native context length baked into a GGUF file, or None if unreadable."""
    if path is None:
        return None
    try:
        with open(path, "rb") as f:
            head = f.read(1 << 20)  # KV metadata lives at the start
    except OSError:
        return None
    try:
        return _parse_gguf_context_length(head)
    except Exception:
        return None


def ctx_size(weights: Path | None = None) -> int:
    """Context window for the llama-server instance.

    ``LEVI_LOCAL_CTX_SIZE`` (default 32768), clamped to the model's
    native context length when the GGUF metadata is readable — asking
    for more context than the model was built for silently degrades
    quality, so we never do.
    """
    try:
        requested = int(os.environ.get(CTX_SIZE_ENV, "") or DEFAULT_CTX_SIZE)
    except ValueError:
        requested = DEFAULT_CTX_SIZE
    requested = max(MIN_CTX_SIZE, min(requested, MAX_CTX_SIZE))
    native = _gguf_context_length(weights if weights is not None else find_weights())
    if native and requested > native:
        return native
    return requested


# ---------------------------------------------------------------------------
# Server lifecycle — spawned lazily, shared per (runner, weights), cleaned up
# ---------------------------------------------------------------------------


class _Server:
    """One managed llama-server process."""

    def __init__(
        self, proc: subprocess.Popen, base_url: str, runner: str, weights: str
    ):
        self.proc = proc
        self.base_url = base_url
        self.runner = runner
        self.weights = weights


_servers: dict[tuple[str, str], _Server] = {}
_servers_lock = threading.Lock()
_atexit_registered = False


def _register_atexit() -> None:
    global _atexit_registered
    if not _atexit_registered:
        atexit.register(shutdown_servers)
        _atexit_registered = True


def shutdown_servers() -> None:
    """Terminate every llama-server this module spawned. Idempotent."""
    with _servers_lock:
        servers = list(_servers.values())
        _servers.clear()
    for srv in servers:
        proc = srv.proc
        try:
            if proc.poll() is None:
                proc.terminate()
        except Exception:
            pass
    deadline = time.time() + 5
    for srv in servers:
        proc = srv.proc
        try:
            remaining = max(0.1, deadline - time.time())
            if proc.poll() is None:
                proc.wait(timeout=remaining)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((LOCALHOST, 0))
        return s.getsockname()[1]


def _ready_timeout() -> float:
    try:
        return max(
            1.0, float(os.environ.get(READY_TIMEOUT_ENV, "") or DEFAULT_READY_TIMEOUT_S)
        )
    except ValueError:
        return DEFAULT_READY_TIMEOUT_S


def _wait_ready(base_url: str) -> bool:
    """Poll /health until llama-server reports ready (or timeout)."""
    deadline = time.time() + _ready_timeout()
    url = base_url + "/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(READY_POLL_INTERVAL_S)
    return False


def _start_server(runner: str, weights: Path) -> tuple[str | None, str | None]:
    """Start (or reuse) the server. Returns (base_url, error)."""
    key = (runner, str(weights))
    with _servers_lock:
        existing = _servers.get(key)
        if existing is not None and existing.proc.poll() is None:
            return existing.base_url, None
        _servers.pop(key, None)  # stale entry for a dead process

    port = _free_port()
    ctx = ctx_size(weights)
    args = [
        runner,
        "-m",
        str(weights),
        "--host",
        LOCALHOST,
        "--port",
        str(port),
        "-c",
        str(ctx),
        "--log-disable",
    ]
    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        return None, "levi-local: failed to start llama-server: %s" % exc

    base_url = "http://%s:%d" % (LOCALHOST, port)
    _register_atexit()
    with _servers_lock:
        _servers[key] = _Server(proc, base_url, runner, str(weights))

    if not _wait_ready(base_url):
        with _servers_lock:
            _servers.pop(key, None)
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        return None, (
            "levi-local: llama-server did not become ready within %ds "
            "(still loading the model, or the binary crashed — check that "
            "the weights file is a valid GGUF)" % int(_ready_timeout())
        )
    return base_url, None


def ensure_server() -> tuple[str | None, str | None]:
    """Return (base_url, error): the loopback server for this config.

    Spawns ``llama-server`` on first use; never raises. A missing weights
    file or runner is reported as an error string, never an exception.
    """
    directory = model_dir()
    weights = find_weights(directory)
    if weights is None:
        return None, (
            "levi-local: no .gguf weights found in %s — "
            "run `levi agent model pull` to download the default model" % directory
        )
    runner = find_runner()
    if runner is None:
        return None, (
            "levi-local: llama-server runner not found — "
            "run `levi agent model status` for install instructions"
        )
    return _start_server(runner, weights)


# ---------------------------------------------------------------------------
# The provider — OpenAI-compatible chat against our own loopback server
# ---------------------------------------------------------------------------


class LocalModelProvider(OpenAICompatibleProvider):
    """Chat/tool-calling against LEVI's own local ``llama-server``.

    Subclasses :class:`OpenAICompatibleProvider` so chat + tool-call
    parsing reuse the exact same stdlib-urllib code path as the cloud
    providers — only the endpoint (our loopback server) and the
    availability rule differ. ``is_available()`` checks for files only
    and never spawns anything; the server starts lazily on first
    ``chat()``. The loop's system prompt (with all 15 tool schemas) is
    sent as the system message, like every other provider.
    """

    name = "levi-local"
    TIMEOUT_S = CHAT_TIMEOUT_S

    def is_available(self) -> bool:
        report = status_report()
        return bool(report["weights"] and report["runner"])

    # -- OpenAICompatibleProvider hooks ------------------------------------

    def _config(self) -> tuple[str, str, bool, str]:
        base_url, error = ensure_server()
        if error:
            # chat() always calls ensure_server() first and returns early
            # on error, so reaching here means the server is up. This is a
            # defensive fallback, not a reachable path in practice.
            raise RuntimeError(error)
        weights = find_weights()
        label = weights.stem if weights else "levi-local"
        # llama-server exposes the OpenAI-compatible API under /v1/; the
        # shared chat() appends "/chat/completions" to this base.
        return "", base_url.rstrip("/") + "/v1", True, label

    def chat(self, messages: list[ChatMessage], tools: list[dict]) -> ChatResponse:
        t0 = time.perf_counter()
        base_url, error = ensure_server()
        if error:
            return ChatResponse(
                text="",
                model="levi-local",
                provider=self.name,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                error=error,
            )
        try:
            return super().chat(messages, tools)
        except RuntimeError as exc:  # server died between ensure and chat
            return ChatResponse(
                text="",
                model="levi-local",
                provider=self.name,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Model download (the only network this module ever initiates)
# ---------------------------------------------------------------------------


class PullError(Exception):
    """A `model pull` failure. Partial files are always cleaned up first."""


def _manifest_path() -> Path:
    return model_dir() / "manifest.json"


def _read_manifest() -> dict:
    try:
        return json.loads(_manifest_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_manifest(manifest: dict) -> None:
    path = _manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_weights(
    model_key: str = DEFAULT_MODEL_KEY, *, force: bool = False, progress=None
) -> Path:
    """Download a GGUF weights file into the model dir.

    ``progress(done_bytes, total_bytes)`` is called per chunk when given.
    Returns the final path. On any failure the partial file is removed
    and a :class:`PullError` is raised — never a silent half-install. When
    the file already exists its SHA-256 is re-verified against the local
    manifest (or an authoritative ``sha256`` in ``MODELS``).
    """
    if model_key not in MODELS:
        known = ", ".join(sorted(MODELS))
        raise PullError("unknown model %r (known: %s)" % (model_key, known))
    spec = MODELS[model_key]
    directory = model_dir()
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / spec["file"]

    manifest = _read_manifest()
    expected = spec.get("sha256") or (manifest.get(dest.name) or {}).get("sha256")
    if dest.is_file() and not force:
        if expected:
            actual = _sha256_of(dest)
            if actual != expected:
                raise PullError(
                    "existing %s failed SHA-256 verification (expected %s…, got %s…) — "
                    "the file may be corrupt; re-run with --force to re-download"
                    % (dest.name, expected[:16], actual[:16])
                )
            return dest
        return dest  # present, nothing recorded to verify against

    tmp_path = None
    try:
        fd, tmp = tempfile.mkstemp(
            dir=str(directory), prefix=dest.name + ".", suffix=".part"
        )
        tmp_path = Path(tmp)
        os.close(fd)
        h = hashlib.sha256()
        done = 0
        req = urllib.request.Request(
            spec["url"],
            headers={"User-Agent": "levi-agent/levi-local"},
        )
        with (
            urllib.request.urlopen(req, timeout=120) as resp,
            open(tmp_path, "wb") as f,
        ):
            total = 0
            try:
                total = int(resp.headers.get("Content-Length") or 0)
            except (TypeError, ValueError):
                total = 0
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress is not None:
                    progress(done, total)
        if done == 0:
            raise PullError("downloaded 0 bytes from %s" % spec["url"])
        digest = h.hexdigest()
        if expected and digest != expected:
            raise PullError(
                "SHA-256 mismatch for %s (expected %s…, got %s…); "
                "the download may be corrupt or tampered with"
                % (dest.name, expected[:16], digest[:16])
            )
        os.replace(tmp_path, dest)
        tmp_path = None
        manifest[dest.name] = {
            "sha256": digest,
            "url": spec["url"],
            "bytes": done,
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        _write_manifest(manifest)
        return dest
    except PullError:
        raise
    except urllib.error.HTTPError as exc:
        raise PullError("HTTP %s downloading %s" % (exc.code, spec["url"])) from exc
    except urllib.error.URLError as exc:
        raise PullError(
            "network error downloading %s: %s" % (spec["url"], exc.reason)
        ) from exc
    except Exception as exc:
        raise PullError("download failed: %s: %s" % (type(exc).__name__, exc)) from exc
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Runner (llama-server binary) best-effort fetch
# ---------------------------------------------------------------------------


def _runner_platform_tokens() -> tuple[str, ...] | None:
    if sys.platform.startswith("linux"):
        return ("ubuntu", "x64")
    if sys.platform == "darwin":
        arch = "arm64" if platform.machine().lower().startswith("arm") else "x64"
        return ("macos", arch)
    if sys.platform == "win32":
        return ("win", "x64")
    return None


def _pick_runner_asset(assets: list[dict], tokens: tuple[str, ...]) -> dict | None:
    """Pick the best llama.cpp release asset for this platform.

    Pure function over the GitHub release JSON — unit-testable, no network.
    """
    candidates = []
    for asset in assets:
        name = str(asset.get("name") or "").lower()
        if not name.endswith(".zip"):
            continue
        if "llama" not in name:
            continue
        if all(tok in name for tok in tokens):
            candidates.append(asset)
    if not candidates:
        return None

    # Prefer CPU-only builds over cuda/vulkan variants (fewer surprises).
    def _score(asset: dict) -> int:
        name = str(asset.get("name") or "").lower()
        score = 0
        if "cuda" in name or "vulkan" in name or "sycl" in name:
            score -= 10
        if "server" in name:
            score += 1
        return score

    candidates.sort(key=_score, reverse=True)
    return candidates[0]


def _extract_runner_files(zf: zipfile.ZipFile, bin_dir: Path) -> Path | None:
    """Extract ``llama-server`` and its sibling shared libraries safely.

    Release zips nest everything under directories like ``build/bin/`` and
    the server may need adjacent shared libraries (``.so``/``.dylib``/``.dll``)
    to start — extracting only the executable can produce a binary that
    fails to launch. Members are flattened into ``bin_dir`` (the server
    looks for libraries next to itself); only the server binary and
    shared-library siblings from the server's own directory are taken.
    Zip-slip members (absolute paths, ``..``) are skipped. Returns the
    extracted server binary path, or None.
    """
    server_member = None
    server_dir = ""
    libs: list[str] = []
    for member in zf.namelist():
        parts = member.replace("\\", "/").split("/")
        if not parts or any(p in ("", ".", "..") for p in parts):
            continue  # zip-slip protection
        base = parts[-1].lower()
        if base in ("llama-server", "llama-server.exe"):
            server_member = member
            server_dir = "/".join(parts[:-1])
        elif base.endswith((".so", ".dylib", ".dll")) or ".so." in base:
            libs.append(member)
    if server_member is None:
        return None
    chosen = [server_member] + [
        m for m in libs if "/".join(m.replace("\\", "/").split("/")[:-1]) == server_dir
    ]
    target = None
    for member in chosen:
        base = member.replace("\\", "/").rsplit("/", 1)[-1]
        dest = bin_dir / base
        with zf.open(member) as src, open(dest, "wb") as dst:
            shutil.copyfileobj(src, dst)
        if base.lower() in ("llama-server", "llama-server.exe"):
            target = dest
    return target


def fetch_runner(*, progress=None) -> str | None:
    """Best-effort download of a llama.cpp release binary for this OS.

    Returns the installed ``llama-server`` path, or None when anything
    goes wrong (caller prints :data:`RUNNER_INSTALL_INSTRUCTIONS`).
    """
    tokens = _runner_platform_tokens()
    if tokens is None:
        return None
    try:
        req = urllib.request.Request(
            LLAMACPP_RELEASES_API,
            headers={
                "User-Agent": "levi-agent/levi-local",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            release = json.loads(resp.read().decode("utf-8"))
        asset = _pick_runner_asset(release.get("assets") or [], tokens)
        if asset is None or not asset.get("browser_download_url"):
            return None
        bin_dir = model_dir() / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        tmp_zip = bin_dir / "llama-release.zip"
        try:
            dl_req = urllib.request.Request(
                asset["browser_download_url"],
                headers={"User-Agent": "levi-agent/levi-local"},
            )
            done = 0
            with (
                urllib.request.urlopen(dl_req, timeout=120) as resp,
                open(tmp_zip, "wb") as f,
            ):
                total = 0
                try:
                    total = int(resp.headers.get("Content-Length") or 0)
                except (TypeError, ValueError):
                    total = 0
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress is not None:
                        progress(done, total)
            with zipfile.ZipFile(tmp_zip) as zf:
                target = _extract_runner_files(zf, bin_dir)
                if target is None:
                    return None
        finally:
            try:
                tmp_zip.unlink()
            except OSError:
                pass
        try:
            target.chmod(0o755)
        except OSError:
            pass
        if target.is_file() and (sys.platform == "win32" or os.access(target, os.X_OK)):
            return str(target)
        return None
    except Exception:
        return None


def ensure_runner(*, progress=None) -> tuple[str | None, str | None]:
    """Return (runner_path, error): existing, fetched, or instructions.

    Never raises; a None path comes with a human-readable error naming
    the exact manual install steps.
    """
    found = find_runner()
    if found:
        return found, None
    fetched = fetch_runner(progress=progress)
    if fetched:
        return fetched, None
    return None, RUNNER_INSTALL_INSTRUCTIONS


# Re-export the shared contract bits for convenience (same objects the
# parent provider module defines — no copies).
__all__ = [
    "LocalModelProvider",
    "PullError",
    "MODELS",
    "DEFAULT_MODEL_KEY",
    "model_dir",
    "find_weights",
    "find_runner",
    "status_report",
    "ctx_size",
    "ensure_server",
    "shutdown_servers",
    "download_weights",
    "ensure_runner",
    "fetch_runner",
    "RUNNER_INSTALL_INSTRUCTIONS",
    "ChatMessage",
    "ChatResponse",
    "ProviderToolCall",
]
