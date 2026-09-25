"""Tests for Income Batch A (gen_microtools): 12 micro-tool generators.

Covers: registry presence (slots 1-12), run() smoke per generator in
dry-run and real mode, dry-run safety (no deliverable files), price
bounds, and a few real-logic assertions per generator.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import levi.income.gen_microtools as batch  # noqa: F401  (self-registers)
from levi.income.engine import REGISTRY, WorkReport

IDS = [gid for gid, *_ in batch._DEFINITIONS]

SAMPLE_PARAMS = {
    "text-deduper": {"text": "apple\nbanana\napple\n\nbanana\ncherry\n", "mode": "line"},
    "csv-columnizer": {
        "csv_text": "First Name;Last Name;Age\nAda;Lovelace;36\nAlan;Turing;41\n"
    },
    "filename-normalizer": {
        "filenames": ["My Report (final).PDF", "my report (final).pdf", "notes.txt"]
    },
    "json-prettifier-validator": {"json_text": '{"b": 2, "a": 1}'},
    "markdown-toc-builder": {"markdown": "# Title\n\n## Setup\n\ntext\n\n## Usage\n"},
    "whitespace-surgeon": {
        "files": {"a.txt": "hello  \n\tworld\n\n\n\nbye"}
    },
    "regex-batch-replacer": {
        "text": "foo bar foo",
        "patterns": [{"pattern": "foo", "replacement": "baz"}],
    },
    "excerpt-extractor": {
        "text": (
            "The quick brown fox jumps over the lazy dog and the fox is clever. "
            "Weather forecasting relies on satellite data and computer models. "
            "The quick brown fox returns to the lazy dog again and again. "
            "Satellite data improves weather forecasting every single year. "
            "Dogs and foxes rarely share the same quiet meadow at dawn."
        ),
        "count": 2,
    },
    "unit-converter-pro": {
        "conversions": [
            {"value": 1, "from": "km", "to": "mi"},
            {"value": 32, "from": "F", "to": "C"},
            {"value": 1024, "from": "KB", "to": "MB"},
        ]
    },
    "passphrase-forge": {"words": 5, "passphrases": 2, "add_digit": True},
    "diff-summarizer": {
        "diff": (
            "diff --git a/app.py b/app.py\n"
            "--- a/app.py\n+++ b/app.py\n"
            "@@ -1,3 +1,4 @@ def main():\n"
            " def main():\n"
            "-    old()\n"
            "+    new()\n"
            "+    extra()\n"
            "     pass\n"
        )
    },
    "license-header-stamper": {
        "files": {"main.py": "#!/usr/bin/env python3\nprint('hi')\n"},
        "owner": "Test Owner",
        "year": "2026",
    },
}


def _ctx(tmp_path: Path, gid: str, dry_run: bool):
    return {
        "levi_home": tmp_path,
        "dry_run": dry_run,
        "params": SAMPLE_PARAMS[gid],
    }


def test_batch_claims_exactly_slots_1_to_12():
    assert len(IDS) == 12
    assert len(set(IDS)) == 12
    for i, gid in enumerate(IDS, start=1):
        assert REGISTRY.slot_of(gid) == i


def test_all_kinds_are_micro_tool():
    for gid in IDS:
        assert REGISTRY.get(gid).kind == "micro-tool"


def test_prices_within_doctrine_bounds():
    for gid in IDS:
        gen = REGISTRY.get(gid)
        assert gen.entry_price_usd is not None
        assert 1.0 <= gen.entry_price_usd <= 5.0


def test_dry_run_safety_no_deliverables(tmp_path):
    """Dry runs must not write any deliverable files under the work dir."""
    for gid in IDS:
        gen = REGISTRY.get(gid)
        report = gen.run(_ctx(tmp_path, gid, True))
        assert isinstance(report, WorkReport)
        assert report.generator_id == gid
        assert report.produced == []
        work = tmp_path / ".levi" / "income" / "work" / gid
        assert not work.exists(), f"{gid} wrote files during dry run"


def test_real_run_writes_artifacts(tmp_path):
    """Real runs write the artifacts they claim in the report."""
    for gid in IDS:
        gen = REGISTRY.get(gid)
        report = gen.run(_ctx(tmp_path, gid, False))
        assert isinstance(report, WorkReport)
        assert report.generator_id == gid
        assert report.produced, f"{gid} produced nothing in real mode"
        work = tmp_path / ".levi" / "income" / "work" / gid
        for artifact in report.produced:
            assert (work / artifact).is_file(), f"{gid}: {artifact} missing"
        if report.quoted_amount_usd is not None:
            assert 1.0 <= report.quoted_amount_usd <= 5.0


def test_dedupe_logic():
    gen = REGISTRY.get("text-deduper")
    r = gen.run({"levi_home": Path("/tmp/nope"), "dry_run": True,
                 "params": {"text": "a\nb\na\n", "mode": "line"}})
    assert "removed 1" in r.notes
    with pytest.raises(ValueError, match="mode"):
        gen.run({"levi_home": Path("/tmp/nope"), "dry_run": True,
                 "params": {"text": "x", "mode": "bogus"}})


def test_columnizer_detects_semicolon_and_slugs_headers(tmp_path):
    gen = REGISTRY.get("csv-columnizer")
    r = gen.run(_ctx(tmp_path, "csv-columnizer", False))
    cleaned = (tmp_path / ".levi" / "income" / "work" / "csv-columnizer" / "cleaned.csv").read_text()
    assert cleaned.splitlines()[0] == "first_name,last_name,age"
    assert "semicolon" in r.notes


def test_normalizer_handles_collisions_and_undo_manifest(tmp_path):
    gen = REGISTRY.get("filename-normalizer")
    gen.run(_ctx(tmp_path, "filename-normalizer", False))
    manifest = json.loads(
        (tmp_path / ".levi" / "income" / "work" / "filename-normalizer" / "undo_manifest.json").read_text()
    )
    vals = list(manifest["mapping"].values())
    assert len(set(vals)) == len(vals)  # collisions resolved
    assert manifest["mapping"]["notes.txt"] == "notes.txt"


def test_json_validator_pinpoints_errors(tmp_path):
    gen = REGISTRY.get("json-prettifier-validator")
    bad = {"levi_home": tmp_path, "dry_run": False,
           "params": {"json_text": '{"a": 1,\n"b": }'}}
    r = gen.run(bad)
    assert r.produced == ["error_report.txt"]
    body = (tmp_path / ".levi" / "income" / "work" / "json-prettifier-validator" / "error_report.txt").read_text()
    assert "line 2" in body and "^" in body
    good = gen.run({"levi_home": tmp_path, "dry_run": True,
                    "params": {"json_text": '{"b":2,"a":1}', "sort_keys": True}})
    assert "Valid JSON" in good.notes


def test_toc_builder_inserts_headings(tmp_path):
    gen = REGISTRY.get("markdown-toc-builder")
    gen.run(_ctx(tmp_path, "markdown-toc-builder", False))
    body = (tmp_path / ".levi" / "income" / "work" / "markdown-toc-builder" / "with_toc.md").read_text()
    assert "- [Title](#title)" in body
    assert "- [Setup](#setup)" in body
    assert "<!-- TOC -->" in body


def test_whitespace_surgeon_report(tmp_path):
    gen = REGISTRY.get("whitespace-surgeon")
    r = gen.run(_ctx(tmp_path, "whitespace-surgeon", False))
    assert "fix(es)" in r.notes
    cleaned = (tmp_path / ".levi" / "income" / "work" / "whitespace-surgeon" / "a.txt").read_text()
    assert not any(line != line.rstrip() for line in cleaned.splitlines())
    assert "\t" not in cleaned


def test_regex_replacer_preview_and_apply(tmp_path):
    gen = REGISTRY.get("regex-batch-replacer")
    dry = gen.run(_ctx(tmp_path, "regex-batch-replacer", True))
    assert "PREVIEW" in dry.notes and "2 match" in dry.notes
    gen.run(_ctx(tmp_path, "regex-batch-replacer", False))
    out = (tmp_path / ".levi" / "income" / "work" / "regex-batch-replacer" / "replaced.txt").read_text()
    assert out == "baz bar baz"


def test_excerpt_extractor_picks_top_sentences(tmp_path):
    gen = REGISTRY.get("excerpt-extractor")
    r = gen.run(_ctx(tmp_path, "excerpt-extractor", False))
    excerpts = (tmp_path / ".levi" / "income" / "work" / "excerpt-extractor" / "excerpts.txt").read_text()
    assert len([p for p in excerpts.strip().split("\n\n") if p]) == 2
    assert "2 key excerpt(s)" in r.notes


def test_converter_math(tmp_path):
    gen = REGISTRY.get("unit-converter-pro")
    r = gen.run(_ctx(tmp_path, "unit-converter-pro", False))
    records = json.loads(
        (tmp_path / ".levi" / "income" / "work" / "unit-converter-pro" / "conversions.json").read_text()
    )
    km_mi = next(x for x in records if x["from"] == "km")
    assert abs(km_mi["result"] - 0.621371) < 1e-5
    f_c = next(x for x in records if x["from"] == "F")
    assert abs(f_c["result"] - 0.0) < 1e-9
    assert "3 value(s)" in r.notes
    with pytest.raises(ValueError, match="incompatible"):
        gen.run({"levi_home": tmp_path, "dry_run": True,
                 "params": {"value": 1, "from": "kg", "to": "m"}})


def test_passphrase_forge_uses_wordlist(tmp_path):
    gen = REGISTRY.get("passphrase-forge")
    r = gen.run(_ctx(tmp_path, "passphrase-forge", False))
    lines = (tmp_path / ".levi" / "income" / "work" / "passphrase-forge" / "passphrases.txt").read_text().splitlines()
    assert len(lines) == 2
    wordlist = set(batch._FORGE_WORDS)
    for line in lines:
        parts = line.split("-")
        assert len(parts) == 6  # 5 words + digit
        assert parts[-1].isdigit()
        assert all(w in wordlist for w in parts[:-1])
    assert "entropy" in r.notes


def test_diff_summarizer_plain_language(tmp_path):
    gen = REGISTRY.get("diff-summarizer")
    r = gen.run(_ctx(tmp_path, "diff-summarizer", False))
    body = (tmp_path / ".levi" / "income" / "work" / "diff-summarizer" / "summary.txt").read_text()
    assert "app.py" in body and "2 line(s) added and 1 removed" in body
    assert "main" in body
    assert "+2/-1" in r.notes


def test_stamper_idempotent_and_shebang_safe(tmp_path):
    gen = REGISTRY.get("license-header-stamper")
    first = _ctx(tmp_path, "license-header-stamper", False)
    gen.run(first)
    stamped = (tmp_path / ".levi" / "income" / "work" / "license-header-stamper" / "main.py").read_text()
    assert stamped.startswith("#!/usr/bin/env python3\n# LEVI-LICENSE-HEADER")
    # restamping the already-stamped file must skip, not double-stamp
    again = gen.run({"levi_home": tmp_path, "dry_run": True,
                     "params": {"files": {"main.py": stamped}, "owner": "T"}})
    assert "1 stamped, 1 already" in again.notes or "0 stamped" in again.notes
    assert stamped.count("LEVI-LICENSE-HEADER") == 1


def test_generators_reject_bad_params(tmp_path):
    bad = {
        "text-deduper": {"text": 123, "mode": "nope"},
        "csv-columnizer": {"csv_text": ""},
        "filename-normalizer": {"filenames": []},
        "json-prettifier-validator": {"json_text": "   "},
        "markdown-toc-builder": {"markdown": "no headings here"},
        "whitespace-surgeon": {"files": {}},
        "regex-batch-replacer": {"text": "x", "patterns": [{"pattern": "("}]},
        "excerpt-extractor": {"text": "hi", "count": 1},
        "unit-converter-pro": {"conversions": []},
        "passphrase-forge": {"words": 2},
        "diff-summarizer": {"diff": ""},
        "license-header-stamper": {"files": {}},
    }
    for gid, params in bad.items():
        with pytest.raises(ValueError):
            REGISTRY.get(gid).run(
                {"levi_home": tmp_path, "dry_run": True, "params": params}
            )
