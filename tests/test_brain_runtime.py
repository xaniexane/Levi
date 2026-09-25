"""Tests for core/levi/brain/runtime.py — LEVI's torch-free model runner.

Hermetic: no network, no daemons, no user HOME writes. The observation
log is redirected per-test with LEVI_OBSERVATIONS_FILE. The torch
cross-check skips honestly when torch is not installed.
"""

import hashlib
import json
import os
import stat
from pathlib import Path

import pytest

from levi.brain import runtime
from levi.brain.runtime import BrainError

WEIGHTS_DIR = (
    Path(__file__).resolve().parent.parent / "core" / "levi" / "brain" / "weights"
)
PORTABLE_DIR = WEIGHTS_DIR / "tiny-gpt-portable"
SOURCE_PT = WEIGHTS_DIR / "tiny-gpt.pt"


@pytest.fixture(autouse=True)
def _obs_sandbox(tmp_path, monkeypatch):
    """Point the observation log at a temp file; never touch ~/.levi."""
    monkeypatch.setenv("LEVI_OBSERVATIONS_FILE", str(tmp_path / "obs.jsonl"))
    yield


@pytest.fixture()
def _clean_registry(monkeypatch):
    """Give registry-mutation tests an isolated model registry."""
    monkeypatch.setattr(runtime, "_MODELS", dict(runtime._MODELS))
    monkeypatch.setattr(runtime, "_ARCHITECTURES", dict(runtime._ARCHITECTURES))
    monkeypatch.setattr(runtime, "_LOADED", dict(runtime._LOADED))
    yield


# ---------------------------------------------------------------- registries


def test_builtin_model_registered():
    spec = runtime.get_model("levi-native")
    assert spec.model_id == "levi-native"
    assert spec.arch == "char-gpt"
    assert spec.origin == "levi"
    assert spec.reference is None
    assert spec.model_label() == "LEVI native model"


def test_builtin_arch_registered():
    arch = runtime.get_architecture("char-gpt")
    assert arch.arch_id == "char-gpt"
    assert "char" in arch.tokenizer.lower()
    assert any(a["arch_id"] == "char-gpt" for a in runtime.list_architectures())


def test_unknown_model_raises_honestly():
    with pytest.raises(BrainError, match="unknown model"):
        runtime.get_model("does-not-exist")
    with pytest.raises(BrainError, match="unknown model"):
        runtime.load_model("does-not-exist")


def test_unknown_arch_rejected_at_registration(_clean_registry):
    # Unknown architectures are rejected honestly at registration —
    # never silently substituted later.
    with pytest.raises(BrainError, match="unknown architecture"):
        runtime.register_model(
            runtime.ModelSpec(model_id="ghost-model", arch="no-such-arch")
        )


def test_model_register_get_list_unregister(_clean_registry):
    spec = runtime.ModelSpec(model_id="test-model", arch="char-gpt")
    runtime.register_model(spec)
    assert runtime.get_model("test-model").model_id == "test-model"
    ids = [m["model_id"] for m in runtime.list_models()]
    assert "test-model" in ids and "levi-native" in ids
    runtime.unregister_model("test-model")
    with pytest.raises(BrainError, match="unknown model"):
        runtime.get_model("test-model")


def test_duplicate_model_rejected(_clean_registry):
    with pytest.raises(BrainError, match="already registered"):
        runtime.register_model(
            runtime.ModelSpec(model_id="levi-native", arch="char-gpt")
        )


def test_duplicate_arch_rejected(_clean_registry):
    with pytest.raises(BrainError, match="already registered"):
        runtime.register_architecture(
            runtime.Architecture(
                arch_id="char-gpt",
                description="dupe",
                load=lambda spec: None,
                weights_format="x",
                tokenizer="y",
            )
        )


def test_bad_model_id_rejected(_clean_registry):
    with pytest.raises(BrainError, match="invalid"):
        runtime.register_model(
            runtime.ModelSpec(model_id="Bad Model!", arch="char-gpt")
        )


def test_qwen_class_arch_reserved_not_implemented(_clean_registry):
    with pytest.raises(BrainError, match="unknown architecture"):
        runtime.get_architecture("qwen-class")


# ---------------------------------------------------------------- identity law


def test_reference_model_requires_reference_id(_clean_registry):
    with pytest.raises(BrainError, match="reference"):
        runtime.register_model(
            runtime.ModelSpec(model_id="qwen3-4b", arch="char-gpt", origin="reference")
        )


def test_reference_model_labeled_not_levi(_clean_registry):
    spec = runtime.ModelSpec(
        model_id="qwen3-4b",
        arch="char-gpt",
        origin="reference",
        reference="qwen3-4b",
    )
    runtime.register_model(spec)
    label = spec.model_label()
    assert "not LEVI" in label
    assert "qwen3-4b" in label
    listed = {m["model_id"]: m for m in runtime.list_models()}
    assert "not LEVI" in listed["qwen3-4b"]["label"]


def test_levi_model_cannot_claim_reference_origin_as_own(_clean_registry):
    """A reference model is never labeled as LEVI's own reasoning source."""
    spec = runtime.get_model("levi-native")
    assert spec.origin == "levi"
    assert "not LEVI" not in spec.model_label()


# ---------------------------------------------------------------- portable format


def test_portable_available():
    assert runtime.portable_available() is True
    assert runtime.portable_available("/no/such/dir") is False


def test_manifest_and_blobs_validate():
    manifest, blobs = runtime.load_portable_tensors(str(PORTABLE_DIR))
    assert manifest["format"] == "levi-brain-portable/1"
    assert manifest["source"]["sha256"] == runtime.EXPECTED_SOURCE_SHA256
    assert len(manifest["chars"]) == 162
    entries = {e["name"]: e for e in manifest["tensors"]}
    # every loaded blob: right length, right sha (the 4 derived causal
    # masks are in the manifest but intentionally not loaded)
    assert len(blobs) == 45
    for name, blob in blobs.items():
        meta = entries[name]
        assert len(blob) == meta["params"] * 4, name
        assert hashlib.sha256(blob).hexdigest() == meta["sha256"], name


def test_source_checkpoint_untouched():
    assert SOURCE_PT.is_file()
    assert (
        hashlib.sha256(SOURCE_PT.read_bytes()).hexdigest()
        == runtime.EXPECTED_SOURCE_SHA256
    )


def test_missing_portable_dir_raises_honestly():
    with pytest.raises(BrainError, match="no torch-free brain export found"):
        runtime.load_portable_tensors("/no/such/portable/dir")


def test_corrupt_manifest_version_rejected(tmp_path):
    bad = tmp_path / "bad-portable"
    bad.mkdir()
    (bad / "manifest.json").write_text(json.dumps({"format": "nope/0"}))
    with pytest.raises(BrainError, match="portable export format"):
        runtime.load_portable_tensors(str(bad))


def _portable_with_tampered_blob(tmp_path, blob_file, tamper_bytes):
    """Build a scratch portable dir: symlinks to the real export, except
    ``blob_file`` which is a real (tampered) copy — the real export is
    never written."""
    dest = tmp_path / "tampered"
    dest.mkdir()
    manifest = json.loads((PORTABLE_DIR / "manifest.json").read_text())
    for entry in manifest["tensors"]:
        name = entry["file"]
        target = dest / name
        if name == blob_file:
            target.write_bytes(tamper_bytes(PORTABLE_DIR / name))
        else:
            target.symlink_to(PORTABLE_DIR / name)
    (dest / "manifest.json").write_text(json.dumps(manifest))
    return dest


def test_corrupt_blob_length_rejected(tmp_path):
    dest = _portable_with_tampered_blob(
        tmp_path, "ln_f.bias.f32", lambda real: b"\x00" * 8
    )
    with pytest.raises(BrainError, match="size"):
        runtime.load_portable_tensors(str(dest))


def test_corrupt_blob_sha_rejected(tmp_path):
    def flip_first_byte(real):
        data = bytearray(real.read_bytes())
        data[0] ^= 0xFF
        return bytes(data)

    dest = _portable_with_tampered_blob(tmp_path, "ln_f.bias.f32", flip_first_byte)
    with pytest.raises(BrainError, match="sha256 mismatch"):
        runtime.load_portable_tensors(str(dest))


# ---------------------------------------------------------------- generation


def _run_kwargs(**over):
    kw = dict(
        model_id="levi-native",
        prompt="the cat sat on the",
        max_new_chars=12,
        temperature=0,
        seed=7,
        record=False,
    )
    kw.update(over)
    return kw


def test_run_returns_labeled_continuation():
    result = runtime.run(**_run_kwargs())
    assert result["label"] == "raw brain continuation — not reasoning"
    assert result["model_id"] == "levi-native"
    assert result["model_label"] == "LEVI native model"
    assert result["arch"] == "char-gpt"
    assert len(result["continuation"]) == 12
    assert result["recorded"] is False


def test_determinism_same_seed_same_output():
    a = runtime.run(**_run_kwargs())["continuation"]
    b = runtime.run(**_run_kwargs())["continuation"]
    assert a == b


def test_temperature_zero_is_argmax():
    handle = runtime.load_model("levi-native")
    ids, _ = handle.encode("levi learns")
    logits = handle.logits_for(ids)
    best = max(range(len(logits)), key=logits.__getitem__)
    cont = runtime.run(**_run_kwargs(prompt="levi learns", max_new_chars=1))[
        "continuation"
    ]
    assert cont == handle.chars[best]


def test_empty_prompt_rejected():
    with pytest.raises(BrainError, match="empty prompt"):
        runtime.run(**_run_kwargs(prompt="   "))


def test_numpy_backend_selected_by_default():
    if runtime._numpy_module() is None:
        pytest.skip("numpy not installed here")
    assert runtime.backend_available() == "numpy"
    handle = runtime.load_model("levi-native")
    assert handle.backend == "numpy"


def test_stdlib_backend_forced():
    result = runtime.run(**_run_kwargs(prompt="ab", max_new_chars=2, backend="stdlib"))
    assert result["backend"] == "stdlib"
    assert len(result["continuation"]) == 2


def test_stdlib_matches_numpy_logits():
    if runtime._numpy_module() is None:
        pytest.skip("numpy not installed here")
    handle_np = runtime.load_runtime_brain(backend="numpy")
    handle_sl = runtime.load_runtime_brain(backend="stdlib")
    ids, _ = handle_np.encode("the course")
    a = handle_np.logits_for(ids)
    b = handle_sl.logits_for(ids)
    assert max(abs(x - y) for x, y in zip(a, b, strict=True)) < 1e-4


def test_socket_blocked_run_still_succeeds(monkeypatch):
    import socket as _socket

    real_socket = _socket.socket

    def _blocked(*a, **k):
        raise OSError("network disabled in test")

    monkeypatch.setattr(_socket, "socket", _blocked)
    try:
        result = runtime.run(**_run_kwargs())
    finally:
        monkeypatch.setattr(_socket, "socket", real_socket)
    assert len(result["continuation"]) == 12


def test_no_listener_on_import_or_run(monkeypatch):
    """Importing the module and running a prompt must not open listeners."""
    import socket as _socket

    bound = []
    real_socket = _socket.socket

    class _Spy(real_socket):
        def bind(self, addr):
            bound.append(addr)
            return super().bind(addr)

    monkeypatch.setattr(_socket, "socket", _Spy)
    runtime.run(**_run_kwargs())
    assert bound == []


def test_torch_cross_check():
    torch = pytest.importorskip("torch", reason="torch not installed")
    from levi.brain.inference import load_brain

    ref = load_brain()
    handle = runtime.load_runtime_brain(backend="numpy")
    for prompt in ("the cat sat on the", "levi is a synthetic"):
        expected = ref.generate(prompt, max_new_chars=20, temperature=0, seed=7)[
            "continuation"
        ]
        got = handle.generate(prompt, max_new_chars=20, temperature=0, seed=7)[
            "continuation"
        ]
        assert got == expected, prompt
    ids, _ = ref.encode("the course teaches")
    with torch.no_grad():
        t_logits = ref._model(torch.tensor([ids]))[0, -1].tolist()
    my_logits = handle.logits_for(ids)
    assert max(abs(a - b) for a, b in zip(t_logits, my_logits, strict=True)) < 1e-4


# ---------------------------------------------------------------- observation store


def _read_obs(**kw):
    return runtime.read_observations(**kw)


def test_record_write_read_round_trip():
    result = runtime.run(**_run_kwargs(record=True))
    report = _read_obs()
    assert report["skipped"] == 0
    assert len(report["records"]) == 1
    rec = report["records"][0]
    assert rec["schema"] == "levi-observation/1"
    assert rec["model_id"] == "levi-native"
    assert rec["arch"] == "char-gpt"
    assert rec["origin"] == "levi"
    assert rec["model_label"] == "LEVI native model"
    assert rec["prompt"] == "the cat sat on the"
    assert rec["prompt_truncated"] is False
    assert rec["prompt_sha256"] == hashlib.sha256(b"the cat sat on the").hexdigest()
    assert rec["output"] == result["continuation"]
    assert rec["output_chars"] == len(result["continuation"])
    assert rec["sampling"]["temperature"] == 0
    assert rec["sampling"]["seed"] == 7
    assert rec["receipt"]["ok"] is True
    assert rec["timing"]["seconds"] >= 0
    assert rec["timing"]["backend"] in ("numpy", "stdlib")
    assert rec["label"] == "recorded model output — not LEVI reasoning"
    assert "ts" in rec


def test_disabled_flag_writes_nothing(tmp_path):
    runtime.run(**_run_kwargs(record=False))
    assert not Path(os.environ["LEVI_OBSERVATIONS_FILE"]).exists()
    assert _read_obs()["records"] == []


def test_failed_run_records_honest_receipt():
    with pytest.raises(BrainError):
        runtime.run(**_run_kwargs(prompt="   ", record=True))
    rec = _read_obs()["records"][0]
    assert rec["receipt"]["ok"] is False
    assert "empty prompt" in rec["receipt"]["error"]
    assert rec["output"] == ""


def test_corrupt_line_skipped_honestly():
    path = Path(os.environ["LEVI_OBSERVATIONS_FILE"])
    runtime.run(**_run_kwargs(record=True))
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("this is not json\n")
        fh.write(json.dumps({"schema": "levi-observation/9"}) + "\n")
        fh.write(
            json.dumps({"schema": "levi-observation/1", "incomplete": True}) + "\n"
        )
    runtime.run(**_run_kwargs(prompt="another prompt", record=True))
    report = _read_obs()
    assert report["skipped"] == 3
    assert len(report["records"]) == 2
    assert report["records"][1]["prompt"] == "another prompt"


def test_observation_file_owner_only(tmp_path):
    if os.name != "posix":
        pytest.skip("POSIX permission check")
    runtime.run(**_run_kwargs(record=True))
    path = Path(os.environ["LEVI_OBSERVATIONS_FILE"])
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600, oct(mode)
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_read_filter_by_model_and_limit():
    runtime.run(**_run_kwargs(record=True))
    runtime.run(**_run_kwargs(prompt="second", record=True))
    assert len(_read_obs(model_id="levi-native")["records"]) == 2
    assert len(_read_obs(model_id="nope")["records"]) == 0
    assert len(_read_obs(limit=1)["records"]) == 1
    assert _read_obs(limit=1)["records"][0]["prompt"] == "second"


def test_long_prompt_truncated_but_hashed_whole():
    long_prompt = "x" * (runtime.OBS_MAX_PROMPT_CHARS + 100)
    runtime.run(**_run_kwargs(prompt=long_prompt, max_new_chars=1, record=True))
    rec = _read_obs()["records"][0]
    assert rec["prompt_truncated"] is True
    assert len(rec["prompt"]) == runtime.OBS_MAX_PROMPT_CHARS
    assert rec["prompt_sha256"] == hashlib.sha256(long_prompt.encode()).hexdigest()


# ---------------------------------------------------------------- loopback server


def test_serve_refuses_non_loopback():
    with pytest.raises(BrainError, match="loopback"):
        runtime.serve_loopback(host="0.0.0.0")
    with pytest.raises(BrainError, match="loopback"):
        runtime.serve_loopback(host="example.com")


def test_serve_loopback_binds_loopback_only():
    server = runtime.serve_loopback(model_id="levi-native", host="127.0.0.1", port=0)
    try:
        host, port = server.server_address[:2]
        assert host == "127.0.0.1"
        assert port > 0
    finally:
        server.server_close()


def test_serve_and_run_round_trip():
    import http.client

    server = runtime.serve_loopback(model_id="levi-native", host="127.0.0.1", port=0)
    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        conn = http.client.HTTPConnection(host, port, timeout=120)
        conn.request("GET", "/models")
        resp = conn.getresponse()
        assert resp.status == 200
        models = json.loads(resp.read())["models"]
        assert any(m["model_id"] == "levi-native" for m in models)

        body = json.dumps(
            {
                "model_id": "levi-native",
                "prompt": "the cat",
                "max_new_chars": 4,
                "temperature": 0,
                "seed": 7,
                "record": True,
            }
        )
        conn.request(
            "POST", "/run", body=body, headers={"Content-Type": "application/json"}
        )
        resp = conn.getresponse()
        assert resp.status == 200
        result = json.loads(resp.read())
        assert result["label"] == "raw brain continuation — not reasoning"
        assert len(result["continuation"]) == 4
        # the served run recorded an observation
        assert len(_read_obs()["records"]) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)
