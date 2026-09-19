"""Tests for the widened operational-log harvest (2026-09-16).

Chauncey's law: all knowledge is good knowledge — only what you DO with
it can be wrong. So the growth loop harvests broadly (hunt waves, build
queue, agent tool-outputs, daily memory logs) while the guards constrain
conduct, not curiosity. These tests pin the new sources: shape,
watermarking/idempotency, caps, and secret-scrubbing.
"""

import json
from datetime import date

import pytest

from levi.growth.experience import (
    _OPS_AGENT_CAP,
    harvest_ops_logs,
)


@pytest.fixture()
def dirs(tmp_path):
    perpetual = tmp_path / "perpetual"
    perpetual.mkdir()
    agents = tmp_path / "agents"
    memlog = tmp_path / "memlog"
    memlog.mkdir()
    return {"perpetual": perpetual, "agents": agents, "memlog": memlog}


def _write_waves(perpetual, waves):
    (perpetual / "hunt_state.json").write_text(
        json.dumps({"waves": waves}), encoding="utf-8"
    )


def test_hunt_waves_completed_only_and_idempotent(dirs):
    _write_waves(
        dirs["perpetual"],
        [
            {
                "id": "wave-1",
                "status": "completed",
                "theme_id": "t",
                "findings_count": 3,
                "research_slug": "r1",
                "completed_at": "2026-09-16T01:00:00Z",
            },
            {"id": "wave-2", "status": "running", "theme_id": "t"},
            {
                "id": "wave-3",
                "status": "completed",
                "theme_id": "t2",
                "findings_count": 1,
                "research_slug": "r3",
                "completed_at": "2026-09-16T02:00:00Z",
            },
        ],
    )
    kw = dict(
        perpetual_dir=dirs["perpetual"],
        agents_dir=dirs["agents"],
        memdir=dirs["memlog"],
    )
    exps, marks = harvest_ops_logs(since={}, **kw)
    waves = [e for e in exps if e.meta.get("ops_source") == "hunt-wave"]
    assert {e.source for e in waves} == {"hunt-wave:wave-1", "hunt-wave:wave-3"}
    exps2, _ = harvest_ops_logs(since=dict(marks), **kw)
    assert not [e for e in exps2 if e.meta.get("ops_source") == "hunt-wave"]


def test_build_queue_appends_only(dirs):
    q = dirs["perpetual"] / "build_queue.jsonl"
    q.write_text(
        "\n".join(json.dumps({"describe": "task %d" % i}) for i in range(3)) + "\n",
        encoding="utf-8",
    )
    kw = dict(
        perpetual_dir=dirs["perpetual"],
        agents_dir=dirs["agents"],
        memdir=dirs["memlog"],
    )
    exps, marks = harvest_ops_logs(since={}, **kw)
    bq = [e for e in exps if e.meta.get("ops_source") == "build-queue"]
    assert len(bq) == 3
    with open(q, "a", encoding="utf-8") as f:
        f.write(json.dumps({"describe": "task 3"}) + "\n")
    exps2, _ = harvest_ops_logs(since=dict(marks), **kw)
    bq2 = [e for e in exps2 if e.meta.get("ops_source") == "build-queue"]
    assert len(bq2) == 1
    assert "task 3" in bq2[0].content


def test_agent_outputs_summarized_capped_idempotent(dirs):
    outdir = dirs["agents"] / "agent-1" / "tool-output"
    outdir.mkdir(parents=True)
    for i in range(_OPS_AGENT_CAP + 5):
        (outdir / ("call_%02d.json" % i)).write_text(
            json.dumps(
                {
                    "browser_task_id": "bt-%d" % i,
                    "status": "done",
                    "terminal_reason": "finished ok",
                }
            ),
            encoding="utf-8",
        )
    kw = dict(
        perpetual_dir=dirs["perpetual"],
        agents_dir=dirs["agents"],
        memdir=dirs["memlog"],
    )
    exps, marks = harvest_ops_logs(since={}, **kw)
    ao = [e for e in exps if e.meta.get("ops_source") == "agent-output"]
    assert len(ao) == _OPS_AGENT_CAP  # backlog drains over cycles
    assert all("bt-" in e.content for e in ao)
    exps2, marks2 = harvest_ops_logs(since=dict(marks), **kw)
    ao2 = [e for e in exps2 if e.meta.get("ops_source") == "agent-output"]
    assert len(ao2) == 5
    exps3, _ = harvest_ops_logs(since=dict(marks2), **kw)
    assert not [e for e in exps3 if e.meta.get("ops_source") == "agent-output"]


def test_daily_log_chunked_and_scrubbed(dirs):
    today = date.today().isoformat()
    lines = ["# log", "", "did some work"]
    lines.append("contact hunter@example.com about the wave")  # PII-ish
    lines.append("api_key = sk-live-abcdef123456")  # secret-ish
    lines += ["filler line %d" % i for i in range(70)]
    (dirs["memlog"] / (today + ".md")).write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    kw = dict(
        perpetual_dir=dirs["perpetual"],
        agents_dir=dirs["agents"],
        memdir=dirs["memlog"],
    )
    exps, marks = harvest_ops_logs(since={}, **kw)
    dl = [e for e in exps if e.meta.get("ops_source") == "daily-log"]
    assert len(dl) >= 2  # 70+ filler lines force multiple chunks
    blob = "\n".join(e.content for e in dl)
    assert "hunter@example.com" not in blob
    assert "sk-live-abcdef123456" not in blob
    assert "filler line 69" in blob
    exps2, _ = harvest_ops_logs(since=dict(marks), **kw)
    assert not [e for e in exps2 if e.meta.get("ops_source") == "daily-log"]


def test_harvest_ops_logs_rejects_bad_since(dirs):
    with pytest.raises(ValueError):
        harvest_ops_logs(since="nope")


def test_missing_sources_are_silent(dirs):
    exps, marks = harvest_ops_logs(
        since={},
        perpetual_dir=dirs["perpetual"],  # exists but empty
        agents_dir=dirs["agents"],  # does not exist
        memdir=dirs["memlog"],  # exists but empty
    )
    assert exps == []
    # untouched watermarks are preserved, not erased
    exps2, marks2 = harvest_ops_logs(
        since={"opslog:hunt-waves": "wave-9"},
        perpetual_dir=dirs["perpetual"],
        agents_dir=dirs["agents"],
        memdir=dirs["memlog"],
    )
    assert exps2 == []
    assert marks2.get("opslog:hunt-waves") == "wave-9"


def _ops_exp(ops_source, content, source="s"):
    from levi.growth.experience import Experience

    return Experience(
        id="t",
        kind="note",
        source=source,
        ts="",
        content=content,
        meta={"ops_source": ops_source},
    )


def test_ops_extractor_distills_waves_and_failures_only():
    from levi.growth.reflect import reflect_rules_detailed

    exps = [
        _ops_exp(
            "hunt-wave",
            "Hunt wave wave-9 completed (2026-09-16T01:00:00Z): theme=t, "
            "findings=4, research=r.",
            source="hunt-wave:wave-9",
        ),
        _ops_exp(
            "agent-output",
            "[a/tool-output/x.json] browser task bt-1: status=failed "
            "terminal_reason=timeout exceeded while loading page",
            source="agent-output:a",
        ),
        _ops_exp(
            "agent-output",
            "[a/tool-output/y.json] browser task bt-2: status=done",
            source="agent-output:a",
        ),
        _ops_exp("build-queue", "Build queued: something"),
        _ops_exp("daily-log", "Daily log 2026-09-16:\nsome chatter"),
    ]
    learnings, evidence = reflect_rules_detailed(exps)
    assert evidence.get("ops_outcomes") == 2
    kinds = {l.kind for l in learnings}
    assert kinds == {"fact", "correction"}
    assert any("wave-9" in l.content for l in learnings)
    assert any("bt-1" in l.content for l in learnings)
