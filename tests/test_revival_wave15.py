"""Wave 15 tests — forge-additions (d): sovereign code-home features."""

import json

import pytest

from core.levi.revival.memory_vaults import (
    RetentionPolicy,
    VaultError,
    VaultStore,
)
from core.levi.revival.workbench_canvas import Canvas, CanvasError
from core.levi.revival.knowledge_packs import PackStore
from core.levi.revival.commitment_devices import Commitment, CommitmentStore
from core.levi.revival.annual_recap import Recap
from core.levi.revival.ritual_discovery import Library
from core.levi.revival.trust_classifieds import Board


# ---------- memory_vaults ------------------------------------------------


def test_vault_ttl_purge_keeps_pinned():
    store = VaultStore()
    vault = store.create_vault(
        "proj", RetentionPolicy(ttl_seconds=100, pin_tags=["keep"])
    )
    vault.put("a", "old", created_at=0.0)
    vault.put("b", "pinned-old", created_at=0.0, tags=["keep"])
    vault.put("c", "fresh", created_at=150.0)
    removed = vault.purge(now=200.0)
    assert removed == 1
    assert vault.get("a") is None
    assert vault.get("b") is not None  # pinned survives TTL
    assert vault.get("c") is not None


def test_vault_max_entries_drops_oldest_and_refuse_mode():
    store = VaultStore()
    vault = store.create_vault("cap", RetentionPolicy(max_entries=2))
    vault.put("a", "1", created_at=1.0)
    vault.put("b", "2", created_at=2.0)
    vault.put("c", "3", created_at=3.0)  # evicts oldest non-pinned
    assert vault.get("a") is None
    assert vault.get("c") is not None

    vault2 = store.create_vault(
        "ref", RetentionPolicy(max_entries=1, on_overflow="refuse")
    )
    vault2.put("a", "1", created_at=1.0)
    with pytest.raises(VaultError):
        vault2.put("b", "2", created_at=2.0)
    assert vault2.get("a") is not None  # nothing was clobbered


def test_vault_save_load_roundtrip(tmp_path):
    store = VaultStore()
    vault = store.create_vault("rt", RetentionPolicy(ttl_seconds=60))
    vault.put("k", "v", created_at=10.0, tags=["t"])
    path = str(tmp_path / "vaults.json")
    store.save(path)
    loaded = VaultStore.load(path)
    assert loaded.list_vaults() == ["rt"]
    entry = loaded.get_vault("rt").get("k")
    assert entry.value == "v" and entry.tags == ["t"]


# ---------- workbench_canvas ---------------------------------------------


def test_canvas_versioning_and_diff():
    canvas = Canvas("demo")
    canvas.new_artifact("plan", "line one\nline two\n")
    canvas.revise("plan", "line one\nline TWO\nline three\n", note="expand")
    assert canvas.get("plan") == "line one\nline TWO\nline three\n"
    assert canvas.get("plan", revision=1) == "line one\nline two\n"
    diff = canvas.diff("plan", 1, 2)
    assert "line TWO" in diff and "plan@r1" in diff
    assert [r.number for r in canvas.history("plan")] == [1, 2]


def test_canvas_chat_stays_separate_from_artifacts():
    canvas = Canvas()
    canvas.chat("let's draft the readme", role="user")
    canvas.chat("on it", role="assistant")
    canvas.new_artifact("readme", "# Hello")
    assert len(canvas.transcript()) == 2
    assert canvas.list_artifacts() == ["readme"]
    assert all("Hello" not in m.text for m in canvas.transcript())


def test_canvas_exports_and_session_bundle():
    canvas = Canvas("wb")
    canvas.new_artifact("notes", "hello *world*")
    md = canvas.export("notes", "markdown")
    assert md.startswith("# notes") and "hello" in md
    html_out = canvas.export("notes", "html")
    assert "<h1>notes</h1>" in html_out and "hello *world*" in html_out
    canvas.chat("hi")
    bundle = canvas.export_session()
    assert "## Chat" in bundle and "## Artifacts" in bundle
    with pytest.raises(CanvasError):
        canvas.export("notes", "pdf")


# ---------- knowledge_packs ----------------------------------------------


def test_pack_search_ranks_relevant_doc():
    store = PackStore()
    pack = store.create_pack("garden", instructions="Answer about plants.")
    pack.add_doc("roses.md", "Roses need pruning in spring and full sun.")
    pack.add_doc("bikes.md", "Bicycle gears and chains need oil.")
    hits = store.search("garden", "pruning roses sun")
    assert hits and hits[0].doc_name == "roses.md"
    assert "pruning" in hits[0].snippet.lower()


def test_pack_render_context_budget_and_instructions():
    store = PackStore()
    pack = store.create_pack("p", instructions="Be brief.")
    pack.add_doc("a.txt", "alpha beta gamma " * 50)
    pack.add_doc("b.txt", "delta epsilon " * 50)
    ctx = store.render_context("p", "alpha", max_chars=300)
    assert "Be brief." in ctx
    assert len(ctx) <= 300 + 200  # budget honored with small overrun allowance
    assert "a.txt" in ctx


def test_pack_from_directory_and_remove(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "one.txt").write_text("first file content")
    (d / "skip.bin").write_text("not text")
    store = PackStore()
    pack = store.from_directory("dir", str(d))
    assert pack.list_docs() == ["one.txt"]
    assert pack.remove_doc("one.txt") is True
    assert pack.doc_count() == 0
    assert store.delete_pack("dir") is True


# ---------- commitment_devices --------------------------------------------


def test_streak_counts_consecutive_and_breaks_on_miss():
    store = CommitmentStore()
    c = store.create("read", target=20.0, unit="minutes")
    c.check_in("2026-09-14", 30.0)
    c.check_in("2026-09-15", 25.0)
    assert c.streak("2026-09-15") == 2
    # 2026-09-16 missed entirely
    assert c.streak("2026-09-16") == 0
    # partial amount does not count
    c.check_in("2026-09-16", 5.0)
    assert c.streak("2026-09-16") == 0
    c.check_in("2026-09-16", 20.0)  # now meets target: 14th, 15th, 16th
    assert c.streak("2026-09-16") == 3


def test_rest_days_are_neutral_not_breaking():
    c = Commitment("run", target=1.0, rest_weekdays=[6])  # Sunday rest
    # 2026-09-13 is a Sunday
    c.check_in("2026-09-12", 1.0)  # Saturday met
    c.check_in("2026-09-14", 1.0)  # Monday met
    assert c.met("2026-09-13") is None  # rest day: neutral
    assert c.streak("2026-09-14") == 2  # rest day skipped, streak intact


def test_status_is_neutral_and_history_immutable():
    c = Commitment("write", target=10.0, unit="pages")
    c.check_in("2026-09-15", 12.0)
    status = c.status("2026-09-15")
    assert "streak 1" in status and "target met" in status
    assert "shame" not in status.lower() and "lazy" not in status.lower()
    c.check_in("2026-09-15", 3.0)  # accumulates, never overwrites
    assert c.day_total("2026-09-15") == 15.0
    assert c.best_streak() >= 1


# ---------- annual_recap --------------------------------------------------


def test_recap_cards_from_events():
    recap = Recap()
    recap.add_event("2026-01-05", "reading", "Dune", 1.0)
    recap.add_event("2026-01-06", "reading", "Dune", 1.0)
    recap.add_event("2026-02-01", "running", "5k", 5.0)
    recap.add_event("2026-02-02", "running", "10k", 10.0)
    yr = recap.recap(2026)
    titles = [c.title for c in yr.cards]
    assert titles == [
        "2026 by the numbers",
        "2026 top shelf",
        "2026 milestones",
        "2026 rhythm",
    ]
    numbers = yr.cards[0].render()
    assert "reading: 2 events" in numbers and "running: 2 events" in numbers
    miles = yr.cards[2].render()
    assert "first reading — Dune (2026-01-05)" in miles
    assert "best running day" in miles


def test_recap_empty_year_and_render_card():
    recap = Recap()
    recap.add_event("2026-03-01", "x", "y")
    yr = recap.recap(2025)
    assert len(yr.cards) == 1 and "No events recorded" in yr.cards[0].render()
    card = recap.render_card(2026, "2026 rhythm")
    assert card is not None and "busiest weekday" in card
    assert recap.render_card(2026, "nope") is None
    assert recap.years() == [2026]


def test_recap_top_shelf_ordering():
    recap = Recap()
    for _ in range(3):
        recap.add_event("2026-04-01", "games", "chess", 1.0)
    recap.add_event("2026-04-02", "games", "go", 1.0)
    top = recap.recap(2026).cards[1].render()
    chess_pos = top.index("chess")
    go_pos = top.index("go")
    assert chess_pos < go_pos  # higher total sorts first


# ---------- ritual_discovery ----------------------------------------------


def test_ritual_is_deterministic_per_week():
    def build():
        lib = Library()
        for i in range(8):
            lib.add_item(f"id{i}", f"Title {i}", kind="book" if i % 2 else "note")
        return lib

    a = [p.item.item_id for p in build().ritual("2026-W37", count=3)]
    b = [p.item.item_id for p in build().ritual("2026-W37", count=3)]
    assert a == b and len(a) == 3


def test_ritual_surfaces_stale_items_and_spreads_kinds():
    lib = Library()
    lib.add_item("fresh", "Fresh", kind="book")
    lib.ritual("2026-W01", count=1)  # surfaces "fresh"-ish pick
    lib.add_item("old", "Old Note", kind="note")
    picks = lib.ritual("2026-W02", count=2)
    ids = [p.item.item_id for p in picks]
    kinds = {p.item.kind for p in picks}
    assert len(ids) == 2 and len(kinds) == 2  # kind spread
    assert all(p.reason for p in picks)  # every pick explains itself


def test_ritual_empty_library_and_marking():
    lib = Library()
    assert lib.ritual("2026-W01") == []
    lib.add_item("x", "X", kind="note")
    picks = lib.ritual("2026-W01", count=5)  # count > size is fine
    assert len(picks) == 1
    assert lib._items["x"].surfaced_count == 1
    assert lib.remove_item("x") is True
    assert lib.size() == 0


# ---------- trust_classifieds ---------------------------------------------


def test_trust_signals_direct_mutual_unknown():
    board = Board()
    board.add_connection("chauncey", "ana")
    board.add_connection("ana", "bob")
    board.add_connection("chauncey", "cara")
    board.add_connection("cara", "bob")
    direct = board.trust("chauncey", "ana")
    assert direct.direct and direct.score >= 0.9
    mutual = board.trust("chauncey", "bob")
    assert not mutual.direct and set(mutual.mutuals) == {"ana", "cara"}
    assert 0.0 < mutual.score < 0.9
    unknown = board.trust("chauncey", "zed")
    assert unknown.score == 0.0 and unknown.hops is None
    assert "unknown" in unknown.explain()


def test_feed_orders_by_trust_then_recency():
    board = Board()
    board.add_connection("me", "friend")
    board.add_listing("Bike", seller="stranger", price=50.0, created_at=2.0)
    board.add_listing("Lamp", seller="friend", price=10.0, created_at=1.0)
    board.add_listing("Desk", seller="me", price=5.0, created_at=0.0)
    feed = board.feed("me")
    sellers = [listing.seller for listing, _ in feed]
    assert sellers[0] == "me"  # own listing first
    assert sellers[1] == "friend"  # trusted before stranger
    assert sellers[2] == "stranger"


def test_export_merge_roundtrip_and_no_ad_layer():
    board = Board()
    board.add_connection("a", "b")
    board.add_listing("Drill", seller="b", price=20.0)
    data = json.loads(board.to_json())
    assert "promoted" not in json.dumps(data)  # no ad layer in the schema
    other = Board("other")
    n_listings, n_conns = other.merge(data)
    assert (n_listings, n_conns) == (1, 1)
    assert other.trust("a", "b").direct is True
    assert len(other.search(category="misc")) == 1
