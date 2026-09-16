"""Per-call token metering with cause attribution.

Every record carries *why* the tokens were spent: the provider, the model,
the task, the agent, the tool on whose behalf the model call was made, and
a fingerprint of the prompt. Any token must be traceable to its cause.

Persistence: append-only JSONL at ``~/.levi/governor/usage.jsonl``.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path


def governor_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    """Directory holding governor state. ``home`` is the user's HOME dir."""
    base = Path(home) if home is not None else Path(os.path.expanduser("~"))
    return base / ".levi" / "governor"


def fingerprint_messages(messages: list) -> str:
    """Stable short fingerprint of a prompt.

    Accepts ChatMessage objects (``.role``/``.content``) or plain dicts.
    Same prompt -> same fingerprint; any change -> different fingerprint.
    """
    parts: list[str] = []
    for m in messages:
        if isinstance(m, dict):
            role, content = m.get("role", ""), m.get("content", "")
        else:
            role, content = getattr(m, "role", ""), getattr(m, "content", "")
        parts.append(f"{role}:{content}")
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


@dataclass
class UsageRecord:
    """One metered provider call."""

    ts: float = 0.0
    provider: str = ""
    model: str = ""
    task_id: str = ""
    agent_id: str = ""
    tool_name: str = ""
    prompt_fingerprint: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    priority_pass_id: str = ""  # burst pass that admitted this call, if any
    error: str | None = None

    @property
    def total(self) -> int:
        return (self.prompt_tokens or 0) + (self.completion_tokens or 0)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "UsageRecord":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


class Meter:
    """Append-only token ledger with filtered reads."""

    def __init__(
        self,
        home: "str | os.PathLike[str] | None" = None,
        clock=time.time,
    ) -> None:
        self._dir = governor_home(home)
        self._ledger = self._dir / "usage.jsonl"
        self._clock = clock

    @property
    def ledger_path(self) -> Path:
        return self._ledger

    def record(
        self,
        *,
        provider: str = "",
        model: str = "",
        task_id: str = "",
        agent_id: str = "",
        tool_name: str = "",
        prompt_fingerprint: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        priority_pass_id: str = "",
        error: str | None = None,
        ts: float | None = None,
    ) -> UsageRecord:
        """Append one usage record. Fail-closed on bad counts."""
        if prompt_tokens < 0 or completion_tokens < 0:
            raise ValueError("token counts must be non-negative")
        rec = UsageRecord(
            ts=self._clock() if ts is None else ts,
            provider=str(provider or ""),
            model=str(model or ""),
            task_id=str(task_id or ""),
            agent_id=str(agent_id or ""),
            tool_name=str(tool_name or ""),
            prompt_fingerprint=str(prompt_fingerprint or ""),
            prompt_tokens=int(prompt_tokens),
            completion_tokens=int(completion_tokens),
            priority_pass_id=str(priority_pass_id or ""),
            error=error,
        )
        self._dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(rec.to_dict(), separators=(",", ":")) + "\n"
        # O_APPEND: each small write lands atomically; single-writer by design.
        fd = os.open(self._ledger, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
        return rec

    def query(
        self,
        *,
        since: float | None = None,
        until: float | None = None,
        provider: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        tool_name: str | None = None,
        limit: int | None = None,
    ) -> list[UsageRecord]:
        """Read records, newest last, honoring every filter given."""
        out: list[UsageRecord] = []
        if not self._ledger.exists():
            return out
        with open(self._ledger, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = UsageRecord.from_dict(json.loads(line))
                except (json.JSONDecodeError, TypeError):
                    continue  # corrupt line: skip, never crash the reader
                if since is not None and rec.ts < since:
                    continue
                if until is not None and rec.ts >= until:
                    continue
                if provider is not None and rec.provider != provider:
                    continue
                if task_id is not None and rec.task_id != task_id:
                    continue
                if agent_id is not None and rec.agent_id != agent_id:
                    continue
                if tool_name is not None and rec.tool_name != tool_name:
                    continue
                out.append(rec)
                if limit is not None and len(out) >= limit:
                    break
        return out

    def totals(self, records: list[UsageRecord] | None = None, **filters) -> dict:
        """Token totals over a record set (or a fresh query with filters)."""
        recs = records if records is not None else self.query(**filters)
        prompt = sum(r.prompt_tokens for r in recs)
        completion = sum(r.completion_tokens for r in recs)
        return {
            "calls": len(recs),
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        }
