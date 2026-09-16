"""Repo browser: file tree, file contents, commit history, README rendering.

Everything is read from the bare repo with stock git. Markdown rendering
is a minimal stdlib-only converter (headings, fenced code, lists, quotes,
bold/italic/code/links) — enough for honest README display, not a spec
implementation.
"""

from __future__ import annotations

import html
import re

from .gitx import GitError, run_git
from .home import validate_name
from .repos import repo_dir, repo_exists


def _rev(home, name, rev) -> str:
    """Resolve rev to a sha; raise GitError with a clear message if bad."""
    rev = rev or "HEAD"
    try:
        return run_git(
            ["rev-parse", "--verify", rev + "^{commit}"],
            cwd=repo_dir(home, name),
        ).stdout.decode("utf-8", "replace").strip()
    except GitError:
        raise GitError("no such revision %r in repo %r" % (rev, name))


def tree(home, name, rev=None, path=""):
    """List directory entries at path: [{'name','type','mode','sha'}, ...]."""
    name = validate_name(name)
    if not repo_exists(home, name):
        raise GitError("no such repo: %r" % name)
    sha = _rev(home, name, rev)
    treeish = sha + ":" + (path.strip("/") or ".")
    try:
        out = run_git(
            ["ls-tree", treeish], cwd=repo_dir(home, name)
        ).stdout.decode("utf-8", "replace")
    except GitError:
        raise GitError("no such path %r at %r" % (path, rev or "HEAD"))
    entries = []
    for line in out.splitlines():
        # "<mode> <type> <sha>\t<name>"
        meta, _, fname = line.partition("\t")
        mode, ftype, fsha = meta.split()
        entries.append({"name": fname, "type": ftype, "mode": mode, "sha": fsha})
    entries.sort(key=lambda e: (e["type"] != "tree", e["name"].lower()))
    return entries


def read_file(home, name, rev=None, path="") -> str:
    """Return decoded file contents at rev:path (binary-safe refusal)."""
    name = validate_name(name)
    if not repo_exists(home, name):
        raise GitError("no such repo: %r" % name)
    sha = _rev(home, name, rev)
    if not path or path.endswith("/"):
        raise GitError("path %r is not a file" % path)
    proc = run_git(
        ["show", sha + ":" + path.strip("/")], cwd=repo_dir(home, name), check=False
    )
    if proc.returncode != 0:
        raise GitError("no such file %r at %r" % (path, rev or "HEAD"))
    blob = proc.stdout
    if b"\x00" in blob[:8192]:
        raise GitError("refusing to render binary file %r" % path)
    return blob.decode("utf-8", "replace")


def log(home, name, rev=None, limit: int = 20):
    """Commit history: [{'sha','author','date','subject'}, ...]."""
    name = validate_name(name)
    if not repo_exists(home, name):
        raise GitError("no such repo: %r" % name)
    out = run_git(
        ["log", "--format=%H%x00%an%x00%ad%x00%s", "--date=iso",
         "-n", str(max(1, limit)), rev or "HEAD"],
        cwd=repo_dir(home, name),
        check=False,
    ).stdout.decode("utf-8", "replace")
    commits = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x00")
        if len(parts) == 4:
            commits.append(
                {"sha": parts[0], "author": parts[1],
                 "date": parts[2], "subject": parts[3]}
            )
    return commits


def find_readme(home, name, rev=None):
    """Return the README filename at repo root, or None."""
    try:
        entries = tree(home, name, rev, "")
    except GitError:
        return None
    cands = [e["name"] for e in entries
             if e["type"] == "blob" and e["name"].upper().startswith("README")]
    cands.sort(key=lambda n: (not n.lower().endswith(".md"), n.lower()))
    return cands[0] if cands else None


# -- minimal markdown -> HTML (stdlib only) --------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def _inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = _INLINE_CODE_RE.sub(lambda m: "<code>%s</code>" % m.group(1), text)
    text = _BOLD_RE.sub(lambda m: "<strong>%s</strong>" % m.group(1), text)
    text = _ITALIC_RE.sub(lambda m: "<em>%s</em>" % m.group(1), text)
    text = _LINK_RE.sub(
        lambda m: '<a href="%s">%s</a>' % (html.escape(m.group(2), quote=True), m.group(1)),
        text,
    )
    return text


def render_markdown(text: str) -> str:
    """Minimal markdown to HTML. Honest subset: headings, fenced code,
    blockquotes, lists, hr, paragraphs, and inline code/bold/italic/links."""
    out = []
    lines = text.splitlines()
    i = 0
    in_list = None  # "ul" | "ol" | None
    para = []

    def flush_para():
        if para:
            out.append("<p>%s</p>" % _inline(" ".join(para)))
            para.clear()

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</%s>" % in_list)
            in_list = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_para()
            close_list()
            lang = stripped[3:].strip()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1  # skip closing fence (or EOF)
            out.append(
                '<pre><code class="lang-%s">%s</code></pre>'
                % (html.escape(lang, quote=True), html.escape("\n".join(code)))
            )
            continue
        m = _HEADING_RE.match(stripped)
        if m:
            flush_para()
            close_list()
            level = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (level, _inline(m.group(2).strip()), level))
            i += 1
            continue
        if stripped in ("---", "***", "___"):
            flush_para()
            close_list()
            out.append("<hr>")
            i += 1
            continue
        if stripped.startswith("> "):
            flush_para()
            close_list()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            out.append("<blockquote>%s</blockquote>" % _inline(" ".join(quote)))
            continue
        um = re.match(r"^[-*]\s+(.*)$", stripped)
        om = re.match(r"^\d+[.)]\s+(.*)$", stripped)
        if um or om:
            flush_para()
            kind = "ul" if um else "ol"
            if in_list != kind:
                close_list()
                out.append("<%s>" % kind)
                in_list = kind
            out.append("<li>%s</li>" % _inline((um or om).group(1)))
            i += 1
            continue
        if not stripped:
            flush_para()
            close_list()
            i += 1
            continue
        para.append(stripped)
        i += 1
    flush_para()
    close_list()
    return "\n".join(out)
