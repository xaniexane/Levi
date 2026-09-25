# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Shellwright tooling tests — snapshots, policy profiles, hook registry.

Hermetic: every test runs under a tmp LEVI_HOME via monkeypatch. No
network, no daemons, no writes to the real user HOME.

Covers: snapshot roundtrip, restore of missing/corrupt snapshots,
path-traversal names, snapshot listing; policy allowlist/denylist
semantics (deny wins, basename matching, malformed argv); hook
registration, rendering, missing-arg and unknown-hook errors.
"""

from __future__ import annotations

import json

import pytest

from levi.dynasty.dna import AgentError
from levi.dynasty.wave.shellwright_tools import (
    HookError,
    HookRegistry,
    PolicyProfile,
    PolicyRefusal,
    SessionSnapshotter,
    SnapshotError,
    open_profile,
    standard_profile,
    strict_profile,
)


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    home = tmp_path / "levi-home"
    monkeypatch.setenv("LEVI_HOME", str(home))
    return home


@pytest.fixture
def snapper(tmp_home):
    return SessionSnapshotter(tmp_home)


# -- snapshots ----------------------------------------------------------


def test_snapshot_roundtrip(snapper):
    record = {"name": "alpha", "status": "open", "pulse_origin": 3}
    transcript = ["$ echo hi", "hi"]
    body = snapper.snapshot("alpha", record, transcript)
    path = snapper.snapshots_dir / f"{body['id']}.json"
    assert path.is_file()
    restored = snapper.restore(body["id"])
    assert restored["session_name"] == "alpha"
    assert restored["record"] == record
    assert restored["transcript"] == transcript
    assert restored["id"] == body["id"]


def test_snapshot_id_roundtrips_for_plain_names(snapper):
    body = snapper.snapshot("my-session_1", {"a": 1}, [])
    assert body["id"] == "my-session_1"
    assert snapper.restore("my-session_1")["session_name"] == "my-session_1"


def test_snapshot_traversal_name_cannot_escape(snapper):
    body = snapper.snapshot("../../evil", {"a": 1}, [])
    path = snapper.snapshots_dir / f"{body['id']}.json"
    assert path.parent == snapper.snapshots_dir
    assert ".." not in path.name
    restored = snapper.restore(body["id"])
    assert restored["session_name"] == "../../evil"
    # No file leaked outside the snapshots dir.
    assert not (snapper.snapshots_dir / "evil.json").exists()


def test_restore_missing_raises_snapshot_error(snapper):
    with pytest.raises(SnapshotError):
        snapper.restore("nope")


def test_restore_rejects_bad_ids(snapper):
    for bad in ["../x", "", "a/b", "x\0"]:
        with pytest.raises(SnapshotError):
            snapper.restore(bad)


def test_restore_corrupt_json_raises(snapper):
    body = snapper.snapshot("alpha", {"a": 1}, [])
    (snapper.snapshots_dir / f"{body['id']}.json").write_text(
        "{not json", encoding="utf-8"
    )
    with pytest.raises(SnapshotError):
        snapper.restore(body["id"])


def test_restore_schema_mismatch_raises(snapper):
    body = snapper.snapshot("alpha", {"a": 1}, [])
    target = snapper.snapshots_dir / f"{body['id']}.json"
    target.write_text(json.dumps({"id": body["id"]}), encoding="utf-8")
    with pytest.raises(SnapshotError):
        snapper.restore(body["id"])
    # Wrong id inside the body is also corruption.
    target.write_text(
        json.dumps(
            {
                "version": 1,
                "id": "different",
                "session_name": "alpha",
                "record": {},
                "transcript": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SnapshotError):
        snapper.restore(body["id"])


def test_list_snapshots_sorted_and_skips_corrupt(snapper):
    snapper.snapshot("zeta", {}, [])
    snapper.snapshot("alpha", {}, [])
    # Plant a corrupt file and a non-snapshot json.
    (snapper.snapshots_dir / "bad.json").write_text("nope", encoding="utf-8")
    (snapper.snapshots_dir / "other.json").write_text(
        json.dumps({"unrelated": True}), encoding="utf-8"
    )
    listed = snapper.list_snapshots()
    assert [e["session_name"] for e in listed] == ["alpha", "zeta"]
    assert all(set(e) == {"id", "session_name"} for e in listed)


def test_list_snapshots_empty_dir(snapper):
    assert snapper.list_snapshots() == []


def test_snapshot_bad_args(snapper):
    with pytest.raises(AgentError):
        snapper.snapshot("", {}, [])
    with pytest.raises(AgentError):
        snapper.snapshot("a", ["not-a-dict"], [])
    with pytest.raises(AgentError):
        snapper.snapshot("a", {}, "not-a-list")


def test_snapshotter_reads_levi_home_from_env(tmp_path, monkeypatch):
    home = tmp_path / "env-home"
    monkeypatch.setenv("LEVI_HOME", str(home))
    snapper = SessionSnapshotter()
    snapper.snapshot("a", {}, [])
    assert (home / "dynasty" / "shell" / "snapshots" / "a.json").is_file()


def test_snapshotter_no_home_no_env_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("LEVI_HOME", raising=False)
    with pytest.raises(AgentError):
        SessionSnapshotter()


# -- command policy -----------------------------------------------------


def test_strict_profile_allows_tiny_set():
    p = strict_profile()
    assert p.check(["echo", "hi"]) == ["echo", "hi"]
    assert p.check(["ls", "-l"])[0] == "ls"


def test_strict_profile_refuses_by_allowlist():
    p = strict_profile()
    with pytest.raises(PolicyRefusal) as exc:
        p.check(["curl", "http://x"])
    msg = str(exc.value)
    assert "strict" in msg and "allowlist" in msg and "curl" in msg


def test_standard_profile_denies_destructive_and_network():
    p = standard_profile()
    for argv, prog in (
        (["rm", "-rf", "/"], "rm"),
        (["dd"], "dd"),
        (["ssh", "host"], "ssh"),
        (["/bin/rm"], "rm"),
    ):
        with pytest.raises(PolicyRefusal) as exc:
            p.check(argv)
        msg = str(exc.value)
        assert "denylist" in msg and prog in msg
    assert p.check(["echo", "ok"])[0] == "echo"
    assert p.check(["chmod", "644", "f"])  # not on the standard denylist


def test_open_profile_minimal_denylist():
    p = open_profile()
    assert p.check(["curl", "http://x"])[0] == "curl"  # net tools allowed
    with pytest.raises(PolicyRefusal) as exc:
        p.check(["rm"])
    assert "denylist" in str(exc.value)


def test_deny_wins_over_allowlist():
    p = PolicyProfile("custom", allowlist={"rm", "echo"}, denylist={"rm"})
    with pytest.raises(PolicyRefusal) as exc:
        p.check(["rm"])
    assert "denylist" in str(exc.value)
    assert p.check(["echo"]) == ["echo"]


def test_policy_matches_program_basename():
    p = PolicyProfile("b", denylist={"rm"})
    with pytest.raises(PolicyRefusal):
        p.check(["/usr/bin/rm", "-f"])


def test_policy_malformed_argv():
    p = standard_profile()
    for bad in ([], (), "echo", ["echo", ""], [123], None):
        with pytest.raises(AgentError):
            p.check(bad)


def test_policy_refusal_is_typed_agent_error():
    p = strict_profile()
    with pytest.raises(AgentError):
        p.check(["nmap"])


def test_policy_bad_profile_name():
    with pytest.raises(AgentError):
        PolicyProfile("")


# -- automation hooks ---------------------------------------------------


def test_hook_register_and_invoke():
    reg = HookRegistry()
    reg.register("greet", ["echo", "hello {who}"])
    assert reg.invoke("greet", {"who": "levi"}) == ["echo", "hello levi"]


def test_hook_template_without_placeholders():
    reg = HookRegistry()
    reg.register("ping", ["echo", "ping"])
    assert reg.invoke("ping") == ["echo", "ping"]
    assert reg.invoke("ping", {"extra": "ignored"}) == ["echo", "ping"]


def test_hook_missing_args_named():
    reg = HookRegistry()
    reg.register("deploy", ["rsync", "{src}", "{dst}"])
    with pytest.raises(HookError) as exc:
        reg.invoke("deploy", {"src": "a"})
    assert "dst" in str(exc.value)


def test_hook_unknown_name():
    reg = HookRegistry()
    with pytest.raises(HookError):
        reg.invoke("nope", {})


def test_hook_duplicate_registration_refused():
    reg = HookRegistry()
    reg.register("x", ["echo"])
    with pytest.raises(HookError):
        reg.register("x", ["echo"])


def test_hook_bad_registration():
    reg = HookRegistry()
    for name, tmpl in [
        ("", ["echo"]),
        (None, ["echo"]),
        ("x", []),
        ("x", ["echo", ""]),
        ("x", "echo"),
        ("x", ["echo", 42]),
    ]:
        with pytest.raises(HookError):
            reg.register(name, tmpl)


def test_hook_bad_invoke_args():
    reg = HookRegistry()
    reg.register("x", ["echo"])
    with pytest.raises(HookError):
        reg.invoke("", {})
    with pytest.raises(AgentError):
        reg.invoke("x", "not-a-dict")


def test_hook_list_hooks_sorted():
    reg = HookRegistry()
    reg.register("zeta", ["echo"])
    reg.register("alpha", ["echo"])
    assert reg.list_hooks() == ["alpha", "zeta"]


def test_hook_brace_escapes_survive():
    reg = HookRegistry()
    reg.register("braces", ["echo", "{{literal}} {val}"])
    assert reg.invoke("braces", {"val": "v"}) == ["echo", "{literal} v"]


def test_hook_arg_values_with_braces_not_reinterpreted():
    reg = HookRegistry()
    reg.register("x", ["echo", "{val}"])
    assert reg.invoke("x", {"val": "{oops}"}) == ["echo", "{oops}"]
