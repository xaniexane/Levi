"""Quietwatch engine — selective calling rebuilt as a LEVI-native decision machine.

Clean-room rebuild of the *pattern* behind SELCAL (1957), queued as
load-bearing in the wave-019 hunt: a cockpit radio stays silent until its
own call sign is broadcast, so a crew can rest through everyone else's
traffic. The archive record describes the *technique*; this module is
original stdlib-only code re-implementing the *idea* — never any
artifact's text, never a paid anything.

An engine, so it is pure and stateless: the watched "call signs" and the
"airwaves" both arrive with the input, and the verdict is deterministic —
same inputs, same verdict, every time. Silence is the default: the engine
reports ``awake`` only when at least one registered call sign is heard in
the transcript.

Input schema::

    {
        "calls": [{"id": "alpha", "pattern": "alpha base"}],
        "transcript": ["line one", "alpha base, come in"],
    }

Matching is explicit and deterministic: casefolded substring match,
line by line, in transcript order; the first matching line per call sign
is recorded. Verdict::

    {"awake": bool, "hits": [{"call": id, "line": n, "text": line}], "lines_scanned": n}
"""

from __future__ import annotations

from typing import Any, Dict, List

from levi.engines.base import Engine, EngineInputError, EngineResult, registry


def _validate_calls(calls: Any) -> List[Dict[str, str]]:
    if not isinstance(calls, list) or not calls:
        raise EngineInputError("quietwatch: 'calls' must be a non-empty list")
    cleaned: List[Dict[str, str]] = []
    for i, call in enumerate(calls):
        if not isinstance(call, dict):
            raise EngineInputError(
                f"quietwatch: calls[{i}] must be a dict with 'id' and 'pattern'"
            )
        cid = call.get("id")
        pattern = call.get("pattern")
        if not isinstance(cid, str) or not cid.strip():
            raise EngineInputError(f"quietwatch: calls[{i}].id must be a non-empty str")
        if not isinstance(pattern, str) or not pattern.strip():
            raise EngineInputError(
                f"quietwatch: calls[{i}].pattern must be a non-empty str"
            )
        cleaned.append({"id": cid.strip(), "pattern": pattern.strip()})
    ids = [c["id"] for c in cleaned]
    if len(set(ids)) != len(ids):
        raise EngineInputError("quietwatch: call ids must be unique")
    return cleaned


def _validate_transcript(transcript: Any) -> List[str]:
    if isinstance(transcript, str):
        transcript = transcript.splitlines()
    if not isinstance(transcript, list) or not all(
        isinstance(line, str) for line in transcript
    ):
        raise EngineInputError(
            "quietwatch: 'transcript' must be a str or a list of str"
        )
    return transcript


def _quietwatch(inputs: Dict[str, Any]) -> EngineResult:
    calls = _validate_calls(inputs.get("calls"))
    transcript = _validate_transcript(inputs.get("transcript"))

    trace: List[str] = [
        f"watching {len(calls)} call sign(s) over {len(transcript)} line(s)"
    ]
    hits: List[Dict[str, Any]] = []
    heard = set()
    for line_no, line in enumerate(transcript):
        folded = line.casefold()
        for call in calls:
            if call["id"] in heard:
                continue
            if call["pattern"].casefold() in folded:
                heard.add(call["id"])
                hits.append({"call": call["id"], "line": line_no, "text": line})
                trace.append(f"  line {line_no}: heard '{call['id']}'")

    awake = bool(hits)
    trace.append(
        "awake — call sign heard" if awake else "silent — nothing addressed to us"
    )
    verdict = {"awake": awake, "hits": hits, "lines_scanned": len(transcript)}
    return EngineResult(
        engine_id="quietwatch",
        verdict=verdict,
        confidence=1.0,  # pattern match is certain, either way
        trace=trace,
    )


QUIETWATCH_ENGINE = Engine(
    id="quietwatch",
    name="Quietwatch",
    description=(
        "Selective calling over a transcript: stays silent (awake=false) "
        "until a registered call sign is heard, then reports exactly which "
        "call was heard and where. Deterministic, casefold substring match."
    ),
    required=("calls", "transcript"),
    schema={
        "calls": "list[{id:str, pattern:str}] (≥1, unique ids)",
        "transcript": "str | list[str] — the airwaves to scan",
    },
    risk="info",
    handler=_quietwatch,
)

registry.register(QUIETWATCH_ENGINE)
