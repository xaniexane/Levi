"""Tool-execution registry for the LEVI agent runtime (blueprint §1, §7).

Reconciliation (binding, per blueprint §1.2 "one canonical implementation
per concept"):

* This module is the **tool-execution registry** for the step-level
  agentic loop: named tools, sandboxed handlers, confirmation gates.
* :mod:`levi.skill.registry` remains the **canonical skill/capability
  catalog** (typed, risk-leveled, permissioned dispatch). It is NOT
  merged here; the ``skill_list`` tool bridges to it.
* :mod:`levi.agent.runtime` remains **task-level specialist dispatch**
  (select specialist → act via skills); ``levi.agent.loop`` (sibling)
  is the **step-level tool loop** and is the consumer of this module's
  public API.
* Scheduling is backed by the canonical
  :class:`levi.daemon.automation.AutomationRegistry` — one store, no
  second schedule database here.

Consequential-action discipline (blueprint §1.5):

* Every tool that changes state outside the agent's own scratch memory
  declares ``requires_confirmation=True``.
* ``ToolRegistry.execute()`` never silently disables gates: when a
  gated tool runs with ``ctx.consent`` unset, ``execute()`` either asks
  the provided ``ctx.confirm`` callback with a human-readable preview,
  or raises :class:`ConfirmationRequired`. There is no flag that turns
  all gates off — this mirrors the confirmation pattern in
  :mod:`levi.plugins.registry`.
* The destructive-shell denylist is enforced *before* any gate and can
  NEVER be bypassed, even with explicit consent.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass
class ToolResult:
    """The honest outcome of one tool execution."""

    ok: bool
    output: str = ""
    error: str = ""


@dataclass
class Tool:
    """A named, described, sandboxed capability the agentic loop can call.

    ``handler`` takes the tool's argument dict and returns a
    :class:`ToolResult`. ``requires_confirmation`` marks state-changing
    tools; it cannot be unset per-call — see ``ToolRegistry.execute``.
    """

    name: str
    description: str
    parameters: dict  # JSON-schema-ish: {"type": "object", "properties": {...}, "required": [...]}
    handler: Callable[[dict], ToolResult]
    requires_confirmation: bool = False


class ConfirmationRequired(Exception):
    """Raised by ``ToolRegistry.execute`` when a gated tool runs without
    consent and no confirm callback (or a declined one) is available."""


@dataclass
class ExecContext:
    """Execution context for one ``execute()`` call.

    ``consent`` — pre-granted approval for gated tools (e.g. CLI --yes).
    ``confirm`` — optional callback invoked with a human-readable
    preview string; the tool runs only if it returns True.
    """

    consent: bool = False
    confirm: Callable[[str], bool] | None = None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ToolRegistry:
    """Named tool store with confirmation gating on ``execute()``."""

    def __init__(
        self,
        *,
        default_consent: bool = False,
        default_confirm: Callable[[str], bool] | None = None,
    ) -> None:
        self._tools: dict[str, Tool] = {}
        self._default_consent = default_consent
        self._default_confirm = default_confirm
        # Cell used to hand the active ExecContext to handlers (e.g.
        # ``delegate``) without changing the handler signature.
        self._active_ctx: ExecContext | None = None

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError("tool must have a non-empty name")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list(self) -> list[Tool]:
        return [self._tools[k] for k in sorted(self._tools)]

    def execute(
        self, name: str, args: dict, ctx: ExecContext | None = None
    ) -> ToolResult:
        """Run a named tool.

        Unknown tool → ``ToolResult(ok=False, error="unknown tool ...")``,
        never raises. A gated tool with no consent asks ``ctx.confirm``
        (if provided) with a human-readable preview; a declined or
        missing callback raises :class:`ConfirmationRequired`.
        """
        tool = self._tools.get(name)
        if tool is None:
            known = ", ".join(sorted(self._tools)) or "(none)"
            return ToolResult(
                ok=False,
                error=f"unknown tool {name!r}. Known tools: {known}",
            )

        if ctx is None:
            ctx = ExecContext(
                consent=self._default_consent, confirm=self._default_confirm
            )

        if tool.requires_confirmation and not ctx.consent:
            preview = _confirmation_preview(tool, args or {})
            approved = ctx.confirm(preview) if ctx.confirm is not None else False
            if not approved:
                raise ConfirmationRequired(
                    f"tool {tool.name!r} requires confirmation and none was "
                    f"granted. Preview shown to approver: {preview}"
                )

        args = dict(args or {})
        previous = self._active_ctx
        self._active_ctx = ctx
        try:
            return tool.handler(args)
        except ConfirmationRequired:
            raise
        except Exception as exc:  # handlers are honest, never fatal
            return ToolResult(ok=False, error=f"tool {name!r} failed: {exc}")
        finally:
            self._active_ctx = previous


def _confirmation_preview(tool: Tool, args: dict) -> str:
    summary = ", ".join(
        f"{k}={str(v)[:80]}" for k, v in sorted(args.items())
    )
    return (
        f"Tool '{tool.name}' requires confirmation. "
        f"Description: {tool.description} Args: {{{summary}}}"
    )


# ---------------------------------------------------------------------------
# Sandbox helpers
# ---------------------------------------------------------------------------


def _resolve_sandboxed(root: Path, user_path: str) -> Path:
    """Resolve ``user_path`` inside ``root``.

    Raises ``ValueError`` for absolute paths or ``..`` escapes.
    """
    if not user_path:
        raise ValueError("path is required")
    p = Path(user_path)
    if p.is_absolute():
        raise ValueError(
            f"refused: absolute paths are not allowed in the sandbox: {user_path!r}"
        )
    resolved = (root / p).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        raise ValueError(
            f"refused: path escapes the workspace root: {user_path!r}"
        )
    return resolved


_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _sanitize_name(name: str) -> str:
    if not name or not _NAME_RE.match(name):
        raise ValueError(
            f"refused: name must match [A-Za-z0-9_-], got {name!r}"
        )
    return name + ".md"


def _default_workspace_root() -> Path:
    return Path.home() / ".levi" / "agent_workspace"


def _default_memory_dir() -> Path:
    return Path.home() / ".levi" / "agent_memory"


def _default_skills_dir() -> Path:
    return Path.home() / ".levi" / "skills"


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _truncate(text: str, limit: int = 50_000) -> str:
    if len(text) > limit:
        return text[:limit] + f"\n… [truncated at {limit} chars]"
    return text


# ---------------------------------------------------------------------------
# Destructive-shell denylist — enforced ALWAYS, consent cannot bypass
# ---------------------------------------------------------------------------


def _split_command_segments(cmd: str) -> list[str]:
    """Split a shell command into rough segments on shell operators so the
    denylist inspects each pipeline element independently."""
    return re.split(r"(?:;|&&|\|\||\||\n|\$\(|`)", cmd)


_DESTRUCTIVE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # rm -rf against filesystem roots / home
    (
        re.compile(
            r"^\s*sudo\s+.*$|^\s*rm\b.*?(^|\s)(/|/\*|~|~/\*|\$HOME|\$\{HOME\})(\s|$|\*)",
            re.IGNORECASE,
        ),
        "rm -rf against a filesystem root or home directory",
    ),
    (
        re.compile(r"^\s*rm\s+(-[a-zA-Z]*r[a-zA-Z]*\s+|--\s+)*/\s*$"),
        "rm -rf /",
    ),
    # mkfs on anything
    (re.compile(r"(^|[\s;&|])mkfs(\s|$|\.)"), "mkfs filesystem creation"),
    # classic fork bomb
    (re.compile(r":\(\)\s*\{|:​\(\)"), "fork bomb"),
    # dd writing to a block device
    (
        re.compile(r"(^|[\s;&|])dd\b[^;&|]*\bof=/dev/"),
        "dd writing to a block device",
    ),
    # overwriting raw devices
    (
        re.compile(r">\s*/dev/(sd|nvme|hd|vd)[a-z]"),
        "writing directly to a disk device",
    ),
]


def _blocked_destructive(cmd: str) -> str | None:
    """Return a reason string if ``cmd`` matches a destructive pattern,
    else None. Applies even with consent — never bypassable."""
    for segment in _split_command_segments(cmd):
        seg = segment.strip()
        for pattern, reason in _DESTRUCTIVE_PATTERNS:
            if pattern.search(seg):
                return reason
    # fork-bomb without spaces variant, e.g. ":(){ :|:& };:"
    if re.search(r":\(\)\{", cmd.replace(" ", "")):
        return "fork bomb"
    return None


# ---------------------------------------------------------------------------
# Default tool handlers (closures over the configured directories)
# ---------------------------------------------------------------------------


def _register_builtins(
    registry: ToolRegistry,
    workspace_root: Path,
    memory_dir: Path,
    skills_dir: Path,
    affect_tracker: Any = None,
) -> None:
    # -- shell_exec ---------------------------------------------------------
    def _shell_exec(args: dict) -> ToolResult:
        cmd = args.get("cmd")
        if not cmd or not str(cmd).strip():
            return ToolResult(ok=False, error="shell_exec: 'cmd' is required")
        cmd = str(cmd)
        reason = _blocked_destructive(cmd)
        if reason is not None:
            return ToolResult(
                ok=False,
                error=(
                    "shell_exec: blocked destructive pattern — "
                    f"{reason}. This block applies even with consent."
                ),
            )
        timeout = args.get("timeout", 30)
        try:
            timeout = float(timeout)
        except (TypeError, ValueError):
            return ToolResult(ok=False, error="shell_exec: 'timeout' must be numeric")
        if timeout <= 0 or timeout > 600:
            return ToolResult(
                ok=False, error="shell_exec: 'timeout' must be in (0, 600]"
            )
        cwd = args.get("cwd")
        run_cwd: Path | None = None
        if cwd is not None:
            try:
                run_cwd = _resolve_sandboxed(workspace_root, str(cwd))
            except ValueError as exc:
                return ToolResult(ok=False, error=f"shell_exec: {exc}")
            _ensure_dir(run_cwd)
        else:
            run_cwd = _ensure_dir(workspace_root)
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(run_cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                ok=False,
                error=f"shell_exec: timed out after {timeout}s",
            )
        except OSError as exc:
            return ToolResult(ok=False, error=f"shell_exec: failed to run: {exc}")
        out = (proc.stdout or "") + (proc.stderr or "")
        return ToolResult(
            ok=proc.returncode == 0,
            output=_truncate(out) or f"(exit {proc.returncode}, no output)",
            error="" if proc.returncode == 0 else f"exit code {proc.returncode}",
        )

    # -- file_read ----------------------------------------------------------
    def _file_read(args: dict) -> ToolResult:
        raw = args.get("path")
        try:
            target = _resolve_sandboxed(workspace_root, str(raw) if raw else "")
        except ValueError as exc:
            return ToolResult(ok=False, error=f"file_read: {exc}")
        if not target.is_file():
            return ToolResult(ok=False, error=f"file_read: no such file: {raw!r}")
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ToolResult(
                ok=False, error=f"file_read: {raw!r} is not UTF-8 text"
            )
        except OSError as exc:
            return ToolResult(ok=False, error=f"file_read: {exc}")
        return ToolResult(ok=True, output=_truncate(text, 200_000))

    # -- file_write ---------------------------------------------------------
    def _file_write(args: dict) -> ToolResult:
        raw = args.get("path")
        try:
            target = _resolve_sandboxed(workspace_root, str(raw) if raw else "")
        except ValueError as exc:
            return ToolResult(ok=False, error=f"file_write: {exc}")
        if "content" not in args:
            return ToolResult(ok=False, error="file_write: 'content' is required")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(args["content"]), encoding="utf-8")
        except OSError as exc:
            return ToolResult(ok=False, error=f"file_write: {exc}")
        return ToolResult(ok=True, output=f"wrote {target}")

    # -- file_edit ----------------------------------------------------------
    def _file_edit(args: dict) -> ToolResult:
        raw = args.get("path")
        try:
            target = _resolve_sandboxed(workspace_root, str(raw) if raw else "")
        except ValueError as exc:
            return ToolResult(ok=False, error=f"file_edit: {exc}")
        old_text = args.get("old_text")
        new_text = args.get("new_text")
        if old_text is None or new_text is None:
            return ToolResult(
                ok=False, error="file_edit: 'old_text' and 'new_text' are required"
            )
        old_text, new_text = str(old_text), str(new_text)
        if not old_text:
            return ToolResult(ok=False, error="file_edit: 'old_text' must not be empty")
        if not target.is_file():
            return ToolResult(ok=False, error=f"file_edit: no such file: {raw!r}")
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return ToolResult(ok=False, error=f"file_edit: cannot read: {exc}")
        count = text.count(old_text)
        if count == 0:
            return ToolResult(
                ok=False, error="file_edit: 'old_text' not found in file"
            )
        if count > 1:
            return ToolResult(
                ok=False,
                error=(
                    f"file_edit: 'old_text' occurs {count} times; "
                    "it must occur exactly once (narrow the match)"
                ),
            )
        try:
            target.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        except OSError as exc:
            return ToolResult(ok=False, error=f"file_edit: {exc}")
        return ToolResult(ok=True, output=f"edited {target}")

    # -- memory_read / memory_write -----------------------------------------
    # The agent's own scratch memory: writing it is the agent thinking,
    # not a consequential external action, so memory_write does NOT
    # require confirmation (documented choice, per task contract).
    def _memory_read(args: dict) -> ToolResult:
        name = args.get("name")
        try:
            fname = _sanitize_name(str(name) if name else "")
        except ValueError as exc:
            return ToolResult(ok=False, error=f"memory_read: {exc}")
        target = _ensure_dir(memory_dir) / fname
        if not target.is_file():
            return ToolResult(ok=False, error=f"memory_read: no such entry: {name!r}")
        try:
            return ToolResult(ok=True, output=_truncate(target.read_text(encoding="utf-8"), 200_000))
        except OSError as exc:
            return ToolResult(ok=False, error=f"memory_read: {exc}")

    def _memory_write(args: dict) -> ToolResult:
        # Backward-compatible with callers that emit only {"text": ...}
        # (the LocalProvider planner): "text" is accepted as an alias for
        # "content", and a missing/empty name defaults to "scratch" rather
        # than failing.
        name = args.get("name") or "scratch"
        try:
            fname = _sanitize_name(str(name))
        except ValueError as exc:
            return ToolResult(ok=False, error=f"memory_write: {exc}")
        content = args.get("content", args.get("text"))
        if content is None:
            return ToolResult(
                ok=False, error="memory_write: 'content' (or 'text') is required"
            )
        target = _ensure_dir(memory_dir) / fname
        try:
            target.write_text(str(content), encoding="utf-8")
        except OSError as exc:
            return ToolResult(ok=False, error=f"memory_write: {exc}")
        return ToolResult(ok=True, output=f"remembered {name!r}")

    # -- skill_list / skill_load --------------------------------------------
    def _skill_list(args: dict) -> ToolResult:
        try:
            from levi.skill.registry import SkillRegistry
        except Exception as exc:
            return ToolResult(
                ok=False,
                error=f"skill_list: cannot import levi.skill.registry: {exc}",
            )
        try:
            skills = SkillRegistry().list()
        except Exception as exc:
            return ToolResult(ok=False, error=f"skill_list: registry failed: {exc}")
        lines = [
            f"{s.id} | risk={int(s.risk_level)} | {s.description}"
            for s in skills
        ]
        return ToolResult(
            ok=True, output=f"{len(skills)} skills:\n" + "\n".join(lines)
        )

    def _skill_load(args: dict) -> ToolResult:
        name = args.get("name")
        try:
            fname = _sanitize_name(str(name) if name else "")
        except ValueError as exc:
            return ToolResult(ok=False, error=f"skill_load: {exc}")
        target = skills_dir / fname
        if not target.is_file():
            return ToolResult(
                ok=False,
                error=f"skill_load: no playbook for skill {name!r} in {skills_dir}",
            )
        try:
            return ToolResult(ok=True, output=_truncate(target.read_text(encoding="utf-8"), 200_000))
        except OSError as exc:
            return ToolResult(ok=False, error=f"skill_load: {exc}")

    # -- course_brief / course_search (curriculum knowledge base) -----------
    def _courses_dir() -> Path:
        return Path(__file__).resolve().parent.parent / "knowledge" / "courses"

    def _course_catalog() -> dict:
        path = _courses_dir() / "catalog.json"
        if not path.exists():
            return {"subjects": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def _course_coverage() -> list:
        path = _courses_dir() / "coverage.json"
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _course_brief(args: dict) -> ToolResult:
        subject = str(args.get("subject") or "").strip().lower().replace("_", "-")
        brief = _courses_dir() / "briefs" / f"{subject}.md"
        if not brief.is_file():
            known = [s["slug"] for s in _course_catalog().get("subjects", [])]
            return ToolResult(
                ok=False,
                error=f"course_brief: unknown subject {subject!r}; "
                f"known: {', '.join(known) or '(catalog not ingested)'}",
            )
        try:
            return ToolResult(ok=True, output=_truncate(brief.read_text(encoding="utf-8"), 100_000))
        except OSError as exc:
            return ToolResult(ok=False, error=f"course_brief: {exc}")

    def _course_search(args: dict) -> ToolResult:
        query = str(args.get("query") or "").strip()
        if not query:
            return ToolResult(ok=False, error="course_search: 'query' is required")
        terms = [t.lower() for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2]
        if not terms:
            return ToolResult(ok=False, error="course_search: query has no searchable terms")
        catalog = _course_catalog()
        coverage = _course_coverage()
        # Map each course to its OWN ingested raw file (via coverage.json),
        # so snippets always come from that course's text — never a neighbor's.
        raw_by_title: dict[tuple[str, str], Path] = {}
        for rec in coverage:
            if rec.get("status") == "ok" and rec.get("file"):
                fp = _courses_dir() / rec["file"]
                if fp.is_file():
                    raw_by_title[(rec.get("subject", ""), rec.get("title", ""))] = fp
        hits: list[str] = []
        for subj in catalog.get("subjects", []):
            for course in subj["courses"]:
                hay = f"{course['title']} {course['school']} {course.get('description','')}".lower()
                score = sum(hay.count(t) for t in terms)
                snippet = ""
                if score:
                    fp = raw_by_title.get((subj["slug"], course["title"]))
                    if fp is not None:
                        try:
                            txt = fp.read_text(encoding="utf-8", errors="replace")
                        except OSError:
                            txt = ""
                        low = txt.lower()
                        for t in terms:
                            i = low.find(t)
                            if i != -1:
                                snippet = ("...[from this course's ingested text] "
                                           + " ".join(txt[max(0, i - 120):i + 200].split())
                                           + "...")
                                break
                if score:
                    line = f"[{subj['slug']}] {course['title']} ({course['school']}) — {course['primary']}"
                    if snippet:
                        line += f"\n    {snippet}"
                    hits.append((score, line))
        hits.sort(key=lambda h: -h[0])
        if not hits:
            return ToolResult(ok=True, output=f"course_search: no matches for {query!r}")
        out = "\n".join(h[1] for h in hits[:10])
        return ToolResult(
            ok=True,
            output=f"course_search: {len(hits)} match(es) for {query!r} (top 10):\n{out}")

    # -- news_latest / news_search (dated current-events recall) ------------
    def _news_dir() -> Path:
        return Path(__file__).resolve().parent.parent / "knowledge" / "news"

    def _news_items() -> list[dict]:
        days = _news_dir() / "days"
        items: list[dict] = []
        if not days.is_dir():
            return items
        for fp in sorted(days.glob("*.jsonl")):
            try:
                for line in fp.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line:
                        items.append(json.loads(line))
            except (OSError, ValueError):
                continue
        return items

    def _fmt_news(it: dict) -> str:
        return (f"[{it.get('date', '?')}] ({it.get('source', '?')}) "
                f"{it.get('title', '')}\n    {it.get('summary', '')}\n    {it.get('url', '')}")

    def _news_latest(args: dict) -> ToolResult:
        try:
            limit = max(1, min(int(args.get("limit", 10)), 50))
        except (TypeError, ValueError):
            return ToolResult(ok=False, error="news_latest: 'limit' must be an int")
        items = _news_items()
        if not items:
            return ToolResult(ok=True, output="news_latest: no ingested news yet — run `levi news refresh`.")
        items.sort(key=lambda r: r.get("date", ""), reverse=True)
        out = "\n".join(_fmt_news(it) for it in items[:limit])
        newest = items[0].get("date", "?")
        return ToolResult(
            ok=True,
            output=f"news_latest: newest ingested date is {newest} "
                   f"(dated recall — cite dates, do not imply freshness):\n{out}")

    def _news_search(args: dict) -> ToolResult:
        query = str(args.get("query") or "").strip()
        if not query:
            return ToolResult(ok=False, error="news_search: 'query' is required")
        terms = [t.lower() for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2]
        if not terms:
            return ToolResult(ok=False, error="news_search: query has no searchable terms")
        hits = []
        for it in _news_items():
            hay = f"{it.get('title', '')} {it.get('summary', '')}".lower()
            score = sum(hay.count(t) for t in terms)
            if score:
                hits.append((score, it.get("date", ""), it))
        hits.sort(key=lambda h: (-h[0], h[1]), reverse=False)
        hits.sort(key=lambda h: -h[0])
        if not hits:
            return ToolResult(ok=True, output=f"news_search: no matches for {query!r} in ingested news.")
        out = "\n".join(_fmt_news(it) for _, _, it in hits[:10])
        return ToolResult(
            ok=True,
            output=f"news_search: {len(hits)} match(es) for {query!r} (top 10, dates shown):\n{out}")

    # -- capabilities (honest capability atlas) ------------------------------
    def _capabilities(args: dict) -> ToolResult:
        path = Path(__file__).resolve().parent.parent / "knowledge" / "capabilities" / "atlas.json"
        if not path.is_file():
            return ToolResult(ok=False, error="capabilities: atlas.json not found")
        try:
            atlas = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return ToolResult(ok=False, error=f"capabilities: {exc}")
        domain = str(args.get("domain") or "").strip()
        domains = atlas.get("domains", [])
        if domain:
            match = next((d for d in domains if d["id"] == domain), None)
            if not match:
                known = ", ".join(d["id"] for d in domains)
                return ToolResult(ok=False, error=f"capabilities: unknown domain {domain!r}; known: {known}")
            domains = [match]
        lines = ["LEVI capability atlas — what the agent can do, honestly:"]
        for d in domains:
            lines.append(f"\n## {d['name']} [{d['id']}]")
            lines.append(d["description"])
            lines.append(f"Tools: {', '.join(d['tools'])}")
            lines.append(f"Limits: {'; '.join(d['known_limits'])}")
        lines.append("\nHonesty rule: if it is not in this atlas or the tool list, say so — do not improvise abilities.")
        return ToolResult(ok=True, output="\n".join(lines))

    # -- affect (5D emotional-intelligence engine) --------------------------
    # -- lab_scenario / lab_footprint (LEVI Lab: read-only) --------------------
    def _lab_scenario(args: dict) -> ToolResult:
        """Playback a captured LEVI Lab scenario transcript (no execution)."""
        try:
            from levi.lab import scenarios as lab_scen
        except Exception as exc:
            return ToolResult(ok=False, error=f"lab_scenario: {exc}")
        sid = str(args.get("scenario") or "").strip()
        if not sid:
            lines = ["lab_scenario: LEVI Lab scenarios (playback only, read-only):"]
            for sc in lab_scen.list_scenarios():
                lines.append(f"  {sc.id}: {sc.title}")
            lines.append("Pass {'scenario': '<id>'} for the captured transcript.")
            return ToolResult(ok=True, output="\n".join(lines))
        if lab_scen.get_scenario(sid) is None:
            return ToolResult(ok=False, error=f"lab_scenario: unknown scenario {sid!r}")
        return ToolResult(ok=True, output=lab_scen.playback(sid))

    def _lab_footprint(args: dict) -> ToolResult:
        """Estimate a model's RAM envelope. Pure math, read-only."""
        try:
            from levi.lab.footprint import footprint as _footprint
            from levi.lab.footprint import format_footprint as _fmt
        except Exception as exc:
            return ToolResult(ok=False, error=f"lab_footprint: {exc}")
        try:
            fp = _footprint(
                args.get("params", "0.6B"),
                quant=str(args.get("quant", "int4")),
                ctx=args.get("ctx", "32k"),
            )
        except ValueError as exc:
            return ToolResult(ok=False, error=f"lab_footprint: {exc}")
        return ToolResult(ok=True, output=_fmt(fp))

    def _affect_detect(args: dict) -> ToolResult:
        text = str(args.get("text") or "").strip()
        if not text:
            return ToolResult(ok=False, error="affect_detect: 'text' is required")
        try:
            from levi.affect import detect
        except Exception as exc:
            return ToolResult(ok=False, error=f"affect_detect: {exc}")
        r = detect(text)
        d = r.to_dict()
        return ToolResult(
            ok=True,
            output=(
                "affect_detect (pattern-based heuristic, not felt emotion): "
                f"dominant={d['dominant']} valence={d['valence']} "
                f"arousal={d['arousal']} confidence={d['confidence']} "
                f"stress={d['stress_signals'] or 'none'}"
            ),
        )

    def _affect_state(args: dict) -> ToolResult:
        try:
            from levi.affect import SessionEI
        except Exception as exc:
            return ToolResult(ok=False, error=f"affect_state: {exc}")
        tracker = affect_tracker if affect_tracker is not None else SessionEI()
        rep = tracker.report()
        dims = ", ".join(
            f"{k}={v:.2f}" for k, v in rep["dimensions"].items()
        )
        sm = rep["self_model"]
        return ToolResult(
            ok=True,
            output=(
                "affect_state — LEVI's tracked EI conduct this session "
                "(pattern-based, not felt emotion):\n"
                f"  dimensions: {dims}\n"
                f"  turns: {rep['turns']}  "
                f"frustration_streak: {rep['frustration_streak']}\n"
                f"  self-model: register={sm['register_id']} "
                f"confidence={sm['confidence']:.2f} "
                f"limits={sm['limits'] or 'none stated'}"
            ),
        )

    # -- delegate -----------------------------------------------------------
    def _delegate(args: dict) -> ToolResult:
        task = args.get("task")
        if not task or not str(task).strip():
            return ToolResult(ok=False, error="delegate: 'task' is required")
        max_steps = args.get("max_steps", 6)
        try:
            max_steps = int(max_steps)
        except (TypeError, ValueError):
            return ToolResult(ok=False, error="delegate: 'max_steps' must be an int")
        max_steps = max(1, min(max_steps, 25))

        try:
            from levi.agent import loop as agent_loop
        except Exception as exc:
            return ToolResult(
                ok=False,
                error=f"delegate: levi.agent.loop is not available: {exc}",
            )

        parent_ctx = registry._active_ctx or ExecContext()
        # The sub-run inherits the parent's consent state. Gated tools
        # stay gated inside the child: without consent (and without a
        # confirm callback) they raise ConfirmationRequired, which the
        # worker converts into an honest denial instead of prompting the
        # parent loop a second time.
        child_registry = build_default_registry(
            workspace_root=workspace_root,
            consent=parent_ctx.consent,
            confirm=parent_ctx.confirm,
            memory_dir=memory_dir,
            skills_dir=skills_dir,
        )
        child_ctx = ExecContext(
            consent=parent_ctx.consent, confirm=parent_ctx.confirm
        )
        result_box: dict[str, Any] = {}

        def _worker() -> None:
            try:
                if hasattr(agent_loop, "run_subtask"):
                    out = agent_loop.run_subtask(
                        task=str(task),
                        registry=child_registry,
                        ctx=child_ctx,
                        max_steps=max_steps,
                    )
                    # HONESTY (blueprint §1.7): a delegated subtask whose
                    # transcript reports ok=False must surface as a failed
                    # tool call, never as a success.
                    if isinstance(out, agent_loop.AgentTranscript):
                        result_box["sub_ok"] = bool(out.ok)
                elif hasattr(agent_loop, "AgentLoop"):
                    out = agent_loop.AgentLoop(
                        registry=child_registry, ctx=child_ctx
                    ).run(str(task), max_steps=max_steps)
                else:
                    out = (
                        "delegate unavailable: levi.agent.loop exposes no "
                        "run_subtask() or AgentLoop entry point"
                    )
                result_box["result"] = str(out)
            except ConfirmationRequired as exc:
                result_box["denied"] = f"denied in subtask: {exc}"
            except Exception as exc:
                result_box["error"] = f"subtask failed: {exc}"

        worker = threading.Thread(target=_worker, daemon=True)
        worker.start()
        worker.join(timeout=300)
        if worker.is_alive():
            return ToolResult(
                ok=False, error="delegate: subtask timed out after 300s"
            )
        if "denied" in result_box:
            return ToolResult(ok=False, error=result_box["denied"])
        if "error" in result_box:
            return ToolResult(ok=False, error=result_box["error"])
        output = result_box.get("result", "")
        # A subtask failure (sub_ok=False) is reported as a failed tool
        # call — the summary text stays in output so the parent agent can
        # see what went wrong instead of a bare success/failure bit.
        if not result_box.get("sub_ok", True):
            return ToolResult(
                ok=False,
                output=output,
                error=f"delegate: subtask failed — {output}",
            )
        return ToolResult(ok=True, output=output)

    # -- schedule_* ----------------------------------------------------------
    def _automation_registry():
        """Canonical backend — one store per concept (blueprint §1.2).

        ``LEVI_AUTOMATIONS_DIR`` overrides the data dir (used by tests
        for hermetic runs); otherwise the AutomationRegistry default.
        """
        from levi.daemon.automation import AutomationRegistry, TriggerKind  # noqa: F401

        override = os.environ.get("LEVI_AUTOMATIONS_DIR")
        if override:
            return AutomationRegistry(data_dir=Path(override))
        return AutomationRegistry()

    def _schedule_add(args: dict) -> ToolResult:
        name = str(args.get("name") or "").strip()
        cron = str(args.get("cron") or "").strip()
        task = str(args.get("task") or "").strip()
        if not name or not cron or not task:
            return ToolResult(
                ok=False,
                error="schedule_add: 'name', 'cron' and 'task' are required",
            )
        try:
            from levi.daemon.automation import AutomationAction, TriggerKind

            reg = _automation_registry()
            auto = reg.create(
                name=name,
                description=task,
                actions=[AutomationAction(skill_id="__scheduled__", args={"task": task})],
                trigger=TriggerKind.SCHEDULE,
                trigger_config={"cron": cron, "task": task},
            )
        except Exception as exc:
            return ToolResult(ok=False, error=f"schedule_add: {exc}")
        return ToolResult(
            ok=True,
            output=f"scheduled {auto.id} ({auto.name}) cron={cron!r} status={auto.status.value}",
        )

    def _schedule_list(args: dict) -> ToolResult:
        try:
            reg = _automation_registry()
            items = reg.list()
        except Exception as exc:
            return ToolResult(ok=False, error=f"schedule_list: {exc}")
        if not items:
            return ToolResult(ok=True, output="no schedules")
        lines = []
        for a in items:
            cfg = a.trigger_config or {}
            lines.append(
                f"{a.id} | {a.status.value} | {a.trigger.value} | {a.name} | "
                f"cron={cfg.get('cron', '—')} | task={str(cfg.get('task', ''))[:80]}"
            )
        return ToolResult(ok=True, output="\n".join(lines))

    def _schedule_remove(args: dict) -> ToolResult:
        schedule_id = str(args.get("schedule_id") or "").strip()
        if not schedule_id:
            return ToolResult(ok=False, error="schedule_remove: 'schedule_id' is required")
        try:
            reg = _automation_registry()
            if reg.get(schedule_id) is None:
                return ToolResult(
                    ok=False,
                    error=f"schedule_remove: unknown schedule id {schedule_id!r}",
                )
            removed = reg.remove(schedule_id)
        except Exception as exc:
            return ToolResult(ok=False, error=f"schedule_remove: {exc}")
        if not removed:
            return ToolResult(
                ok=False,
                error=f"schedule_remove: unknown schedule id {schedule_id!r}",
            )
        return ToolResult(ok=True, output=f"removed {schedule_id}")

    # -- web_search / web_fetch / http_request --------------------------------
    def _offline() -> ToolResult | None:
        if os.environ.get("LEVI_OFFLINE") == "1":
            return ToolResult(
                ok=False, error="network unavailable (offline mode)"
            )
        return None

    def _http_error(exc: Exception) -> ToolResult:
        return ToolResult(ok=False, error=f"network request failed: {exc}")

    def _web_search(args: dict) -> ToolResult:
        query = str(args.get("query") or "").strip()
        if not query:
            return ToolResult(ok=False, error="web_search: 'query' is required")
        blocked = _offline()
        if blocked:
            return blocked
        url = (
            "https://html.duckduckgo.com/html/?q="
            + urllib.parse.quote_plus(query)
        )
        req = urllib.request.Request(
            url, headers={"User-Agent": "LEVI-agent/1.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read(200_000).decode("utf-8", errors="replace")
        except Exception as exc:
            return _http_error(exc)
        results = []
        for m in re.finditer(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        ):
            href = m.group(1)
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            if href.startswith("//"):
                href = "https:" + href
            results.append(f"{title} — {href}")
            if len(results) >= 8:
                break
        if not results:
            return ToolResult(
                ok=False,
                error="web_search: no results parsed from search response",
            )
        return ToolResult(ok=True, output="\n".join(results))

    def _web_fetch(args: dict) -> ToolResult:
        url = str(args.get("url") or "").strip()
        if not url:
            return ToolResult(ok=False, error="web_fetch: 'url' is required")
        blocked = _offline()
        if blocked:
            return blocked
        scheme = urllib.parse.urlparse(url).scheme.lower()
        if scheme not in ("http", "https"):
            return ToolResult(
                ok=False, error=f"web_fetch: blocked non-http(s) scheme: {scheme!r}"
            )
        req = urllib.request.Request(
            url, headers={"User-Agent": "LEVI-agent/1.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read(100_000)
                ctype = resp.headers.get("Content-Type", "")
                charset = "utf-8"
                m = re.search(r"charset=([^\s;]+)", ctype)
                if m:
                    charset = m.group(1)
                text = raw.decode(charset, errors="replace")
        except Exception as exc:
            return _http_error(exc)
        return ToolResult(ok=True, output=_truncate(text, 100_000))

    def _http_request(args: dict) -> ToolResult:
        method = str(args.get("method") or "GET").upper()
        url = str(args.get("url") or "").strip()
        if method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"):
            return ToolResult(
                ok=False, error=f"http_request: unsupported method {method!r}"
            )
        if not url:
            return ToolResult(ok=False, error="http_request: 'url' is required")
        blocked = _offline()
        if blocked:
            return blocked
        scheme = urllib.parse.urlparse(url).scheme.lower()
        if scheme not in ("http", "https"):
            return ToolResult(
                ok=False,
                error=f"http_request: blocked non-http(s) scheme: {scheme!r}",
            )
        timeout = args.get("timeout", 15)
        try:
            timeout = float(timeout)
        except (TypeError, ValueError):
            return ToolResult(ok=False, error="http_request: 'timeout' must be numeric")
        headers = args.get("headers") or {}
        if not isinstance(headers, dict):
            return ToolResult(ok=False, error="http_request: 'headers' must be a dict")
        body = args.get("body")
        data = body.encode("utf-8") if isinstance(body, str) else body
        # Never let a caller smuggle credentials through our logs — we
        # simply do not log headers or body at all.
        req = urllib.request.Request(
            url, data=data, headers=dict(headers), method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = resp.read(100_000).decode("utf-8", errors="replace")
                status = resp.status
        except Exception as exc:
            return _http_error(exc)
        return ToolResult(
            ok=True, output=f"HTTP {status}\n{_truncate(payload, 100_000)}"
        )

    # -- register everything -------------------------------------------------
    def _schema(properties: dict, required: list[str]) -> dict:
        return {"type": "object", "properties": properties, "required": required}

    tools = [
        Tool(
            name="shell_exec",
            description=(
                "Run a shell command inside the agent workspace sandbox. "
                "Destructive patterns (rm -rf /, mkfs, fork bombs, raw-device "
                "writes) are blocked even with consent."
            ),
            parameters=_schema(
                {
                    "cmd": {"type": "string"},
                    "timeout": {"type": "number"},
                    "cwd": {"type": "string"},
                },
                ["cmd"],
            ),
            handler=_shell_exec,
            requires_confirmation=True,
        ),
        Tool(
            name="file_read",
            description="Read a UTF-8 text file inside the agent workspace.",
            parameters=_schema({"path": {"type": "string"}}, ["path"]),
            handler=_file_read,
        ),
        Tool(
            name="file_write",
            description="Write a file inside the agent workspace (sandboxed).",
            parameters=_schema(
                {"path": {"type": "string"}, "content": {"type": "string"}},
                ["path", "content"],
            ),
            handler=_file_write,
            requires_confirmation=True,
        ),
        Tool(
            name="file_edit",
            description=(
                "Replace text in a workspace file. 'old_text' must occur "
                "exactly once."
            ),
            parameters=_schema(
                {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                ["path", "old_text", "new_text"],
            ),
            handler=_file_edit,
            requires_confirmation=True,
        ),
        Tool(
            name="memory_read",
            description="Read one entry from the agent's scratch memory.",
            parameters=_schema({"name": {"type": "string"}}, ["name"]),
            handler=_memory_read,
        ),
        Tool(
            name="memory_write",
            description=(
                "Write one entry to the agent's scratch memory. This is the "
                "agent's own working memory — not an external action — so "
                "no confirmation is required. 'name' defaults to 'scratch' "
                "when omitted; 'text' is accepted as an alias for 'content'."
            ),
            parameters=_schema(
                {
                    "name": {
                        "type": "string",
                        "description": "Entry name; defaults to 'scratch' when omitted",
                    },
                    "content": {"type": "string"},
                    "text": {
                        "type": "string",
                        "description": "Alias for 'content' (LocalProvider compatibility)",
                    },
                },
                [],
            ),
            handler=_memory_write,
        ),
        Tool(
            name="skill_list",
            description=(
                "List skills from the canonical levi.skill.registry "
                "capability catalog."
            ),
            parameters=_schema({}, []),
            handler=_skill_list,
        ),
        Tool(
            name="skill_load",
            description="Load a markdown skill playbook from the skills directory.",
            parameters=_schema({"name": {"type": "string"}}, ["name"]),
            handler=_skill_load,
        ),
        Tool(
            name="course_brief",
            description=(
                "Return the field guide for one awesome-courses subject "
                "(start-here picks, topic keywords, full course list). "
                "Subjects: systems, programming-languages-compilers, "
                "algorithms, cs-theory, introduction-to-cs, "
                "machine-learning, security, artificial-intelligence, "
                "computer-graphics, misc, statistics. Read-only."
            ),
            parameters=_schema({"subject": {"type": "string"}}, ["subject"]),
            handler=_course_brief,
        ),
        Tool(
            name="course_search",
            description=(
                "Search the awesome-courses catalog and ingested course texts "
                "for a query; returns matching courses with text snippets. "
                "Read-only."
            ),
            parameters=_schema({"query": {"type": "string"}}, ["query"]),
            handler=_course_search,
        ),
        Tool(
            name="news_latest",
            description=(
                "Newest ingested news headlines with dates and sources. "
                "Dated recall, not live awareness — always cite the dates. Read-only."
            ),
            parameters=_schema({"limit": {"type": "string"}}, []),
            handler=_news_latest,
        ),
        Tool(
            name="news_search",
            description=(
                "Search ingested news by query; results always show their dates. "
                "Dated recall, not live awareness. Read-only."
            ),
            parameters=_schema({"query": {"type": "string"}}, ["query"]),
            handler=_news_search,
        ),
        Tool(
            name="capabilities",
            description=(
                "Return LEVI's honest capability atlas (what the agent can do, "
                "which tools serve each domain, known limits). Use to answer "
                "'what can you do?' truthfully instead of improvising. Optional "
                "'domain' arg narrows to one domain. Read-only."
            ),
            parameters=_schema({"domain": {"type": "string"}}, []),
            handler=_capabilities,
        ),
        Tool(
            name="lab_scenario",
            description=(
                "Play back a captured LEVI Lab scenario: real transcripts of "
                "the agentic loop (fail→recover, red→green, research brief, "
                "effort A/B). Playback only — never executes. Read-only."
            ),
            parameters=_schema({"scenario": {"type": "string"}}, []),
            handler=_lab_scenario,
        ),
        Tool(
            name="lab_footprint",
            description=(
                "Estimate a model's RAM envelope: weights (params × "
                "bytes/param per quant) + KV cache + headroom. Pure math, "
                "an estimate not a measurement. Read-only."
            ),
            parameters=_schema(
                {
                    "params": {"type": "string"},
                    "quant": {"type": "string"},
                    "ctx": {"type": "string"},
                },
                [],
            ),
            handler=_lab_footprint,
        ),
        Tool(
            name="affect_detect",
            description=(
                "Run LEVI's pattern-based affect detector on a text: returns "
                "valence, arousal, dominant emotion, stress signals. "
                "Heuristic labels for conduct shaping — not felt emotion, "
                "not a diagnosis. Read-only."
            ),
            parameters=_schema({"text": {"type": "string"}}, ["text"]),
            handler=_affect_detect,
        ),
        Tool(
            name="affect_state",
            description=(
                "Report LEVI's tracked 5D emotional-intelligence state for "
                "this session (self-awareness, self-regulation, motivation, "
                "empathy, social skills) plus its self-model: active "
                "register, confidence, stated limits. Read-only."
            ),
            parameters=_schema({}, []),
            handler=_affect_state,
        ),
        Tool(
            name="delegate",
            description=(
                "Run a subtask in a worker thread with an isolated context. "
                "The sub-run inherits consent; gated tools stay gated."
            ),
            parameters=_schema(
                {"task": {"type": "string"}, "max_steps": {"type": "integer"}},
                ["task"],
            ),
            handler=_delegate,
        ),
        Tool(
            name="schedule_add",
            description=(
                "Add a cron-scheduled automation backed by the canonical "
                "AutomationRegistry."
            ),
            parameters=_schema(
                {
                    "name": {"type": "string"},
                    "cron": {"type": "string"},
                    "task": {"type": "string"},
                },
                ["name", "cron", "task"],
            ),
            handler=_schedule_add,
            requires_confirmation=True,
        ),
        Tool(
            name="schedule_list",
            description="List scheduled automations from the AutomationRegistry.",
            parameters=_schema({}, []),
            handler=_schedule_list,
        ),
        Tool(
            name="schedule_remove",
            description="Remove a scheduled automation by id.",
            parameters=_schema({"schedule_id": {"type": "string"}}, ["schedule_id"]),
            handler=_schedule_remove,
        ),
        Tool(
            name="web_search",
            description=(
                "Web search via a best-effort provider; returns titles and "
                "URLs. Honest failure when unavailable."
            ),
            parameters=_schema({"query": {"type": "string"}}, ["query"]),
            handler=_web_search,
        ),
        Tool(
            name="web_fetch",
            description="Fetch a page over http(s); returns text content.",
            parameters=_schema({"url": {"type": "string"}}, ["url"]),
            handler=_web_fetch,
            requires_confirmation=True,
        ),
        Tool(
            name="http_request",
            description=(
                "Raw http(s) request. Non-http(s) schemes are blocked; "
                "nothing sensitive is logged."
            ),
            parameters=_schema(
                {
                    "method": {"type": "string"},
                    "url": {"type": "string"},
                    "headers": {"type": "object"},
                    "body": {"type": "string"},
                    "timeout": {"type": "number"},
                },
                ["method", "url"],
            ),
            handler=_http_request,
            requires_confirmation=True,
        ),
    ]
    for tool in tools:
        registry.register(tool)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_default_registry(
    workspace_root: Path | None = None,
    consent: bool = False,
    confirm: Callable[[str], bool] | None = None,
    memory_dir: Path | None = None,
    skills_dir: Path | None = None,
    affect_tracker: Any = None,
) -> ToolRegistry:
    """Build a registry with all built-in tools.

    Defaults (all created lazily on first use):
    ``~/.levi/agent_workspace/``, ``~/.levi/agent_memory/``,
    ``~/.levi/skills/``.

    ``affect_tracker`` is an optional :class:`levi.affect.SessionEI`
    shared with the ``affect_state`` tool so the agent can report its
    live session state.
    """
    root = Path(workspace_root) if workspace_root else _default_workspace_root()
    mem = Path(memory_dir) if memory_dir else _default_memory_dir()
    sk = Path(skills_dir) if skills_dir else _default_skills_dir()
    registry = ToolRegistry(default_consent=consent, default_confirm=confirm)
    _register_builtins(registry, root, mem, sk, affect_tracker)
    return registry
