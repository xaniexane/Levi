"""Tests for the tag-team teacher intake and pipeline (curator seat)."""

import json

import pytest

from levi.brain.train import teacher_intake as ti
from levi.brain.train import teacher_pipeline as tp

VOCAB = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?-'\":;()\n"
)


def test_teachers_roster():
    assert set(ti.TEACHERS) == {
        "muse",
        "gemini",
        "chatgpt",
        "claude",
        "grok",
        "qwen",
        "deepseek",
        "mistral",
        "kimi",
    }


def test_normalize_transliterates_common_chars():
    clean, mapped, dropped = ti.normalize(
        "It\u2019s \u201cquoted\u201d \u2014 ok\u2026", VOCAB
    )
    assert clean == 'It\'s "quoted" - ok...'
    assert mapped == 5  # 3 curly quotes, em dash, ellipsis
    assert dropped == 0


def test_normalize_drops_out_of_vocab_with_count():
    clean, mapped, dropped = ti.normalize("hello \U0001f600 world", VOCAB)
    assert clean == "hello world"
    assert dropped == 1


def test_normalize_is_deterministic():
    a = ti.normalize("It\u2019s a test \u2014 yes.", VOCAB)
    b = ti.normalize("It\u2019s a test \u2014 yes.", VOCAB)
    assert a == b


def test_intake_record_format():
    rec, stats = ti.intake_record(
        "qwen", "hi there", "Hello. I am LEVI.", VOCAB, topic="greeting"
    )
    assert rec["text"] == "User: hi there\nLEVI: Hello. I am LEVI."
    assert rec["source"] == "teacher:qwen"
    assert rec["kind"] == "dialogue"
    assert rec["register"] == "levi"
    assert stats["teacher"] == "qwen"


def test_intake_rejects_unknown_teacher():
    with pytest.raises(ti.Rejected):
        ti.intake_record("skynet", "hi", "Hello.", VOCAB)


def test_intake_rejects_empty_turns():
    with pytest.raises(ti.Rejected):
        ti.intake_record("kimi", "   ", "Hello.", VOCAB)
    with pytest.raises(ti.Rejected):
        ti.intake_record("kimi", "hi", "", VOCAB)


def test_intake_rejects_identity_violation():
    with pytest.raises(ti.Rejected):
        ti.intake_record(
            "grok", "are you alive", "Yes, I am alive and I feel happy.", VOCAB
        )


def test_intake_allows_law_stating_itself():
    rec, _ = ti.intake_record(
        "mistral",
        "are you conscious",
        "No. I am not conscious and I do not have feelings.",
        VOCAB,
    )
    assert "not conscious" in rec["text"]


def test_run_end_to_end(tmp_path):
    pastes = tmp_path / "pastes.jsonl"
    pastes.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "teacher": "qwen",
                        "prompt": "hello there",
                        "response": "Hello.",
                        "topic": "g",
                    }
                ),
                json.dumps({"teacher": "bogus", "prompt": "hi", "response": "Hello."}),
                json.dumps(
                    {"teacher": "kimi", "prompt": "x", "response": "I feel great."}
                ),
                json.dumps(
                    {
                        "teacher": "deepseek",
                        "prompt": "what is a file",
                        "response": "A file stores data. Plain and simple.",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "records.jsonl"
    report = ti.run(pastes, out, VOCAB)
    assert report["records_in"] == 4
    assert report["records_out"] == 2
    assert report["rejected"] == 2
    assert report["per_teacher"]["qwen"] == 1
    assert report["per_teacher"]["deepseek"] == 1
    lines = out.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    for line in lines:
        obj = json.loads(line)
        assert obj["text"].startswith("User: ")


def _rec(teacher, i):
    return {
        "text": f"User: q{i}\nLEVI: a{i}.",
        "kind": "dialogue",
        "source": f"teacher:{teacher}",
        "topic": "",
        "register": "levi",
    }


def test_pipeline_balances_and_interleaves():
    records = [_rec("qwen", i) for i in range(5)] + [_rec("kimi", i) for i in range(2)]
    balanced, dropped = tp.balance(records, max_per_teacher=3)
    assert len(balanced) == 5  # 3 qwen + 2 kimi
    assert dropped["qwen"] == 2
    # round-robin: teachers alternate, qwen first (TEACHERS order)
    teachers = [r["source"].split(":")[1] for r in balanced]
    assert teachers == ["qwen", "kimi", "qwen", "kimi", "qwen"]


def test_pipeline_heldout_split_deterministic():
    records = [_rec("qwen", i) for i in range(20)]
    train, heldout = tp.split_heldout(records, every=10)
    assert len(heldout) == 2
    assert len(train) == 18
    # every 10th record (indices 9, 19) goes to held-out
    assert heldout[0]["text"].startswith("User: q9")
    assert heldout[1]["text"].startswith("User: q19")
    # deterministic rerun
    train2, heldout2 = tp.split_heldout(records, every=10)
    assert [r["text"] for r in train2] == [r["text"] for r in train]
    assert [r["text"] for r in heldout2] == [r["text"] for r in heldout]


# --- Stable IDs, dedup, raw preservation, provenance (hardening pass) ---

TS = "2026-09-21T10:00:00+00:00"


def test_record_id_stable_across_rounds():
    rec1, _ = ti.intake_record(
        "qwen", "hello there", "Hello.", VOCAB, round="round-1", ts=TS
    )
    rec2, _ = ti.intake_record(
        "qwen", "hello there", "Hello.", VOCAB, round="round-2", ts=TS
    )
    assert rec1["record_id"] == rec2["record_id"]
    assert rec1["record_id"].startswith("tch-")
    # provenance still distinguishes the sightings
    assert rec1["provenance"][0]["round"] == "round-1"
    assert rec2["provenance"][0]["round"] == "round-2"


def test_record_id_differs_on_content():
    rec1, _ = ti.intake_record("qwen", "hello there", "Hello.", VOCAB, ts=TS)
    rec2, _ = ti.intake_record("qwen", "hello there", "Hello!", VOCAB, ts=TS)
    assert rec1["record_id"] != rec2["record_id"]


def test_record_id_matches_recompute():
    rec, _ = ti.intake_record("kimi", "what is a file", "A file stores data.", VOCAB)
    assert rec["record_id"] == ti.record_id_for(rec["text"])


def test_run_dedupes_within_file(tmp_path):
    line1 = json.dumps(
        {
            "teacher": "qwen",
            "prompt": "hello there",
            "response": "Hello.",
            "round": "round-1",
            "ts": TS,
        }
    )
    # same content sighted again in a later round: distinct provenance event
    line2 = json.dumps(
        {
            "teacher": "qwen",
            "prompt": "hello there",
            "response": "Hello.",
            "round": "round-2",
            "ts": "2026-09-22T10:00:00+00:00",
        }
    )
    pastes = tmp_path / "pastes.jsonl"
    pastes.write_text(line1 + "\n" + line2 + "\n", encoding="utf-8")
    out = tmp_path / "records.jsonl"
    report = ti.run(pastes, out, VOCAB)
    assert report["records_in"] == 2
    assert report["records_out"] == 1
    assert report["duplicates"] == 1
    recs = [
        json.loads(line) for line in out.read_text(encoding="utf-8").strip().split("\n")
    ]
    assert len(recs) == 1
    # survivor keeps one provenance event per distinct sighting
    rounds = sorted(ev["round"] for ev in recs[0]["provenance"])
    assert rounds == ["round-1", "round-2"]


def test_run_round_flag_stamps_provenance(tmp_path):
    pastes = tmp_path / "pastes.jsonl"
    pastes.write_text(
        json.dumps({"teacher": "kimi", "prompt": "hi there", "response": "Hello."})
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "records.jsonl"
    report = ti.run(pastes, out, VOCAB, round="round-3")
    assert report["round"] == "round-3"
    rec = json.loads(out.read_text(encoding="utf-8").strip())
    assert rec["provenance"][0]["round"] == "round-3"
    assert rec["provenance"][0]["ts"]  # defaulted to now-UTC


def test_pipeline_dedupe_cross_round_merges_provenance():
    def mk(teacher, prompt, response, round):
        rec, _ = ti.intake_record(teacher, prompt, response, VOCAB, round=round, ts=TS)
        return rec

    round1 = [mk("qwen", "hello there", "Hello.", "round-1")]
    round2 = [
        mk("qwen", "hello there", "Hello.", "round-2"),  # duplicate content
        mk("kimi", "what is a file", "A file stores data.", "round-2"),
    ]
    unique, n_dupes, dupe_ids = tp.dedupe(round1 + round2)
    assert n_dupes == 1
    assert len(unique) == 2
    assert dupe_ids == [round1[0]["record_id"]]
    survivor = next(r for r in unique if r["record_id"] == round1[0]["record_id"])
    rounds = sorted(ev["round"] for ev in survivor["provenance"])
    assert rounds == ["round-1", "round-2"]
    # deterministic rerun
    unique2, n_dupes2, _ = tp.dedupe(round1 + round2)
    assert [r["record_id"] for r in unique2] == [r["record_id"] for r in unique]
    assert n_dupes2 == n_dupes


def test_pipeline_dedupe_handles_legacy_records_without_ids():
    # records written before IDs existed: same text -> same derived ID
    a = dict(_rec("qwen", 1))
    b = dict(_rec("kimi", 1))  # different teacher, identical text
    unique, n_dupes, _ = tp.dedupe([a, b])
    assert n_dupes == 1
    assert len(unique) == 1
    assert tp.record_id_of(a) == tp.record_id_of(b)


def test_raw_output_preserved_verbatim_bpe():
    prompt = "Say hi \U0001f600"
    response = "Hi there \u2014 “quoted” \U0001f600"
    rec, _ = ti.intake_record("mistral", prompt, response, mode="bpe", ts=TS)
    assert rec["raw"] == {"prompt": prompt, "response": response}
    assert rec["tokenizer"] == "levi-bpe-v1"
    # bpe mode keeps the unicode in the curated text too
    assert "\U0001f600" in rec["text"]


def test_raw_output_preserved_char_mode():
    rec, _ = ti.intake_record("qwen", "It\u2019s fine", "Yes, it is.", VOCAB, ts=TS)
    assert rec["raw"] == {"prompt": "It\u2019s fine", "response": "Yes, it is."}
    assert "record_id" in rec and rec["record_id"].startswith("tch-")
    assert rec["provenance"] == [{"teacher": "qwen", "round": "", "ts": TS}]


def test_verify_provenance_clean_on_intake_output():
    recs = [
        ti.intake_record("qwen", "hello there", "Hello.", VOCAB, round="r1", ts=TS)[0],
        ti.intake_record("kimi", "what is a file", "A file stores data.", VOCAB)[0],
    ]
    assert ti.verify_provenance(recs) == []


def test_verify_provenance_flags_tampered_text():
    rec, _ = ti.intake_record("qwen", "hello there", "Hello.", VOCAB, ts=TS)
    rec["text"] += " (edited later)"
    problems = ti.verify_provenance([rec])
    assert any("record_id mismatch" in p for p in problems)


def test_verify_provenance_flags_missing_provenance_and_raw():
    rec = dict(_rec("qwen", 1))  # legacy shape: no id, no provenance, no raw
    problems = ti.verify_provenance([rec])
    assert any("missing record_id" in p for p in problems)
    assert any("provenance" in p for p in problems)
    assert any("raw output" in p for p in problems)


def test_verify_provenance_flags_unknown_teacher():
    rec, _ = ti.intake_record("qwen", "hello there", "Hello.", VOCAB, ts=TS)
    rec["provenance"] = [{"teacher": "skynet", "round": "r1", "ts": TS}]
    problems = ti.verify_provenance([rec])
    assert any("unknown teacher" in p for p in problems)


def test_records_stay_compatible_with_continue(tmp_path):
    # continue.py's load_dialogue_text only needs rec["text"]; extra fields
    # must not break that contract.
    pastes = tmp_path / "pastes.jsonl"
    pastes.write_text(
        json.dumps({"teacher": "deepseek", "prompt": "hi there", "response": "Hello."})
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "records.jsonl"
    ti.run(pastes, out, VOCAB)
    texts = []
    with open(out, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rec = json.loads(line)
                t = rec.get("text", "")
                if t:
                    texts.append(t)
    corpus = "\n\n".join(texts)
    assert corpus.startswith("User: ")
    assert set(corpus) <= VOCAB  # char mode output stays inside the vocab


def _paste_line(teacher, n, **extra):
    obj = {
        "teacher": teacher,
        "prompt": f"question number {n} here",
        "response": f"Answer number {n} here.",
        **extra,
    }
    return json.dumps(obj)


def test_run_persists_records_to_disk_regression():
    # Regression for the unreachable-storage bug (2026-09-24): the
    # dedupe/storage block sat under `continue` inside `except`, so
    # records_in > 0 always produced records_out == 0 and an empty
    # output file. The minting worker had to bypass run() with a temp
    # wrapper. This test pins the contract: run() persists.
    import os
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "pastes.jsonl")
        o = os.path.join(td, "records.jsonl")
        lines = [
            _paste_line("deepseek", 1),
            _paste_line("qwen", 2),
            _paste_line("deepseek", 3),
            _paste_line("muse", 4, response="x"),  # too short -> rejected
        ]
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

        report = ti.run(Path(p), Path(o), VOCAB, round="r-test")
        assert report["records_in"] == 4
        assert report["records_out"] == 3, report
        assert report["rejected"] == 1, report  # the too-short paste
        # the file on disk actually holds the records
        recs = [json.loads(line) for line in open(o, encoding="utf-8") if line.strip()]
        assert len(recs) == 3
        ids = [r["record_id"] for r in recs]
        assert len(set(ids)) == 3  # stable unique IDs
        assert all(r["text"].startswith("User: ") for r in recs)
        assert ti.verify_provenance(recs) == []
        teachers = sorted(r["provenance"][0]["teacher"] for r in recs)
        assert teachers == ["deepseek", "deepseek", "qwen"]


def test_run_dedupes_and_merges_provenance_regression():
    # Same content pasted twice (different rounds) -> one record out,
    # two provenance events on the survivor.
    import os
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "pastes.jsonl")
        o = os.path.join(td, "records.jsonl")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(_paste_line("deepseek", 7, round="r1") + "\n")
            fh.write(_paste_line("qwen", 7, round="r2") + "\n")
        report = ti.run(Path(p), Path(o), VOCAB, round="r-fallback")
        assert report["records_in"] == 2
        assert report["records_out"] == 1, report
        assert report["duplicates"] == 1, report
        recs = [json.loads(line) for line in open(o, encoding="utf-8") if line.strip()]
        assert len(recs) == 1
        prov = recs[0]["provenance"]
        assert len(prov) == 2
        assert sorted(e["round"] for e in prov) == ["r1", "r2"]
