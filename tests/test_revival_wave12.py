"""Hermetic tests for wave 12: forge-additions (a) — sovereign code-home features."""

from __future__ import annotations

import json

import pytest

from levi.revival.full_export import BUNDLE_FORMAT, FullExport
from levi.revival.signed_reputation import Attestation, KeyPair, ReputationWallet
from levi.revival.no_training_charter import NoTrainingCharter
from levi.revival.local_ci import LocalCI, Pipeline, Runner, Step
from levi.revival.offline_noaccount import LocalHome
from levi.revival.open_federation import FederationNode
from levi.revival.byo_import import Importer
from levi.revival.chronological_discovery import Discovery, Item


# ---------------------------------------------------------------- full_export
def test_export_everything_writes_manifest_and_sections(tmp_path):
    exp = FullExport("my-home")
    exp.collect_repo("levi", [{"sha": "abc", "message": "init", "at": 1.0}])
    exp.collect("issues", [{"number": 1, "title": "bug"}])
    dest = exp.export_everything(tmp_path / "bundle")
    manifest = json.loads((dest / "MANIFEST.json").read_text())
    assert manifest["format"] == BUNDLE_FORMAT
    assert manifest["home"] == "my-home"
    assert manifest["total_records"] == 2
    assert (dest / "README.md").read_text().startswith("# Full export")


def test_verify_detects_tampered_section(tmp_path):
    exp = FullExport("home")
    exp.collect("stars", [{"repo": "a/b"}])
    dest = exp.export_everything(tmp_path / "bundle")
    assert FullExport.verify(dest)["intact"] is True
    # tamper with the section file
    (dest / "stars.json").write_text('{"section": "stars", "records": []}')
    result = FullExport.verify(dest)
    assert result["intact"] is False
    assert result["broken"] == ["stars"]


def test_read_bundle_roundtrip(tmp_path):
    exp = FullExport("home")
    exp.collect("follows", [{"user": "ada"}, {"user": "grace"}])
    dest = exp.export_everything(tmp_path / "bundle")
    back = FullExport.read_bundle(dest)
    assert [r["user"] for r in back["follows"]] == ["ada", "grace"]


# ------------------------------------------------------- signed_reputation
def _keys():
    return KeyPair.generate(), KeyPair.generate()


def test_sign_verify_roundtrip():
    issuer, subject = _keys()
    att = Attestation(
        issuer=issuer.public_hex(),
        subject=subject.public_hex(),
        kind="endorsement",
        payload={"note": "writes careful parsers"},
    ).sign_with(issuer)
    assert att.verify() is True


def test_tampered_payload_fails_verification():
    issuer, subject = _keys()
    att = Attestation(
        issuer=issuer.public_hex(), subject=subject.public_hex(), kind="contribution"
    ).sign_with(issuer)
    att.payload["forged"] = True
    assert att.verify() is False


def test_wrong_issuer_key_fails_verification():
    issuer, subject = _keys()
    other = KeyPair.generate()
    att = Attestation(
        issuer=issuer.public_hex(), subject=subject.public_hex(), kind="endorsement"
    ).sign_with(issuer)
    att.issuer = other.public_hex()  # attacker swaps the claimed issuer
    assert att.verify() is False


def test_wallet_verify_all_and_portable_roundtrip():
    issuer, subject = _keys()
    wallet = ReputationWallet()
    wallet.add(
        Attestation(
            issuer=issuer.public_hex(),
            subject=subject.public_hex(),
            kind="contribution",
        ).sign_with(issuer)
    )
    bad = Attestation(
        issuer=issuer.public_hex(), subject=subject.public_hex(), kind="endorsement"
    )  # unsigned
    wallet.add(bad)
    result = wallet.verify_all()
    assert result == {"valid": [0], "invalid": [1]}
    # portable export/import survives the trip and still verifies
    wallet2 = ReputationWallet.import_portable(wallet.export_portable())
    assert wallet2.verify_all() == {"valid": [0], "invalid": [1]}


# ------------------------------------------------------ no_training_charter
def test_charter_renders_plain_language_guarantees():
    charter = NoTrainingCharter(adopted_by="chauncey")
    text = charter.current().render()
    assert "never trains anyone's model" in text
    assert "version 1" in text


def test_check_flags_model_training_upload():
    charter = NoTrainingCharter()
    compliant, violated, _notes = charter.check(
        {
            "kind": "upload_code",
            "description": "upload repo to train a model",
            "destination": "cloud-model-training",
        }
    )
    assert compliant is False
    assert "C1" in violated


def test_check_allows_benign_local_action():
    charter = NoTrainingCharter()
    compliant, violated, notes = charter.check(
        {"kind": "export", "description": "export my repos to a local bundle"}
    )
    assert compliant is True
    assert violated == []
    assert any("heuristic" in n for n in notes)


def test_opt_in_gates_on_device_training():
    charter = NoTrainingCharter()
    action = {"kind": "train", "description": "train on-device assistant on my corpus"}
    compliant, violated, _ = charter.check(action, user="chauncey")
    assert compliant is False and "C4" in violated  # no consent yet
    charter.opt_in("chauncey")
    compliant, violated, _ = charter.check(action, user="chauncey")
    assert compliant is True and violated == []
    charter.revoke("chauncey")
    compliant, violated, _ = charter.check(action, user="chauncey")
    assert compliant is False and "C4" in violated  # revoked: blocked again


def test_amend_supersedes_without_editing_history():
    charter = NoTrainingCharter()
    v2 = charter.amend(charter.current().clauses)
    assert v2.number == 2
    assert [v.number for v in charter.history()] == [1, 2]
    assert charter.current().number == 2


# ----------------------------------------------------------------- local_ci
def test_pipeline_runs_steps_in_dependency_order(tmp_path):
    (tmp_path / "order.txt").write_text("")
    pipe = Pipeline("build")
    pipe.add_step(
        Step("first", ["sh", "-c", f"echo first >> {tmp_path}/order.txt"])
    ).add_step(
        Step(
            "second",
            ["sh", "-c", f"echo second >> {tmp_path}/order.txt"],
            needs=["first"],
        )
    )
    result = Runner().run_pipeline(pipe)
    assert result.ok
    assert (tmp_path / "order.txt").read_text().split() == ["first", "second"]


def test_failing_step_stops_pipeline_and_records_output():
    pipe = Pipeline("bad")
    pipe.add_step(Step("boom", ["sh", "-c", "echo the-error >&2; exit 3"]))
    pipe.add_step(Step("never", ["sh", "-c", "exit 0"]))
    result = Runner().run_pipeline(pipe)
    assert not result.ok
    assert result.failed_step == "boom"
    assert len(result.records) == 1  # second step never ran
    assert result.records[0].exit_code == 3
    assert "the-error" in result.records[0].stderr


def test_retries_recover_a_flaky_step(tmp_path):
    flag = tmp_path / "flag"
    pipe = Pipeline("flaky")
    pipe.add_step(
        Step(
            "flaky",
            ["sh", "-c", f"test -f {flag} || (touch {flag}; exit 1)"],
            retries=1,
        )
    )
    result = Runner().run_pipeline(pipe)
    assert result.ok
    assert result.records[-1].attempt == 1


def test_no_minute_metering_and_queue_drain():
    ci = LocalCI()
    pipe = Pipeline("p")
    pipe.add_step(Step("ok", ["true"]))
    ci.enqueue(pipe)
    assert ci.queued() == ["p"]
    results = ci.drain()
    assert len(results) == 1 and results[0].ok
    assert ci.queued() == []
    assert LocalCI.minutes_used() == 0
    assert LocalCI.minutes_remaining() == float("inf")


def test_dependency_cycle_is_rejected():
    pipe = Pipeline("cycle")
    pipe.add_step(Step("a", ["true"], needs=["b"]))
    pipe.add_step(Step("b", ["true"], needs=["a"]))
    with pytest.raises(ValueError, match="cycle"):
        Runner().run_pipeline(pipe)


# ------------------------------------------------------- offline_noaccount
def test_local_home_works_with_no_account():
    home = LocalHome(owner="chauncey")
    home.add_repo("levi")
    home.commit("levi", "sha1", "init")
    home.open_issue(1, "first bug")
    home.open_pr(1, "first pr")
    home.star("someone/else")
    assert home.identity.fingerprint  # self-made, no registry
    assert len(home.repos["levi"].commits) == 1
    assert home.stars == ["someone/else"]


def test_peer_sync_merges_both_sides():
    a = LocalHome(owner="a")
    b = LocalHome(owner="b")
    a.open_issue(1, "from a")
    b.open_issue(2, "from b")
    report = a.sync_with_peer(b)
    assert report["issues"] == [1, 2]
    assert b.issues[1].title == "from a"  # symmetric: b learned too
    assert a.conflicts() == []


def test_peer_sync_logs_conflict_on_newer_peer_edit():
    a = LocalHome(owner="a")
    b = LocalHome(owner="b")
    a.open_issue(1, "old title")
    a.issues[1].updated_at = 100.0
    b.open_issue(1, "newer title")
    b.issues[1].updated_at = 200.0
    a.sync_with_peer(b)
    assert a.issues[1].title == "newer title"
    conflicts = a.conflicts()
    assert len(conflicts) == 1
    assert conflicts[0].chosen == "peer"


# ---------------------------------------------------------- open_federation
def test_handshake_negotiates_highest_common_version():
    a = FederationNode("a", versions=(1, 2))
    b = FederationNode("b", versions=(1,))
    assert a.handshake(b) == 1
    assert a.remotes["b"] is b


def test_handshake_fails_with_no_common_version():
    a = FederationNode("a", versions=(2,))
    b = FederationNode("b", versions=(1,))
    with pytest.raises(ValueError, match="no common protocol version"):
        a.handshake(b)


def test_replicate_converges_both_sides():
    a = FederationNode("a")
    b = FederationNode("b")
    a.handshake(b)
    a.track_commits("levi", ["c1", "c2"])
    b.track_commits("levi", ["c1", "c2"])
    a.set_ref("levi", "c1")
    b.set_ref("levi", "c2")
    report = a.replicate("b")
    assert report["fast_forwarded"] == ["levi"]
    assert a.refs["levi"] == "c2"  # a caught up


def test_diverged_refs_are_flagged_never_merged():
    a = FederationNode("a")
    b = FederationNode("b")
    a.handshake(b)
    a.set_ref("levi", "aaa")  # no shared chain: neither is an ancestor
    b.set_ref("levi", "bbb")
    report = a.replicate("b")
    assert report["diverged"] == ["levi"]
    assert a.refs["levi"] == "aaa"  # untouched
    assert b.refs["levi"] == "bbb"  # untouched
    assert any(e.event == "divergence" for e in a.audit)


# ---------------------------------------------------------------- byo_import
def _bundle():
    return {
        "code": [
            {
                "repo": "levi",
                "commits": [{"sha": "c1", "message": "init"}],
                "readme": "hi",
            }
        ],
        "issues": [{"number": 1, "title": "bug", "state": "open"}],
        "pull_requests": [
            {"number": 2, "title": "fix", "base": "main", "head": "patch"}
        ],
        "wikis": [{"repo": "levi", "page": "Home", "body": "welcome"}],
        "stars": [{"repo": "a/b"}],
        "follows": [{"user": "ada"}],
    }


def test_import_everything_lands_all_kinds():
    importer = Importer()
    report = importer.import_everything(_bundle())
    assert report.total_landed() == 6
    assert importer.home.repos["levi"].commits[0]["sha"] == "c1"
    assert importer.home.issues[1].title == "bug"
    assert importer.home.pull_requests[2].head == "patch"
    assert importer.wikis["levi"]["Home"] == "welcome"
    assert importer.home.stars == ["a/b"]
    assert importer.follows == ["ada"]


def test_import_is_idempotent():
    importer = Importer()
    importer.import_everything(_bundle())
    report = importer.import_everything(_bundle())
    assert report.total_landed() == 0
    assert report.skipped["code"] == 1
    assert "code: 1 landed" not in report.summary()


def test_unknown_sections_are_reported_not_dropped():
    importer = Importer()
    report = importer.import_everything({"mystery": [{"x": 1}]})
    assert report.unhandled == ["mystery"]
    assert "unhandled sections: mystery" in report.summary()


# ------------------------------------------------- chronological_discovery
def test_timeline_is_strictly_reverse_chronological():
    feed = Discovery()
    feed.add(Item("old", "repo", "a", "Old", at=100.0))
    feed.add(Item("new", "repo", "a", "New", at=300.0))
    feed.add(Item("mid", "repo", "a", "Mid", at=200.0))
    assert [i.id for i in feed.timeline()] == ["new", "mid", "old"]


def test_filtered_narrows_without_reordering():
    feed = Discovery()
    feed.add(Item("r1", "repo", "ada", "R1", at=100.0, tags=["synthetic"]))
    feed.add(Item("p1", "person", "grace", "P1", at=200.0))
    feed.add(Item("r2", "repo", "ada", "R2", at=300.0, tags=["synthetic"]))
    result = feed.filtered(kinds=["repo"], tags=["synthetic"])
    assert [i.id for i in result] == ["r2", "r1"]  # still newest-first


def test_ranked_refuses_until_user_opts_in():
    feed = Discovery()
    feed.add(Item("a", "repo", "x", "A", at=1.0))
    with pytest.raises(RuntimeError, match="enable_ranking"):
        feed.ranked()
    assert not feed.ranking_enabled
    feed.enable_ranking(lambda item: 1.0 if item.author == "x" else 0.0, name="by-x")
    assert feed.ranking_enabled
    assert [i.id for i in feed.ranked()] == ["a"]
    feed.disable_ranking()
    assert not feed.ranking_enabled
