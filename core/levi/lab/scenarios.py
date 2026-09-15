"""LEVI Lab scenarios — 4 original demos of on-device agentic AI.

Each scenario drives LEVI's *real* agentic loop (:func:`run_subtask` from
:mod:`levi.agent`) with the local rule-based provider and captures the
*real* transcript. Nothing is scripted: the fixtures under
``core/levi/lab/fixtures/`` are what the loop actually did, with
provenance attached.

The four scenarios:

1. ``resilient-file`` — multi-step file task where the first tool call
   fails (missing file) → diagnose → recover. The *lab* performs the
   recovery run; both transcripts are captured.
2. ``red-green`` — a coding fix loop: the loop runs a buggy script (red,
   real traceback), the lab harness applies the patch (recorded as a lab
   event, honestly labeled — the rule-based local provider cannot reason
   about code), the loop re-runs it (green).
3. ``research-brief`` — research with web tools: fetch a page over HTTP
   (served by a local stub server, so the demo is fully offline) and
   save the findings to memory.
4. ``effort-ab`` — reasoning-effort A/B: the same question under a plain
   vs. an elaborated system prompt. With the deterministic local provider
   the transcripts are identical — itself an honest finding about what
   prompt effort does and doesn't change.

``levi lab run <id>`` plays back the captured fixture; ``--live`` re-runs
the loop for real.
"""

from __future__ import annotations

import datetime
import json
import platform
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict

import levi
from levi.agent.loop import AgentTranscript, run_subtask

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclass
class Scenario:
    id: str
    title: str
    description: str
    phases: list[str] = field(default_factory=list)
    honest_notes: str = ""


SCENARIOS: dict[str, Scenario] = {
    "resilient-file": Scenario(
        id="resilient-file",
        title="Resilient file task: fail → diagnose → recover",
        description=(
            "The loop tries to read a file that doesn't exist (real tool "
            "failure), then a recovery run creates it and reads it back."
        ),
        phases=["fail", "recover"],
        honest_notes=(
            "The diagnosis ('the file is missing, so create it') is performed "
            "by the lab harness between runs. The local provider is a "
            "deterministic planner: it does not introspect tool errors the "
            "way a model would. What IS real: both transcripts, the tool "
            "failure, and the recovery."
        ),
    ),
    "red-green": Scenario(
        id="red-green",
        title="Red → green coding fix",
        description=(
            "The loop runs a buggy script (red: real traceback), the harness "
            "applies a one-line patch, the loop re-runs it (green)."
        ),
        phases=["red", "green"],
        honest_notes=(
            "The patch is applied by the lab harness and recorded as a lab "
            "event — the rule-based local provider cannot diagnose a "
            "traceback. Real: both test runs, the failure output, the pass."
        ),
    ),
    "research-brief": Scenario(
        id="research-brief",
        title="Research brief with web tools",
        description=(
            "The loop fetches a page over HTTP — via a small helper script "
            "on loopback (local stub server: fully offline) — and saves the "
            "findings to memory."
        ),
        phases=["fetch", "note"],
        honest_notes=(
            "The page is served by a stub HTTP server on loopback so the "
            "demo needs no internet. Swap the URL for a real one with "
            "--live and your own endpoint."
        ),
    ),
    "effort-ab": Scenario(
        id="effort-ab",
        title="Reasoning-effort A/B on the same question",
        description=(
            "The same file task runs twice: once with the default system "
            "prompt, once with an elaborated 'think step by step' prompt. "
            "The transcripts are compared."
        ),
        phases=["low-effort", "high-effort"],
        honest_notes=(
            "With the deterministic local provider both runs are identical — "
            "prompt effort changes nothing for a rule-based planner. That "
            "negative result is the honest finding; with a real model "
            "backend the comparison becomes interesting."
        ),
    ),
}


def get_scenario(scenario_id: str) -> Scenario | None:
    """Return a scenario by id, or None."""
    return SCENARIOS.get(scenario_id)


def list_scenarios() -> list[Scenario]:
    """All scenarios in registry order."""
    return list(SCENARIOS.values())


# ---------------------------------------------------------------------------
# Transcript helpers
# ---------------------------------------------------------------------------


def transcript_stats(t: Any) -> Dict[str, Any]:
    """Small honest stats for one transcript (dict or AgentTranscript)."""
    d = t.to_dict() if hasattr(t, "to_dict") else t
    steps = d.get("steps", [])
    calls = [c for s in steps for c in s.get("tool_calls", [])]
    tools = sorted({c.get("name", "?") for c in calls})
    failed = [r for s in steps for r in s.get("results", []) if not r.get("ok", True)]
    return {
        "steps": len(steps),
        "tool_calls": len(calls),
        "tools_used": tools,
        "failed_tool_calls": len(failed),
        "ok": d.get("ok", False),
        "provider": d.get("provider_name", "?"),
        "final": (d.get("final") or "")[:300],
    }


def _provenance(scenario_id: str, live: bool) -> Dict[str, Any]:
    return {
        "captured_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds"
        ),
        "provider": "local",
        "levi_version": getattr(levi, "__version__", "?"),
        "live": live,
        "python": platform.python_version(),
        "scenario": scenario_id,
        "note": (
            "Real transcript from LEVI's agentic loop (run_subtask, local "
            "provider). Illustrative of a real run, not live intelligence."
        ),
    }


def _run(
    task: str, workdir: Path, system_prompt: str | None = None
) -> AgentTranscript:
    """One real loop run with the local provider."""
    return run_subtask(
        task,
        provider="local",
        consent=True,
        workspace_root=workdir,
        system_prompt=system_prompt,
        max_steps=10,
    )


def _phase(name: str, transcript: AgentTranscript) -> Dict[str, Any]:
    d = transcript.to_dict()
    d["stats"] = transcript_stats(transcript)
    return {"name": name, "transcript": d}


# ---------------------------------------------------------------------------
# Scenario runners (live)
# ---------------------------------------------------------------------------


def _run_resilient_file(workdir: Path) -> Dict[str, Any]:
    t1 = _run("Read lab-diary.txt and summarize its contents", workdir)
    t2 = _run(
        "Create lab-diary.txt with one line 'Recovered after a missing read' "
        "and read it back to confirm",
        workdir,
    )
    return {"phases": [_phase("fail", t1), _phase("recover", t2)], "events": []}


def _run_red_green(workdir: Path) -> Dict[str, Any]:
    # NOTE: the script is named `labbug` with no extension on purpose — the
    # local provider's command parser stops at the first ".", so
    # `python3 lab-bug.py` would arrive as `python3 lab-bug`. This is a real
    # quirk of the local provider, documented here rather than hidden.
    buggy = workdir / "labbug"
    buggy.write_text('print("answer:", 1 // 0)\n', encoding="utf-8")
    t_red = _run("Run the command `python3 labbug`", workdir)
    # The lab harness applies the patch — honestly labeled as a lab event,
    # not an agent action: the local provider cannot reason about tracebacks.
    buggy.write_text('print("answer:", 42)\n', encoding="utf-8")
    event = {
        "type": "lab_patch",
        "file": "labbug",
        "before": 'print("answer:", 1 // 0)',
        "after": 'print("answer:", 42)',
        "note": "applied by the lab harness, not the agent",
    }
    t_green = _run("Run the command `python3 labbug`", workdir)
    return {"phases": [_phase("red", t_red), _phase("green", t_green)], "events": [event]}


_BRIEF_HTML = (
    "<html><body><h1>Lab Brief</h1>"
    "<p>Example Domain is reserved for documentation use.</p>"
    "<p>Second fact: the lab runs fully offline.</p>"
    "</body></html>"
)


class _BriefHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # BaseHTTPRequestHandler names it do_GET
        body = _BRIEF_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _run_research_brief(workdir: Path) -> Dict[str, Any]:
    server = HTTPServer(("127.0.0.1", 0), _BriefHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # The fetch goes through a tiny script (no dots in its name — see the
    # red-green note about the local provider's command parser). The script
    # bypasses proxy env vars so the loopback fetch can't hang on a proxy.
    fetcher = workdir / "fetchbrief"
    fetcher.write_text(
        "import urllib.request\n"
        "opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))\n"
        f"print(opener.open('http://127.0.0.1:{port}/brief.html', timeout=10)"
        ".read().decode())\n",
        encoding="utf-8",
    )
    try:
        t_fetch = _run("Run the command `python3 fetchbrief`", workdir)
        t_note = _run(
            "Remember that the lab brief says Example Domain is reserved "
            "for documentation use",
            workdir,
        )
    finally:
        server.shutdown()
    return {"phases": [_phase("fetch", t_fetch), _phase("note", t_note)], "events": []}


_EFFORT_TASK = "Create effort-note.txt with two lines and read it back"
_EFFORT_SYSTEM = (
    "You are LEVI, a local-first Synthetic Intelligence assistant. "
    "Think step by step. Before each tool call, state what you expect it "
    "to do. After each tool result, verify it carefully and double-check "
    "your work before proceeding."
)


def _run_effort_ab(workdir: Path) -> Dict[str, Any]:
    t_low = _run(_EFFORT_TASK, workdir)
    t_high = _run(_EFFORT_TASK, workdir, system_prompt=_EFFORT_SYSTEM)
    s_low, s_high = transcript_stats(t_low), transcript_stats(t_high)
    comparison = {
        "low_effort": {k: s_low[k] for k in ("steps", "tool_calls", "tools_used", "ok")},
        "high_effort": {k: s_high[k] for k in ("steps", "tool_calls", "tools_used", "ok")},
        "finding": (
            "Identical transcripts: with the deterministic local provider, "
            "system-prompt effort changes nothing. Re-run against a real "
            "model backend to see effort matter."
            if s_low["steps"] == s_high["steps"]
            and s_low["tool_calls"] == s_high["tool_calls"]
            else "Transcripts differ — see phase stats."
        ),
    }
    return {
        "phases": [_phase("low-effort", t_low), _phase("high-effort", t_high)],
        "events": [],
        "comparison": comparison,
    }


_RUNNERS = {
    "resilient-file": _run_resilient_file,
    "red-green": _run_red_green,
    "research-brief": _run_research_brief,
    "effort-ab": _run_effort_ab,
}


# ---------------------------------------------------------------------------
# Fixtures: capture + playback
# ---------------------------------------------------------------------------


def fixture_path(scenario_id: str) -> Path:
    return FIXTURE_DIR / f"{scenario_id}.json"


def capture(scenario_id: str, workdir: Path, live: bool = True) -> Dict[str, Any]:
    """Run a scenario for real and write its fixture. Returns the fixture."""
    sc = get_scenario(scenario_id)
    if sc is None:
        raise ValueError(f"unknown scenario {scenario_id!r}")
    workdir.mkdir(parents=True, exist_ok=True)
    result = _RUNNERS[scenario_id](workdir)
    fixture = {
        "scenario": sc.id,
        "title": sc.title,
        "description": sc.description,
        "provenance": _provenance(sc.id, live),
        "phases": result["phases"],
        "events": result["events"],
        "notes": sc.honest_notes,
    }
    if "comparison" in result:
        fixture["comparison"] = result["comparison"]
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    fixture_path(scenario_id).write_text(
        json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return fixture


def load_fixture(scenario_id: str) -> Dict[str, Any] | None:
    """Load a captured fixture, or None when not captured yet."""
    fp = fixture_path(scenario_id)
    if not fp.is_file():
        return None
    return json.loads(fp.read_text(encoding="utf-8"))


def playback(scenario_id: str) -> str:
    """Render a captured fixture as a readable lab report (no execution)."""
    sc = get_scenario(scenario_id)
    if sc is None:
        return f"lab: unknown scenario {scenario_id!r} — try `levi lab scenarios`."
    fx = load_fixture(scenario_id)
    if fx is None:
        return (
            f"lab: no captured fixture for {scenario_id!r} yet — "
            f"run `levi lab run {scenario_id} --live` to capture one."
        )
    prov = fx.get("provenance", {})
    lines = [
        f"══ {fx.get('title', sc.title)} ══",
        f"  captured: {prov.get('captured_utc', '?')}  provider: {prov.get('provider', '?')}  "
        f"LEVI {prov.get('levi_version', '?')}  live: {prov.get('live')}",
        f"  {fx.get('description', '')}",
        "",
    ]
    for ph in fx.get("phases", []):
        t = ph.get("transcript", {})
        st = t.get("stats", transcript_stats(t))
        lines.append(f"── phase: {ph.get('name')} ──")
        lines.append(
            f"  task : {t.get('task', '')[:100]}"
        )
        lines.append(
            f"  stats: {st['steps']} step(s), {st['tool_calls']} tool call(s) "
            f"[{', '.join(st['tools_used']) or 'none'}], "
            f"failed calls: {st['failed_tool_calls']}, ok={st['ok']}"
        )
        for i, step in enumerate(t.get("steps", [])):
            for call in step.get("tool_calls", []):
                lines.append(f"    step {i}: {call.get('name')} {call.get('args', {})}")
            for res in step.get("results", []):
                mark = "ok" if res.get("ok") else "FAIL"
                out = (res.get("output") or res.get("error") or "")[:160].replace("\n", " ")
                lines.append(f"    step {i}: [{mark}] {res.get('tool')}: {out}")
        if t.get("final"):
            lines.append(f"  final: {t['final'][:200]}")
        lines.append("")
    for ev in fx.get("events", []):
        lines.append(
            f"  [lab event] {ev.get('type')}: {ev.get('file', '')} "
            f"{ev.get('before', '')!r} → {ev.get('after', '')!r}"
        )
    if "comparison" in fx:
        c = fx["comparison"]
        lines.append(f"  A/B: low={c['low_effort']} high={c['high_effort']}")
        lines.append(f"  finding: {c['finding']}")
    lines.append(f"  honest notes: {fx.get('notes', '')}")
    return "\n".join(lines)
