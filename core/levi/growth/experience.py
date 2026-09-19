"""Experience harvesting for LEVI's growth loop.

An *experience* is one unit of "something happened that Levi could learn
from": a user message, one of Levi's own turns, a session summary, or an
automation run record. Harvesting is read-only — it never modifies the
sources it reads.

Sources (all local-first):
  * agent chat sessions  — ``~/.levi/agent/sessions/*.jsonl``
  * daemon automations   — ``~/.levi/automations/automations.json``
  * affect signals       — ``~/.levi/affect/signals.jsonl`` (motivation
    intake for the 5D affect engine: frustration streaks, repairs, rapport)
  * operational logs     — hunt waves (``~/.levi/perpetual/hunt_state.json``),
    build queue (``~/.levi/perpetual/build_queue.jsonl``), agent
    tool-outputs (``~/workspace/agents/*/tool-output/*.json``), and daily
    memory logs (``~/memory/YYYY-MM-DD.md``); see ``harvest_ops_logs``.

    Chauncey's law: all knowledge is good knowledge — only what you DO
    with it can be wrong. So intake is broad; the guards (growth-tagged
    writes only, no sentience claims, no autonomous rewriting) constrain
    conduct, not curiosity.

A watermark per source (``~/.levi/growth/state.json``) keeps cycles
idempotent: re-running a cycle never re-harvests the same records.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass
class Experience:
    """One learnable unit of past activity."""

    id: str
    kind: str  # "user-said" | "levi-did" | "distilled" | "automation" | "note"
    source: str  # session name / automation id / "note"
    ts: str  # ISO timestamp ("" when unknown)
    content: str
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Session harvesting
# ---------------------------------------------------------------------------

_WS = re.compile(r"\s+")


def _clean(text: str, limit: int = 1200) -> str:
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("_clean: limit must be a positive int, got %r" % (limit,))
    text = _WS.sub(" ", (text or "").strip())
    return text[:limit]


def _session_records(path: Path) -> Iterator[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict) and rec.get("kind"):
                    yield rec
    except OSError:
        return


def harvest_sessions(
    sessions_dir: Path | None = None,
    since: dict[str, str] | None = None,
) -> tuple[list[Experience], dict[str, str]]:
    """Harvest new experiences from chat sessions.

    ``since`` maps session name -> ISO timestamp watermark; only records
    with ``ts`` strictly greater than the watermark are harvested.
    Files whose (mtime, size) fingerprint is unchanged since the last
    cycle are skipped entirely (``__stat__:<name>`` watermarks) so
    repeat cycles don't rescan gigabytes of session JSONL.
    Returns ``(experiences, new_watermarks)``.
    """
    if since is not None and not isinstance(since, dict):
        raise ValueError("harvest_sessions: since must be a dict or None")
    if sessions_dir is None:
        try:
            from levi.agent.chat import sessions_dir as _sd

            sessions_dir = _sd()
        except Exception:
            return [], {}
    since = since or {}
    experiences: list[Experience] = []
    watermarks: dict[str, str] = {}
    if not sessions_dir or not sessions_dir.is_dir():
        return [], {}

    for path in sorted(sessions_dir.glob("*.jsonl")):
        name = path.stem
        mark = since.get(name, "")
        stat_key = f"__stat__:{name}"
        try:
            st = path.stat()
            sig = f"{st.st_mtime_ns}:{st.st_size}"
        except OSError:
            continue  # unreadable; harvesting is best-effort
        if since.get(stat_key) == sig:
            # Untouched since the last cycle: nothing new to harvest.
            watermarks[name] = mark
            watermarks[stat_key] = sig
            continue
        latest = mark
        n = 0
        for rec in _session_records(path):
            ts = str(rec.get("ts", "") or "")
            if ts > latest:
                latest = ts
            if mark and ts <= mark:
                continue
            kind = rec.get("kind")
            if kind == "message":
                role = rec.get("role", "")
                content = _clean(str(rec.get("content", "") or ""))
                if not content or len(content) < 3:
                    continue
                if role == "user":
                    ekind = "user-said"
                elif role == "assistant":
                    ekind = "levi-did"
                elif role == "tool":
                    ekind = "levi-did"
                    content = f"[tool {rec.get('name', '?')}] {content}"
                else:
                    continue
                n += 1
                experiences.append(
                    Experience(
                        id=f"ses:{name}:{n}",
                        kind=ekind,
                        source=name,
                        ts=ts,
                        content=content,
                    )
                )
            elif kind == "summary":
                content = _clean(str(rec.get("content", "") or ""))
                if not content:
                    continue
                n += 1
                experiences.append(
                    Experience(
                        id=f"ses:{name}:{n}",
                        kind="distilled",
                        source=name,
                        ts=ts,
                        content=content,
                        meta={"covers_messages": rec.get("covers_messages", 0)},
                    )
                )
            elif kind == "note":
                content = _clean(str(rec.get("content", "") or ""))
                if not content:
                    continue
                n += 1
                experiences.append(
                    Experience(
                        id=f"ses:{name}:{n}",
                        kind="note",
                        source=name,
                        ts=ts,
                        content=content,
                    )
                )
        watermarks[name] = latest
        watermarks[stat_key] = sig
    return experiences, watermarks


# ---------------------------------------------------------------------------
# Automation harvesting
# ---------------------------------------------------------------------------


def harvest_automations(auto_path: Path | None = None) -> list[Experience]:
    """One experience per automation that has run at least once."""
    if auto_path is None:
        auto_path = Path.home() / ".levi" / "automations" / "automations.json"
    try:
        raw = json.loads(auto_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(raw, dict) or not isinstance(raw.get("automations"), list):
        return []  # malformed source; harvesting is best-effort
    out: list[Experience] = []
    for a in raw["automations"]:
        if not isinstance(a, dict):
            continue
        try:
            runs = int(a.get("run_count", 0) or 0)
        except (TypeError, ValueError):
            continue
        if runs <= 0:
            continue
        name = a.get("name", a.get("id", "?"))
        last = a.get("last_result", "") or ""
        out.append(
            Experience(
                id=f"auto:{a.get('id', '?')}",
                kind="automation",
                source=str(a.get("id", "?")),
                ts=str(a.get("last_run", "") or ""),
                content=(
                    f"Automation '{name}' has run {runs} time(s); "
                    f"status={a.get('status', '?')}; last result: {_clean(last, 400)}"
                ),
                meta={"run_count": runs, "status": a.get("status", "?")},
            )
        )
    return out


# ---------------------------------------------------------------------------
# Top-level harvest
# ---------------------------------------------------------------------------


def harvest_affect_signals(
    signals_path: Path | None = None,
    since: dict[str, str] | None = None,
) -> tuple[list[Experience], dict[str, str]]:
    """Harvest motivation signals written by ``levi.affect.modulation``.

    Source: ``~/.levi/affect/signals.jsonl`` (frustration streaks, repair
    events, rapport, proactive opportunities). Watermarked under the
    ``"affect"`` key so re-runs never re-harvest. This is the growth
    loop's intake for Dimension 3 (motivation): observed friction becomes
    a drive to improve.
    """
    if signals_path is None:
        base = _levi_home()
        signals_path = base / "affect" / "signals.jsonl"
    since = since or {}
    if not isinstance(since, dict):
        raise ValueError("harvest_affect_signals: since must be a dict or None")
    mark = since.get("affect", "")
    stat_key = "__stat__:affect"
    experiences: list[Experience] = []
    latest = mark
    sig = ""
    if signals_path.is_file():
        try:
            st = signals_path.stat()
            sig = f"{st.st_mtime_ns}:{st.st_size}"
        except OSError:
            sig = ""
        if sig and since.get(stat_key) == sig:
            # Untouched since the last cycle: nothing new to harvest.
            return [], ({"affect": mark, stat_key: sig} if mark else {stat_key: sig})
        try:
            lines = signals_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        n = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            ts = str(rec.get("ts", "") or "")
            if ts > latest:
                latest = ts
            if mark and ts <= mark:
                continue
            kind = str(rec.get("kind", "affect-signal") or "affect-signal")
            detail = _clean(str(rec.get("detail", "") or ""))
            if not detail:
                continue
            n += 1
            experiences.append(
                Experience(
                    id=f"affect:{n}",
                    kind="note",
                    source="affect-signals",
                    ts=ts,
                    content=f"[motivation-signal:{kind}] {detail}",
                    meta={"dimensions": rec.get("dimensions", {})},
                )
            )
    marks = {"affect": latest} if latest else {}
    if sig:
        marks[stat_key] = sig
    return experiences, marks


# ---------------------------------------------------------------------------
# Operational-log harvesting — "widen what it harvests" (2026-09-16)
#
# Chauncey's law: all knowledge is good knowledge; only what you DO with
# it can be wrong. So the loop harvests broadly — hunt waves, build
# queue, agent tool-outputs (browser task reports), daily memory logs —
# while the *guards* (growth-tagged writes only, no sentience claims, no
# autonomous rewriting) constrain what the loop does with it.
# Broad intake, strict conduct.
# ---------------------------------------------------------------------------

_OPS_CHUNK_LINES = 60
_OPS_AGENT_CAP = 25  # max agent tool-output files harvested per cycle


def _scrub(text: str, limit: int = 1200) -> str:
    """Clean + secret-scrub ops-log text. Best-effort, never total."""
    from levi.growth.redact import redact_text

    return _clean(redact_text(text or ""), limit)


def _levi_home() -> Path:
    """Base dir for ``~/.levi`` — overridable via ``LEVI_HOME`` (tests)."""
    return Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))


def _workspace_dir() -> Path:
    """Base dir for ``~/workspace`` — overridable via ``LEVI_WORKSPACE``."""
    return Path(os.environ.get("LEVI_WORKSPACE", Path.home() / "workspace"))


def _memory_dir() -> Path:
    """Base dir for ``~/memory`` — overridable via ``LEVI_MEMORY_DIR``."""
    return Path(os.environ.get("LEVI_MEMORY_DIR", Path.home() / "memory"))


def _harvest_hunt_waves(
    since: dict, perpetual_dir: Path | None = None
) -> tuple[list[Experience], dict[str, str]]:
    """One experience per completed hunt wave not yet harvested."""

    if perpetual_dir is None:
        perpetual_dir = _levi_home() / "perpetual"
    state_path = perpetual_dir / "hunt_state.json"
    key = "opslog:hunt-waves"
    seen = set((since.get(key) or "").split(",")) - {""}
    experiences: list[Experience] = []
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], {}
    waves = raw.get("waves") if isinstance(raw, dict) else None
    if not isinstance(waves, list):
        return [], {}
    new_ids: list[str] = []
    for w in waves:
        if not isinstance(w, dict):
            continue
        wid = str(w.get("id", "") or "")
        if not wid or wid in seen or w.get("status") != "completed":
            continue
        ts = str(w.get("completed_at", "") or "")
        content = _scrub(
            "Hunt wave %s completed (%s): theme=%s, findings=%s, research=%s. %s"
            % (
                wid,
                ts or "unknown time",
                w.get("theme_id", "?"),
                w.get("findings_count", "?"),
                w.get("research_slug", "?"),
                w.get("notes", ""),
            )
        )
        experiences.append(
            Experience(
                id=f"hunt:{wid}",
                kind="note",
                source=f"hunt-wave:{wid}",
                ts=ts,
                content=content,
                meta={"ops_source": "hunt-wave"},
            )
        )
        new_ids.append(wid)
    if new_ids:
        seen.update(new_ids)
        return experiences, {key: ",".join(sorted(seen))}
    return [], {}


def _harvest_build_queue(
    since: dict, perpetual_dir: Path | None = None
) -> tuple[list[Experience], dict[str, str]]:
    """New build-queue lines beyond the watermarked line count."""
    if perpetual_dir is None:
        perpetual_dir = _levi_home() / "perpetual"
    qpath = perpetual_dir / "build_queue.jsonl"
    key = "opslog:buildq-lines"
    try:
        start = int(since.get(key) or 0)
    except (TypeError, ValueError):
        start = 0
    try:
        lines = qpath.read_text(encoding="utf-8").splitlines()
    except OSError:
        return [], {}
    experiences: list[Experience] = []
    n = 0
    for line in lines[start:]:
        n += 1
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            desc = rec.get("describe") or rec.get("task") or rec.get("id") or line
        except ValueError:
            desc = line
        experiences.append(
            Experience(
                id=f"buildq:{start + n}",
                kind="note",
                source="build-queue",
                ts=str(rec.get("queued_at", "") if isinstance(rec, dict) else ""),
                content=_scrub("Build queued: %s" % desc, 600),
                meta={"ops_source": "build-queue"},
            )
        )
    return experiences, {key: str(len(lines))}


def _summarize_tool_output(rel: str, raw: object) -> str:
    """Best-effort one-line summary of an agent tool-output dump."""
    if isinstance(raw, dict):
        keys = raw.keys()
        if "browser_task_id" in keys or "status" in keys:
            return "browser task %s: status=%s %s" % (
                raw.get("browser_task_id", "?"),
                raw.get("status", "?"),
                _clean(
                    str(
                        raw.get("terminal_reason")
                        or raw.get("final_response_preview")
                        or ""
                    ),
                    300,
                ),
            )
        if "ok" in keys or "result" in keys:
            return "tool result: %s" % _clean(
                str(raw.get("result") or raw.get("ok")), 300
            )
        sample = _clean(json.dumps(raw)[:400], 400)
        return "tool-output dump: %s" % sample
    if isinstance(raw, list):
        return "tool-output list with %d entries" % len(raw)
    return "tool-output: %s" % _clean(str(raw), 300)


def _harvest_agent_outputs(
    since: dict, agents_dir: Path | None = None
) -> tuple[list[Experience], dict[str, str]]:
    """Summaries of new agent tool-output files (browser task reports, etc.).

    Files are write-once dumps named by call id; once harvested a file is
    never harvested again. Capped per cycle so a backlog can't flood one
    cycle.
    """
    if agents_dir is None:
        agents_dir = _workspace_dir() / "agents"
    key = "opslog:agentout"
    seen = set((since.get(key) or "").split(",")) - {""}
    candidates: list[tuple[float, str, Path]] = []
    if agents_dir.is_dir():
        for path in agents_dir.glob("*/tool-output/*.json"):
            rel = str(path.relative_to(agents_dir))
            if rel in seen:
                continue
            try:
                candidates.append((path.stat().st_mtime, rel, path))
            except OSError:
                continue
    candidates.sort()  # oldest first: deterministic
    experiences: list[Experience] = []
    harvested: list[str] = []
    for _, rel, path in candidates[:_OPS_AGENT_CAP]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            harvested.append(rel)  # unreadable: don't retry forever
            continue
        agent_id = rel.split("/", 1)[0]
        summary = _scrub(_summarize_tool_output(rel, raw), 800)
        experiences.append(
            Experience(
                id="agentout:%d" % (len(seen) + len(harvested)),
                kind="note",
                source="agent-output:%s" % agent_id,
                ts="",
                content="[%s] %s" % (rel, summary),
                meta={"ops_source": "agent-output", "relpath": rel},
            )
        )
        harvested.append(rel)
    if harvested:
        seen.update(harvested)
        # keep the watermark bounded: remember the most recent 2000
        ordered = sorted(seen)
        return experiences, {key: ",".join(ordered[-2000:])}
    return [], {}


def _harvest_daily_logs(
    since: dict, memdir: Path | None = None
) -> tuple[list[Experience], dict[str, str]]:
    """New lines from ~/memory/YYYY-MM-DD.md (today + yesterday), chunked.

    The daily log is where cron workers, hunts, and the assistant append
    observations — it is the narrative counterpart to the structured
    sources above.
    """
    from datetime import datetime, timedelta

    if memdir is None:
        memdir = _memory_dir()
    marks: dict[str, str] = {}
    experiences: list[Experience] = []
    today = datetime.now().date()
    for day in (today, today - timedelta(days=1)):
        name = day.isoformat()
        path = memdir / (name + ".md")
        key = "opslog:memlog:%s" % name
        try:
            start = int(since.get(key) or 0)
        except (TypeError, ValueError):
            start = 0
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        new_lines = [ln for ln in lines[start:] if ln.strip()]
        for i in range(0, len(new_lines), _OPS_CHUNK_LINES):
            chunk = new_lines[i : i + _OPS_CHUNK_LINES]
            experiences.append(
                Experience(
                    id="memlog:%s:%d" % (name, start + i),
                    kind="note",
                    source="daily-log:%s" % name,
                    ts=name,
                    content=_scrub("Daily log %s:\n%s" % (name, "\n".join(chunk))),
                    meta={"ops_source": "daily-log"},
                )
            )
        marks[key] = str(len(lines))
    return experiences, marks


def harvest_ops_logs(
    since: dict[str, str] | None = None,
    *,
    perpetual_dir: Path | None = None,
    agents_dir: Path | None = None,
    memdir: Path | None = None,
) -> tuple[list[Experience], dict[str, str]]:
    """Harvest all new operational-log experiences across widened sources.

    Sources (all local, read-only, best-effort):
      * hunt waves        — ``<LEVI_HOME>/perpetual/hunt_state.json``
      * build queue       — ``<LEVI_HOME>/perpetual/build_queue.jsonl``
      * agent tool-output — ``<LEVI_WORKSPACE>/agents/*/tool-output/*.json``
      * daily memory logs — ``<LEVI_MEMORY_DIR>/YYYY-MM-DD.md`` (today + yesterday)

    Every source is watermarked in ``since`` so cycles stay idempotent.
    Content is secret-scrubbed via :mod:`levi.growth.redact`.
    """
    if since is not None and not isinstance(since, dict):
        raise ValueError("harvest_ops_logs: since must be a dict or None")
    since = since or {}
    experiences: list[Experience] = []
    watermarks: dict[str, str] = {}
    import functools

    harvesters = (
        functools.partial(_harvest_hunt_waves, perpetual_dir=perpetual_dir),
        functools.partial(_harvest_build_queue, perpetual_dir=perpetual_dir),
        functools.partial(_harvest_agent_outputs, agents_dir=agents_dir),
        functools.partial(_harvest_daily_logs, memdir=memdir),
    )
    for fn in harvesters:
        try:
            exps, marks = fn(since)
        except Exception:
            continue  # one bad source never breaks the widening
        experiences.extend(exps)
        watermarks.update(marks)
    # Echo untouched watermarks: a source with nothing new must not erase
    # the mark that keeps it silent. (Convention shared with the session
    # harvester's __stat__ keys.)
    for k, v in since.items():
        if k.startswith("opslog:") and k not in watermarks:
            watermarks[k] = v
    return experiences, watermarks


def harvest_new(
    since: dict[str, str] | None = None,
) -> tuple[list[Experience], dict[str, str]]:
    """Harvest all new experiences across sources.

    Sources: local chat sessions, automations, affect signals, operational
    logs (hunt waves, build queue, agent tool-outputs, daily memory logs),
    and — consent-gated — cloud API chat sessions (see
    :mod:`levi.growth.harvest_cloud`). Cloud experiences carry
    ``meta["origin"] = "cloud"``; everything else is ``"local"``
    (tagged here so downstream counts are total).

    Returns ``(experiences, watermarks)`` where watermarks should be
    persisted by the caller (see :mod:`levi.growth.cycle`).
    """
    if since is not None and not isinstance(since, dict):
        raise ValueError("harvest_new: since must be a dict or None")
    experiences, watermarks = harvest_sessions(since=since)
    experiences.extend(harvest_automations())
    aff, aff_marks = harvest_affect_signals(since=since)
    experiences.extend(aff)
    watermarks.update(aff_marks)
    ops, ops_marks = harvest_ops_logs(since=since)
    experiences.extend(ops)
    watermarks.update(ops_marks)
    try:
        from levi.growth.harvest_cloud import harvest_cloud_sessions

        cloud_exps, cloud_marks = harvest_cloud_sessions(since=since)
    except Exception:
        cloud_exps, cloud_marks = [], {}
    experiences.extend(cloud_exps)
    watermarks.update(cloud_marks)
    for exp in experiences:
        exp.meta.setdefault("origin", "local")
    return experiences, watermarks
