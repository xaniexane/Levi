"""Tests for the Omega Triple Threat Elite host-agnostic surgeon core.

Hermetic: SnapshotStore takes tmp_path (no HOME writes), no network, no
randomness. All fixtures synthetic.

Laws under machine check:
  L1 snapshot-before-mutation
  L2 never silent apply (confirmed=True or fail closed; allow-hook denial)
  L3 documentation is never deleted (anti comment-compression guard)
  L4 behavioral parity with the original levi_surgeon.js rules
  L5 four version modes, withholding modes gated
"""

import re

import pytest

from levi.surgeon.triple_threat import (
    VERSION_MODES,
    AcodeAdapter,
    DocLossError,
    HicombAdapter,
    SnapshotStore,
    apply_advancement,
    approve_and_write,
    assert_no_doc_loss,
    cleanup,
    default_owner,
    format_version,
    propose_advancements,
)

_EQ_NONE = re.compile(r"(\b\w+)\s*==\s*None\b")
_NE_NONE = re.compile(r"(\b\w+)\s*!=\s*None\b")


def _mgr(tmp_path):
    return SnapshotStore(path=tmp_path / "snaps.json")


# ---------------------------------------------------------------------------
# L4 — parity with the original's five rules
# ---------------------------------------------------------------------------


def test_tabs_become_two_spaces_not_four():
    # The original uses 2 spaces; the 4-space ports deviate.
    res = cleanup("def f():\n\tx = 1\n")
    assert res.text == "def f():\n  x = 1\n"
    assert res.fixes["tabs"] == 1


def test_trailing_whitespace_stripped():
    res = cleanup("x = 1   \ny = 2\t\n")
    assert res.text == "x = 1\ny = 2\n"
    assert res.fixes["trailing_whitespace"] == 1


def test_blank_runs_collapse_to_three():
    res = cleanup("a\n\n\n\n\nb\n")
    assert res.text == "a\n\n\nb\n"
    assert res.fixes["blank_lines"] == 1


def test_none_rewrites_counted_per_occurrence():
    res = cleanup("if x == None or y == None:\n    z = w != None\n")
    assert res.text == "if x is None or y is None:\n    z = w is not None\n"
    assert res.fixes["eq_none"] == 2
    assert res.fixes["ne_none"] == 1


def test_none_word_boundary():
    res = cleanup("x = NoneType\n")  # must not touch
    assert res.text == "x = NoneType\n"
    assert res.total == 0


def test_trailing_newline_state_preserved():
    assert cleanup("x = 1\n").text == "x = 1\n"
    assert cleanup("x = 1").text == "x = 1"  # no newline added
    assert cleanup("x = 1   ").text == "x = 1"  # strip, still no newline added


def test_cleanup_rejects_non_str():
    with pytest.raises(ValueError, match="must be str"):
        cleanup(123)


# ---------------------------------------------------------------------------
# Property gates
# ---------------------------------------------------------------------------

_ADVERSARIAL = [
    "x=1",
    "",
    "\n",
    "\t\tindented\n",
    "a\n\n\n\n\n\n\nb",
    "x = 1   \n\t\n  \n",
    "# c1\n# c2\n# c3\n# c4\n# c5\n# c6\n# c7\n# c8\n# c9\n# c10\n# c11\nx=1\n",
    '"""docstring"""\n# license header\n# Copyright (c) 2026 X\n\n\n\n\ndef f():\n\treturn None\n',
    "if a == None:\n\tb != None\n",
    "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\nimport os\n",
    "x='a\\tb'\n",  # tab inside a string literal — still normalized (textual rule)
    "\u00a0nbsp\u00a0\n",  # non-breaking space is NOT trailing-ws per the rule
]


def test_cleanup_idempotent():
    for src in _ADVERSARIAL:
        once = cleanup(src).text
        twice = cleanup(once).text
        assert twice == once, f"not idempotent for {src!r}"


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def test_cleanup_preserves_non_whitespace_tokens():
    """Only whitespace and the documented None rewrites may change."""
    for src in _ADVERSARIAL:
        got = cleanup(src).text
        expected = _norm(_NE_NONE.sub(r"\1isnotNone", _EQ_NONE.sub(r"\1isNone", src)))
        assert _norm(got) == expected, f"token loss for {src!r}"


def test_doc_loss_guard_blocks_comment_compression():
    # The old Omega-script bug: 10+ comment lines got deleted. Here they survive.
    src = "".join(f"# documentation line {i}\n" for i in range(25)) + "x = 1\n"
    got = cleanup(src).text
    assert_no_doc_loss(src, got)
    assert got.count("# documentation line") == 25


def test_doc_loss_guard_raises_on_synthetic_loss():
    before = "# keep me\nx = 1\n"
    after = "x = 1\n"
    with pytest.raises(DocLossError, match="delete documentation"):
        assert_no_doc_loss(before, after)


def test_doc_loss_guard_counts_multiplicity():
    before = "# dup\n# dup\nx=1\n"
    after = "# dup\nx=1\n"  # one of two identical lines vanished
    with pytest.raises(DocLossError):
        assert_no_doc_loss(before, after)


# ---------------------------------------------------------------------------
# L1 — snapshot before every mutation
# ---------------------------------------------------------------------------


def test_apply_advancement_snapshots_first(tmp_path):
    mgr = _mgr(tmp_path)
    src = "x = 1   \n"
    r = apply_advancement(src, "adv_elite_cleanup", confirmed=True, snapshots=mgr)
    assert r["ok"] is True
    assert mgr.revert(r["snapshot_id"]) == src


def test_approve_and_write_snapshots_original(tmp_path):
    mgr = _mgr(tmp_path)
    p = tmp_path / "f.py"
    p.write_text("orig\n")
    r = approve_and_write(p, "new\n", snapshots=mgr, confirmed=True)
    assert r["ok"] is True
    assert mgr.revert(r["snapshot_id"]) == "orig\n"
    assert p.read_text() == "new\n"


def test_snapshot_store_roundtrip(tmp_path):
    m = _mgr(tmp_path)
    sid = m.take("lbl", "code\n")
    assert m.list()[0]["id"] == sid
    assert "code" not in m.list()[0]
    assert m.revert(sid) == "code\n"
    assert m.revert("nope") is None
    m2 = _mgr(tmp_path)
    assert m2.revert(sid) == "code\n"


# ---------------------------------------------------------------------------
# L2 — never silent apply
# ---------------------------------------------------------------------------


def test_apply_advancement_requires_confirmation(tmp_path):
    r = apply_advancement("x=1\n", "adv_elite_cleanup", snapshots=_mgr(tmp_path))
    assert r["ok"] is False
    assert "approval" in r["reason"]


def test_apply_advancement_honors_allow_hook_denial(tmp_path):
    r = apply_advancement(
        "x=1\n",
        "adv_elite_cleanup",
        snapshots=_mgr(tmp_path),
        allow=lambda action, ctx: False,
        confirmed=True,
    )
    assert r["ok"] is False
    assert "denied" in r["reason"]


def test_apply_advancement_honors_custom_allow(tmp_path):
    seen = {}

    def allow(action, ctx):
        seen["action"] = action
        return True

    r = apply_advancement(
        "x=1\n", "adv_guard_null", snapshots=_mgr(tmp_path), allow=allow
    )
    assert r["ok"] is True
    assert seen["action"] == "enhance"  # his cybrus.allow('enhance', opts) gate


def test_apply_advancement_unknown_id_fails_closed(tmp_path):
    r = apply_advancement("x=1\n", "adv_nope", snapshots=_mgr(tmp_path), confirmed=True)
    assert r["ok"] is False


def test_approve_and_write_requires_confirmation(tmp_path):
    p = tmp_path / "f.py"
    p.write_text("orig\n")
    r = approve_and_write(p, "new\n", snapshots=_mgr(tmp_path), confirmed=False)
    assert r["ok"] is False
    assert p.read_text() == "orig\n"  # untouched on the failure path


def test_approve_and_write_refuses_empty(tmp_path):
    p = tmp_path / "f.py"
    p.write_text("orig\n")
    r = approve_and_write(p, "   \n", snapshots=_mgr(tmp_path), confirmed=True)
    assert r["ok"] is False
    assert p.read_text() == "orig\n"


# ---------------------------------------------------------------------------
# L5 — four version modes, his exact semantics
# ---------------------------------------------------------------------------


def test_four_version_modes_present():
    assert set(VERSION_MODES) == {
        "closed_private",
        "opensource_minimal",
        "encrypted_stub",
        "pay_tier_limited",
    }
    assert VERSION_MODES["encrypted_stub"].limit_scale == 0.12
    assert VERSION_MODES["pay_tier_limited"].limit_scale == 0.40


def test_closed_private_header_shape():
    r = format_version("x = 1\n", "closed_private", owner="T. Tester")
    assert "CLOSED SOURCE" in r.text
    assert "T. Tester" in r.text
    assert r.text.endswith("x = 1\n")


def test_oss_header_shape():
    r = format_version("x = 1\n", "opensource_minimal", owner="T. Tester")
    assert "SPDX-License-Identifier: MIT" in r.text


def test_header_already_present_untouched():
    src = "/**\n * CLOSED SOURCE – All Rights Reserved\n */\n\nx = 1\n"
    r = format_version(src, "closed_private", owner="T. Tester")
    assert r.text == src
    assert r.note == "header already present"


def test_withholding_modes_require_confirmation():
    body = "line\n" * 100
    for mode in ("encrypted_stub", "pay_tier_limited"):
        r = format_version(body, mode, owner="T. Tester", confirmed=False)
        assert r.text == body  # refused: input returned unchanged
        assert "confirmation" in r.note


def test_encrypted_stub_limits_body():
    body = "x = %d\n" % 1 * 200  # long body
    r = format_version(body, "encrypted_stub", owner="T. Tester", confirmed=True)
    assert "ENCRYPTED DISTRIBUTION STUB" in r.text
    assert "encrypted body omitted" in r.text
    assert len(r.text) < len(body)


def test_pay_tier_limits_lines():
    body = "".join(f"line {i}\n" for i in range(100))
    r = format_version(body, "pay_tier_limited", owner="T. Tester", confirmed=True)
    assert "TRIAL / TIER-LIMITED" in r.text
    assert r.text.count("\n") < 100


def test_unknown_mode_raises():
    with pytest.raises(ValueError, match="unknown mode"):
        format_version("x\n", "nope")


def test_default_owner_precedence(monkeypatch):
    assert default_owner("Explicit") == "Explicit"
    monkeypatch.setenv("LEVI_OWNER_NAME", "Env Owner")
    assert default_owner() == "Env Owner"
    monkeypatch.delenv("LEVI_OWNER_NAME")
    assert default_owner() == "Chauncey (CJ) Logan — LEVI Apex"  # his original default


# ---------------------------------------------------------------------------
# Advancements — his ids
# ---------------------------------------------------------------------------


def test_advancement_ids_match_original():
    ids = {a.id for a in propose_advancements("x=1\n", "f.js")}
    assert ids == {
        "adv_guard_null",
        "adv_log_entry",
        "adv_pure_helpers",
        "adv_hitl_wrap",
        "adv_version_closed",
        "adv_version_oss",
        "adv_elite_cleanup",
    }


def test_python_gets_type_hint_proposal():
    ids = {a.id for a in propose_advancements("x=1\n", "f.py")}
    assert "adv_type_hints" in ids


def test_apply_hitl_wrap_uses_hash_for_python(tmp_path):
    r = apply_advancement(
        "x=1\n",
        "adv_hitl_wrap",
        filename="f.py",
        snapshots=_mgr(tmp_path),
        confirmed=True,
    )
    assert r["code"].startswith("# LEVI HITL")


def test_apply_hitl_wrap_uses_slashes_for_js(tmp_path):
    r = apply_advancement(
        "x=1\n",
        "adv_hitl_wrap",
        filename="f.js",
        snapshots=_mgr(tmp_path),
        confirmed=True,
    )
    assert r["code"].startswith("// LEVI HITL")


def test_apply_log_entry_python(tmp_path):
    r = apply_advancement(
        "def f():\n    pass\n",
        "adv_log_entry",
        filename="f.py",
        snapshots=_mgr(tmp_path),
        confirmed=True,
    )
    assert "# LEVI entry: f" in r["code"]


# ---------------------------------------------------------------------------
# Adapters — thin, host-shaped, no I/O
# ---------------------------------------------------------------------------


def test_acode_adapter_cleanup_shape():
    out = AcodeAdapter.cleanup("x = 1   \n")
    assert out["text"] == "x = 1\n"
    assert out["total"] == 1
    assert set(out) == {"text", "fixes", "total"}


def test_acode_adapter_apply_gated(tmp_path):
    denied = AcodeAdapter.apply("x=1\n", "adv_elite_cleanup", confirmed=False)
    assert denied["ok"] is False
    ok = AcodeAdapter.apply(
        "x=1\n", "adv_elite_cleanup", confirmed=True, snapshots=_mgr(tmp_path)
    )
    assert ok["ok"] is True


def test_hicomb_adapter_operate_receipt(tmp_path):
    out = HicombAdapter.operate("x = 1   \n", uri="hicomb://buf/1", confirmed=False)
    assert out["ok"] is True
    assert out["buffer"] == "x = 1\n"
    assert out["receipt"]["instrument"] == "triple_threat.operate"
    assert out["receipt"]["uri"] == "hicomb://buf/1"
    assert out["receipt"]["applied"] is None  # not confirmed -> propose only


def test_hicomb_adapter_operate_confirmed_applies(tmp_path):
    out = HicombAdapter.operate(
        "x = 1   \n", uri="hicomb://buf/1", confirmed=True, snapshots=_mgr(tmp_path)
    )
    assert out["receipt"]["applied"]["adv_id"] == "adv_elite_cleanup"
    assert out["receipt"]["applied"]["snapshot_id"].startswith("snap_")


def test_hicomb_adapter_withholding_mode_refused_without_confirm():
    out = HicombAdapter.stamp("x=1\n" * 50, "encrypted_stub", uri="hicomb://buf/2")
    assert out["ok"] is False
    assert "confirmation" in out["receipt"]["note"]


def test_adapters_do_no_io(tmp_path):
    probe = tmp_path / "probe.txt"
    probe.write_text("x")
    before = probe.stat().st_mtime_ns
    AcodeAdapter.cleanup("x = 1   \n")
    HicombAdapter.operate("y = 2   \n")
    assert probe.stat().st_mtime_ns == before
    assert probe.read_text() == "x"


# ---------------------------------------------------------------------------
# Regression tests from the 5-pass elite audit (⛏️)
# ---------------------------------------------------------------------------


def test_format_version_none_code_withholding_confirmed():
    # Degenerate input must not crash the omitted-chars accounting.
    r = format_version(None, "encrypted_stub", owner="T. Tester", confirmed=True)
    assert r.ok is True
    assert "ENCRYPTED DISTRIBUTION STUB" in r.text


def test_cleanup_comment_with_none_comparison_survives():
    # The doc-loss guard must tolerate the documented None rewrites
    # inside comments — the original rewrites them too.
    res = cleanup("# check: x == None means unset\nx = 1\n")
    assert res.text == "# check: x is None means unset\nx = 1\n"


def test_cleanup_comment_with_tab_survives():
    res = cleanup("#\tindented comment\nx = 1\n")
    assert res.text == "#  indented comment\nx = 1\n"


def test_cleanup_js_comment_with_none_survives():
    res = cleanup("// x == None means unset\nx = 1;\n")
    assert res.text == "// x is None means unset\nx = 1;\n"


def test_doc_loss_guard_still_catches_real_deletion():
    before = "// gone\nx = 1;\n"
    after = "x = 1;\n"
    with pytest.raises(DocLossError):
        assert_no_doc_loss(before, after)


def test_doc_loss_guard_tolerates_rewrite_collision():
    # Two comments converging under a documented rewrite is not deletion.
    before = "# x == None\n# x is None\n"
    after = "# x is None\n# x is None\n"
    assert_no_doc_loss(before, after)  # must not raise


def test_adv_log_entry_gets_own_line(tmp_path):
    r = apply_advancement(
        "function f() { return 1; }",
        "adv_log_entry",
        filename="f.js",
        snapshots=_mgr(tmp_path),
        confirmed=True,
    )
    assert r["code"].startswith("function f() {\n  // LEVI entry: f\n")


def test_adv_log_entry_python_gets_own_line(tmp_path):
    r = apply_advancement(
        "def f(): return 1",
        "adv_log_entry",
        filename="f.py",
        snapshots=_mgr(tmp_path),
        confirmed=True,
    )
    assert r["code"].startswith("def f():\n    # LEVI entry: f\n")


def test_stamped_result_ok_flag():
    body = "x = 1\n" * 50
    refused = format_version(body, "encrypted_stub", confirmed=False)
    assert refused.ok is False
    assert refused.text == body
    stamped = format_version("x = 1\n", "closed_private", owner="T. Tester")
    assert stamped.ok is True


def test_acode_adapter_stamp_confirmed_passthrough():
    body = "x = 1\n" * 50
    denied = AcodeAdapter.stamp(body, "encrypted_stub")
    assert denied["ok"] is False
    assert denied["text"] == body
    ok = AcodeAdapter.stamp(body, "encrypted_stub", confirmed=True)
    assert ok["ok"] is True
    assert "ENCRYPTED DISTRIBUTION STUB" in ok["text"]


def test_hicomb_adapter_stamp_confirmed_passthrough():
    body = "x = 1\n" * 50
    out = HicombAdapter.stamp(body, "pay_tier_limited", uri="u", confirmed=True)
    assert out["ok"] is True
    assert "TRIAL / TIER-LIMITED" in out["buffer"]


def test_approve_and_write_root_confinement(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    inside = root / "sub" / "f.py"
    r = approve_and_write(
        inside, "new\n", snapshots=_mgr(tmp_path), confirmed=True, root=root
    )
    assert r["ok"] is True
    assert inside.read_text() == "new\n"
    escape = tmp_path / "outside.py"
    r = approve_and_write(
        escape, "new\n", snapshots=_mgr(tmp_path), confirmed=True, root=root
    )
    assert r["ok"] is False
    assert "confinement" in r["reason"]
    assert not escape.exists()
    # ".." traversal is resolved before the check.
    sneaky = root / "sub" / ".." / ".." / "outside2.py"
    r = approve_and_write(
        sneaky, "new\n", snapshots=_mgr(tmp_path), confirmed=True, root=root
    )
    assert r["ok"] is False


def test_snapshot_ids_unique_even_in_same_ms(tmp_path):
    mgr = _mgr(tmp_path)
    ids = [mgr.take("t", "code") for _ in range(50)]
    assert len(set(ids)) == 50


def test_original_version_constant():
    from levi.surgeon.triple_threat import ORIGINAL_SURGEON_VERSION

    assert ORIGINAL_SURGEON_VERSION == "15.4.1-private"
