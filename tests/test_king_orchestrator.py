"""King orchestration: engine drives harvest into the ledger; gates hold."""

from levi.graph.story_fabric import StoryFabric
from levi.king import King
from levi.lwp.model_engine import LWPModelEngine


def _king(tmp_path):
    fabric = StoryFabric(data_dir=tmp_path / "stories")
    engine = LWPModelEngine(path=tmp_path / "lwp_state.json")
    return King(data_dir=tmp_path / "king", story_fabric=fabric, model_engine=engine)


def test_status_fresh(tmp_path):
    k = _king(tmp_path)
    out = k.status()
    assert "rank=D2" in out
    assert "story_fabric=yes" in out
    assert "model_engine=yes" in out
    assert "session_rom_locks=0" in out


def test_pulse_without_stories_guides_no_autocreate(tmp_path):
    k = _king(tmp_path)
    out = k.pulse()
    assert "story --create" in out  # guidance, not a silent auto-create
    assert k.ledger.total_banks == 0  # nothing harvested


def test_pulse_harvests_story_fabric(tmp_path):
    k = _king(tmp_path)
    story = k._fabric().create_story("A lighthouse keeps the last signal.", genre="literary")
    out = k.pulse(story_id=story.id)
    assert "words" in out and "bank(s) harvested" in out
    assert k.ledger.total_words > 0
    assert k.ledger.total_banks >= 1
    assert story.id in k.ledger.entities
    assert any(e["relation"] == "advances" for e in k.ledger.edges)
    assert "ledger: rank=" in out


def test_pulse_latest_story_by_default(tmp_path):
    k = _king(tmp_path)
    k._fabric().create_story("First tale.", genre="literary")
    k._fabric().create_story("Second tale.", genre="noir")
    k.pulse()
    assert k.ledger.total_banks >= 1


def test_pulse_unknown_story(tmp_path):
    k = _king(tmp_path)
    assert "Unknown story" in k.pulse(story_id="story.nope")


def test_pulse_manuscript_harvests(tmp_path):
    k = _king(tmp_path)
    out = k.pulse_manuscript(n=1)
    assert k.ledger.total_words > 0
    assert k.ledger.total_banks >= 1
    assert any(e["kind"] == "scene" for e in k.ledger.entities.values())
    assert "harvested:" in out


def test_reim_registers_tracks_zero_words(tmp_path):
    k = _king(tmp_path)
    out = k.reim(tracks=3, seed="a fork in the road")
    assert "REIM" in out
    tracks = [e for e in k.ledger.entities.values() if e["kind"] == "reim_track"]
    assert len(tracks) == 3
    # forks are not canon: the harvest must record 0 words / 0 banks
    last = k.ledger.harvests[-1]
    assert last["words"] == 0 and last["banks"] == 0
    assert "reim" in last["event"]


def test_deny_approve_passthrough_and_audit(tmp_path):
    k = _king(tmp_path)
    k.pulse_manuscript(n=1)
    words_before = k.ledger.total_words
    deny_out = k.deny()
    assert "Denied" in deny_out
    assert k.ledger.total_words < words_before  # negative harvest recorded
    assert k.review.decisions[-1]["action"] == "deny"
    k.pulse_manuscript(n=1)
    appr_out = k.approve()
    assert "Approved" in appr_out
    assert k.review.decisions[-1]["action"] == "approve"


def test_deny_approve_with_review_id(tmp_path):
    k = _king(tmp_path)
    k.social(platform="x")
    item_id = k.review.pending[0]["id"]
    assert "Approved review item" in k.approve(review_id=item_id)
    k.social(platform="x")
    item2 = k.review.pending[0]["id"]
    assert "Denied review item" in k.deny(review_id=item2)
    assert "not pending" in k.approve(review_id="rev.nope")


def test_rupture_passthrough_harvests(tmp_path):
    k = _king(tmp_path)
    out = k.rupture(lens="mccarthy")
    assert "Wyrd-Rupture" in out
    assert any(e["kind"] == "rom_lock" for e in k.ledger.entities.values())
    assert k.ledger.total_banks >= 1


def test_d5_promotion_and_reset(tmp_path):
    k = _king(tmp_path)
    out = k.d5()
    assert "D5 baseline promotion" in out
    assert k.ledger.rank() == "D5"
    assert k.rom.count() == 1
    lock = k.rom.latest()
    assert lock["reason"].startswith("d5 baseline promotion")
    assert lock["ledger_fingerprint"] == k.ledger.fingerprint()
    assert "PROMOTED" in k.status()
    assert "cleared" in k.d5(reset=True)
    assert k.ledger.rank() == "D2"


def test_social_queues_pending_pack(tmp_path):
    k = _king(tmp_path)
    k.pulse_manuscript(n=1)
    out = k.social(platform="x")
    assert "queued for review" in out
    assert "review id:" in out
    assert k.review.pending_count() == 1
    # the queued caption satisfies the sanitize contract
    from levi.king.social import assert_pack_clean
    assert_pack_clean({"caption": k.review.pending[0]["caption"]})


def test_social_post_gates(tmp_path):
    k = _king(tmp_path)
    k.pulse_manuscript(n=1)
    k.social(platform="x")
    item_id = k.review.pending[0]["id"]

    # Gate 1: not approved yet
    r = k.social_post(item_id, confirm=True)
    assert r["ok"] is False and r["gate"] == "approval"
    assert "Nothing was sent" in r["message"]

    # Gate 2: approved but no confirmation
    k.approve(review_id=item_id)
    r = k.social_post(item_id, confirm=False)
    assert r["ok"] is False and r["gate"] == "confirmation"
    assert "Nothing was sent" in r["message"]

    # Unknown id
    r = k.social_post("rev.nope", confirm=True)
    assert r["ok"] is False


def test_social_post_loopback_success(tmp_path):
    import levi.plugins.social_stub as stub
    from levi.plugins.registry import get_connector

    stub.OUTBOX.clear()
    k = _king(tmp_path)
    k.pulse_manuscript(n=1)
    k.social(platform="x")
    item_id = k.review.pending[0]["id"]
    k.approve(review_id=item_id)

    r = k.social_post(item_id, confirm=True)
    assert r["ok"] is True, r["message"]
    assert r["result"]["status"] == "ok"
    assert r["result"]["data"]["loopback"] is True
    assert len(stub.OUTBOX) == 1
    assert stub.OUTBOX[0]["platform"] == "x"
    assert stub.OUTBOX[0]["caption"] == k.review.get(item_id)["caption"]

    # Connector-level confirmation gate trips even when called directly.
    conn = get_connector("social-stub")
    res = conn.execute("publish", {"platform": "x", "caption": "hi"}, confirm=False)
    assert res.ok is False and res.status == "confirmation_required"


def test_engines_absent_degrades_gracefully(tmp_path):
    k = King(data_dir=tmp_path / "king", story_fabric=None, model_engine=None)
    assert k.fabric_available is False
    assert k.engine_available is False
    assert "unavailable" in k.pulse()
    assert "unavailable" in k.pulse_manuscript()
    assert "unavailable" in k.reim()
    assert "unavailable" in k.rupture()
    assert "no (graceful)" in k.status()
    # non-engine surfaces still work
    assert "D5 baseline promotion" in k.d5()
    assert "cleared" in k.d5(reset=True)


def test_ledger_is_single_aggregation_point(tmp_path):
    k = _king(tmp_path)
    story = k._fabric().create_story("Ledger aggregation tale.", genre="literary")
    k.pulse(story_id=story.id)
    k.pulse_manuscript(n=1)
    sources = {h["source"] for h in k.ledger.harvests}
    assert sources == {"story_fabric", "model_engine"}
    assert k.ledger.total_words > 0
