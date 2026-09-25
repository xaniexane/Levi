"""KFX2 BUILDERS milestone 1 — scaffold engine + bounded verify/retry, no meter.

Hermetic: no network, no daemons. The generated skeleton is exercised for
real (compile, smoke, live HTTP roundtrip on loopback).
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from decimal import Decimal

import pytest

from levi.builders import (
    PLATFORM_CUT,
    MAX_BUILDER_RETRIES,
    BuildLedger,
    BuildOutcome,
    LedgerEntry,
    OwnerGateRequired,
    ScaffoldEngine,
    VerifyLoop,
    build,
    collect_payment,
    marketplace_royalty,
)

PROMPT = "Build me a simple app to track my vinyl records and manage playlists"


def _read_tree(root):
    tree = {}
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            full = os.path.join(dirpath, name)
            with open(full, "rb") as fh:
                tree[os.path.relpath(full, root)] = fh.read()
    return tree


# -- determinism -----------------------------------------------------------


def test_same_prompt_same_bytes():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        ra = build(PROMPT, workdir=a)
        rb = build(PROMPT, workdir=b)
        ta, tb = _read_tree(ra.target_dir), _read_tree(rb.target_dir)
    assert ra.outcome is BuildOutcome.VERIFIED
    assert rb.outcome is BuildOutcome.VERIFIED
    assert ta, "build produced no files"
    assert ta == tb


def test_different_prompts_differ():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        ra = build(PROMPT, workdir=a)
        rb = build("A todo list app with reminders", workdir=b)
        ta, tb = _read_tree(ra.target_dir), _read_tree(rb.target_dir)
    assert ta != tb


def test_empty_prompt_rejected():
    with pytest.raises(ValueError):
        ScaffoldEngine("   ")


# -- scaffold produces a real, runnable project ----------------------------


def test_scaffold_tree_shape_and_provenance():
    with tempfile.TemporaryDirectory() as tmp:
        report = build(PROMPT, workdir=tmp)
        assert report.outcome is BuildOutcome.VERIFIED
        assert report.attempts == 1
        assert report.repairs == []
        for expected in (
            "app.py",
            "tests/test_smoke.py",
            "theme.yaml",
            "README.md",
            ".provenance.json",
        ):
            assert expected in report.files, expected
        prov = json.loads(
            open(os.path.join(report.target_dir, ".provenance.json")).read()
        )
        assert prov["provenance"] == "builder"
        assert prov["prompt_sha256"] == ScaffoldEngine(PROMPT).prompt_hash
        assert "record" in prov["entities"] or "playlist" in prov["entities"]


def test_theme_manifest_structured_and_safe():
    with tempfile.TemporaryDirectory() as tmp:
        report = build(PROMPT, workdir=tmp)
        theme = open(os.path.join(report.target_dir, "theme.yaml")).read()
    assert "<script" not in theme.lower()
    assert "eval(" not in theme
    for color in re.findall(r"#[0-9a-fA-F]{6}", theme):
        assert len(color) == 7
    assert "customizable: true" in theme


def test_generated_app_serves_crud_over_http():
    with tempfile.TemporaryDirectory() as tmp:
        report = build(PROMPT, workdir=tmp)
        assert report.outcome is BuildOutcome.VERIFIED
        app = os.path.join(report.target_dir, "app.py")
        data = os.path.join(tmp, "http-data.json")
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        proc = subprocess.Popen(
            [sys.executable, app, "--port", str(port), "--data", data],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.time() + 10
            while time.time() < deadline:
                line = proc.stdout.readline()
                if "serving" in line:
                    break
                if proc.poll() is not None:
                    raise AssertionError("server died: %s" % proc.stderr.read())
            else:
                raise AssertionError("server never printed ready line")
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            base = "http://127.0.0.1:%d/api/record" % port

            def call(method, url, payload=None):
                body = json.dumps(payload).encode() if payload is not None else None
                req = urllib.request.Request(
                    url,
                    data=body,
                    method=method,
                    headers={"Content-Type": "application/json"},
                )
                with opener.open(req, timeout=5) as resp:
                    return resp.status, json.loads(resp.read().decode())

            status, created = call("POST", base, {"name": "Kind of Blue"})
            assert status == 201 and created["id"]
            status, listed = call("GET", base)
            assert status == 200 and any(r["id"] == created["id"] for r in listed)
            status, updated = call("PUT", base + "/" + created["id"], {"name": "Blue"})
            assert status == 200 and updated["name"] == "Blue"
            status, deleted = call("DELETE", base + "/" + created["id"])
            assert status == 200 and deleted["deleted"] == created["id"]
            status, listed = call("GET", base)
            assert all(r["id"] != created["id"] for r in listed)
        finally:
            proc.terminate()
            proc.wait(timeout=10)


# -- bounded verify/retry: the honest-retry law -----------------------------


def _break_app_on_attempts(bad_attempts):
    def hook(attempt, files):
        if attempt in bad_attempts:
            files["app.py"] = files["app.py"] + "\ndef broken(:\n"

    return hook


def test_self_healed_when_builder_breaks_first_attempt():
    ledger = BuildLedger()
    with tempfile.TemporaryDirectory() as tmp:
        report = build(
            PROMPT, workdir=tmp, ledger=ledger, _fault_hook=_break_app_on_attempts({0})
        )
    assert report.outcome is BuildOutcome.SELF_HEALED
    assert report.attempts == 2
    assert len(report.repairs) == 1
    assert ledger.total_charged() == Decimal("0.00")
    assert all(e.units_charged == Decimal("0.00") for e in ledger.entries())
    retry_events = [e for e in ledger.entries() if e.event == "builder_retry"]
    assert len(retry_events) == 1
    assert "free by construction" in retry_events[0].detail


def test_owner_decision_when_bound_exhausted():
    with tempfile.TemporaryDirectory() as tmp:
        report = build(
            PROMPT, workdir=tmp, _fault_hook=_break_app_on_attempts(set(range(10)))
        )
    assert report.outcome is BuildOutcome.OWNER_DECISION_NEEDED
    assert report.attempts == 1 + MAX_BUILDER_RETRIES
    assert len(report.repairs) == MAX_BUILDER_RETRIES
    assert report.diagnostics, "exhaustion must ship a diagnostics bundle"
    assert not report.ok


def test_verify_loop_rejects_negative_retries():
    with pytest.raises(ValueError):
        VerifyLoop(max_retries=-1)


def test_zero_retry_bound_goes_straight_to_owner():
    engine = ScaffoldEngine(PROMPT, _fault_hook=_break_app_on_attempts(set(range(10))))
    with tempfile.TemporaryDirectory() as tmp:
        report = VerifyLoop(max_retries=0).run(engine, tmp)
    assert report.outcome is BuildOutcome.OWNER_DECISION_NEEDED
    assert report.attempts == 1


# -- economics: no meter, 12% hook, gated payments --------------------------


def test_ledger_cannot_record_nonzero_charge():
    with pytest.raises(ValueError):
        LedgerEntry(seq=1, event="x", detail="y", units_charged=Decimal("0.01"))


def test_ledger_total_always_zero_even_with_retries():
    ledger = BuildLedger()
    with tempfile.TemporaryDirectory() as tmp:
        build(
            PROMPT, workdir=tmp, ledger=ledger, _fault_hook=_break_app_on_attempts({0})
        )
    assert ledger.total_charged() == Decimal("0.00")
    assert len(ledger.entries()) >= 3  # scaffold, retry, verify


def test_platform_cut_constant_and_royalty_math():
    assert PLATFORM_CUT == Decimal("0.12")
    assert marketplace_royalty(Decimal("100.00")) == Decimal("12.00")
    assert marketplace_royalty(Decimal("10.005")) == Decimal("1.20")
    assert marketplace_royalty(Decimal("0")) == Decimal("0.00")
    with pytest.raises(ValueError):
        marketplace_royalty(Decimal("-1"))


def test_collect_payment_is_owner_gated():
    with pytest.raises(OwnerGateRequired):
        collect_payment(amount=Decimal("10.00"))


# -- offline: no network in core paths --------------------------------------


def test_full_build_with_network_blocked(monkeypatch):
    def _no_connect(self, *args, **kwargs):
        raise OSError("network blocked by test")

    monkeypatch.setattr(socket.socket, "connect", _no_connect)
    with tempfile.TemporaryDirectory() as tmp:
        report = build(PROMPT, workdir=tmp)
    assert report.outcome is BuildOutcome.VERIFIED
