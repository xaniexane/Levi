"""Hermetic tests for LEVI Lab (levi.lab).

No network (the probe test runs a loopback stub server), no model, no
writes outside tmp_path. Fixture-schema tests read the committed fixtures
in ``core/levi/lab/fixtures/``.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from levi.lab.footprint import (
    footprint,
    format_footprint,
    kv_cache_bytes,
    parse_ctx,
    parse_params,
    weight_bytes,
)
from levi.lab import live
from levi.lab import models as lab_models
from levi.lab import scenarios as lab_scen


# ---------------------------------------------------------------------------
# footprint math — hand-computed values
# ---------------------------------------------------------------------------


def test_parse_params():
    assert parse_params("30B") == 30_000_000_000
    assert parse_params("0.6B") == 600_000_000
    assert parse_params("600M") == 600_000_000
    assert parse_params("3.3M") == 3_300_000
    assert parse_params("1.2T") == 1_200_000_000_000
    assert parse_params("500K") == 500_000
    assert parse_params(1000) == 1000
    with pytest.raises(ValueError):
        parse_params("lots")


def test_parse_ctx():
    assert parse_ctx("32k") == 32_768
    assert parse_ctx("128K") == 131_072
    assert parse_ctx("4096") == 4096
    assert parse_ctx(8192) == 8192
    with pytest.raises(ValueError):
        parse_ctx("wide")


def test_weight_bytes():
    # 1B params @ fp16 = 2 bytes/param = 2e9 bytes, by hand.
    assert weight_bytes(1_000_000_000, "fp16") == 2_000_000_000
    assert weight_bytes(1_000_000_000, "int4") == 500_000_000
    assert weight_bytes(1_000_000_000, "fp32") == 4_000_000_000
    assert weight_bytes(1_000_000_000, "int8") == 1_000_000_000
    with pytest.raises(ValueError):
        weight_bytes(1_000_000_000, "q9_zz")


def test_kv_cache_bytes():
    # 2 * 32 layers * 4096 hidden * 4096 ctx * 2 bytes = 2,147,483,648, by hand.
    assert kv_cache_bytes(32, 4096, 4096, 2.0) == 2_147_483_648
    with pytest.raises(ValueError):
        kv_cache_bytes(0, 4096, 4096)


def test_footprint_explicit_arch():
    out = footprint(
        "1B",
        quant="fp16",
        ctx="4k",
        layers=32,
        hidden_dim=4096,
        headroom_gb=1.0,
        overhead=1.0,
    )
    assert out["arch_estimated"] is False
    assert out["weights_gb"] == 2.0
    # 2.147483648 GB rounded to 3 decimals.
    assert out["kv_cache_gb"] == 2.147
    # (2.0 + 2.147483648 + 1.0) * 1.0 = 5.147483648 -> 5.147
    assert out["total_gb"] == 5.147


def test_footprint_estimated_arch():
    out = footprint("0.6B", quant="int8", ctx="32k")
    assert out["arch_estimated"] is True
    assert (out["layers"], out["hidden_dim"]) == (28, 1024)
    assert out["weights_gb"] == 0.6
    # KV = 2*28*1024*32768*2 = 3,758,096,384 bytes -> 3.758096384 GB -> 3.758
    assert out["kv_cache_gb"] == 3.758
    # (0.6 + 3.758096384 + 1.0) * 1.15 = 6.1618108416 -> 6.162
    assert out["total_gb"] == 6.162


def test_footprint_unknown_size_needs_arch():
    with pytest.raises(ValueError):
        footprint("123B", quant="int4", ctx="32k")


def test_format_footprint():
    out = footprint("4B", quant="int4", ctx="32k", layers=36, hidden_dim=2560)
    text = format_footprint(out)
    assert "total" in text and "estimate" in text


# ---------------------------------------------------------------------------
# scenario registry integrity
# ---------------------------------------------------------------------------


def test_scenario_registry():
    scs = lab_scen.list_scenarios()
    assert {s.id for s in scs} == {
        "resilient-file",
        "red-green",
        "research-brief",
        "effort-ab",
    }
    for s in scs:
        assert s.title and s.description and s.phases and s.honest_notes
    assert lab_scen.get_scenario("nope") is None


# ---------------------------------------------------------------------------
# fixture schema (committed fixtures)
# ---------------------------------------------------------------------------


def _fixtures():
    d = lab_scen.FIXTURE_DIR
    files = sorted(d.glob("*.json"))
    assert files, "lab fixtures missing — run the capture step"
    return files


def test_fixture_schema():
    for path in _fixtures():
        fx = json.loads(path.read_text(encoding="utf-8"))
        for key in ("scenario", "title", "provenance", "phases", "notes"):
            assert key in fx, f"{path.name}: missing {key}"
        prov = fx["provenance"]
        assert prov["provider"] == "local"
        assert prov["captured_utc"] and prov["levi_version"]
        assert isinstance(prov["live"], bool)
        assert fx["phases"], f"{path.name}: no phases"
        for ph in fx["phases"]:
            assert ph["name"]
            t = ph["transcript"]
            for key in ("task", "steps", "final", "provider_name"):
                assert key in t, f"{path.name}/{ph['name']}: missing {key}"
            assert t["steps"], f"{path.name}/{ph['name']}: no steps"
            for step in t["steps"]:
                assert "tool_calls" in step and "results" in step


def test_fixture_scenarios_match_registry():
    names = {p.stem for p in _fixtures()}
    assert names == {s.id for s in lab_scen.list_scenarios()}


def test_playback_renders():
    text = lab_scen.playback("resilient-file")
    assert "phase: fail" in text and "phase: recover" in text
    assert "honest notes" in text
    assert "unknown scenario" in lab_scen.playback("nope")


# ---------------------------------------------------------------------------
# model cards
# ---------------------------------------------------------------------------


def test_model_cards():
    card = lab_models.get_card("qwen3-0.6b")
    assert card["params"] == 600_000_000
    assert card["provider"] == "levi-local"
    assert lab_models.get_card("QWEN3-4B")["params"] == 4_000_000_000
    tiny = lab_models.get_card("tiny-gpt")
    assert tiny["params"] == 3_271_168
    assert tiny["status"] == "experimental"
    assert lab_models.get_card("gpt-99") is None


# ---------------------------------------------------------------------------
# live probe/chat against a loopback stub (no real network dependency)
# ---------------------------------------------------------------------------


class _StubHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        assert self.path == "/v1/models"
        body = json.dumps({"data": [{"id": "stub-model"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        assert self.path == "/v1/chat/completions"
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        body = json.dumps(
            {"choices": [{"message": {"content": "hello stub"}}]}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture()
def stub_endpoint():
    server = HTTPServer(("127.0.0.1", 0), _StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_probe_and_chat_against_stub(stub_endpoint):
    res = live.probe(stub_endpoint)
    assert res["ok"] is True
    assert res["models"] == ["stub-model"]
    out = live.chat(stub_endpoint, "stub-model", [{"role": "user", "content": "hi"}])
    assert out["ok"] is True
    assert out["text"] == "hello stub"


def test_probe_unreachable():
    # Bind then close: guaranteed connection-refused on loopback.
    tmp = HTTPServer(("127.0.0.1", 0), _StubHandler)
    port = tmp.server_address[1]
    tmp.server_close()
    res = live.probe(f"http://127.0.0.1:{port}", timeout=2.0)
    assert res["ok"] is False
    assert "unreachable" in res["error"]


def test_resolve_endpoint():
    assert live.resolve_endpoint("http://x:8080/") == "http://x:8080"
    assert live.resolve_endpoint(None) is None
    import os

    os.environ["LEVI_LAB_ENDPOINT"] = "http://env:1234"
    try:
        assert live.resolve_endpoint() == "http://env:1234"
        assert live.resolve_endpoint("http://arg:1") == "http://arg:1"
    finally:
        del os.environ["LEVI_LAB_ENDPOINT"]


# ---------------------------------------------------------------------------
# agent tools (read-only)
# ---------------------------------------------------------------------------


def test_lab_agent_tools_registered():
    from levi.agent.tools import build_default_registry

    reg = build_default_registry(
        workspace_root="/tmp/levi-lab-test-ws",
        memory_dir="/tmp/levi-lab-test-mem",
        skills_dir="/tmp/levi-lab-test-sk",
        consent=False,
    )
    names = {t.name for t in reg.list()}
    assert "lab_scenario" in names
    assert "lab_footprint" in names


def test_lab_footprint_tool_read_only(tmp_path):
    from levi.agent.tools import build_default_registry

    reg = build_default_registry(
        workspace_root=str(tmp_path / "ws"),
        memory_dir=str(tmp_path / "mem"),
        skills_dir=str(tmp_path / "sk"),
        consent=False,
    )
    from levi.agent.tools import ExecContext

    res = reg.execute(
        "lab_footprint",
        {"params": "1B", "quant": "fp16", "ctx": "4k"},
        ExecContext(),
    )
    assert res.ok
    assert "total" in res.output


def test_lab_scenario_tool_playback(tmp_path):
    from levi.agent.tools import build_default_registry

    reg = build_default_registry(
        workspace_root=str(tmp_path / "ws"),
        memory_dir=str(tmp_path / "mem"),
        skills_dir=str(tmp_path / "sk"),
        consent=False,
    )
    from levi.agent.tools import ExecContext

    ctx = ExecContext()
    res = reg.execute("lab_scenario", {"scenario": "effort-ab"}, ctx)
    assert res.ok
    assert "phase: low-effort" in res.output
    res2 = reg.execute("lab_scenario", {}, ctx)
    assert res2.ok and "resilient-file" in res2.output
