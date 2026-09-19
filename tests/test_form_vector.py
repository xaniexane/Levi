"""vector form tests: the sandbox facade.

Proving bar: capabilities are honest (no invented isolation), dry runs
never execute, hostile argv is data (never executed), empty commands are
refused, and every run returns a receipt.
"""

from levi.vector import FORM_NAME, capabilities, run_vector


def test_capabilities_never_invent_isolation():
    caps = capabilities()
    assert caps["form"] == FORM_NAME
    names = [b["name"] for b in caps["backends"]]
    assert set(names) == {"bubblewrap", "unshare", "subprocess"}
    for b in caps["backends"]:
        assert b["isolation"].upper() in ("STRONG", "BASIC", "NONE")
        assert (
            "NO isolation" in caps["honest_limit"]
            or "no " in caps["honest_limit"].lower()
        )
    # selected backend must be one of the three
    assert caps["selected"] in names


def test_dry_run_never_executes(tmp_path):
    marker = tmp_path / "should-not-exist"
    r = run_vector(
        ["python3", "-c", f"open({str(marker)!r}, 'w').write('x')"],
        dry_run=True,
    )
    assert r["status"] == "dry-run"
    assert r["dry_run"] is True
    assert not marker.exists()  # purity: nothing executed


def test_dry_run_carries_would_be_argv():
    r = run_vector(["echo", "hi"], dry_run=True, net=True)
    assert r["argv"] == ["echo", "hi"]
    assert r["net"] is True
    assert r["reason"]  # receipts always carry a reason


def test_hostile_argv_is_data_never_executed(tmp_path):
    marker = tmp_path / "should-not-exist-either"
    evil = ["python3", "-c", f"open({str(marker)!r}, 'w').write('x')", 42, None]
    r = run_vector(evil, dry_run=False)
    assert r["status"] == "rejected"
    assert "hostile" in r["reason"]
    assert not marker.exists()


def test_non_sequence_and_empty_rejected():
    for bad in ("echo hi", b"echo", 42, None, []):
        r = run_vector(bad, dry_run=True)
        assert r["status"] == "rejected", bad


def test_live_run_executes_and_receipts():
    # Hermetic: /bin/true or python3 -c pass; no filesystem writes.
    r = run_vector(["python3", "-c", "pass"])
    assert r["status"] in ("executed", "refused")
    if r["status"] == "executed":
        assert r["returncode"] == 0
        assert r["backend"] in ("bubblewrap", "unshare", "subprocess")


def test_degraded_without_ack_is_refused():
    # Forcing subprocess without acknowledgement must refuse, not run.
    r = run_vector(["python3", "-c", "pass"], backend="subprocess")
    assert r["status"] == "refused"
    assert "acknowledgement" in r["reason"]
