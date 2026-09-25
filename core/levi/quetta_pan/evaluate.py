"""Mutation evaluation: every applied projection is judged before it stands.

A mutation passes when:
- the result still parses (Python: real ``ast`` parse; JS/TS: honest
  shallow bracket-balance check — documented as shallow, not a parse), and
- the optional test command (if given) exits 0.

Heuristic delta (suggestion count before vs after) is reported but never
gates: a mutation may be neutral yet valid. Fail-closed: any evaluation
error marks the mutation failed with the reason recorded — the engine
then rolls back and composts it.
"""

from __future__ import annotations

import ast
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

# suggest_fn signature: (content: str, suffix: str) -> list of suggestion dicts
SuggestFn = Callable[[str, str], List[dict]]


@dataclass
class MutationResult:
    ok: bool
    parse_ok: bool
    parse_detail: str = ""
    heuristics_before: int = 0
    heuristics_after: int = 0
    test_ok: Optional[bool] = None
    test_detail: str = ""
    failure_reason: str = ""
    applied_fix_ids: List[str] = field(default_factory=list)


def _python_parse_ok(content: str) -> tuple[bool, str]:
    try:
        ast.parse(content)
    except SyntaxError as exc:
        return False, f"python parse failed: {exc}"
    return True, "python ast.parse ok"


def _js_shallow_balance_ok(content: str) -> tuple[bool, str]:
    """Honest shallow check for JS/TS: bracket balance ignoring strings
    and comments. NOT a real parse — reported as shallow in the detail."""
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: List[str] = []
    i, n = 0, len(content)
    in_str: Optional[str] = None
    while i < n:
        ch = content[i]
        nxt = content[i + 1] if i + 1 < n else ""
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
        elif ch == "/" and nxt == "/":
            while i < n and content[i] != "\n":
                i += 1
            continue
        elif ch == "/" and nxt == "*":
            i += 2
            while i + 1 < n and not (content[i] == "*" and content[i + 1] == "/"):
                i += 1
            i += 2
            continue
        elif ch in ("'", '"', "`"):
            in_str = ch
        elif ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack.pop() != pairs[ch]:
                return False, f"js-ts shallow balance failed at offset {i}"
        i += 1
    if in_str:
        return False, "js-ts shallow check: unterminated string"
    if stack:
        return False, f"js-ts shallow check: unclosed {stack[-1]}"
    return True, "js-ts shallow bracket-balance ok (not a full parse)"


def check_parse(path: Path | str, content: str) -> tuple[bool, str]:
    suffix = Path(path).suffix.lower()
    if suffix == ".py":
        return _python_parse_ok(content)
    if suffix in (".js", ".ts", ".jsx", ".tsx"):
        return _js_shallow_balance_ok(content)
    return True, f"no parse check for {suffix or 'unknown'}; skipped"


def run_test_command(
    test_cmd: List[str] | str, cwd: Path | str, timeout: int = 120
) -> tuple[bool, str]:
    """Run the caller's test command. Non-zero exit, timeout, or launch
    failure all count as failure — fail-closed, with the reason kept."""
    try:
        proc = subprocess.run(
            test_cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"test command timed out after {timeout}s"
    except OSError as exc:
        return False, f"test command failed to launch: {exc}"
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = tail[-5:] if tail else ["no output"]
        return False, f"test command exited {proc.returncode}: " + " | ".join(tail)
    return True, "test command exited 0"


def evaluate_mutation(
    path: Path | str,
    before: str,
    after: str,
    suggest_fn: Optional[SuggestFn] = None,
    test_cmd: Optional[List[str] | str] = None,
    test_timeout: int = 120,
) -> MutationResult:
    """Judge an applied mutation. Pure: reads nothing, writes nothing."""
    path = Path(path)
    parse_ok, parse_detail = check_parse(path, after)

    hb = ha = 0
    if suggest_fn is not None:
        try:
            hb = len(suggest_fn(before, path.suffix))
            ha = len(suggest_fn(after, path.suffix))
        except Exception as exc:  # heuristic crash must not mask the verdict
            return MutationResult(
                ok=False,
                parse_ok=parse_ok,
                parse_detail=parse_detail,
                failure_reason=f"heuristic re-scan crashed: {exc}",
            )

    test_ok: Optional[bool] = None
    test_detail = ""
    if test_cmd:
        test_ok, test_detail = run_test_command(
            test_cmd, cwd=path.parent, timeout=test_timeout
        )

    if not parse_ok:
        return MutationResult(
            ok=False,
            parse_ok=False,
            parse_detail=parse_detail,
            heuristics_before=hb,
            heuristics_after=ha,
            test_ok=test_ok,
            test_detail=test_detail,
            failure_reason=f"parse check failed: {parse_detail}",
        )
    if test_ok is False:
        return MutationResult(
            ok=False,
            parse_ok=True,
            parse_detail=parse_detail,
            heuristics_before=hb,
            heuristics_after=ha,
            test_ok=False,
            test_detail=test_detail,
            failure_reason=f"test command failed: {test_detail}",
        )
    return MutationResult(
        ok=True,
        parse_ok=True,
        parse_detail=parse_detail,
        heuristics_before=hb,
        heuristics_after=ha,
        test_ok=test_ok,
        test_detail=test_detail,
    )
