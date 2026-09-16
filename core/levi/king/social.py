"""Sanitized social-pack generation — content only, NEVER the network.

Blueprint §4: caption text + hashtags per platform, genuinely stripped of
any markdown syntax that leaked in from source story text. This exact bug
shipped once before (``#``/``**`` reaching a real social caption), so the
contract is enforced by assertions on the generated text, not a skim.

THE SANITIZE CONTRACT
---------------------
1. All markdown *structure* is removed from source text before a caption
   is built: ATX headings (``# Title``), emphasis markers (``**bold**``,
   ``__``/``*``/``_`` wrappers), inline code spans (backticks), images,
   links (``[text](url)`` → ``text``), blockquotes, horizontal rules.
2. Any ``#`` surviving step 1 is stripped from the *body* as well — a
   ``#`` in a final caption may only ever be one we generated ourselves
   as a hashtag. (Source hashtags lose their ``#`` but keep the word.)
3. Hashtags are generated fresh from content keywords and appended in a
   trailing block, AFTER sanitization. Every ``#x`` in a final caption
   matches ``#[A-Za-z][A-Za-z0-9_]*`` and sits in the hashtag block.

``build_pack()`` is a pure function of (source_text, platform, title):
no network, no credentials, no side effects. Actual posting routes
through ``levi.plugins.registry`` (see ``King.social_post``) and is
confirmation-gated there with no bypass.
"""

from __future__ import annotations

import re
from typing import Dict, List

# -- sanitize ------------------------------------------------------------

_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_CODE = re.compile(r"`([^`]+?)`")
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MD_BOLD_US = re.compile(r"__(.+?)__")
_MD_ITAL = re.compile(r"(?<!\*)\*(?!\*)([^*\n]+?)(?<!\*)\*(?!\*)")
_MD_ITAL_US = re.compile(r"(?<!_)_(?!_)([^_\n]+?)(?<!_)_(?!_)")
_MD_STRIKE = re.compile(r"~~(.+?)~~")
_MD_HEADING = re.compile(r"(?m)^\s{0,3}#{1,6}\s+")
_MD_QUOTE = re.compile(r"(?m)^\s{0,3}>\s?")
_MD_HR = re.compile(r"(?m)^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")
_MD_FENCE = re.compile(r"(?m)^\s{0,3}```.*$")
_WS = re.compile(r"[ \t]+")
_BLANK = re.compile(r"\n{3,}")


def sanitize(text: str) -> str:
    """Strip markdown syntax from source text. Pure function."""
    if text is None:
        return ""
    if not isinstance(text, str):
        raise ValueError(f"sanitize needs a string, got {type(text).__name__}")
    if not text:
        return ""
    out = text
    out = _MD_IMAGE.sub(r"\1", out)
    out = _MD_LINK.sub(r"\1", out)
    out = _MD_CODE.sub(r"\1", out)
    out = _MD_FENCE.sub("", out)
    out = _MD_BOLD.sub(r"\1", out)
    out = _MD_BOLD_US.sub(r"\1", out)
    out = _MD_STRIKE.sub(r"\1", out)
    out = _MD_ITAL.sub(r"\1", out)
    out = _MD_ITAL_US.sub(r"\1", out)
    out = _MD_HEADING.sub("", out)
    out = _MD_QUOTE.sub("", out)
    out = _MD_HR.sub("", out)
    # Contract step 2: no stray '#' survives in the body.
    out = out.replace("#", "")
    out = _WS.sub(" ", out)
    out = _BLANK.sub("\n\n", out)
    return out.strip()


_HASHTAG_RE = re.compile(r"#[A-Za-z][A-Za-z0-9_]*")

_STOPWORDS = frozenset(
    """
    the a an and or of to in on for with as at by from is was are were be
    been being it its this that these those they them their he she his her
    we you your i me my our us not no but if then than so such into over
    after before between through during under again once here there when
    where which who whom whose what how why all any both each few more
    most other some such only own same too very can will just don should
    now had has have do does did would could ought than then
    """.split()
)
_WORD = re.compile(r"[a-z][a-z0-9']{3,}")


def hashtags_from(text: str, limit: int = 5) -> List[str]:
    """Deterministic keyword hashtags from sanitized text.

    Frequency-ranked, ties broken alphabetically — same input, same
    tags, every run. Never emits a tag for a stopword.
    """
    if not isinstance(text, str):
        raise ValueError(f"hashtags_from needs a string, got {type(text).__name__}")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError(
            f"hashtags_from limit must be a non-negative int, got {limit!r}"
        )
    counts: Dict[str, int] = {}
    for m in _WORD.finditer(text.lower()):
        w = m.group(0).strip("'")
        if len(w) < 4 or w in _STOPWORDS:
            continue
        counts[w] = counts.get(w, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return ["#" + w for w, _ in ranked[: max(0, limit)]]


# -- platforms -----------------------------------------------------------

PLATFORMS: Dict[str, Dict[str, int]] = {
    "x": {"caption_max": 280, "excerpt_max": 200, "hashtags": 3},
    "threads": {"caption_max": 500, "excerpt_max": 320, "hashtags": 4},
    "bluesky": {"caption_max": 300, "excerpt_max": 210, "hashtags": 3},
    "instagram": {"caption_max": 2200, "excerpt_max": 400, "hashtags": 8},
    "tiktok": {"caption_max": 2200, "excerpt_max": 160, "hashtags": 5},
}


def _excerpt(clean: str, max_chars: int) -> str:
    if len(clean) <= max_chars:
        return clean
    cut = clean[:max_chars]
    # Prefer a sentence boundary; fall back to a word boundary.
    for sep in (". ", "! ", "? ", "\n"):
        idx = cut.rfind(sep)
        if idx > max_chars // 2:
            return cut[: idx + 1].strip()
    idx = cut.rfind(" ")
    return (cut[:idx] if idx > 0 else cut).strip()


def build_pack(
    source_text: str, platform: str = "x", title: str = ""
) -> Dict[str, object]:
    """Build a sanitized social pack. Pure function — no network.

    Returns ``{"platform", "title", "caption", "hashtags",
    "caption_chars", "source_chars"}``. ``caption`` is the sanitized
    excerpt plus a trailing hashtag block; it is guaranteed to satisfy
    the sanitize contract (asserted by the test suite on real output).
    """
    if not isinstance(platform, str) or platform not in PLATFORMS:
        raise ValueError(
            f"Unknown platform {platform!r}. Choose: {', '.join(sorted(PLATFORMS))}"
        )
    if not isinstance(title, str):
        raise ValueError(f"title must be a string, got {type(title).__name__}")
    spec = PLATFORMS[platform]
    clean = sanitize(source_text)
    if not clean:
        raise ValueError("Nothing to post: source text sanitizes to empty.")
    body = _excerpt(clean, spec["excerpt_max"])
    if title:
        head = sanitize(title)
        body = (head + "\n\n" + body) if head else body
    tags = hashtags_from(clean, spec["hashtags"])
    caption = body + ("\n\n" + " ".join(tags) if tags else "")
    if len(caption) > spec["caption_max"]:
        # Re-trim the body (never the hashtags) to fit the platform cap.
        room = spec["caption_max"] - len(" ".join(tags)) - 2
        body = _excerpt(body, max(40, room))
        caption = body + ("\n\n" + " ".join(tags) if tags else "")
    return {
        "platform": platform,
        "title": title,
        "caption": caption,
        "hashtags": tags,
        "caption_chars": len(caption),
        "source_chars": len(source_text or ""),
    }


def assert_pack_clean(pack: Dict[str, object]) -> None:
    """Enforce the sanitize contract on a built pack. Raises AssertionError."""
    if not isinstance(pack, dict):
        raise ValueError(
            f"assert_pack_clean needs a pack dict, got {type(pack).__name__}"
        )
    caption = str(pack.get("caption", ""))
    assert "**" not in caption, "markdown bold leaked into caption"
    assert "__" not in caption, "markdown bold leaked into caption"
    assert "`" not in caption, "markdown code span leaked into caption"
    for line in caption.splitlines():
        assert not re.match(r"^\s*#{1,6}\s+\S", line), (
            f"markdown heading leaked into caption: {line[:60]!r}"
        )
    # Every '#' must be a well-formed hashtag in the trailing block.
    for m in re.finditer(r"#", caption):
        rest = caption[m.start() :]
        assert _HASHTAG_RE.match(rest), f"stray '#' at offset {m.start()}"
    # Hashtags live only in the trailing block (last paragraph).
    paras = [p for p in caption.split("\n\n") if p.strip()]
    if paras and "#" in caption:
        assert "#" not in "\n\n".join(paras[:-1]), "hashtag outside trailing block"
