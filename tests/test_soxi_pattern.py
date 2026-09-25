"""SOXI pattern tests — run from zero: python3 -m pytest tests/test_soxi_pattern.py -q"""

import time

import pytest

from levi.soxi.fr_friction import FrictionStore
from levi.soxi.et_etch import EtchBoard
from levi.soxi.ln_router import LoomRouter
from levi.soxi.wc_witness import WitnessLog
from levi.soxi.th_threshold import Threshold
from levi.soxi.dr_drift import DriftTimeline
from levi.soxi.sh_shadow import ShadowLog
from levi.soxi.cv_cadence import rhythm_vector, read_vector
from levi.soxi.xi_gremlin import GremlinLab
from levi.soxi.gr_gleaner import Gleaner
from levi.soxi.bt_bent import BentMind


def test_fr_learns_from_correction(tmp_path):
    fr = FrictionStore(tmp_path)
    fr.correct("hey levion the the to the", "hey levi, what's up", mood="annoyed")
    fixed, hit = fr.apply("hey levion the the to the")
    assert fixed == "hey levi, what's up"
    assert hit is not None and hit["overlap"] >= 0.85
    # unrelated text untouched
    same, hit2 = fr.apply("what time is the meeting tomorrow")
    assert same == "what time is the meeting tomorrow" and hit2 is None
    assert fr.export_pairs() == [("hey levion the the to the", "hey levi, what's up")]
    fr.close()


def test_et_chain_verifies_and_detects_tamper(tmp_path):
    board = EtchBoard(tmp_path)
    r0 = board.etch("Don't take freelance work that kills weekends.", kind="law")
    board.annotate(r0["seq"], "added after the june burnout")
    ok, bad = board.verify()
    assert ok and bad is None
    # tamper with the file
    lines = board.path.read_text().splitlines()
    import json
    rec = json.loads(lines[0])
    rec["text"] = "Take all freelance work."
    lines[0] = json.dumps(rec)
    board.path.write_text("\n".join(lines) + "\n")
    ok2, bad2 = board.verify()
    assert not ok2 and bad2 == 0


def test_et_check_decision_flags_law(tmp_path):
    board = EtchBoard(tmp_path)
    board.etch("Don't take freelance work that kills weekends.", kind="law")
    hits = board.check_decision("should I take this freelance gig this weekend")
    assert any(h["text"].startswith("Don't take freelance") for h in hits)


def test_ln_routes_and_learns(tmp_path):
    router = LoomRouter(tmp_path)
    top = router.route("rewrite this in my voice please")[0][0]
    assert top == "FR"
    router.record_outcome("FR", True)
    router.record_outcome("FR", True)
    assert router.status()["scoreboard"]["FR"] == {"win": 2, "loss": 0}


def test_wc_silent_until_reveal(tmp_path):
    wc = WitnessLog(tmp_path, reveal_after_s=30 * 86400)
    wc.observe("tired tuesday")
    r = wc.reveal()
    assert not r["revealed"] and "silent" in r["reason"]
    wc2 = WitnessLog(tmp_path, reveal_after_s=0)
    r2 = wc2.reveal()
    assert r2["revealed"] and r2["entries"][0][1] == "tired tuesday"


def test_th_speaks_on_third_circle(tmp_path):
    th = Threshold(tmp_path, name="demo", circles=3)
    assert not th.observe("late-night doubt")["spoke"]
    assert not th.observe("late-night doubt")["spoke"]
    third = th.observe("late-night doubt")
    assert third["spoke"] and len(third["events"]) == 3
    # resets after speaking
    assert not th.observe("late-night doubt")["spoke"]


def test_dr_reports_drift(tmp_path):
    dr = DriftTimeline(tmp_path)
    first = dr.note("freelance", "I will never do freelance again")
    assert first["drift"] == 0.0
    second = dr.note("freelance", "maybe one small freelance project")
    assert second["drift"] > 0.3
    assert len(dr.timeline("freelance")) == 2
    dr.close()


def test_sh_nudge_and_quit_hours(tmp_path):
    sh = ShadowLog(tmp_path)
    sh.log_abandoned("draft email", task_type="writing", context="tired")
    nudge = sh.nudge("draft email", task_type="writing")
    assert "Smallest next step" in nudge
    sh.close()


def test_cv_vector_is_12_bytes():
    vec = rhythm_vector([95.0, 110.0, 400.0, 90.0])
    assert len(vec) == 12
    read = read_vector(vec)
    assert "heuristic_read" in read


def test_xi_ledger(tmp_path):
    lab = GremlinLab(tmp_path)
    lab.experiment("tone-shift", "append one FR pair", "0.001s cpu", "rewrite matched")
    assert lab.summary()["experiments"] == 1


def test_gr_metadata_only(tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "idea.txt").write_text("secret contents here")
    g = Gleaner(tmp_path / "data")
    n = g.scan([tmp_path / "notes"])
    assert n >= 1
    hits = g.search("idea")
    assert hits and hits[0]["name"] == "idea.txt"
    # contents never stored
    assert "secret contents" not in g.db_path.read_bytes().decode("utf-8", "ignore")
    g.close()


def test_bt_offline_stub_without_runner(tmp_path, monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda *_: None)
    mind = BentMind(domain="journal")
    res = mind.generate("today was heavy")
    assert res.backend == "stub" and "no local model installed" in res.text


def test_bt_rejects_unknown_domain():
    with pytest.raises(ValueError):
        BentMind(domain="do-everything")
