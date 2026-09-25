"""Client-side naive Bayes, trained on the local corpus.

Token-based spam scoring. The model is a local JSON file; retraining
is a housekeeping operation that runs fully offline on the labeled
corpus (labels from user corrections + filter outcomes — the archive
itself). Deterministic: same corpus → same model bytes.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

__all__ = ["BayesModel", "tokenize", "train", "score", "retrain"]

TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(text.lower())


@dataclass
class BayesModel:
    """Naive-Bayes token counts per class."""

    spam_counts: Dict[str, int] = field(default_factory=dict)
    ham_counts: Dict[str, int] = field(default_factory=dict)
    n_spam: int = 0
    n_ham: int = 0

    def to_dict(self) -> Dict[str, object]:
        return {
            "spam_counts": self.spam_counts,
            "ham_counts": self.ham_counts,
            "n_spam": self.n_spam,
            "n_ham": self.n_ham,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, object]) -> "BayesModel":
        return cls(
            spam_counts=dict(raw.get("spam_counts", {})),
            ham_counts=dict(raw.get("ham_counts", {})),
            n_spam=int(raw.get("n_spam", 0)),
            n_ham=int(raw.get("n_ham", 0)),
        )

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps(self.to_dict(), sort_keys=True, indent=1), encoding="utf-8"
        )

    @classmethod
    def load(cls, path: Path) -> "BayesModel":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


def train(corpus: Iterable[Tuple[str, str]]) -> BayesModel:
    """Train on ``(text, label)`` pairs; label in {"spam", "ham"}."""
    model = BayesModel()
    for text, label in corpus:
        tokens = tokenize(text)
        if label == "spam":
            model.n_spam += 1
            for tok in tokens:
                model.spam_counts[tok] = model.spam_counts.get(tok, 0) + 1
        elif label == "ham":
            model.n_ham += 1
            for tok in tokens:
                model.ham_counts[tok] = model.ham_counts.get(tok, 0) + 1
        else:
            raise ValueError(f"bad label: {label!r}")
    return model


def score(model: BayesModel, text: str) -> float:
    """P(spam | text) via log-odds with Laplace smoothing. In [0, 1]."""
    if model.n_spam == 0 or model.n_ham == 0:
        return 0.5
    tokens = tokenize(text)
    vocab = set(model.spam_counts) | set(model.ham_counts)
    v = max(len(vocab), 1)
    total_spam = sum(model.spam_counts.values())
    total_ham = sum(model.ham_counts.values())
    log_odds = math.log(model.n_spam / model.n_ham)
    for tok in set(tokens):
        p_tok_spam = (model.spam_counts.get(tok, 0) + 1) / (total_spam + v)
        p_tok_ham = (model.ham_counts.get(tok, 0) + 1) / (total_ham + v)
        log_odds += math.log(p_tok_spam / p_tok_ham)
    return 1.0 / (1.0 + math.exp(-log_odds))


def retrain(model_path: Path, corpus_path: Path) -> BayesModel:
    """Offline retrain: rebuild the model from the labeled corpus file.

    ``corpus_path`` is JSONL: ``{"text": ..., "label": "spam"|"ham"}``.
    Writes the new model to ``model_path`` and returns it.
    """
    corpus: List[Tuple[str, str]] = []
    for line in corpus_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        corpus.append((row["text"], row["label"]))
    model = train(corpus)
    model.save(model_path)
    return model
