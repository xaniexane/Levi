"""Tests for the modality field on teacher intake + pipeline.

Backward-compatible: records without a modality key intake as "text".
New: "photo"/"video" records carry their modality through intake,
dedupe, balance, and held-out split untouched.
"""

import json

import pytest

from levi.brain.train import teacher_intake as ti
from levi.brain.train import teacher_pipeline as tp

VOCAB = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?-'\":;()\n"
)

PHOTO_PROMPT = "Generate a photo of a mystery box product shot while offline?"
PHOTO_RESP = ("Subject: a mystery box product shot. "
              "Composition: overhead flat-lay arrangement. "
              "Lighting: soft window light from the left. "
              "Style: clean product photography. "
              "Mood: focused and industrious.")
VIDEO_PROMPT = "Make a short video about the 45 dollar flip ladder?"
VIDEO_RESP = ("Shot 1 (0-3s): hands opening the box. "
              "Shot 2 (3-7s): close-up of the shipping label. "
              "Shot 3 (7-10s): stacking the finished boxes. "
              "Captions: Rung by rung. Audio: ambient workshop sound, no music.")


def test_modality_defaults_to_text():
    rec, _ = ti.intake_record("qwen", "hi there", "Hello. I am LEVI.",
                              VOCAB, topic="greeting")
    assert rec["modality"] == "text"


def test_photo_modality_accepted_and_stored():
    rec, _ = ti.intake_record("qwen", PHOTO_PROMPT, PHOTO_RESP, VOCAB,
                              topic="photo", modality="photo")
    assert rec["modality"] == "photo"
    assert rec["topic"] == "photo"


def test_video_modality_accepted_and_stored():
    rec, _ = ti.intake_record("grok", VIDEO_PROMPT, VIDEO_RESP, VOCAB,
                              topic="video", modality="video")
    assert rec["modality"] == "video"


def test_modality_case_and_whitespace_normalized():
    rec, _ = ti.intake_record("qwen", PHOTO_PROMPT, PHOTO_RESP, VOCAB,
                              modality=" Photo ")
    assert rec["modality"] == "photo"


def test_unknown_modality_rejected():
    with pytest.raises(ti.Rejected):
        ti.intake_record("qwen", "hi there", "Hello. I am LEVI.", VOCAB,
                         modality="hologram")


def test_bpe_mode_carries_modality():
    rec, _ = ti.intake_record("qwen", PHOTO_PROMPT, PHOTO_RESP,
                              mode="bpe", modality="photo")
    assert rec["modality"] == "photo"
    assert rec["tokenizer"] == "levi-bpe-v1"


def test_modality_does_not_change_record_id():
    a, _ = ti.intake_record("qwen", "hi there", "Hello. I am LEVI.", VOCAB)
    b, _ = ti.intake_record("qwen", "hi there", "Hello. I am LEVI.", VOCAB,
                            modality="text")
    assert a["record_id"] == b["record_id"]


def test_run_ingests_mixed_modalities(tmp_path):
    pastes = tmp_path / "pastes.jsonl"
    pastes.write_text("\n".join([
        json.dumps({"teacher": "qwen", "prompt": "hi there",
                    "response": "Hello. I am LEVI."}),
        json.dumps({"teacher": "qwen", "prompt": PHOTO_PROMPT,
                    "response": PHOTO_RESP, "topic": "photo",
                    "modality": "photo"}),
        json.dumps({"teacher": "grok", "prompt": VIDEO_PROMPT,
                    "response": VIDEO_RESP, "topic": "video",
                    "modality": "video"}),
        json.dumps({"teacher": "kimi", "prompt": "bad one",
                    "response": "nope", "modality": "hologram"}),
    ]) + "\n", encoding="utf-8")
    out = tmp_path / "records.jsonl"
    report = ti.run(pastes, out, VOCAB, mode="char", round="mm-1")
    assert report["records_out"] == 3
    assert report["rejected"] == 1  # the hologram
    assert report["per_modality"] == {"text": 1, "photo": 1, "video": 1}
    recs = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert [r["modality"] for r in recs] == ["text", "photo", "video"]


def test_pipeline_preserves_modality_end_to_end(tmp_path):
    pastes = tmp_path / "pastes.jsonl"
    lines = []
    for i, (pr, re, mo, to) in enumerate([
        ("hi there", "Hello. I am LEVI.", "text", ""),
        (PHOTO_PROMPT, PHOTO_RESP, "photo", "photo"),
        (VIDEO_PROMPT, VIDEO_RESP, "video", "video"),
    ]):
        lines.append(json.dumps({"teacher": "qwen", "prompt": f"{pr} {i}",
                                 "response": f"{re} {i}", "topic": to,
                                 "modality": mo}))
    pastes.write_text("\n".join(lines) + "\n", encoding="utf-8")
    records = tmp_path / "records.jsonl"
    ti.run(pastes, records, VOCAB, mode="char", round="mm-1")
    train = tmp_path / "train.jsonl"
    heldout = tmp_path / "heldout.jsonl"
    rc = tp.main(["--in", str(records), "--train-out", str(train),
                  "--heldout-out", str(heldout), "--max-per-teacher", "100",
                  "--heldout-every", "10"])
    assert rc == 0
    got = {}
    for path in (train, heldout):
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            got[r["modality"]] = got.get(r["modality"], 0) + 1
    assert got == {"text": 1, "photo": 1, "video": 1}


def test_verify_provenance_accepts_modalities():
    rec, _ = ti.intake_record("qwen", PHOTO_PROMPT, PHOTO_RESP, VOCAB,
                              modality="photo")
    assert ti.verify_provenance([rec]) == []


def test_verify_provenance_flags_bad_modality():
    rec, _ = ti.intake_record("qwen", PHOTO_PROMPT, PHOTO_RESP, VOCAB,
                              modality="photo")
    rec["modality"] = "hologram"
    problems = ti.verify_provenance([rec])
    assert any("modality" in p for p in problems)


def test_verify_provenance_tolerates_legacy_records():
    rec, _ = ti.intake_record("qwen", "hi there", "Hello. I am LEVI.", VOCAB)
    del rec["modality"]  # simulate a pre-modality record
    assert ti.verify_provenance([rec]) == []
