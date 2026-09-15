"""Visual checkpoint URLs: pure string construction, no HTTP ever."""
import urllib.parse
from pathlib import Path

import pytest

from levi.king import visual as visual_mod
from levi.king.visual import (
    POLLINATIONS_BASE,
    checkpoint_url,
    checkpoint_urls,
    visual_checkpoint_for_ledger,
)


def test_url_shape():
    url = visual_mod.checkpoint_url("a dark tower", width=512, height=512, seed=7)
    assert url.startswith(POLLINATIONS_BASE + "/")
    assert "width=512" in url and "height=512" in url
    assert "seed=7" in url and "model=flux" in url and "nologo=true" in url


def test_prompt_is_url_encoded():
    url = visual_mod.checkpoint_url("dark tower & storm?")
    path_part = url.split("?")[0]
    assert " " not in path_part
    encoded = path_part.rsplit("/", 1)[-1]
    assert urllib.parse.unquote(encoded) == "dark tower & storm?"


def test_seed_deterministic_without_argument():
    a = visual_mod.checkpoint_url("same prompt")
    b = visual_mod.checkpoint_url("same prompt")
    assert a == b
    c = visual_mod.checkpoint_url("different prompt")
    assert a != c


def test_empty_prompt_raises():
    with pytest.raises(ValueError):
        visual_mod.checkpoint_url("   ")


def test_batch_builder():
    urls = checkpoint_urls({"one": "tower", "two": "storm"}, seed=3)
    assert set(urls) == {"one", "two"}
    assert all(u.startswith(POLLINATIONS_BASE) for u in urls.values())


def test_ledger_checkpoint():
    cps = visual_checkpoint_for_ledger({"rank": "D3", "total_words": 6000, "total_banks": 12})
    assert len(cps) == 1
    assert cps[0]["name"] == "king-d3"
    assert "D3" in cps[0]["prompt"]
    assert cps[0]["url"].startswith(POLLINATIONS_BASE)


def _imported_modules(mod) -> set:
    import ast
    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


def test_no_network_by_construction():
    # This module must be incapable of network I/O: fail loudly if
    # anyone adds a socket/http-client import later.
    imported = _imported_modules(visual_mod)
    banned = {"urllib.request", "urllib.error", "http.client", "socket",
              "requests", "subprocess"}
    assert not (imported & banned), f"network-capable imports in visual.py: {imported & banned}"
    assert "urllib.parse" in imported  # string building only, no I/O
