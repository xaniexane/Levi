"""Tests for the conversational corpus and continued-training path.

- corpus builder: format, determinism, non-empty turns, identity law,
  register labels, size target.
- candidate weights: load in the torch-free runtime and generate
  deterministically (via learn_eval.export_portable).
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TRAIN = REPO / "core" / "levi" / "brain" / "train"
WEIGHTS = REPO / "core" / "levi" / "brain" / "weights"
DIALOGUE_CORPUS = TRAIN / "corpus_dialogue.jsonl"
CANDIDATE = WEIGHTS / "staging" / "tiny-gpt-continued.pt"

sys.path.insert(0, str(REPO / "core"))


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_dialogue_corpus", TRAIN / "build_dialogue_corpus.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def builder():
    return _load_builder()


@pytest.fixture(scope="module")
def built(builder):
    recs, problems = builder.build()
    return recs, problems


def test_builder_validation_clean(built):
    recs, problems = built
    assert problems == [], f"validation problems: {problems[:5]}"
    assert len(recs) > 200


def test_builder_deterministic(builder):
    r1, _ = builder.build()
    r2, _ = builder.build()
    j1 = [json.dumps(r, sort_keys=True) for r in r1]
    j2 = [json.dumps(r, sort_keys=True) for r in r2]
    assert j1 == j2


def test_dialogue_format_and_nonempty_turns(built):
    recs, _ = built
    n_dialogue = 0
    for r in recs:
        if r["kind"] != "dialogue":
            continue
        n_dialogue += 1
        text = r["text"]
        assert "User: " in text and "LEVI: " in text, r.get("topic")
        for turn in text.split("\n"):
            turn = turn.strip()
            if turn.startswith("User:"):
                assert len(turn) > len("User: "), f"empty user turn: {r.get('topic')}"
            if turn.startswith("LEVI:"):
                assert len(turn) > len("LEVI: "), f"empty LEVI turn: {r.get('topic')}"
    assert n_dialogue > 300


def test_identity_law_no_feeling_claims(built):
    """LEVI turns must never claim feelings/consciousness as experience."""
    import re

    recs, _ = built
    claim_pats = [
        r"\bi feel\b",
        r"\bi'm conscious\b",
        r"\bi am conscious\b",
        r"\bi'm alive\b",
        r"\bi am alive\b",
        r"\bi'm sentient\b",
    ]
    for r in recs:
        if r["kind"] != "dialogue":
            continue
        for turn in r["text"].split("\n"):
            turn = turn.strip()
            if not turn.startswith("LEVI:"):
                continue
            body = turn[len("LEVI:") :]
            for pat in claim_pats:
                for m in re.finditer(pat, body, re.IGNORECASE):
                    # negation within 60 chars = the law stating itself
                    window = body[max(0, m.start() - 60) : m.start()].lower()
                    neg = any(
                        h in window
                        for h in ("never", "not ", "no ", "n't", "don't", "without")
                    )
                    assert neg, (
                        f"feeling claim {pat!r} in {r.get('topic')}: {body[:120]}"
                    )


def test_registers_labeled(built):
    recs, _ = built
    regs = {r.get("register") for r in recs}
    assert regs <= {"levi", "lwp"}, f"unexpected registers: {regs}"
    assert "levi" in regs and "lwp" in regs, "both registers must be present"
    n_lwp = sum(1 for r in recs if r.get("register") == "lwp")
    assert n_lwp > 100, f"too few lwp-register records: {n_lwp}"


def test_corpus_file_sized():
    assert DIALOGUE_CORPUS.exists(), "run build_dialogue_corpus.py first"
    chars = sum(
        len(json.loads(line)["text"]) for line in DIALOGUE_CORPUS.open() if line.strip()
    )
    assert chars >= 150_000, f"dialogue corpus only {chars:,} chars, need >=150k"


def test_corpus_file_matches_builder(built, builder):
    recs, _ = built
    on_disk = [json.loads(line) for line in DIALOGUE_CORPUS.open() if line.strip()]
    assert len(on_disk) == len(recs), "corpus file stale — rebuild it"
    assert on_disk[0]["text"] == recs[0]["text"]
    assert on_disk[-1]["text"] == recs[-1]["text"]


# ------------------------------------------------- candidate weights


def _export_candidate_to_portable(tmp_path):
    pytest.importorskip("torch", reason="candidate test needs torch")
    from levi.brain.learn_eval import export_portable

    if not CANDIDATE.exists():
        pytest.skip("candidate weights not trained yet — run train/continue.py first")
    out = tmp_path / "candidate-portable"
    export_portable(CANDIDATE, out)
    return out


def test_candidate_loads_in_torchfree_runtime_and_is_deterministic(tmp_path):
    out = _export_candidate_to_portable(tmp_path)
    from levi.brain.runtime import load_runtime_brain

    handle = load_runtime_brain(portable_dir=str(out))
    a = handle.generate("User: hello\nLEVI:", max_new_chars=40, seed=11)
    b = handle.generate("User: hello\nLEVI:", max_new_chars=40, seed=11)
    assert a["continuation"] == b["continuation"], "generation not deterministic"
    assert len(a["continuation"]) > 0, "empty continuation"
    assert a["label"].startswith("raw brain continuation"), a["label"]


def test_candidate_keeps_original_vocab(tmp_path):
    torch = pytest.importorskip("torch", reason="candidate test needs torch")
    if not CANDIDATE.exists():
        pytest.skip("candidate not trained yet")
    cand = torch.load(CANDIDATE, map_location="cpu", weights_only=True)
    orig = torch.load(WEIGHTS / "tiny-gpt.pt", map_location="cpu", weights_only=True)
    assert cand["chars"] == orig["chars"], "candidate must keep the original vocab"
    assert cand["config"]["n_layer"] == orig["config"]["n_layer"]
    assert "parent" in cand["config"], "candidate must record its parent checkpoint"


# ------------------------------------------------- interpenetration


def test_fused_records_present_and_blended(built):
    """Interpenetration: fused records must exist, name >=2 pressures each,
    and span both registers. The blends are the point, not the pure forms."""
    recs, _ = built
    fused = [r for r in recs if "fusions" in r]
    assert len(fused) >= 40, f"too few fused records: {len(fused)}"
    for r in fused:
        assert isinstance(r["fusions"], list) and len(r["fusions"]) >= 2, (
            f"fused record {r.get('topic')} names fewer than 2 pressures"
        )
        assert r["register"] in ("levi", "lwp"), "register label must stay"
    regs = {r["register"] for r in fused}
    assert regs == {"levi", "lwp"}, f"fusions must span both registers: {regs}"
    n_triple = sum(1 for r in fused if len(r["fusions"]) >= 3)
    assert n_triple >= 20, f"too few triple fusions: {n_triple}"
    kinds = {r["kind"] for r in fused}
    assert "dialogue" in kinds and "lwp_prose" in kinds, (
        f"fusions must cover dialogue and prose: {kinds}"
    )


def test_fused_records_pass_identity_law(built, builder):
    recs, _ = built
    fused = [r for r in recs if "fusions" in r and r["kind"] == "dialogue"]
    assert fused
    for r in fused:
        for turn in r["text"].split("\n"):
            turn = turn.strip()
            if turn.startswith("LEVI:"):
                body = turn[len("LEVI:") :].strip()
                problems = builder._check_levi_turn(body, r.get("topic", "?"))
                assert problems == [], (
                    f"identity-law breach in {r.get('topic')}: {problems}"
                )
