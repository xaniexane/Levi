"""Hermetic tests for levi.brain.train.v2.eval_harness (numpy only).

Fake models script exact logits, so every number asserted here is a real
measured value from the harness — no torch needed.
"""

import json

import numpy as np
import pytest

from levi.brain.train.v2 import eval_harness as eh
from levi.brain.train.v2.eval_harness import EvalError


class FakeTokenizer:
    def __init__(self, words):
        self._w2i = {w: i for i, w in enumerate(words)}

    @property
    def vocab_size(self):
        return len(self._w2i)

    def encode(self, text):
        return [self._w2i[w] for w in text.split()]

    def decode(self, ids):
        inv = {i: w for w, i in self._w2i.items()}
        return " ".join(inv[i] for i in ids)


class ScriptedModel:
    """Logit 10.0 for the scripted next token, 0.0 elsewhere."""

    def __init__(self, vocab_size, mapping):
        self._v = vocab_size
        self._mapping = {tuple(k): v for k, v in mapping.items()}

    def logits_for_batch(self, prefixes):
        out = np.zeros((len(prefixes), self._v))
        for i, p in enumerate(prefixes):
            target = self._mapping.get(tuple(p), 0)
            out[i, target] = 10.0
        return out


class UniformModel:
    def __init__(self, vocab_size):
        self._v = vocab_size

    def logits_for_batch(self, prefixes):
        return np.zeros((len(prefixes), self._v))


WORDS = ["the", "cat", "sat", "dog", "ran", "pet", "wild"]


@pytest.fixture()
def tok():
    return FakeTokenizer(WORDS)


def test_perplexity_perfect_model_near_one(tok):
    # "the cat sat" repeated: script the -> cat, cat -> sat, sat -> the.
    ids = tok.encode("the cat sat the cat sat")
    the, cat, sat = tok.encode("the")[0], tok.encode("cat")[0], tok.encode("sat")[0]
    model = ScriptedModel(tok.vocab_size, {(the,): cat, (cat,): sat, (sat,): the})
    # prefix (the,) appears only as first token; longer prefixes unscripted.
    # Score single bigrams instead: chunk the sequence into pairs via max_len=2.
    out = eh.perplexity(model, tok, ids, max_len=2)
    assert out["n_tokens"] == 3  # 3 chunks of 2 tokens -> 3 scored bigrams
    assert out["perplexity"] < 1.5


def test_perplexity_uniform_equals_vocab_size(tok):
    ids = tok.encode("the cat sat dog ran pet")
    out = eh.perplexity(UniformModel(tok.vocab_size), tok, ids)
    assert out["n_tokens"] == 5
    assert out["perplexity"] == pytest.approx(tok.vocab_size, rel=1e-6)


def test_perplexity_empty_raises(tok):
    with pytest.raises(EvalError, match="no scorable"):
        eh.perplexity(UniformModel(tok.vocab_size), tok, [tok.encode("the")[0]])


def test_next_token_accuracy(tok):
    the, cat, dog = (tok.encode(w)[0] for w in ("the", "cat", "dog"))
    probes = [
        {"prefix": "the", "expected": "cat"},
        {"prefix": "the", "expected": "dog"},
    ]
    model = ScriptedModel(tok.vocab_size, {(the,): cat})
    out = eh.next_token_accuracy(model, tok, probes)
    assert out == {"accuracy": 0.5, "n": 2, "correct": 1}


def test_next_token_no_probes(tok):
    out = eh.next_token_accuracy(UniformModel(tok.vocab_size), tok, [])
    assert out["accuracy"] is None and out["n"] == 0


def test_next_token_empty_prefix_rejected(tok):
    with pytest.raises(EvalError, match="empty"):
        eh.next_token_accuracy(
            UniformModel(tok.vocab_size), tok, [{"prefix": "", "expected": "cat"}]
        )


def test_topic_classification_accuracy(tok):
    # Two probes with distinct prefixes; the scripted model prefers the
    # correct label for each, so shuffling cannot change the outcome.
    the, pet, wild, cat, dog = (
        tok.encode(w)[0] for w in ("the", "pet", "wild", "cat", "dog")
    )
    probes = [
        {
            "text": "the pet",
            "choices": [
                {"label": "cat", "text": "cat"},
                {"label": "dog", "text": "dog"},
            ],
        },
        {
            "text": "the wild",
            "choices": [
                {"label": "dog", "text": "dog"},
                {"label": "cat", "text": "cat"},
            ],
        },
    ]
    model = ScriptedModel(tok.vocab_size, {(the, pet): cat, (the, wild): dog})
    out = eh.topic_classification_accuracy(model, tok, probes)
    assert out == {"accuracy": 1.0, "n": 2, "correct": 2}
    # Deterministic: same seed -> same shuffle -> same score.
    again = eh.topic_classification_accuracy(model, tok, probes, seed=0)
    assert again == out


def test_topic_no_choices_rejected(tok):
    with pytest.raises(EvalError, match="no choices"):
        eh.topic_classification_accuracy(
            UniformModel(tok.vocab_size), tok, [{"text": "the pet", "choices": []}]
        )


def test_nan_logits_rejected(tok):
    class NaNModel:
        def logits_for_batch(self, prefixes):
            out = np.zeros((len(prefixes), tok.vocab_size))
            out[0, 0] = np.nan
            return out

    with pytest.raises(EvalError, match="non-finite"):
        eh.perplexity(NaNModel(), tok, tok.encode("the cat sat"))


def test_shape_mismatch_rejected(tok):
    class BadModel:
        def logits_for_batch(self, prefixes):
            return np.zeros((len(prefixes), tok.vocab_size + 1))

    with pytest.raises(EvalError, match="contract violated"):
        eh.perplexity(BadModel(), tok, tok.encode("the cat sat"))


def test_load_probes(tmp_path):
    p = tmp_path / "probes.jsonl"
    p.write_text(
        "# fixture header: first topic choice is the correct label\n"
        "\n"
        '{"kind": "next_token", "prefix": "the", "expected": "cat"}\n'
        '{"kind": "topic", "text": "the pet", "choices": '
        '[{"label": "cat", "text": "cat"}, {"label": "dog", "text": "dog"}]}\n',
        encoding="utf-8",
    )
    nt, topic = eh.load_probes(p)
    assert len(nt) == 1 and len(topic) == 1


def test_load_probes_bad_kind(tmp_path):
    p = tmp_path / "probes.jsonl"
    p.write_text('{"kind": "essay"}\n', encoding="utf-8")
    with pytest.raises(EvalError, match="unknown probe kind"):
        eh.load_probes(p)


def test_load_probes_missing(tmp_path):
    with pytest.raises(EvalError, match="not found"):
        eh.load_probes(tmp_path / "nope.jsonl")


def test_run_eval_honest_notes_for_weak_model(tok, tmp_path):
    # A model that confidently picks the WRONG label on every probe scores
    # 0.0 — at/below chance — and the report must say NOT capable plainly.
    the, pet, cat, dog = (tok.encode(w)[0] for w in ("the", "pet", "cat", "dog"))
    lines = [
        json.dumps(
            {
                "kind": "topic",
                "text": "the pet",
                "choices": [
                    {"label": "dog", "text": "dog"},
                    {"label": "cat", "text": "cat"},
                ],
            }
        )
        for _ in range(4)
    ]
    p = tmp_path / "probes.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    model = ScriptedModel(tok.vocab_size, {(the, pet): cat})  # wrong every time
    report = eh.run_eval(
        model, tok, model_name="confidently-wrong", step=0, probes_path=p
    )
    assert report.topic["accuracy"] == pytest.approx(0.0)
    assert "NOT capable" in " ".join(report.notes)


def test_capability_note_thresholds():
    assert "NOT capable" in eh._capability_note("t", 0.5, chance=0.5)
    assert "NOT capable" in eh._capability_note("t", 0.0, chance=0.5)
    assert "not reliable" in eh._capability_note("t", 0.4, chance=0.25)
    assert "untested" in eh._capability_note("t", None, chance=0.5)
    assert "modest signal" in eh._capability_note("t", 0.8, chance=0.5)


def test_run_eval_perplexity_note_for_bad_model(tok):
    ids = tok.encode("the cat sat dog ran pet")
    report = eh.run_eval(
        UniformModel(tok.vocab_size),
        tok,
        model_name="uniform",
        step=0,
        val_token_ids=ids,
    )
    assert report.perplexity["perplexity"] == pytest.approx(tok.vocab_size)
    # vocab 6 -> ppl 6, no "very high" note; force it with tiny crafted case
    assert report.notes == []


def test_run_eval_no_inputs(tok):
    report = eh.run_eval(UniformModel(tok.vocab_size), tok, model_name="m", step=0)
    assert any("nothing was measured" in n for n in report.notes)


def test_write_report_roundtrip(tok, tmp_path):
    report = eh.run_eval(
        UniformModel(tok.vocab_size),
        tok,
        model_name="m",
        step=7,
        val_token_ids=tok.encode("the cat sat"),
    )
    path = eh.write_report(report, tmp_path / "report.json")
    back = json.loads(path.read_text(encoding="utf-8"))
    assert back["model_name"] == "m"
    assert back["step"] == 7
    assert back["perplexity"]["n_tokens"] == 2


def _rep(name, ppl=None, nt=None, topic=None):
    return {
        "model_name": name,
        "perplexity": {"perplexity": ppl} if ppl else {},
        "next_token": {"accuracy": nt} if nt is not None else {},
        "topic": {"accuracy": topic} if topic is not None else {},
    }


def test_compare_improved():
    out = eh.compare_reports(
        _rep("base", ppl=100.0, nt=0.5), _rep("cand", ppl=80.0, nt=0.6)
    )
    assert out["metrics"]["perplexity"]["verdict"] == "improved"
    assert out["metrics"]["next_token"]["verdict"] == "improved"
    assert out["overall"] == "improved across all measured metrics"
    assert "honesty" in out


def test_compare_regressed_blocks_promotion():
    out = eh.compare_reports(
        _rep("base", ppl=80.0, nt=0.9), _rep("cand", ppl=70.0, nt=0.5)
    )
    assert out["metrics"]["perplexity"]["verdict"] == "improved"
    assert out["metrics"]["next_token"]["verdict"] == "regressed"
    assert "do not promote" in out["overall"]


def test_compare_within_noise():
    out = eh.compare_reports(
        _rep("base", ppl=100.0, nt=0.50), _rep("cand", ppl=99.0, nt=0.51)
    )
    assert out["metrics"]["perplexity"]["verdict"] == "within noise"
    assert out["metrics"]["next_token"]["verdict"] == "within noise"
    assert out["overall"] == "no clear change — within noise"


def test_compare_not_comparable():
    out = eh.compare_reports(_rep("base"), _rep("cand"))
    assert out["overall"].startswith("not comparable")


def test_make_probes_deterministic_and_loadable(tmp_path):
    from levi.brain.train.v2 import make_probes

    def doc(i):
        kind = "course" if i % 2 == 0 else "academy"
        sents = [" ".join(f"d{i}s{s}w{k}" for k in range(20)) + "." for s in range(4)]
        return {"id": f"d{i}", "text": " ".join(sents), "meta": {"kind": kind}}

    src = tmp_path / "docs.jsonl"
    src.write_text(
        "\n".join(json.dumps(doc(i)) for i in range(10)), encoding="utf-8"
    )
    out1, out2 = tmp_path / "p1.jsonl", tmp_path / "p2.jsonl"
    assert make_probes.main(["--input", str(src), "--output", str(out1)]) == 0
    assert make_probes.main(["--input", str(src), "--output", str(out2)]) == 0
    assert out1.read_bytes() == out2.read_bytes()  # same seed, same probes

    nt, topic = eh.load_probes(out1)
    assert len(nt) == 10 and len(topic) == 10
    assert all(p["kind"] == "next_token" for p in nt)
    assert all(p["choices"][0]["label"] in ("course", "academy") for p in topic)
