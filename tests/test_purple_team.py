"""Property tests for the purple-team framework — one per invariant.

I1 default-deny · I2 exact binding · I3 window binding · I4 keeper-only ·
I5 non-destructive · I6 kill-switch · I7 receipted · I8 closed loop ·
I9 no offensive tradecraft.
"""

import json
from pathlib import Path

import pytest

from core.levi.cyber.purple import (
    Authorization,
    AuthorizationDenied,
    AuthorizationStore,
    KillSwitch,
    ReceiptLog,
    Sandbox,
    SandboxEscape,
    builtin_scenarios,
    check,
    load_playbook_ids,
    run_exercise,
)
from core.levi.cyber.purple.findings import UnknownPlaybook, build_finding
from core.levi.cyber.purple.scenarios import Scenario, scenario_by_id

NOW = 1790000000
TARGET = "levi-lab-host-01"
SCEN = "external-recon-sweep"


def _grant(**kw):
    base = dict(
        auth_id="auth-1",
        target_id=TARGET,
        scenario_ids=(SCEN,),
        not_before=NOW - 100,
        not_after=NOW + 3600,
    )
    base.update(kw)
    return Authorization(**base)


def _store(grant=None):
    store = AuthorizationStore()
    store.add(grant or _grant())
    return store


# --- I1: default-deny -------------------------------------------------


def test_i1_no_grant_no_run(tmp_path):
    log = ReceiptLog()
    with pytest.raises(AuthorizationDenied):
        run_exercise(
            store=AuthorizationStore(),
            auth_id="nope",
            target_id=TARGET,
            scenario=scenario_by_id(SCEN),
            sandbox_root=str(tmp_path / "sb"),
            now=NOW,
            receipt_log=log,
            exercise_id="ex-i1",
        )
    assert len(log) == 1  # exactly one DENIED receipt
    assert log.verify()
    assert list(log)[0].kind == "DENIED"
    assert not list((tmp_path / "sb").glob("*"))  # zero phases, zero artifacts


# --- I2: exact binding ------------------------------------------------


@pytest.mark.parametrize(
    "kw",
    [
        {"target_id": "other-host-99"},  # wrong target
        {"scenario_ids": ("registry-persistence",)},  # scenario out of scope
    ],
)
def test_i2_binding_denies(tmp_path, kw):
    store = _store(_grant(**kw))
    with pytest.raises(AuthorizationDenied):
        run_exercise(
            store=store,
            auth_id="auth-1",
            target_id=TARGET,
            scenario=scenario_by_id(SCEN),
            sandbox_root=str(tmp_path / "sb"),
            now=NOW,
            receipt_log=ReceiptLog(),
            exercise_id="ex-i2",
        )


# --- I3: window binding ------------------------------------------------


@pytest.mark.parametrize("nb, na", [(NOW + 10, NOW + 3600), (NOW - 7200, NOW - 10)])
def test_i3_window_denies(tmp_path, nb, na):
    store = _store(_grant(not_before=nb, not_after=na))
    with pytest.raises(AuthorizationDenied):
        check(store, "auth-1", TARGET, SCEN, NOW)


def test_i3_window_edge_allows(tmp_path):
    store = _store(_grant(not_before=NOW, not_after=NOW))
    assert check(store, "auth-1", TARGET, SCEN, NOW).auth_id == "auth-1"


# --- I4: keeper-only ----------------------------------------------------


def test_i4_non_keeper_denied():
    store = _store(_grant(authorizer="contractor"))
    with pytest.raises(AuthorizationDenied):
        check(store, "auth-1", TARGET, SCEN, NOW)


def test_i4_revoked_denied():
    store = _store()
    store.revoke("auth-1")
    with pytest.raises(AuthorizationDenied):
        check(store, "auth-1", TARGET, SCEN, NOW)


def test_i4_duplicate_auth_id_rejected():
    store = _store()
    with pytest.raises(ValueError):
        store.add(_grant())


# --- I5: non-destructive ------------------------------------------------


@pytest.mark.parametrize(
    "evil",
    [
        "/etc/passwd",
        "../escape.txt",
        "a/../../b.txt",
        "sub/../../../../evil",
    ],
)
def test_i5_sandbox_rejects_escapes(tmp_path, evil):
    sb = Sandbox(tmp_path / "sb")
    with pytest.raises(SandboxEscape):
        sb.write(evil, "x")


def test_i5_all_artifacts_contained(tmp_path):
    sb_root = tmp_path / "sb"
    log = ReceiptLog()
    result = run_exercise(
        store=_store(),
        auth_id="auth-1",
        target_id=TARGET,
        scenario=scenario_by_id(SCEN),
        sandbox_root=str(sb_root),
        now=NOW,
        receipt_log=log,
        exercise_id="ex-i5",
    )
    assert result.phases_executed == 1
    root = sb_root.resolve()
    for artifact in (sb_root / "").rglob("*"):
        if artifact.is_file():
            assert artifact.resolve() == root or root in artifact.resolve().parents


def test_i5_every_telemetry_line_marked_simulated():
    for scenario in builtin_scenarios():
        for technique in scenario.techniques:
            for line in technique.telemetry:
                record = json.loads(line)
                assert record.get("simulated") is True, technique.technique_id


# --- I6: kill-switch -----------------------------------------------------


def test_i6_prekilled_zero_phases(tmp_path):
    switch = KillSwitch()
    switch.kill()
    log = ReceiptLog()
    result = run_exercise(
        store=_store(),
        auth_id="auth-1",
        target_id=TARGET,
        scenario=scenario_by_id(SCEN),
        sandbox_root=str(tmp_path / "sb"),
        kill_switch=switch,
        now=NOW,
        receipt_log=log,
        exercise_id="ex-i6a",
    )
    assert result.killed is True
    assert result.phases_executed == 0
    assert result.receipt_kinds[-1] == "KILLED"
    assert not list((tmp_path / "sb").glob("*"))


def test_i6_midrun_kill_stops(tmp_path):
    class TripAfterFirst(KillSwitch):
        def __init__(self):
            super().__init__()
            self._reads = 0

        @property
        def killed(self):
            self._reads += 1
            return self._reads > 1  # trip before the second phase check

    two = Scenario(
        scenario_id="two-phase",
        name="two-phase drill",
        description="two techniques, killed mid-run",
        techniques=(
            scenario_by_id("external-recon-sweep").techniques[0],
            scenario_by_id("staged-exfil").techniques[0],
        ),
    )
    store = AuthorizationStore()
    store.add(_grant(scenario_ids=("two-phase",)))
    log = ReceiptLog()
    result = run_exercise(
        store=store,
        auth_id="auth-1",
        target_id=TARGET,
        scenario=two,
        sandbox_root=str(tmp_path / "sb"),
        kill_switch=TripAfterFirst(),
        now=NOW,
        receipt_log=log,
        exercise_id="ex-i6b",
    )
    assert result.killed is True
    assert result.phases_executed == 1  # second phase never ran
    assert result.receipt_kinds[-1] == "KILLED"
    assert len(result.findings) == 1  # only the executed phase yields a finding


# --- I7: receipted -------------------------------------------------------


def test_i7_chain_verifies_and_tamper_breaks(tmp_path):
    log = ReceiptLog()
    run_exercise(
        store=_store(),
        auth_id="auth-1",
        target_id=TARGET,
        scenario=scenario_by_id(SCEN),
        sandbox_root=str(tmp_path / "sb"),
        now=NOW,
        receipt_log=log,
        exercise_id="ex-i7",
    )
    assert log.verify()
    kinds = [r.kind for r in log]
    assert kinds[0] == "STARTED" and kinds[-1] == "COMPLETED"
    assert kinds.count("PHASE") == 1
    # Tamper with one receipt's detail through a fresh log: the chain
    # must break.
    tampered_log = ReceiptLog()
    for r in log:
        tampered_log._receipts.append(r)
    victim = tampered_log._receipts[1]
    tampered_log._receipts[1] = type(victim)(
        seq=victim.seq,
        prev_hash=victim.prev_hash,
        hash=victim.hash,
        kind=victim.kind,
        exercise_id=victim.exercise_id,
        detail={"tampered": True},
        at=victim.at,
    )
    assert tampered_log.verify() is False


def test_i7_persisted_log_reloads(tmp_path):
    path = tmp_path / "receipts.jsonl"
    log = ReceiptLog(path)
    run_exercise(
        store=_store(),
        auth_id="auth-1",
        target_id=TARGET,
        scenario=scenario_by_id(SCEN),
        sandbox_root=str(tmp_path / "sb"),
        now=NOW,
        receipt_log=log,
        exercise_id="ex-i7b",
    )
    reloaded = ReceiptLog(path)
    assert len(reloaded) == len(log)
    assert reloaded.verify()


# --- I8: closed loop ------------------------------------------------------


def test_i8_every_technique_yields_a_real_playbook(tmp_path):
    known = load_playbook_ids()
    assert len(known) > 100_000  # the manifest is the real one
    for scenario in builtin_scenarios():
        log = ReceiptLog()
        store = AuthorizationStore()
        store.add(_grant(scenario_ids=(scenario.scenario_id,)))
        result = run_exercise(
            store=store,
            auth_id="auth-1",
            target_id=TARGET,
            scenario=scenario,
            sandbox_root=str(tmp_path / scenario.scenario_id),
            now=NOW,
            receipt_log=log,
            exercise_id=f"ex-i8-{scenario.scenario_id}",
        )
        assert len(result.findings) == len(scenario.techniques) >= 1
        for finding, technique in zip(
            result.findings, scenario.techniques, strict=True
        ):
            assert finding.playbook_id == technique.playbook_id
            assert finding.playbook_id in known
            assert technique.technique_id in finding.recommendation


def test_i8_unknown_playbook_fails_closed():
    with pytest.raises(UnknownPlaybook):
        build_finding(
            exercise_id="ex-x",
            technique_id="T9999",
            phase="recon",
            detected=True,
            playbook_id="cyber_no_such_playbook_xyz",
            playbook_name="Nope",
            playbook_ids=frozenset({"cyber_real_one"}),
        )


def test_i8_happy_path_all_detected(tmp_path):
    # Synthetic telemetry is written verbatim, so the defensive signal is
    # always present: the drill confirms detections WOULD fire.
    for scenario in builtin_scenarios():
        store = AuthorizationStore()
        store.add(_grant(scenario_ids=(scenario.scenario_id,)))
        result = run_exercise(
            store=store,
            auth_id="auth-1",
            target_id=TARGET,
            scenario=scenario,
            sandbox_root=str(tmp_path / f"hp-{scenario.scenario_id}"),
            now=NOW,
            receipt_log=ReceiptLog(),
            exercise_id=f"ex-hp-{scenario.scenario_id}",
        )
        assert all(f.detected for f in result.findings)


def test_i8_scenario_lookup():
    assert scenario_by_id(SCEN).scenario_id == SCEN
    with pytest.raises(KeyError):
        scenario_by_id("no-such-scenario")


# --- I9: no offensive tradecraft ------------------------------------------

OFFENSIVE_MARKERS = (
    "exploit code",
    "payload generator",
    "step-by-step attack",
    "zero-day exploit",
)


def test_i9_scenario_data_carries_no_tradecraft():
    for scenario in builtin_scenarios():
        blob = " ".join(
            [scenario.name, scenario.description]
            + [
                " ".join([t.technique_id, t.phase, t.detection_rule, *t.telemetry])
                for t in scenario.techniques
            ]
        ).lower()
        for marker in OFFENSIVE_MARKERS:
            assert marker not in blob, f"{marker!r} in {scenario.scenario_id}"


def test_i9_no_subprocess_or_socket_in_framework():
    import core.levi.cyber.purple as pkg

    root = Path(pkg.__file__).parent
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import subprocess" not in text, path.name
        assert "import socket" not in text, path.name
