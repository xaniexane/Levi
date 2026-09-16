"""Tests for levi.shareware — the honest trial engine."""

import json
import os
import stat

import pytest

from levi.shareware import GrantStore, SharewareError


@pytest.fixture()
def store(tmp_path):
    return GrantStore(root=tmp_path / "sw")


NOW = 1_800_000_000.0


def test_issue_requires_a_bound(store):
    with pytest.raises(SharewareError):
        store.issue(pack="craft-pro", features=["export"])


def test_issue_validates_inputs(store):
    with pytest.raises(SharewareError):
        store.issue(pack="", features=["export"], days=30)
    with pytest.raises(SharewareError):
        store.issue(pack="x", features=[], days=30)
    with pytest.raises(SharewareError):
        store.issue(pack="x", features=["a"], days=0)
    with pytest.raises(SharewareError):
        store.issue(pack="x", features=["a"], max_uses=0)


def test_issue_and_get(store):
    g = store.issue(pack="craft-pro", features=["export", "pdf"], days=30, now=NOW)
    assert g.id.startswith("sw-")
    got = store.get(g.id)
    assert got.pack == "craft-pro"
    assert got.expires_at == NOW + 30 * 86400
    assert got.uses_left() is None  # no use bound


def test_uses_bound(store):
    g = store.issue(pack="x", features=["a"], max_uses=3, now=NOW)
    assert g.uses_left() == 3
    store.redeem(g.id, now=NOW)
    assert store.get(g.id).uses_left() == 2


def test_redeem_exhaustion_refused(store):
    g = store.issue(pack="x", features=["a"], max_uses=1, now=NOW)
    store.redeem(g.id, now=NOW)
    with pytest.raises(SharewareError):
        store.redeem(g.id, now=NOW)


def test_redeem_expired_refused(store):
    g = store.issue(pack="x", features=["a"], days=1, now=NOW)
    with pytest.raises(SharewareError) as ei:
        store.redeem(g.id, now=NOW + 2 * 86400)
    # honest refusal: data is untouched
    assert "untouched" in str(ei.value)


def test_redeem_unknown_feature_refused(store):
    g = store.issue(pack="x", features=["a"], days=30, now=NOW)
    with pytest.raises(SharewareError):
        store.redeem(g.id, feature="b", now=NOW)
    # covered feature redeems fine
    r = store.redeem(g.id, feature="a", now=NOW)
    assert r["feature"] == "a"


def test_revoke_and_refusal(store):
    g = store.issue(pack="x", features=["a"], days=30, now=NOW)
    store.revoke(g.id, reason="fraud", now=NOW)
    assert store.get(g.id).revoked is True
    with pytest.raises(SharewareError):
        store.redeem(g.id, now=NOW)


def test_redeem_unknown_grant_refused(store):
    with pytest.raises(SharewareError):
        store.redeem("sw-nope", now=NOW)


def test_ledger_is_hash_chained_and_verifies(store):
    g = store.issue(pack="x", features=["a"], days=30, now=NOW)
    store.redeem(g.id, now=NOW + 1)
    rep = store.verify()
    assert rep["ok"] is True
    assert rep["entries"] == 2


def test_ledger_tamper_detected(store):
    g = store.issue(pack="x", features=["a"], days=30, now=NOW)
    store.redeem(g.id, now=NOW + 1)
    ledger = store.root / "ledger.jsonl"
    lines = ledger.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[1])
    rec["uses"] = 999  # attacker edits history
    lines[1] = json.dumps(rec, sort_keys=True)
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rep = store.verify()
    assert rep["ok"] is False
    assert rep["bad"]


def test_store_dir_is_owner_only(store):
    mode = stat.S_IMODE(os.stat(store.root).st_mode)
    assert mode == 0o700


def test_terms_promise_data_not_hostage(store):
    g = store.issue(pack="craft-pro", features=["export"], days=7, now=NOW)
    t = g.terms_text()
    assert "never deletes" in t
    assert "hostage" in t
    assert "no account" in t.lower() or "No account" in t


def test_grant_serializes_roundtrip(store):
    g = store.issue(pack="x", features=["a"], days=1, max_uses=5, now=NOW)
    store2 = GrantStore(root=store.root)
    got = store2.get(g.id)
    assert got == g


def test_cli_issue_redeem_verify(tmp_path, capsys):
    root = tmp_path / "sw"
    import levi.shareware.__main__ as m

    orig = m._store
    m._store = lambda: GrantStore(root=root)
    try:
        assert m.main(["issue", "--pack", "x", "--features", "a", "--days", "30"]) == 0
        out = capsys.readouterr().out
        gid = out.splitlines()[0].strip()
        assert gid.startswith("sw-")
        assert m.main(["redeem", gid]) == 0
        assert m.main(["verify"]) == 0
        # terms prints the honest promise
        assert m.main(["terms", gid]) == 0
        out = capsys.readouterr().out
        assert "hostage" in out
        # bad issue is refused, not crashed
        assert m.main(["issue", "--pack", "x", "--features", "a"]) == 1
    finally:
        m._store = orig
