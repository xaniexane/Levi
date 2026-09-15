"""Social packs: sanitize contract enforced by real assertions on output."""
import re
from pathlib import Path

import pytest

from levi.king import social as social_mod
from levi.king.social import (
    PLATFORMS,
    assert_pack_clean,
    build_pack,
    hashtags_from,
    sanitize,
)

NASTY = """# The **Bold** Title

> A quoted line with `code` and a [link](https://example.com/x).

Some *italic* and __underlined__ and ~~struck~~ text, plus ![alt](img.png).

## Sub heading with #hashtag inside

Final para with a stray # mark and **more bold**.
"""


def test_sanitize_strips_all_markdown():
    clean = sanitize(NASTY)
    assert "**" not in clean
    assert "__" not in clean
    assert "`" not in clean
    assert "#" not in clean  # contract: no '#' survives the body
    assert "https://example.com" not in clean  # link target gone...
    assert "link" in clean  # ...but link text kept
    assert "The Bold Title" in clean
    assert ">" not in clean.splitlines()[0]


def test_sanitize_empty():
    assert sanitize("") == ""
    assert sanitize("   \n  ") == ""


def test_build_pack_all_platforms_clean():
    for platform in PLATFORMS:
        pack = build_pack(NASTY, platform=platform, title="## **Titled**")
        assert_pack_clean(pack)  # raises on any contract violation
        assert pack["caption_chars"] == len(pack["caption"])
        assert pack["caption_chars"] <= PLATFORMS[platform]["caption_max"]


def test_every_hash_is_a_generated_hashtag():
    pack = build_pack("The lattice remembers the weather. The weather keeps the receipt.",
                      platform="x")
    assert_pack_clean(pack)
    for m in re.finditer(r"#", pack["caption"]):
        rest = pack["caption"][m.start():]
        assert re.match(r"#[A-Za-z][A-Za-z0-9_]*", rest), f"stray # at {m.start()}"


def test_hashtags_live_only_in_trailing_block():
    pack = build_pack(NASTY, platform="instagram")
    paras = [p for p in pack["caption"].split("\n\n") if p.strip()]
    assert len(paras) >= 2  # body + tag block
    assert "#" not in "\n\n".join(paras[:-1])


def test_hashtags_deterministic():
    text = "Storms gather over the inland canopy. Canopy shadows remember storms."
    assert hashtags_from(text, 4) == hashtags_from(text, 4)
    tags = hashtags_from(text, 4)
    assert all(t.startswith("#") for t in tags)
    assert "#the" not in tags  # stopwords never become tags


def test_unknown_platform_raises():
    with pytest.raises(ValueError):
        build_pack("hello", platform="myspace")


def test_empty_source_raises():
    with pytest.raises(ValueError):
        build_pack("   ", platform="x")
    with pytest.raises(ValueError):
        build_pack("##", platform="x")  # sanitizes to empty


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
    imported = _imported_modules(social_mod)
    banned = {"urllib.request", "urllib.error", "http.client", "socket",
              "requests", "subprocess"}
    assert not (imported & banned), f"network-capable imports in social.py: {imported & banned}"
