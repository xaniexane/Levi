"""Proof tests for the NeighborOS dispatch bridge (laws L1-L7).

L1  A gig is claimed by at most one worker.
L2  Settlement only on proven work; disputed gigs freeze settlement.
L3  Worker keep >= 90% on every settlement.
L4  Gates enforced: dispatch refused outside an allowed stage.
L5  Bloodline limits: founder-only actions refuse on bloodline flavor.
L6  Metering: publish/offer/accept/settle append metering events on bloodline.
L7  Nothing is deleted: the bridge exposes no delete path.
Plus: verticals include the trades + tech support; category_match ranks
the right trade worker first.
"""

import json
import sys
from pathlib import Path

import pytest

BRIDGE_DIR = Path(__file__).resolve().parents[1] / "apps" / "neighboros-android" / "python-src"
sys.path.insert(0, str(BRIDGE_DIR))

import neighboros_bridge as b  # noqa: E402


def ok(raw: str) -> dict:
    d = json.loads(raw)
    assert d.get("ok"), f"expected ok, got: {d}"
    return d


def err(raw: str) -> str:
    d = json.loads(raw)
    assert not d.get("ok"), f"expected error, got: {d}"
    return d.get("error", "")


@pytest.fixture()
def ws(tmp_path):
    b.set_workspace(str(tmp_path))
    b.set_flavor("founder")
    return tmp_path


def _worker(ws, name="Rosa", cats="plumbing,hvac", cell="springfield-test"):
    return ok(b.worker_register(name, "555-0100", cats, cell))["worker"]


def _gig(ws, category="plumbing", cell="springfield-test"):
    draft = ok(b.gig_draft("Fix leaky faucet", category, "Kitchen faucet drips.",
                           "Cust", "555-0101", cell, "120"))["draft"]
    ok(b.gig_preview(json.dumps(draft)))
    return ok(b.gig_publish(json.dumps(draft), True))["gig"]


def _to_active_dispatch():
    # founder-only test helper: jump the gate machine for dispatch tests
    assert json.loads(b.gate_override("tester", "active_dispatch",
                                      "test"))["ok"]


def _full_loop(ws):
    """post -> offer -> accept -> checkin -> checkout -> signoff -> gig."""
    _to_active_dispatch()
    w = _worker(ws)
    gig = _gig(ws)
    cands = ok(b.dispatch_candidates(gig["id"]))["candidates"]
    assert cands, "no dispatch candidates"
    # trade vertical: the plumber outranks anyone without the category
    assert cands[0]["worker_id"] == w["id"]
    ok(b.offer_make(gig["id"], w["id"], "tester", True))
    ok(b.offer_accept(gig["id"], w["id"]))
    ok(b.proof_checkin(gig["id"], w["id"]))
    ok(b.proof_note(gig["id"], w["id"], "on my way"))
    ok(b.proof_checkout(gig["id"], w["id"]))
    ok(b.proof_signoff(gig["id"], "Cust", "5"))
    return gig, w


# L1 -----------------------------------------------------------------------
def test_l1_single_claim(ws):
    _to_active_dispatch()
    w1 = _worker(ws, name="Rosa")
    w2 = _worker(ws, name="Dev", cats="plumbing")
    gig = _gig(ws)
    ok(b.offer_make(gig["id"], w1["id"], "tester", True))
    ok(b.offer_accept(gig["id"], w1["id"]))
    # second worker cannot claim the same gig
    e = err(b.offer_accept(gig["id"], w2["id"]))
    assert "offer" in e.lower() or "accept" in e.lower() or "status" in e.lower()
    # and a fresh offer to the second worker is refused (not open anymore)
    e2 = err(b.offer_make(gig["id"], w2["id"], "tester", True))
    assert e2


# L2 -----------------------------------------------------------------------
def test_l2_settle_refused_before_proof(ws):
    _to_active_dispatch()
    gig = _gig(ws)
    e = err(b.settle_execute(gig["id"], "120", "cash", "ref-1", True))
    assert e  # not done / no sign-off


def test_l2_dispute_freezes_settlement(ws):
    gig, w = _full_loop(ws)
    ok(b.dispute_raise(gig["id"], "Cust", "not happy"))
    e = err(b.settle_execute(gig["id"], "120", "cash", "ref-1", True))
    assert "disput" in e.lower() or "frozen" in e.lower()


# L3 -----------------------------------------------------------------------
def test_l3_worker_keep_floor(ws):
    gig, w = _full_loop(ws)
    plan = ok(b.settle_plan(gig["id"], "200"))["plan"]
    assert plan["keep_rate"] >= 0.90, plan
    entry = ok(b.settle_execute(gig["id"], "200", "cash", "ref-9", True))["settlement"]
    assert entry["keep_rate"] >= 0.90
    assert entry["verified"] is True
    receipt = ok(b.settle_receipt(entry["id"]))["receipt"]
    assert "200" in receipt


# L4 -----------------------------------------------------------------------
def test_l4_gate_blocks_dispatch_at_waitlist(ws):
    stage = ok(b.gate_stage())["stage"]
    assert stage == "waitlist_only"
    w = _worker(ws)
    gig = _gig(ws)
    e = err(b.offer_make(gig["id"], w["id"], "tester", True))
    assert "gate" in e.lower()


# L5 -----------------------------------------------------------------------
def test_l5_bloodline_limits(ws):
    b.set_flavor("bloodline")
    assert "founder-only" in err(b.gate_advance("tester", True))
    assert "founder-only" in err(b.gate_override("tester", "active_dispatch", "x"))
    assert "founder-only" in err(b.dispute_resolve("d1", "tester", "release", "x"))
    assert "founder-only" in err(b.metering_log())
    assert json.loads(b.flavor())["limited"] is True


# L6 -----------------------------------------------------------------------
def test_l6_bloodline_metering(ws):
    b.set_flavor("bloodline")
    gig = _gig(ws)  # publish is metered even at waitlist stage
    b.set_flavor("founder")  # founder reads the log
    log = ok(b.metering_log())
    kinds = [e["kind"] for e in log["events"]]
    assert "gig_publish" in kinds
    assert all(e["flavor"] == "bloodline" for e in log["events"])


def test_l6_founder_not_metered(ws):
    _gig(ws)
    assert ok(b.metering_log())["count"] == 0


# L7 -----------------------------------------------------------------------
def test_l7_no_delete_path():
    for name in dir(b):
        assert "delete" not in name.lower(), name
        assert "remove" not in name.lower(), name
        assert not name.startswith("drop"), name


# verticals ----------------------------------------------------------------
def test_verticals_include_trades_and_tech_support(ws):
    cats = ok(b.categories())["categories"]
    for v in ("plumbing", "hvac", "electrical", "tech_support"):
        assert v in cats, cats


def test_category_match_ranks_trade_worker(ws):
    _to_active_dispatch()
    plumber = _worker(ws, name="Rosa", cats="plumbing")
    _worker(ws, name="Dev", cats="yard")
    gig = _gig(ws, category="plumbing")
    cands = ok(b.dispatch_candidates(gig["id"]))["candidates"]
    assert cands[0]["worker_id"] == plumber["id"]
    breakdown = {x["rule"]: x for x in cands[0]["breakdown"]}
    assert breakdown["category_match"]["matched"] is True


# zip-packaged seeding (Chaquopy app.imy) ----------------------------------
def test_zip_packaged_policies_seed(tmp_path):
    """On Android, levi.neighbor ships INSIDE Chaquopy's app.imy zip, so
    Path(__file__)-based seeding (store.ensure_policies) cannot copy the
    packaged default. The bridge must seed the workspace policies.json
    via importlib.resources, which reads zip-packaged data fine."""
    import subprocess
    import zipfile

    repo = Path(__file__).resolve().parents[1]
    src_tree = (repo / "apps" / "neighboros-android" / "neighboros" /
                "src" / "main" / "python")
    zippath = tmp_path / "app.imy"
    with zipfile.ZipFile(zippath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in src_tree.rglob("*"):
            if p.is_file() and "__pycache__" not in str(p):
                z.write(p, p.relative_to(src_tree).as_posix())
    script = (
        "import sys, json\n"
        f"sys.path.insert(0, {str(zippath)!r})\n"
        f"sys.path.insert(0, {(repo / 'apps' / 'neighboros-android' / 'python-src').as_posix()!r})\n"
        f"sys.path.insert(0, {(repo / 'core').as_posix()!r})\n"
        "import neighboros_bridge as nb\n"
        f"ws = {(tmp_path / 'ws').as_posix()!r}\n"
        "assert nb.set_workspace(ws) == 'true'\n"
        "d = json.loads(nb.categories())\n"
        "assert d['ok'], d\n"
        "assert 'tech_support' in d['categories'], d\n"
        "assert 'plumbing' in d['categories'], d\n"
        "from pathlib import Path\n"
        "pf = Path(ws) / 'neighboros' / 'dispatch' / 'policies.json'\n"
        "assert pf.exists(), 'workspace policies.json was not seeded'\n"
        "assert json.loads(pf.read_text())['worker_keep_floor'] == 0.9\n"
        "print('ZIP_SEED_OK')\n"
    )
    r = subprocess.run([sys.executable, "-c", script],
                       capture_output=True, text=True)
    assert "ZIP_SEED_OK" in r.stdout, r.stderr[-3000:]
