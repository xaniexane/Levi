"""Hermetic tests for wave 44 revival modules (extensibility, co-editing,
substrate design — doors, OT, capability strings)."""

from __future__ import annotations

import sys

import pytest

from levi.revival.chained_programs import ChainRegistry, ChainSpec
from levi.revival.dropfile_ipc import DropSession, read_dropfile, write_dropfile
from levi.revival.plugin_contract import ContractError, Plugin, PluginHost
from levi.revival.op_transform import Delete, Insert, apply, converge
from levi.revival.auto_hypertext import HypertextIndex
from levi.revival.multinet_syndication import (
    Article,
    NetworkAdapter,
    Syndicator,
    CLASSIC_NETWORKS,
)
from levi.revival.cutdown_html import cutdown
from levi.revival.small_tool_ethos import (
    Budget,
    check_budget,
    measure,
    simplicity_score,
)
from levi.revival.enfilade import Enfilade
from levi.revival.capability_strings import parse_acs


@pytest.fixture()
def registry():
    reg = ChainRegistry()
    reg.register(
        ChainSpec(
            name="echoer",
            argv=[sys.executable, "-c", "import sys; print(' '.join(sys.argv[1:]))"],
            budget_s=5.0,
            description="echoes args",
        )
    )
    return reg


def test_chain_runs_and_captures_output(registry):
    result = registry.run_chain("echoer", ["hello", "world"])
    assert result.ok
    assert result.stdout.strip() == "hello world"
    assert result.returncode == 0
    assert not result.timed_out


def test_chain_timeout_reported():
    reg = ChainRegistry()
    reg.register(
        ChainSpec(
            name="sleeper",
            argv=[sys.executable, "-c", "import time; time.sleep(30)"],
            budget_s=0.5,
        )
    )
    result = reg.run_chain("sleeper")
    assert result.timed_out
    assert not result.ok


def test_chain_unknown_name_and_menu(registry):
    with pytest.raises(KeyError):
        registry.run_chain("nope")
    assert registry.unregister("echoer") is True
    assert registry.unregister("echoer") is False
    assert registry.names() == []


def test_chain_arg_cap_and_bad_registration():
    reg = ChainRegistry()
    with pytest.raises(ValueError):
        reg.register(ChainSpec(name="", argv=["x"]))
    with pytest.raises(ValueError):
        reg.register(ChainSpec(name="bad", argv=[]))
    reg.register(ChainSpec(name="c", argv=["true"], max_args=1))
    # over the cap: extras are dropped, never shell-interpreted
    result = reg.run_chain("c", ["a", "b", "c"])
    assert result.ok


def test_dropfile_round_trip(tmp_path):
    session = DropSession(
        user_name="chauncey",
        user_handle="levi",
        terminal_kind="ansi",
        rows=25,
        cols=80,
        time_limit_s=3600,
        time_used_s=61,
        node=2,
        capabilities="doors,chat",
    )
    path = tmp_path / "s.drop"
    write_dropfile(session, path)
    assert read_dropfile(path) == session
    assert session.time_left_s == 3539


def test_dropfile_refuses_secrets_and_bad_format(tmp_path):
    session = DropSession(user_name="x", user_handle="y", terminal_kind="weird")
    with pytest.raises(ValueError):
        write_dropfile(session, tmp_path / "never.drop")
    path = tmp_path / "bad.drop"
    path.write_text("NOTADROP\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_dropfile(path)


def test_dropfile_rejects_missing_fields(tmp_path):
    path = tmp_path / "short.drop"
    path.write_text("LEVIDROP\nversion=1\nuser_name=x\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_dropfile(path)


def test_plugin_register_load_dispatch_order():
    host = PluginHost()
    calls = []
    host.register(
        Plugin(
            name="a",
            kind="filter",
            handle=lambda s: s + "a",
            on_load=lambda p, h: calls.append("a"),
        )
    )
    host.register(
        Plugin(name="b", kind="filter", requires=["a"], handle=lambda s: s + "b")
    )
    assert host.load_all() == ["a", "b"]
    assert calls == ["a"]
    # fan-out: each filter sees the original payload independently
    assert host.dispatch("filter", "") == ["a", "b"]
    assert host.dispatch("source", "") == []


def test_plugin_rejects_bad_api_and_cycles():
    host = PluginHost()
    with pytest.raises(ContractError):
        host.register(Plugin(name="x", kind="filter", api="other/9"))
    with pytest.raises(ContractError):
        host.register(Plugin(name="x", kind="nope"))
    host.register(Plugin(name="p", kind="filter", requires=["q"]))
    host.register(Plugin(name="q", kind="filter", requires=["p"]))
    with pytest.raises(ContractError):
        host.load_all()


def test_plugin_unload_guards_dependents():
    host = PluginHost()
    host.register(Plugin(name="base", kind="source"))
    host.register(Plugin(name="dep", kind="filter", requires=["base"]))
    with pytest.raises(ContractError):
        host.unregister("base")
    assert host.unregister("dep").name == "dep"
    assert host.unregister("base").name == "base"


def test_ot_insert_insert_converges():
    doc = "abcdef"
    left, right = converge(doc, Insert(1, "X", client="a"), Insert(1, "Y", client="b"))
    assert left == right == "aXYbcdef"


def test_ot_mixed_insert_delete_converges():
    doc = "abcdef"
    left, right = converge(doc, Insert(1, "X", client="a"), Delete(2, 3, client="b"))
    assert left == right == "aXbf"


def test_ot_delete_delete_overlap_converges():
    doc = "abcdefgh"
    left, right = converge(doc, Delete(1, 3, client="a"), Delete(2, 3, client="b"))
    assert left == right == "afgh"


def test_ot_apply_validates_positions():
    with pytest.raises(ValueError):
        apply("ab", [Insert(5, "x")])
    with pytest.raises(ValueError):
        apply("ab", [Delete(1, 5)])
    assert apply("hello", [Delete(1, 2), Insert(0, "H")]) == "Hhlo"


@pytest.fixture()
def index():
    idx = HypertextIndex()
    idx.add("Great Library", "the archive of all known works", aliases=("the Library",))
    idx.add("Library", "a smaller collection")
    idx.add("Delphi", "the gateway")
    return idx


def test_hypertext_longest_match_wins(index):
    links = index.link("Visit the Great Library today.")
    assert len(links) == 1
    assert links[0].entry == "Great Library"
    assert links[0].span == (10, 23)


def test_hypertext_aliases_and_render(index):
    links = index.link("the Library echoes Delphi")
    by_entry = {link.entry: link for link in links}
    assert by_entry["Great Library"].matched == "the Library"
    assert by_entry["Delphi"].matched == "Delphi"
    rendered = index.render("See Delphi.")
    assert "Delphi" in rendered and "the gateway" in rendered


def test_hypertext_no_partial_words(index):
    assert index.link("Delphinium is a flower.") == []
    assert index.link("nothing known here") == []


def test_hypertext_duplicates_and_removal():
    idx = HypertextIndex()
    idx.add("Alpha", "first")
    with pytest.raises(ValueError):
        idx.add("alpha", "again")
    assert idx.remove("ALPHA") is True
    assert idx.remove("alpha") is False
    assert idx.link("Alpha") == []


def test_syndication_respects_caps():
    syn = Syndicator(CLASSIC_NETWORKS)
    article = Article(
        title="A very long title that exceeds every classic network cap easily",
        body="word " * 500,
        tags=("t1",),
    )
    payloads = syn.publish(article)
    assert set(payloads) == {"CompuServe", "Prodigy", "AOL", "AppleLink"}
    apple = payloads["AppleLink"]
    assert apple.title_trimmed and apple.body_trimmed and apple.tags_dropped
    aol = payloads["AOL"]
    assert aol.tags == ("t1",)
    assert len(apple.title) <= 27  # 24 + "..."


def test_syndication_unknown_network():
    syn = Syndicator([NetworkAdapter(name="Solo")])
    with pytest.raises(KeyError):
        syn.publish(Article(title="t", body="b"), networks=["Ghost"])


def test_syndication_subset_and_line_width():
    syn = Syndicator(CLASSIC_NETWORKS)
    article = Article(title="t", body="alpha beta gamma delta")
    payloads = syn.publish(article, networks=["CompuServe"])
    assert list(payloads) == ["CompuServe"]
    assert payloads["CompuServe"].body == "alpha beta gamma delta"


def test_cutdown_drops_scripts_and_forms():
    html = (
        "<html><head><style>x{}</style><script>alert(1)</script></head>"
        "<body><h1>Hi</h1><p>Text <a href='/x'><b>bold</b></a></p>"
        "<form><input></form></body></html>"
    )
    result = cutdown(html)
    assert "<script" not in result.markup
    assert "<form" not in result.markup
    assert "<h1>Hi</h1>" in result.markup
    assert '<a href="/x">' in result.markup
    assert result.kept_links == 1
    assert result.reduction_ratio > 0


def test_cutdown_sanitizes_img():
    result = cutdown('<p><img src="a.png" alt="pic" onclick="evil()"></p>')
    assert "onclick" not in result.markup
    assert 'src="a.png"' in result.markup
    assert 'alt="pic"' in result.markup


def test_cutdown_unwraps_unknown_tags_keeps_text():
    result = cutdown("<div><span>kept words</span></div>")
    assert "kept words" in result.markup
    assert "<div" not in result.markup
    assert result.removed_tags.get("div") == 1


def test_ethos_measures_local_tool(tmp_path):
    (tmp_path / "tool.py").write_text("import os\nimport requests\n\nx = 1\n")
    m = measure(tmp_path)
    assert m.file_count == 1
    assert m.total_bytes > 0
    assert "os" in m.stdlib_imports
    assert "requests" in m.third_party_imports


def test_ethos_budget_violations_and_score():
    from levi.revival.small_tool_ethos import Measurement

    budget = Budget(max_bytes=10, max_files=1, max_third_party_deps=0)
    m = Measurement(
        path="x",
        total_bytes=100,
        file_count=3,
        stdlib_imports=("os",),
        third_party_imports=("requests", "yaml"),
    )
    violations = check_budget(budget, m)
    assert {v.field for v in violations} == {"bytes", "files", "third_party_deps"}
    assert 0 <= simplicity_score(budget, m) <= 100
    clean = check_budget(Budget(max_bytes=1000, max_files=5, max_third_party_deps=5), m)
    assert clean == []


def test_ethos_rejects_non_directory(tmp_path):
    with pytest.raises(ValueError):
        measure(tmp_path / "missing")


def test_enfilade_edit_and_resolve():
    enf = Enfilade("The quick brown fox.")
    enf.add_span("adj", 4, 5)  # "quick"
    v1 = enf.edit(4, 5, "slow", note="slower")
    assert v1 == 1
    assert enf.text() == "The slow brown fox."
    assert enf.resolve("adj") == "slow"  # span absorbed the edit
    assert enf.resolve("adj", version=0) == "quick"
    assert [h[0] for h in enf.history()] == [0, 1]


def test_enfilade_span_before_and_after_edit():
    enf = Enfilade("abcdef")
    enf.add_span("head", 0, 2)  # "ab"
    enf.add_span("tail", 4, 2)  # "ef"
    enf.edit(2, 2, "XYZ")  # "abXYZef"
    assert enf.resolve("head") == "ab"
    assert enf.resolve("tail") == "ef"
    assert enf.text() == "abXYZef"


def test_enfilade_bounds_checked():
    enf = Enfilade("abc")
    with pytest.raises(ValueError):
        enf.add_span("bad", 2, 5)
    with pytest.raises(ValueError):
        enf.edit(0, 9, "x")
    with pytest.raises(KeyError):
        enf.resolve("missing")


def test_acs_parse_and_evaluate():
    caps = parse_acs("s10g5m")
    assert [c.letter for c in caps.claims] == ["s", "g", "m"]
    assert caps.allows({"security": 12, "groups": {5}, "menu_ok": True})
    assert not caps.allows({"security": 8, "groups": {5}, "menu_ok": True})
    assert not caps.allows({"security": 12, "groups": {9}, "menu_ok": True})


def test_acs_failing_and_describe():
    caps = parse_acs("s10x0")
    ctx = {"security": 3, "doors_ok": True}
    # s10 fails (level too low); x0 *denies* external programs, which are on
    assert [c.letter for c in caps.failing(ctx)] == ["s", "x"]
    words = caps.describe()
    assert any("security" in w for w in words)
    assert any("denies" in w for w in words)


def test_acs_rejects_garbage():
    for bad in ["", "q5", "s10!", "5s", "s1.5"]:
        with pytest.raises(ValueError):
            parse_acs(bad)


def test_acs_flag_and_minutes():
    caps = parse_acs("t30d")
    assert caps.allows({"minutes_left": 45, "display_ok": True})
    assert not caps.allows({"minutes_left": 10, "display_ok": True})
    assert not caps.allows({"minutes_left": 45, "display_ok": False})
