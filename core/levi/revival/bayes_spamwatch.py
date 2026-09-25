"""LEVI's SpamWatch: client-side Bayesian spam filtering.

Studied from: desktop-casualties-20260916 / report.md [3. Eudora]
(SpamWatch, client-side Bayesian spam filtering.)

The studied shape kept the judgment on your own machine: you taught it
what spam looked like, and it scored new mail with plain statistics —
no cloud, no blocklist subscription. This module rebuilds that as
LEVI's own Bayesian watcher. It learns word frequencies from mail you
mark spam or ham, then scores new mail with a Naive Bayes combination
over the most "interesting" words (those farthest from neutral).

What this is NOT: intelligence. It is counting plus Bayes' rule —
labeled plainly as a heuristic wherever it appears. It adapts only
when you teach it, it is honest about having too little data (it says
"undecided" instead of guessing), and it never deletes anything by
itself; it reports a probability and leaves the decision to filters
or to you.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple


ORIGIN = "levi-revival/bayes-spamwatch"

_TOKEN = re.compile(r"[a-z0-9']+")


@dataclass
class WordStats:
    """What the watcher has seen of one token."""

    spam: int = 0
    ham: int = 0

    def probability(self, spam_total: int, ham_total: int) -> float:
        """Spam probability of this word, Laplace-smoothed.

        Unseen words return 0.5 (neutral); words seen only a few times
        are pulled toward neutral so early training can't be tyrannical.
        """
        if self.spam + self.ham == 0:
            return 0.5
        # raw rate, then shrink toward 0.5 by a strength-of-evidence term
        raw = self.spam / (self.spam + self.ham)
        weight = (self.spam + self.ham) / (self.spam + self.ham + 3.0)
        return 0.5 + weight * (raw - 0.5)


class SpamWatch:
    """A client-side Bayesian spam scorer you teach yourself.

    ``learn(text, is_spam)`` feeds it examples. ``score(text)`` returns
    (label, probability) where the label is "spam", "ham", or
    "undecided". Thresholds and the undecided band are yours to set.
    """

    def __init__(
        self,
        spam_threshold: float = 0.9,
        ham_threshold: float = 0.1,
        interesting_words: int = 15,
        min_words_to_judge: int = 5,
    ) -> None:
        self.spam_threshold = spam_threshold
        self.ham_threshold = ham_threshold
        self.interesting_words = interesting_words
        self.min_words_to_judge = min_words_to_judge
        self._words: Dict[str, WordStats] = {}
        self._spam_messages = 0
        self._ham_messages = 0

    # -- teaching -------------------------------------------------------

    @staticmethod
    def tokens(text: str) -> List[str]:
        """Tokenize for learning/scoring: lowercase alphanumerics."""
        return _TOKEN.findall(text.lower())

    def learn(self, text: str, is_spam: bool) -> int:
        """Teach one message. Returns the number of distinct tokens seen."""
        seen = set(self.tokens(text))
        for token in seen:
            stats = self._words.setdefault(token, WordStats())
            if is_spam:
                stats.spam += 1
            else:
                stats.ham += 1
        if is_spam:
            self._spam_messages += 1
        else:
            self._ham_messages += 1
        return len(seen)

    def unlearn(self, text: str, was_spam: bool) -> None:
        """Take back a lesson (e.g. a mis-marked message)."""
        for token in set(self.tokens(text)):
            stats = self._words.get(token)
            if stats is None:
                continue
            if was_spam and stats.spam:
                stats.spam -= 1
            elif not was_spam and stats.ham:
                stats.ham -= 1
            if stats.spam == 0 and stats.ham == 0:
                del self._words[token]
        if was_spam and self._spam_messages:
            self._spam_messages -= 1
        elif not was_spam and self._ham_messages:
            self._ham_messages -= 1

    # -- judging ----------------------------------------------------------

    def score(self, text: str) -> Tuple[str, float]:
        """Score a message: (label, combined probability of spam).

        The label is a heuristic verdict — "spam", "ham", or
        "undecided" — from the Naive Bayes combination of the most
        interesting known words. "undecided" means the watcher admits
        it doesn't know yet; that honesty is the feature.
        """
        words = self.tokens(text)
        probs = []
        for token in set(words):
            stats = self._words.get(token)
            if stats is None or (stats.spam + stats.ham) == 0:
                continue
            p = stats.probability(self._spam_messages, self._ham_messages)
            probs.append((abs(p - 0.5), p))
        if len(probs) < self.min_words_to_judge:
            return ("undecided", 0.5)
        probs.sort(reverse=True)
        chosen = [p for _, p in probs[: self.interesting_words]]
        combined = self._combine(chosen)
        if combined >= self.spam_threshold:
            return ("spam", combined)
        if combined <= self.ham_threshold:
            return ("ham", combined)
        return ("undecided", combined)

    @staticmethod
    def _combine(probs: List[float]) -> float:
        """Naive Bayes combination of independent word probabilities."""
        prod = 1.0
        inv_prod = 1.0
        for p in probs:
            p = min(max(p, 0.01), 0.99)  # keep logs finite
            prod *= p
            inv_prod *= 1.0 - p
        return prod / (prod + inv_prod)

    # -- inspection -------------------------------------------------------

    def vocabulary_size(self) -> int:
        return len(self._words)

    def training_counts(self) -> Tuple[int, int]:
        """(spam messages, ham messages) taught so far."""
        return (self._spam_messages, self._ham_messages)

    def most_spammy(self, n: int = 10) -> List[Tuple[str, float]]:
        """Top-n tokens by spam probability — the watcher's own vocabulary."""
        ranked = [
            (t, s.probability(self._spam_messages, self._ham_messages))
            for t, s in self._words.items()
        ]
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:n]

    def export(self) -> Dict:
        """Plain-data snapshot of everything learned. Yours to keep."""
        return {
            "spam_messages": self._spam_messages,
            "ham_messages": self._ham_messages,
            "words": {t: [s.spam, s.ham] for t, s in self._words.items()},
        }

    def load(self, snapshot: Dict) -> None:
        """Restore from :meth:`export`. Replaces current knowledge."""
        self._spam_messages = snapshot.get("spam_messages", 0)
        self._ham_messages = snapshot.get("ham_messages", 0)
        self._words = {
            t: WordStats(spam=c[0], ham=c[1])
            for t, c in snapshot.get("words", {}).items()
        }
