"""Hermetic tests for the teach pipeline (core/levi/teach/).

No network, no daemons, no user HOME writes (LEVI_HOME is redirected to
tmp_path wherever the registry is touched). Synthetic fixtures only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from levi.brain.train.v2.config import load_config
from levi.brain.train.v2.corpus_manager import (
    PolicyError,
    check_policy,
    load_manifest,
    verify_manifest,
)
from levi.brain.train.v2.corpus_manager import load_jsonl_docs
from levi.brain.train.v2.curriculum import load_curriculum
from levi.teach import registry_dir, teach_home
from levi.teach.cli import cmd_teach
from levi.teach.converters import (
    SOURCES,
    _split_frontmatter,
    academy_docs,
    briefs_docs,
    collect,
    courses_docs,
    growth_docs,
    playbooks_docs,
    sanitize_text,
    seed_docs,
)
from levi.teach.prepare import (
    TeachError,
    _teachback_for_sources,
    make_sequences,
    plan_teaching,
    prepare,
)
from levi.teach.probes import PROBES, probes_for_source
from levi.teach.teachback import TeachbackError, coverage, teachback_report
from levi.teach.verify import check_bundle


# ---------------------------------------------------------------------------
# Fixture helpers


def _fake_repo(tmp_path: Path) -> Path:
    """Minimal repo layout: courses raw texts + academy corpus."""
    raw = tmp_path / "core" / "levi" / "knowledge" / "courses" / "raw"
    (raw / "algorithms").mkdir(parents=True)
    (raw / "algorithms" / "sorting.txt").write_text(
        "Sorting algorithms arrange data in order. Contact ta@example.edu.\n"
        + "Quicksort uses divide and conquer. Mergesort is stable. " * 20,
        encoding="utf-8",
    )
    (raw / "algorithms" / "graphs.txt").write_text(
        "Graph traversal visits nodes. Breadth first search uses a queue. "
        "Depth first search uses a stack. Dijkstra finds shortest paths. " * 20,
        encoding="utf-8",
    )
    (raw / "misc").mkdir(parents=True)
    (raw / "misc" / "tiny.txt").write_text("too short", encoding="utf-8")
    # malformed + blank lines in the academy corpus must be skipped
    acad = tmp_path / "core" / "levi" / "brain" / "train"
    acad.mkdir(parents=True)
    (acad / "corpus_academy.jsonl").write_text(
        "\n"
        '{"text": "Defensive analysts map adversary behavior to detection '
        "coverage using telemetry, evidence-first thinking, and structured "
        'playbooks that turn raw alerts into prioritized investigations.", '
        '"track": "A"}\n'
        "not json at all\n"
        '{"text": "   "}\n'
        '{"no_text": true}\n',
        encoding="utf-8",
    )
    briefs = tmp_path / "core" / "levi" / "knowledge" / "courses" / "briefs"
    briefs.mkdir(parents=True)
    (briefs / "algorithms.md").write_text(
        "# Algorithms — field guide\n\n"
        "Extractive summary — keyword frequencies from fetched course pages.\n\n"
        "## Start here (live links verified at ingest time)\n\n"
        "- **CS 61B: Data Structures** — sorting, searching, and graphs.\n\n"
        "## Topic keywords\n\n"
        "algorithms, sorting, graphs, recursion, complexity, data structures.\n\n"
        "## All courses\n\n"
        "- **CS 61B** — Data Structures, UC Berkeley.\n",
        encoding="utf-8",
    )
    cyber = tmp_path / "core" / "levi" / "skill" / "playbooks" / "cyber"
    cyber.mkdir(parents=True)
    (cyber / "test-playbook.md").write_text(
        "---\n"
        "skill_id: cyber_test_playbook\n"
        "name: Test Detection Playbook\n"
        "risk: low\n"
        "tags: [detection, windows]\n"
        "---\n"
        "# Test Detection Playbook\n\n"
        + (
            "This playbook guides detection and triage. Harden the host, "
            "collect telemetry, hunt for anomalies, map findings to MITRE "
            "techniques, and apply hardening checklists. A good playbook "
            "shortens triage time.\n"
        )
        * 4,
        encoding="utf-8",
    )
    (cyber / "no-frontmatter.md").write_text(
        "# Bare Playbook\n\n" + "Detection prose without frontmatter. " * 10,
        encoding="utf-8",
    )
    return tmp_path


class _FakeEntry:
    def __init__(self, id, content, tags, metadata=None, importance=0.5):
        self.id = id
        self.content = content
        self.tags = tags
        self.metadata = metadata or {}
        self.importance = importance
        self.created_at = "2026-09-15T00:00:00Z"


class _FakeStore:
    def __init__(self, entries):
        self._entries = entries

    def list(self, limit=5000):
        return self._entries[:limit]


@pytest.fixture()
def repo(tmp_path):
    return _fake_repo(tmp_path)


@pytest.fixture()
def home_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


# ---------------------------------------------------------------------------
# sanitize_text


def test_sanitize_masks_email_and_collapses_whitespace():
    out = sanitize_text("  mail  ta@example.edu\n\nfoo   bar  ")
    assert "ta@example.edu" not in out
    assert "[email redacted]" in out
    assert out == "mail [email redacted] foo bar"


def test_sanitize_non_str_returns_empty():
    assert sanitize_text(None) == ""
    assert sanitize_text(123) == ""


# ---------------------------------------------------------------------------
# converters


def test_courses_docs_chunk_and_tag(repo):
    docs = courses_docs(repo)
    assert docs
    assert all("courses" in d.tags for d in docs)
    assert all(d.text.startswith("[courses ·") for d in docs)
    # email from the fixture is masked
    assert not any("ta@example.edu" in d.text for d in docs)
    # tiny.txt (< MIN_CHUNK_WORDS) produces no docs
    assert not any("tiny" in d.source for d in docs)


def test_courses_docs_missing_dir_returns_empty(tmp_path):
    assert courses_docs(tmp_path) == []


def test_courses_docs_unreadable_file_skipped(repo, monkeypatch):
    # a file that raises on read is skipped, not fatal
    import levi.teach.converters as conv

    real_read = Path.read_text

    def boom(self, *a, **k):
        if self.name == "graphs.txt":
            raise OSError("disk gone")
        return real_read(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", boom)
    docs = conv.courses_docs(repo)
    assert docs
    assert not any("graphs" in d.source for d in docs)


def test_academy_docs_skips_malformed(repo):
    docs = academy_docs(repo)
    assert len(docs) == 1
    assert "academy" in docs[0].tags
    assert docs[0].meta.get("track") == "A"


def test_academy_docs_missing_file_returns_empty(tmp_path):
    assert academy_docs(tmp_path) == []


def test_growth_docs_from_fake_store():
    store = _FakeStore(
        [
            _FakeEntry(
                "m1",
                "Prefer short diagnostic commands over long speculative explanations every time.",
                ["growth", "levi-learned", "procedural"],
                {"confidence": 0.8, "corroborated_count": 2},
            ),
            _FakeEntry(
                "m2",
                "short",
                ["growth", "levi-learned", "fact"],
            ),  # too short, dropped
            _FakeEntry(
                "m3",
                "Unrelated memory entry with enough words here.",
                ["other"],
            ),  # wrong tags, dropped
        ]
    )
    docs = growth_docs(store=store)
    assert len(docs) == 1
    assert docs[0].text.startswith("[growth · procedural]")
    assert docs[0].meta["corroborated_count"] == 2


def test_growth_docs_min_confidence_filters():
    store = _FakeStore(
        [
            _FakeEntry(
                "m1",
                "A well corroborated learning about testing harnesses daily matters.",
                ["growth", "levi-learned", "fact"],
                {"confidence": 0.3},
            )
        ]
    )
    assert growth_docs(store=store, min_confidence=0.0)
    assert growth_docs(store=store, min_confidence=0.9) == []


def test_seed_docs_have_provenance():
    docs = seed_docs()
    assert docs
    assert all("seed-curriculum" in d.tags for d in docs)
    assert all(d.meta.get("lesson_id") for d in docs)


def test_collect_unknown_source_raises(repo):
    with pytest.raises(ValueError):
        collect(["courses", "nope"], root=repo)


def test_collect_all_sources(repo):
    out = collect(SOURCES, root=repo, min_confidence=0.0)
    assert set(out) == set(SOURCES)
    assert all(isinstance(v, list) for v in out.values())


def test_news_policy_gate_blocks_tagged_corpus():
    with pytest.raises(PolicyError):
        check_policy(("news",))


def test_news_policy_gate_blocks_news_path(tmp_path):
    with pytest.raises(PolicyError):
        check_policy(("courses",), str(tmp_path / "news" / "headlines.jsonl"))


# ---------------------------------------------------------------------------
# plan


def test_plan_teaching_reports_stats(repo):
    summary = plan_teaching(["courses", "academy"], root=repo, run_teachback=False)
    assert summary.n_docs_unique > 0
    assert summary.n_docs_raw >= summary.n_docs_unique
    assert len(summary.stages) == 4
    assert sum(summary.split_counts.values()) == summary.n_docs_unique
    assert abs(sum(summary.mix.values()) - 1.0) < 0.01
    # stages are contiguous simple -> complex (empty stages have None bounds)
    diffs = [s["difficulty_min"] for s in summary.stages]
    diffs = [d for d in diffs if d is not None]
    assert diffs == sorted(diffs)


def test_plan_teaching_unknown_source_raises(repo):
    with pytest.raises(TeachError):
        plan_teaching(["nope"], root=repo)


def test_plan_teaching_empty_sources_raise(tmp_path):
    with pytest.raises(TeachError):
        plan_teaching(["courses"], root=tmp_path)  # no raw dir -> no docs


def test_plan_teaching_bad_args(repo):
    with pytest.raises(TeachError):
        plan_teaching(["courses"], root=repo, n_stages=0)
    with pytest.raises(TeachError):
        plan_teaching(["courses"], root=repo, max_seq_len=4)


def test_plan_teachback_is_data_side_only(repo):
    summary = plan_teaching(["courses"], root=repo, run_teachback=True)
    tb = summary.teachback
    # probes filtered to the chosen sources (courses probes only)
    assert tb["n_probes"] == len(probes_for_source("courses"))
    assert 0.0 <= tb["coverage"] <= 1.0
    assert "probes" not in tb  # plan stays readable


# ---------------------------------------------------------------------------
# make_sequences


def test_make_sequences_curriculum_order_and_stages(repo):
    from levi.brain.train.v2.corpus_manager import dedupe
    from levi.brain.train.v2.curriculum import build_curriculum

    docs, _ = dedupe(courses_docs(repo))
    manifest = build_curriculum(docs, name="t", n_stages=2, seed=1)
    seqs = make_sequences(
        docs,
        order=manifest.order,
        stage_of=manifest.stage_of,
        max_seq_len=32,
    )
    assert seqs
    # order follows the manifest
    seen_docs = [s["doc_id"] for s in seqs]
    assert seen_docs == sorted(seen_docs, key=lambda i: manifest.order.index(i))
    # stage tags match the manifest
    for s in seqs:
        assert s["stage"] == manifest.stage_of[s["doc_id"]]
    # every sequence has words and provenance
    assert all(s["text"].split() for s in seqs)
    assert all(s["source"].startswith("courses:") for s in seqs)


def test_make_sequences_drops_runt_tails(repo):
    from levi.teach.prepare import _windows

    # 40 words, window 32 -> tail of 8 (< 16) dropped, 1 sequence
    text = " ".join(f"w{i}" for i in range(40))
    assert len(_windows(text, 32)) == 1
    # 50 words -> tail of 18 (>= 16) kept, 2 sequences
    text2 = " ".join(f"w{i}" for i in range(50))
    assert len(_windows(text2, 32)) == 2


# ---------------------------------------------------------------------------
# prepare


def test_prepare_writes_trainer_consumable_bundle(repo, home_env):
    out = repo / "bundle"
    manifest_path = prepare(
        out, name="t1", sources=["courses", "academy"], root=repo, seed=7
    )
    assert manifest_path.is_file()

    corpora = out / "corpora"
    for split in ("train", "val", "test"):
        jsonl = corpora / f"{split}.jsonl"
        assert jsonl.is_file()
        m = load_manifest(corpora / f"{split}.manifest.json")
        assert m.n_docs == len(load_jsonl_docs(jsonl))
    # per-source manifests verify against the written files
    for src in ("courses", "academy"):
        mp = corpora / f"source_{src}.manifest.json"
        assert verify_manifest(load_manifest(mp), base_dir=out) == []

    # curriculum + sequences
    curr = load_curriculum(out / "curriculum.json")
    assert len(curr.order) > 0
    seq_lines = (out / "sequences_train.jsonl").read_text(encoding="utf-8").splitlines()
    assert seq_lines
    first = json.loads(seq_lines[0])
    train_ids = {
        json.loads(line)["id"]
        for line in (corpora / "train.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    expected_first = next(i for i in curr.order if i in train_ids)
    assert first["doc_id"] == expected_first
    assert set(first) >= {"seq_id", "doc_id", "stage", "source", "text"}

    # train.yaml validates with the v2 config loader
    cfg = load_config(out / "train.yaml")
    assert cfg.name == "t1"
    assert cfg.data.mix
    assert {m_["manifest"] for m_ in cfg.data.mix} == {
        "corpora/source_courses.manifest.json",
        "corpora/source_academy.manifest.json",
    }

    # teach manifest + registry entry
    tm = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert tm["policy"] == "news-excluded"
    assert tm["n_docs_unique"] > 0
    reg_files = list(registry_dir().glob("*.json"))
    assert len(reg_files) == 1


def test_prepare_no_register_skips_home(repo, home_env):
    out = repo / "bundle2"
    prepare(out, name="t2", sources=["courses"], root=repo, register=False)
    assert list(registry_dir().glob("*.json")) == []


def test_prepare_rejects_empty_out(repo):
    with pytest.raises(TeachError):
        prepare("   ", sources=["courses"], root=repo)


def test_prepare_is_deterministic(repo, home_env):
    a = repo / "a"
    b = repo / "b"
    prepare(a, name="det", sources=["courses"], root=repo, seed=42)
    prepare(b, name="det", sources=["courses"], root=repo, seed=42)
    la = (a / "sequences_train.jsonl").read_text(encoding="utf-8")
    lb = (b / "sequences_train.jsonl").read_text(encoding="utf-8")
    assert la == lb
    ca = json.loads((a / "curriculum.json").read_text(encoding="utf-8"))["order"]
    cb = json.loads((b / "curriculum.json").read_text(encoding="utf-8"))["order"]
    assert ca == cb


def test_prepare_second_run_overwrites_cleanly(repo, home_env):
    out = repo / "bundle3"
    prepare(out, name="t3", sources=["courses"], root=repo)
    prepare(out, name="t3", sources=["academy"], root=repo)
    tm = json.loads((out / "teach.manifest.json").read_text(encoding="utf-8"))
    assert tm["sources"] == ["academy"]
    assert not (out / ".tmp").exists()


# ---------------------------------------------------------------------------
# teachback


def test_coverage_math():
    texts = ["Sorting algorithms arrange data. Quicksort is fast."]
    probes = [
        {
            "id": "p1",
            "topic": "t",
            "keywords": ("sorting", "quicksort", "banana"),
        }
    ]
    r = coverage(texts, probes, threshold=0.5)
    assert r["n_covered"] == 1
    assert r["coverage"] == 1.0
    assert r["probes"][0]["matched"] == 2
    assert r["probes"][0]["missing"] == ["banana"]


def test_coverage_threshold_boundary():
    texts = ["alpha beta"]
    probes = [{"id": "p", "topic": "t", "keywords": ("alpha", "gamma")}]
    assert coverage(texts, probes, threshold=0.5)["n_covered"] == 1
    assert coverage(texts, probes, threshold=0.6)["n_covered"] == 0


def test_coverage_bad_threshold_raises():
    with pytest.raises(TeachbackError):
        coverage(["x"], PROBES, threshold=0.0)
    with pytest.raises(TeachbackError):
        coverage(["x"], [], threshold=0.5)


def test_teachback_report_reads_prepared_bundle(repo, home_env):
    out = repo / "bundle4"
    prepare(out, name="tb", sources=["courses", "academy"], root=repo)
    report = teachback_report(out, split="train")
    assert report["n_texts"] > 0
    assert report["n_probes"] == len(PROBES)
    assert "NOT a claim" in report["disclaimer"]
    assert "model" in report["disclaimer"].lower()


def test_teachback_report_missing_bundle_raises(tmp_path):
    with pytest.raises(TeachbackError):
        teachback_report(tmp_path / "nope")


def test_probes_are_synthetic_and_sourced():
    assert len(PROBES) >= 10
    assert all(p.id and p.topic and p.source and p.keywords for p in PROBES)
    assert set(probes_for_source("courses")) <= set(PROBES)


# ---------------------------------------------------------------------------
# CLI


def _ns(**kw):
    base = dict(
        teach_cmd="plan",
        sources=["all"],
        name="cli",
        seed=1337,
        stages=2,
        max_seq_len=64,
        repo="",
        min_confidence=0.0,
        no_teachback=False,
        teachback_fail_under=None,
        out="",
        no_register=False,
    )
    base.update(kw)
    return argparse.Namespace(**base)


def test_cli_plan_smoke(repo, home_env, monkeypatch, capsys):
    monkeypatch.setenv("LEVI_REPO", str(repo))
    assert cmd_teach(_ns(teach_cmd="plan", stages=2)) == 0
    out = capsys.readouterr().out
    assert "teach plan" in out
    assert "news-excluded" in out
    assert "curriculum" in out


def test_cli_plan_unknown_source_exits_2(repo, monkeypatch):
    monkeypatch.setenv("LEVI_REPO", str(repo))
    parser_args = argparse.ArgumentParser()
    from levi.teach.cli import register_teach_parser

    sub = parser_args.add_subparsers()
    register_teach_parser(sub)
    with pytest.raises(SystemExit):
        parser_args.parse_args(["teach", "plan", "--sources", "nope"])


def test_cli_prepare_and_stats(repo, home_env, monkeypatch, capsys):
    monkeypatch.setenv("LEVI_REPO", str(repo))
    out = home_env / "bundle"
    ns = _ns(
        teach_cmd="prepare",
        stages=2,
        max_seq_len=64,
        out=str(out),
        sources=["courses", "academy"],
    )
    assert cmd_teach(ns) == 0
    assert (out / "teach.manifest.json").is_file()
    capsys.readouterr()

    assert cmd_teach(_ns(teach_cmd="stats")) == 0
    printed = capsys.readouterr().out
    assert "cli@" in printed or "cli" in printed


def test_cli_stats_empty_registry(home_env, capsys):
    assert cmd_teach(_ns(teach_cmd="stats")) == 0
    assert "no runs registered" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# round 3: bundle verification


def test_check_bundle_ok(repo, home_env):
    out = repo / "bundle6"
    prepare(out, name="chk", sources=["courses", "academy"], root=repo)
    report = check_bundle(out)
    assert report["ok"], report["problems"]
    assert report["stats"]["train_docs"] > 0
    assert report["stats"]["train_sequences"] > 0
    assert report["stats"]["curriculum_stages"] == 4


def test_check_bundle_missing_dir(tmp_path):
    report = check_bundle(tmp_path / "nope")
    assert not report["ok"]
    assert any("missing" in p for p in report["problems"])


def test_check_bundle_detects_tampered_corpus(repo, home_env):
    out = repo / "bundle7"
    prepare(out, name="chk2", sources=["courses"], root=repo)
    # tamper with a corpus file -> manifest hash check must fire
    p = out / "corpora" / "train.jsonl"
    p.write_text(
        p.read_text(encoding="utf-8") + '{"text": "injected"}\n', encoding="utf-8"
    )
    report = check_bundle(out)
    assert not report["ok"]
    assert any("hash mismatch" in prob for prob in report["problems"])


def test_check_bundle_missing_sequences(repo, home_env):
    out = repo / "bundle8"
    prepare(out, name="chk3", sources=["courses"], root=repo)
    (out / "sequences_test.jsonl").unlink()
    report = check_bundle(out)
    assert not report["ok"]
    assert any("sequences_test.jsonl" in prob for prob in report["problems"])


def test_check_bundle_broken_curriculum(repo, home_env):
    out = repo / "bundle9"
    prepare(out, name="chk4", sources=["courses"], root=repo)
    (out / "curriculum.json").write_text("{broken", encoding="utf-8")
    report = check_bundle(out)
    assert not report["ok"]
    assert any("curriculum.json" in prob for prob in report["problems"])


def test_check_bundle_broken_train_yaml(repo, home_env):
    out = repo / "bundle10"
    prepare(out, name="chk5", sources=["courses"], root=repo)
    (out / "train.yaml").write_text("name: [unclosed\n", encoding="utf-8")
    report = check_bundle(out)
    assert not report["ok"]
    assert any("train.yaml" in prob for prob in report["problems"])


def test_cli_check_command(repo, home_env, monkeypatch, capsys):
    monkeypatch.setenv("LEVI_REPO", str(repo))
    out = home_env / "bundle11"
    prepare(out, name="chk6", sources=["courses"], root=repo)
    assert cmd_teach(_ns(teach_cmd="check", dir=str(out))) == 0
    assert "teach check: OK" in capsys.readouterr().out
    # and a failing check exits 2
    assert cmd_teach(_ns(teach_cmd="check", dir=str(home_env / "nope"))) == 2
    assert "FAILED" in capsys.readouterr().out


def test_teach_home_uses_levi_home(home_env):
    # LEVI_HOME is the .levi dir itself (repo convention)
    assert teach_home() == home_env / "teach"
    assert registry_dir() == home_env / "teach" / "manifests"


# ---------------------------------------------------------------------------
# round 2: new sources, frontmatter, teachback gate


def test_briefs_docs(repo):
    docs = briefs_docs(repo)
    assert len(docs) == 1
    assert "field-guides" in docs[0].tags
    assert docs[0].text.startswith("[field guide · algorithms]")
    assert docs[0].meta["guide"] == "algorithms"


def test_briefs_docs_missing_dir_returns_empty(tmp_path):
    assert briefs_docs(tmp_path) == []


def test_playbooks_docs(repo):
    docs = playbooks_docs(repo)
    assert len(docs) == 2
    by_src = {d.source: d for d in docs}
    pb = by_src["playbooks:test-playbook.md#c0"]
    assert "defensive" in pb.tags
    assert pb.text.startswith("[defensive playbook · Test Detection Playbook]")
    assert pb.meta["playbook"] == "cyber_test_playbook"
    assert pb.meta["risk"] == "low"
    assert pb.meta["pb_tags"] == "detection,windows"
    # no-frontmatter file still converts, named by stem
    bare = by_src["playbooks:no-frontmatter.md#c0"]
    assert "Bare Playbook" in bare.text


def test_playbooks_docs_missing_dir_returns_empty(tmp_path):
    assert playbooks_docs(tmp_path) == []


def test_playbooks_news_path_still_gated(tmp_path):
    # the converter policy-checks the playbooks path: a news-looking path
    # is rejected even with clean tags
    from levi.brain.train.v2.corpus_manager import check_policy
    from levi.teach.converters import SOURCE_TAGS

    with pytest.raises(PolicyError):
        check_policy(SOURCE_TAGS["playbooks"], str(tmp_path / "news" / "x.md"))


def test_split_frontmatter_edge_cases():
    # no frontmatter
    meta, body = _split_frontmatter("# Title\n\nbody text here")
    assert meta == {}
    assert "body text here" in body
    # unterminated frontmatter -> treated as plain text, never raises
    meta, body = _split_frontmatter("---\nname: nope\nbody")
    assert meta == {}
    # malformed lines are skipped, good ones kept
    meta, body = _split_frontmatter(
        "---\nname: Good Name\nnot a kv line\nrisk: low\n---\nbody"
    )
    assert meta == {"name": "Good Name", "risk": "low"}
    assert body.strip() == "body"


def test_collect_all_sources_includes_new(repo):
    out = collect(SOURCES, root=repo, min_confidence=0.0)
    assert set(out) == set(SOURCES)
    assert out["briefs"]
    assert out["playbooks"]


def test_plan_with_new_sources(repo):
    summary = plan_teaching(["briefs", "playbooks"], root=repo, run_teachback=True)
    assert summary.n_docs_unique >= 3
    tb = summary.teachback
    assert tb["n_probes"] == 2  # filtered to the chosen sources
    assert {p.id for p in probes_for_source("briefs")} == {"field-guides"}
    assert {p.id for p in probes_for_source("playbooks")} == {"playbooks"}


def test_teachback_gate_raises_below_threshold(repo):
    with pytest.raises(TeachError, match="teachback gate"):
        plan_teaching(["courses"], root=repo, teachback_fail_under=0.5)


def test_teachback_gate_passes_at_zero(repo):
    summary = plan_teaching(["courses"], root=repo, teachback_fail_under=0.0)
    assert summary.teachback["coverage"] >= 0.0


def test_teachback_gate_bad_value_raises(repo):
    with pytest.raises(TeachError, match="within 0..1"):
        plan_teaching(["courses"], root=repo, teachback_fail_under=1.5)


def test_teachback_skipped_when_no_probes_match():
    result = _teachback_for_sources(["some text here"], ("zzz",))
    assert "skipped" in result


def test_plan_mix_bar_printed(repo, capsys):
    summary = plan_teaching(["courses", "seed"], root=repo, run_teachback=False)
    from levi.teach.cli import _print_plan

    _print_plan(summary)
    assert "█" in capsys.readouterr().out


def test_cli_prepare_fail_under_exits_2(repo, home_env, monkeypatch, capsys):
    monkeypatch.setenv("LEVI_HOME", str(home_env))
    monkeypatch.setenv("LEVI_REPO", str(repo))
    ns = _ns(
        teach_cmd="prepare",
        out=str(home_env / "bundle5"),
        sources=["courses"],
        teachback_fail_under=0.9,
    )
    assert cmd_teach(ns) == 2
    assert "teachback gate" in capsys.readouterr().out
