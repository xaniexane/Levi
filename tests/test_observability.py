"""Hermetic tests for LEVI observability (core/levi/observability/).

No network, no real HOME writes, no real secrets: every test runs the
bloodstream turn against a tmp data_dir and asserts on the corpus that
lands in ``<tmp>/observability``.
"""

import json
import os
import stat

from levi.bloodstream.stages import (
    BehaviorKind,
    RouteKind,
    StageRecord,
    TurnContext,
    TurnResult,
)
from levi.bloodstream.turn import reset_session_state, run_turn
from levi.observability import __main__ as obs_cli
from levi.observability.hook import emit_turn_trace
from levi.observability.redact import REDACTED, params_hash, redact
from levi.observability.schema import (
    AWAITING_PERMISSION,
    DENIED,
    FAILED,
    SUCCESS,
    from_bloodstream,
)
from levi.observability.store import TraceStore
from levi.policy.gates import RiskLevel


def _ctx(tmp_path, **kw):
    reset_session_state()
    # data_dir doubles as the LEVI home: the corpus lands at
    # <tmp>/h/.levi/observability, which is also what --home expects.
    base = dict(data_dir=tmp_path / "h" / ".levi", session_id="obs-test")
    base.update(kw)
    return TurnContext(**base)


def _obsdir(tmp_path):
    return tmp_path / "h" / ".levi" / "observability"


def _store(tmp_path):
    return TraceStore(base_dir=_obsdir(tmp_path))


def _raw_lines(tmp_path):
    base = tmp_path / "h" / ".levi" / "observability"
    lines = []
    for f in sorted(base.glob("traces-*.jsonl")):
        lines.extend(f.read_text(encoding="utf-8").splitlines())
    return lines


# ---------------------------------------------------------------------------
# Round-trip: a full agent turn lands in the corpus and is queryable
# ---------------------------------------------------------------------------


def test_full_turn_round_trips_into_corpus(tmp_path, capsys):
    run_turn("hello, what is the capital of france", _ctx(tmp_path))
    store = _store(tmp_path)

    recent = store.recent(limit=5)
    assert len(recent) == 1
    trace = recent[0]

    assert trace.outcome == SUCCESS
    assert trace.raw_outcome == "replied"
    assert trace.session_id == "obs-test"
    assert trace.route == "model"
    assert trace.risk_ceiling >= 0
    assert trace.turn_id

    names = [s.stage for s in trace.stages]
    for expected in (
        "companion_ei",
        "persona",
        "governor",
        "policy",
        "memory",
        "trace",
    ):
        assert expected in names

    # Instrumented stages carry real timings; uninstrumented ones are
    # honestly None rather than invented.
    timed = {s.stage: s.duration_ms for s in trace.stages}
    assert timed["companion_ei"] is not None and timed["companion_ei"] >= 0
    assert timed["policy"] is not None and timed["policy"] >= 0

    # Queryable by id and by filter.
    assert store.get(trace.turn_id).turn_id == trace.turn_id
    assert store.filter(outcome=SUCCESS)[0].turn_id == trace.turn_id
    assert store.get("no-such-turn") is None

    # CLI entrypoint sees it too (home override → the same fake home).
    home = tmp_path / "h"
    assert obs_cli.main(["--home", str(home), "recent", "--limit", "5"]) == 0
    out = capsys.readouterr().out
    assert trace.turn_id in out


def test_denied_turn_records_risk_ceiling(tmp_path):
    ctx = _ctx(
        tmp_path,
        auto_approve_up_to=RiskLevel.LOW,
        confirm=lambda proposal: False,  # human denies at the gate
    )
    result = run_turn("please send an email to the whole team now", ctx)
    store = _store(tmp_path)

    denied = store.filter(outcome=DENIED, min_risk=3)
    assert len(denied) == 1
    trace = denied[0]
    assert trace.raw_outcome == "denied"
    assert trace.risk_ceiling == 3
    assert "denied" in (trace.reason or "").lower()
    assert trace.receipt_id is None
    assert result.risk_level == 3

    # The policy stage itself recorded the ceiling it evaluated under.
    policy = next(s for s in trace.stages if s.stage == "policy")
    assert policy.decision == "denied"
    assert policy.risk_ceiling == 3


def test_awaiting_permission_recorded(tmp_path):
    ctx = _ctx(tmp_path, auto_approve_up_to=RiskLevel.LOW, confirm=None)
    run_turn("please send an email to the whole team now", ctx)
    store = _store(tmp_path)

    pending = store.filter(outcome=AWAITING_PERMISSION)
    assert len(pending) == 1
    assert pending[0].risk_ceiling == 3
    assert "nothing executed" in (pending[0].reason or "").lower()


def test_failed_outcome_mapping(tmp_path):
    result = TurnResult(
        reply="broken",
        route=RouteKind.FAILED,
        behavior=BehaviorKind.NONE,
        persona_id="normal",
        risk_level=0,
        receipt_summary="",
        trace_id="t-fail-1",
        ok=False,
        error="ValueError: kaboom",
        outcome="failed",
        session_id="s-fail",
        stages=[StageRecord(stage="failure", decision="composted", detail={})],
    )
    trace = emit_turn_trace(
        result,
        "do the thing",
        composted={"engine": "reim", "ok": True},
        base_dir=_obsdir(tmp_path),
    )
    assert trace is not None
    assert trace.outcome == FAILED
    assert trace.reason == "ValueError: kaboom"
    assert trace.composted is True

    stored = _store(tmp_path).get("t-fail-1")
    assert stored is not None and stored.outcome == FAILED


# ---------------------------------------------------------------------------
# Secret safety: raw values never reach the corpus
# ---------------------------------------------------------------------------

SECRET_ARGS = {
    "query": "summarize this",
    "api_key": "sk-abcdefghijklmnopqrstuvwx",
    "password": "hunter2-hunter2-hunter2",
    "nested": {"token": "xoxb-1234-abcdefghijklmno", "ok": "fine"},
    "bearer_blob": "Bearer eyJhbGciOiJIUzI1NiJ9.cGF5bG9hZA.signature",
}


def _synthetic_result_with_tools():
    return TurnResult(
        reply="done",
        route=RouteKind.MODEL,
        behavior=BehaviorKind.NONE,
        persona_id="normal",
        risk_level=1,
        receipt_summary="",
        trace_id="t-tools-1",
        outcome="replied",
        session_id="s-tools",
        tool_calls=[{"name": "web_search", "args": SECRET_ARGS}],
        stages=[StageRecord(stage="policy", decision="executed", detail={"risk": 1})],
    )


def test_secret_values_never_persist(tmp_path):
    result = _synthetic_result_with_tools()
    trace = emit_turn_trace(result, "search", base_dir=_obsdir(tmp_path))
    assert trace is not None

    call = trace.tool_calls[0]
    assert call.name == "web_search"
    assert call.params["query"] == "summarize this"
    assert call.params["api_key"] == REDACTED
    assert call.params["password"] == REDACTED
    assert call.params["nested"]["token"] == REDACTED
    assert call.params["nested"]["ok"] == "fine"
    assert call.params["bearer_blob"] == REDACTED
    assert len(call.params_hash) == 64

    raw = "\n".join(_raw_lines(tmp_path))
    for secret in (
        "sk-abcdefghijklmnopqrstuvwx",
        "hunter2-hunter2-hunter2",
        "xoxb-1234-abcdefghijklmno",
        "eyJhbGciOiJIUzI1NiJ9",
    ):
        assert secret not in raw
    assert REDACTED in raw


def test_params_hash_is_redacted_shape_stable():
    a = {"api_key": "sk-aaaaaaaaaaaaaaaaaaaaaaaa", "q": "x"}
    b = {"api_key": "sk-bbbbbbbbbbbbbbbbbbbbbbbb", "q": "x"}
    c = {"api_key": "sk-aaaaaaaaaaaaaaaaaaaaaaaa", "q": "y"}
    # Same redacted shape → same hash (hash covers redacted form only).
    assert params_hash(a) == params_hash(b)
    assert params_hash(a) != params_hash(c)
    assert params_hash(a) == params_hash(redact(a))


def test_redact_never_raises_on_hostile_shapes():
    sentinel = object()
    assert redact(sentinel) is sentinel  # opaque scalars pass through untouched
    assert redact({"k": sentinel})["k"] is sentinel
    assert redact(None) is None
    assert redact(42) == 42
    assert redact([sentinel])[0] is sentinel


# ---------------------------------------------------------------------------
# Store: rotation, permissions, resilience
# ---------------------------------------------------------------------------


def test_store_rotation_and_owner_only_permissions(tmp_path):
    store = TraceStore(base_dir=_obsdir(tmp_path))
    mode = stat.S_IMODE(os.stat(store.base_dir).st_mode)
    assert mode == 0o700

    trace = from_bloodstream(_synthetic_result_with_tools(), "search")
    path = store.append(trace)
    assert path is not None
    assert path.name.startswith("traces-") and path.name.endswith(".jsonl")
    file_mode = stat.S_IMODE(os.stat(path).st_mode)
    assert file_mode & 0o077 == 0  # group/other have no access

    assert store.days() == [path.name[len("traces-") : -len(".jsonl")]]
    assert len(store.read_day()) == 1
    assert store.read_day("1999-01-01") == []  # missing day → empty, no raise


def test_corrupt_lines_do_not_abort_reads(tmp_path):
    store = TraceStore(base_dir=_obsdir(tmp_path))
    trace = from_bloodstream(_synthetic_result_with_tools(), "search")
    store.append(trace)
    path = store._path_for()
    with path.open("a", encoding="utf-8") as fh:
        fh.write("this is not json\n")
        fh.write('["not", "a", "dict"]\n')
    assert len(store.read_day()) == 1


def test_hook_never_raises(tmp_path):
    # Unwritable base dir: the observer fails silently, the turn is fine.
    result = _synthetic_result_with_tools()
    out = emit_turn_trace(
        result, "search", base_dir="/proc/definitely-not-writable-xyz/obs"
    )
    assert out is None or out.turn_id == "t-tools-1"


def test_stats_census(tmp_path):
    run_turn("hello there", _ctx(tmp_path))
    stats = _store(tmp_path).stats()
    assert stats["total"] == 1
    assert stats["by_outcome"] == {SUCCESS: 1}
    assert len(stats["days"]) == 1


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


def test_cli_show_and_filter(tmp_path, capsys):
    run_turn("hello there", _ctx(tmp_path))
    ctx = _ctx(
        tmp_path,
        auto_approve_up_to=RiskLevel.LOW,
        confirm=lambda proposal: False,
    )
    run_turn("please send an email to the whole team now", ctx)
    home = tmp_path / "h"  # corpus already at <home>/.levi/observability
    store = _store(tmp_path)
    denied_id = store.filter(outcome=DENIED)[0].turn_id

    assert (
        obs_cli.main(
            [
                "--home",
                str(home),
                "filter",
                "--outcome",
                "denied",
                "--min-risk",
                "3",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert denied_id in out
    assert "risk=3" in out

    assert obs_cli.main(["--home", str(home), "show", denied_id]) == 0
    out = capsys.readouterr().out
    assert "denied" in out and "-- stages --" in out and "-- tool calls --" not in out

    assert obs_cli.main(["--home", str(home), "show", "nope"]) == 1

    assert obs_cli.main(["--home", str(home), "stats"]) == 0
    out = capsys.readouterr().out
    assert "total traces: 2" in out

    assert obs_cli.main(["--home", str(home), "recent", "--limit", "1", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list) and len(payload) == 1
    assert payload[0]["outcome"] == DENIED
