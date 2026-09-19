"""Tests for the Omega resurrection: blueprint (Echo), generators (Alpha),
nexus (Nexus) — all LEVI-native, stdlib-only."""

import pytest

from levi.revival.omega import blueprint as bp
from levi.revival.omega import generators as gen
from levi.revival.omega import nexus as nx


# ---- blueprint (Echo) ----


def test_detect_webpage():
    types = bp.detect_product_types("build me a landing page website for my bakery")
    assert types[0] == "webpage"


def test_detect_cli_and_api():
    types = bp.detect_product_types("a command line tool with a fastapi backend api")
    assert "cli" in types and "api" in types


def test_detect_fallback_is_skill():
    assert bp.detect_product_types("something utterly unrelated xyzzy") == ["skill"]
    assert bp.detect_product_types("") == ["skill"]


def test_detection_scores_exposed():
    scores = bp.detection_scores("build a website")
    assert scores.get("webpage", 0) > 0


def test_build_blueprint_structure():
    b = bp.build_blueprint("todo list web app with fastapi backend")
    assert b["name"].endswith(("-site", "-api", "-cli", "-mcp", "-flow", "-skill"))
    assert set(b["product_types"]) >= {"webpage", "api"}
    assert b["components"] and b["layers"] and b["artifacts"]
    assert b["origin"] == bp.ORIGIN
    assert bp.validate_blueprint(b)["ok"]


def test_build_blueprint_rejects_empty():
    with pytest.raises(ValueError):
        bp.build_blueprint("   ")


def test_build_blueprint_rejects_unknown_type():
    with pytest.raises(ValueError):
        bp.build_blueprint("x", product_types=["teleporter"])


def test_validate_blueprint_never_raises():
    assert bp.validate_blueprint(None) == {
        "ok": False,
        "errors": ["blueprint must be a dict"],
    }
    result = bp.validate_blueprint({"name": "x"})
    assert not result["ok"] and any("missing field" in e for e in result["errors"])


# ---- generators (Alpha) ----


def test_registry_has_six_generators():
    assert set(gen.registered()) == {
        "webpage",
        "cli",
        "api",
        "mcp_server",
        "automation",
        "skill",
    }


def test_duplicate_registration_rejected():
    with pytest.raises(ValueError):
        gen.register(
            gen.Generator(
                name="webpage",
                title="dup",
                description="dup",
                product_types=["webpage"],
                generate=lambda b: {},
            )
        )


def test_compile_webpage_blueprint():
    b = bp.build_blueprint("landing page for my dog grooming site")
    assert b["product_types"] == ["webpage"]
    result = gen.compile_blueprint(b)
    assert result["ok"], result["errors"]
    assert f"{b['name']}/index.html" in result["files"]
    html = result["files"][f"{b['name']}/index.html"]
    assert "<!DOCTYPE html>" in html and b["title"] in html


def test_compile_cli_blueprint_runs():
    b = bp.build_blueprint("command line tool to rename photos")
    result = gen.compile_blueprint(b)
    assert result["ok"], result["errors"]
    module = b["name"].replace("-", "_")
    src = result["files"][f"{b['name']}/{module}.py"]
    assert "argparse" in src
    # the generated scaffold is valid Python
    compile(src, "<generated-cli>", "exec")


def test_compile_api_blueprint_marks_dependency():
    b = bp.build_blueprint("rest api backend for notes", product_types=["api"])
    result = gen.compile_blueprint(b)
    assert result["ok"], result["errors"]
    assert "fastapi" in result["files"][f"{b['name']}/requirements.txt"].lower()


def test_compile_mcp_server_blueprint():
    b = bp.build_blueprint("mcp server exposing my notes", product_types=["mcp_server"])
    result = gen.compile_blueprint(b)
    assert result["ok"], result["errors"]
    module = b["name"].replace("-", "_")
    src = result["files"][f"{b['name']}/{module}.py"]
    assert "list_tools" in src
    compile(src, "<generated-mcp>", "exec")


def test_compile_rejects_invalid_blueprint():
    result = gen.compile_blueprint({"name": "broken"})
    assert not result["ok"] and result["files"] == {}


def test_end_to_end_prompt_to_files():
    b = bp.build_blueprint("todo list web app with fastapi backend")
    result = gen.compile_blueprint(b)
    assert result["ok"], result["errors"]
    # webpage + api generators both ran
    assert any(p.endswith("index.html") for p in result["files"])
    assert any(p.endswith("requirements.txt") for p in result["files"])


# ---- nexus ----


def _providers():
    return [
        nx.Provider(
            name="levi-local",
            source=nx.SOURCE_LOCAL,
            kinds=frozenset({"chat", "code"}),
            cost=1,
            quality=0.6,
        ),
        nx.Provider(
            name="levi-si-cloud",
            source=nx.SOURCE_CLOUD,
            kinds=frozenset({"chat", "code", "vision"}),
            cost=6,
            quality=0.9,
        ),
        nx.Provider(
            name="rival-x",
            source=nx.SOURCE_REFERENCE,
            kinds=frozenset({"chat"}),
            cost=2,
            quality=0.5,
        ),
    ]


def test_route_balanced_prefers_coverage():
    task = nx.Task(kinds=frozenset({"chat", "vision"}), label="see this photo")
    routes = nx.route(task, _providers())
    assert routes[0].provider == "levi-si-cloud"  # only eligible one covering vision
    assert routes[0].eligible
    # references never route, even when they cover the kinds
    ref = [r for r in routes if r.provider == "rival-x"]
    assert ref and not ref[0].eligible


def test_route_fast_prefers_cheap():
    task = nx.Task(kinds=frozenset({"chat"}), label="quick question")
    routes = nx.route(task, _providers(), mode="fast")
    # levi-local is the cheapest eligible chat-capable provider (cost 1),
    # so it honestly wins fast mode
    assert routes[0].provider == "levi-local"
    assert routes[0].eligible


def test_route_offline_is_deny_closed():
    task = nx.Task(kinds=frozenset({"chat"}), label="private")
    routes = nx.route(task, _providers(), mode="offline")
    assert routes[0].provider == "levi-local"
    non_local = [r for r in routes if r.provider != "levi-local"]
    assert all(not r.eligible and r.confidence == 0.0 for r in non_local)


def test_route_needs_local_excludes_remote():
    task = nx.Task(kinds=frozenset({"chat"}), needs_local=True)
    routes = nx.route(task, _providers())
    assert routes[0].provider == "levi-local"
    assert all(not r.eligible for r in routes[1:])


def test_route_rejects_bad_input():
    with pytest.raises(ValueError):
        nx.route(nx.Task(), _providers(), mode="turbo")
    with pytest.raises(ValueError):
        nx.route(nx.Task(), [])


def test_route_confidence_is_ranked():
    task = nx.Task(kinds=frozenset({"chat"}))
    routes = nx.route(task, _providers(), mode="deep")
    confs = [r.confidence for r in routes if r.eligible]
    assert confs == sorted(confs, reverse=True)
    assert all(0.0 <= c <= 1.0 for c in confs)


def test_explain_lists_reasons():
    task = nx.Task(kinds=frozenset({"chat"}))
    text = nx.explain(nx.route(task, _providers()))
    assert "levi-local" in text and "conf=" in text
