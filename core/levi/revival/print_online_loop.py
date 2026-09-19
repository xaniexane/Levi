"""Print-online feedback loop: the magazine feeds the forum feeds the magazine.

Studied from: dead-networks-20260916/report.md [BIX]
(print-online feedback loop: magazine articles invite discussion on BIX, and
BIX excerpts get printed in the magazine).

This is an original, from-scratch implementation for LEVI. A ``Loop`` couples
a print *edition* cycle to an online *discussion* space:

- An edition publishes *articles*. Each article carries a discussion prompt —
  a question or call for response that names the online thread where readers
  should reply.
- Readers reply online; posts accrue *endorsements* (explicit reader counts,
  not algorithmic ranking).
- At edition time, an editor *harvests* excerpts: the top posts by
  endorsements, quoted with full provenance (thread id, post id, author, the
  article they answer). Harvested posts are marked so the same post is never
  printed twice, and a minimum-endorsement bar keeps the bar honest.
- The next edition *assembles*: new articles plus a "from the forum" section
  built from the harvested excerpts, each citing its online origin. The loop
  is closed and auditable — every printed line traces back to a post.

The module models the loop; it does not typeset or publish anything.

Public surface:
- ``Loop``: ``publish_article``, ``open_thread``, ``post``, ``endorse``,
  ``harvest_excerpts`` (selection), ``assemble_edition`` (close the loop),
  ``provenance()``, ``census()``.
- ``Article``, ``Excerpt``, ``LoopError`` for embedding.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Mapping

ORIGIN = "levi-revival/print-online-loop"


class LoopError(ValueError):
    """Raised when a loop operation cannot be honored."""


@dataclass(frozen=True)
class Article:
    """One print article with a discussion prompt pointing online."""

    article_id: str
    title: str
    body: str
    discussion_prompt: str
    thread_id: str

    def __post_init__(self) -> None:
        if not self.article_id or not self.title or not self.thread_id:
            raise LoopError("article_id, title, and thread_id must be non-empty")


@dataclass(frozen=True)
class Excerpt:
    """A harvested online post, quoted with full provenance."""

    quote: str
    author: str
    thread_id: str
    post_id: str
    answering_article: str
    endorsements: int


@dataclass
class _Post:
    post_id: str
    author: str
    body: str
    endorsements: int = 0
    harvested: bool = False


@dataclass
class _Thread:
    thread_id: str
    article_id: str
    posts: Dict[str, _Post] = field(default_factory=dict)


class Loop:
    """A print↔online feedback loop with provenance on every printed line."""

    def __init__(self, name: str, harvest_bar: int = 3, max_excerpts: int = 5) -> None:
        if not name:
            raise LoopError("loop name must be non-empty")
        if harvest_bar < 0 or max_excerpts < 1:
            raise LoopError("harvest_bar must be >= 0 and max_excerpts >= 1")
        self.name = name
        self.harvest_bar = harvest_bar  # min endorsements to be printable
        self.max_excerpts = max_excerpts
        self._articles: Dict[str, Article] = {}
        self._threads: Dict[str, _Thread] = {}
        self._editions: List[Dict[str, object]] = []
        self._seq = 0
        self._ledger: List[str] = []

    # -- ledger -----------------------------------------------------------
    def _log(self, entry: str) -> None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._ledger.append(f"{stamp} {entry}")

    def ledger(self) -> List[str]:
        return list(self._ledger)

    # -- print side: articles that invite discussion ------------------------------------
    def publish_article(
        self, article_id: str, title: str, body: str, discussion_prompt: str
    ) -> Article:
        """Publish an article; auto-opens its discussion thread online."""
        if article_id in self._articles:
            raise LoopError(f"article {article_id!r} already published")
        if not discussion_prompt.strip():
            raise LoopError("an article must carry a discussion prompt")
        thread_id = f"thread:{article_id}"
        article = Article(
            article_id=article_id,
            title=title,
            body=body,
            discussion_prompt=discussion_prompt,
            thread_id=thread_id,
        )
        self._articles[article_id] = article
        self._threads[thread_id] = _Thread(thread_id=thread_id, article_id=article_id)
        self._log(f"ARTICLE id={article_id} prompt={discussion_prompt!r}")
        return article

    # -- online side: discussion -----------------------------------------------------------
    def open_thread(self, thread_id: str, topic: str) -> _Thread:
        """Open a free-standing thread (not tied to an article)."""
        if thread_id in self._threads:
            raise LoopError(f"thread {thread_id!r} already open")
        thread = _Thread(thread_id=thread_id, article_id="")
        self._threads[thread_id] = thread
        self._log(f"THREAD id={thread_id} topic={topic!r}")
        return thread

    def post(self, thread_id: str, author: str, body: str) -> str:
        thread = self._require_thread(thread_id)
        if not author or not body.strip():
            raise LoopError("author and body must be non-empty")
        self._seq += 1
        post_id = f"p{self._seq:04d}"
        thread.posts[post_id] = _Post(post_id=post_id, author=author, body=body)
        self._log(f"POST thread={thread_id} id={post_id} author={author}")
        return post_id

    def endorse(self, thread_id: str, post_id: str, count: int = 1) -> int:
        """Explicit reader endorsements (a count, not a ranking algorithm)."""
        post = self._require_post(thread_id, post_id)
        if count < 1:
            raise LoopError("endorsement count must be >= 1")
        post.endorsements += count
        return post.endorsements

    # -- the loop closes: harvest, then assemble ----------------------------------------------
    def harvest_excerpts(self) -> List[Excerpt]:
        """Select printable excerpts: top endorsed, unharvested, above the bar.

        Selection is deterministic: endorsements descending, then post id.
        Harvested posts are marked so they are never printed twice.
        """
        candidates: List[Excerpt] = []
        for thread in self._threads.values():
            for post in thread.posts.values():
                if post.harvested or post.endorsements < self.harvest_bar:
                    continue
                candidates.append(
                    Excerpt(
                        quote=post.body,
                        author=post.author,
                        thread_id=thread.thread_id,
                        post_id=post.post_id,
                        answering_article=thread.article_id,
                        endorsements=post.endorsements,
                    )
                )
        candidates.sort(key=lambda e: (-e.endorsements, e.post_id))
        chosen = candidates[: self.max_excerpts]
        for excerpt in chosen:
            self._threads[excerpt.thread_id].posts[excerpt.post_id].harvested = True
        self._log(f"HARVEST count={len(chosen)}")
        return chosen

    def assemble_edition(
        self, edition_no: int, new_articles: List[Article]
    ) -> Mapping[str, object]:
        """Close the loop: new articles + 'from the forum' section of excerpts.

        Edition numbers must increase; every excerpt cites its provenance.
        """
        if self._editions and edition_no <= int(self._editions[-1]["edition_no"]):
            raise LoopError("edition numbers must increase")
        excerpts = self.harvest_excerpts()
        edition = {
            "edition_no": edition_no,
            "assembled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "articles": [a.article_id for a in new_articles],
            "from_the_forum": [
                {
                    "quote": e.quote,
                    "author": e.author,
                    "thread_id": e.thread_id,
                    "post_id": e.post_id,
                    "answering_article": e.answering_article,
                    "endorsements": e.endorsements,
                }
                for e in excerpts
            ],
        }
        self._editions.append(edition)
        self._log(
            f"EDITION no={edition_no} articles={len(new_articles)} excerpts={len(excerpts)}"
        )
        return edition

    # -- provenance and census -------------------------------------------------------------------
    def provenance(self, edition_no: int) -> List[Mapping[str, str]]:
        """Where every printed line came from."""
        for edition in self._editions:
            if int(edition["edition_no"]) == edition_no:
                return [
                    {
                        "post_id": str(e["post_id"]),
                        "thread_id": str(e["thread_id"]),
                        "author": str(e["author"]),
                        "answering_article": str(e["answering_article"]),
                    }
                    for e in edition["from_the_forum"]  # type: ignore[union-attr]
                ]
        raise LoopError(f"unknown edition {edition_no}")

    def editions(self) -> List[Mapping[str, object]]:
        return list(self._editions)

    def census(self) -> Mapping[str, int]:
        return {
            "articles": len(self._articles),
            "threads": len(self._threads),
            "posts": sum(len(t.posts) for t in self._threads.values()),
            "editions": len(self._editions),
            "printed_excerpts": sum(len(e["from_the_forum"]) for e in self._editions),
        }

    def _require_thread(self, thread_id: str) -> _Thread:
        try:
            return self._threads[thread_id]
        except KeyError:
            raise LoopError(f"unknown thread {thread_id!r}") from None

    def _require_post(self, thread_id: str, post_id: str) -> _Post:
        thread = self._require_thread(thread_id)
        try:
            return thread.posts[post_id]
        except KeyError:
            raise LoopError(f"unknown post {post_id!r} in {thread_id!r}") from None
