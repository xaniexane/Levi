"""Service registry for the LEVI bot.

A *service* is a named, repeatable unit of work the bot performs: a morning
briefing, a bounty watch, a backup status check, a research brief. Services
are stored as JSON in ``~/.levi/bot/services.json`` (override the root with
``LEVI_BOT_HOME``) so user-added services survive restarts.

Definitions are validated fail-closed: a bad name, unknown type, malformed
schedule, or non-dict params is rejected with a clear error — never stored.

The bot does NOT implement its own scheduler. Recurring services attach to
the existing cron/daemon mechanism, e.g.::

    0 7 * * * cd ~/workspace/levi && python -m levi.bot service run morning-briefing

See ``docs/BOT.md`` for the full scheduling story.

All imports of other LEVI modules are lazy (inside handler functions) so
this module imports clean standalone. Handlers degrade honestly: when a
module is unavailable, the report says so instead of inventing results.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# State / paths
# ---------------------------------------------------------------------------


def _state_dir() -> str:
    """Return the bot state directory (override via ``LEVI_BOT_HOME``)."""
    override = os.environ.get("LEVI_BOT_HOME")
    if override:
        return os.path.join(override, "bot")
    return os.path.join(os.path.expanduser("~"), ".levi", "bot")


def _registry_path() -> str:
    return os.path.join(_state_dir(), "services.json")


def _services_out_dir() -> str:
    return os.path.join(_state_dir(), "services")


# ---------------------------------------------------------------------------
# Validation (fail-closed)
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,47}$")
_SERVICE_TYPES = ("briefing", "monitor", "research", "custom")

# 5-field cron bounds: minute hour day-of-month month day-of-week
_CRON_BOUNDS = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))
_CRON_FIELD_RE = re.compile(r"^(\*|(\*/\d+)|(\d+(-\d+)?(,\d+(-\d+)?)*))$")
_SCHEDULE_KEYWORDS = {
    "@hourly": "0 * * * *",
    "@daily": "0 7 * * *",
    "@weekly": "0 7 * * 1",
    "@monthly": "0 7 1 * *",
    "hourly": "0 * * * *",
    "daily": "0 7 * * *",
    "weekly": "0 7 * * 1",
    "monthly": "0 7 1 * *",
}


class ServiceError(ValueError):
    """Raised for any invalid service definition or registry operation."""


def validate_name(name: Any) -> str:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise ServiceError(
            "service name must match ^[a-z0-9][a-z0-9-]{1,47}$, got %r" % (name,)
        )
    return name


def validate_type(service_type: Any) -> str:
    if service_type not in _SERVICE_TYPES:
        raise ServiceError(
            "service type must be one of %s, got %r"
            % (", ".join(_SERVICE_TYPES), service_type)
        )
    return service_type


def _validate_cron_field(value: str, lo: int, hi: int) -> bool:
    if not _CRON_FIELD_RE.match(value):
        return False
    if value == "*":
        return True
    if value.startswith("*/"):
        step = int(value[2:])
        return step >= 1
    for part in value.split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            if not (a.isdigit() and b.isdigit()):
                return False
            if not (lo <= int(a) <= int(b) <= hi):
                return False
        else:
            if not part.isdigit() or not (lo <= int(part) <= hi):
                return False
    return True


def normalize_schedule(spec: Any) -> str:
    """Validate a schedule spec and return its canonical 5-field cron form.

    Accepts a 5-field cron string or a keyword (``daily``, ``@hourly`` …).
    Anything else raises :class:`ServiceError`.
    """
    if not isinstance(spec, str) or not spec.strip():
        raise ServiceError("schedule must be a non-empty string, got %r" % (spec,))
    spec = spec.strip()
    lowered = spec.lower()
    if lowered in _SCHEDULE_KEYWORDS:
        return _SCHEDULE_KEYWORDS[lowered]
    fields = spec.split()
    if len(fields) != 5:
        raise ServiceError(
            "schedule must be a 5-field cron ('M H DOM MON DOW') or one of "
            "%s; got %r" % (sorted(_SCHEDULE_KEYWORDS), spec)
        )
    for value, (lo, hi) in zip(fields, _CRON_BOUNDS):
        if not _validate_cron_field(value, lo, hi):
            raise ServiceError("invalid cron field %r in schedule %r" % (value, spec))
    return " ".join(fields)


def validate_params(params: Any) -> Dict[str, Any]:
    if params is None:
        return {}
    if not isinstance(params, dict):
        raise ServiceError("params must be a JSON object, got %r" % (params,))
    return dict(params)


# ---------------------------------------------------------------------------
# Service definition
# ---------------------------------------------------------------------------


@dataclass
class ServiceDefinition:
    """A validated, storable service definition."""

    name: str
    description: str
    service_type: str
    schedule: str  # canonical 5-field cron
    params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    builtin: bool = False
    created_at: str = ""

    def __post_init__(self) -> None:
        self.name = validate_name(self.name)
        if not isinstance(self.description, str) or not self.description.strip():
            raise ServiceError("description must be a non-empty string")
        self.description = self.description.strip()
        self.service_type = validate_type(self.service_type)
        self.schedule = normalize_schedule(self.schedule)
        self.params = validate_params(self.params)
        self.enabled = bool(self.enabled)
        self.builtin = bool(self.builtin)
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "service_type": self.service_type,
            "schedule": self.schedule,
            "params": self.params,
            "enabled": self.enabled,
            "builtin": self.builtin,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ServiceDefinition":
        if not isinstance(raw, dict):
            raise ServiceError("service record must be an object, got %r" % (raw,))
        try:
            return cls(
                name=raw["name"],
                description=raw.get("description", ""),
                service_type=raw.get("service_type", ""),
                schedule=raw.get("schedule", ""),
                params=raw.get("params"),
                enabled=raw.get("enabled", True),
                builtin=raw.get("builtin", False),
                created_at=raw.get("created_at", ""),
            )
        except KeyError as exc:
            raise ServiceError("service record missing field %s" % (exc,)) from None


# ---------------------------------------------------------------------------
# Built-in services
# ---------------------------------------------------------------------------


def _builtin_definitions() -> List[ServiceDefinition]:
    return [
        ServiceDefinition(
            name="morning-briefing",
            description=(
                "Daily digest: news headlines, growth status, academy "
                "progress, demand highlights."
            ),
            service_type="briefing",
            schedule="daily",
            builtin=True,
        ),
        ServiceDefinition(
            name="bounty-watch",
            description=(
                "Check the bounty finding store for new findings since the "
                "last run and report them. Set params.live=true to run a "
                "fresh recon pass first (touches the network)."
            ),
            service_type="monitor",
            schedule="daily",
            params={"live": False},
            builtin=True,
        ),
        ServiceDefinition(
            name="backup-status",
            description="Report backup snapshot status (latest snapshot, counts).",
            service_type="monitor",
            schedule="daily",
            builtin=True,
        ),
        ServiceDefinition(
            name="research-brief",
            description=(
                "Parameterized deep-dive: research a topic with the agent "
                "runtime, write a dated brief file, return a summary. "
                "Requires params.topic (or --params '{\"topic\": ...}')."
            ),
            service_type="research",
            schedule="@weekly",
            builtin=True,
        ),
    ]


# ---------------------------------------------------------------------------
# Registry (JSON-persisted)
# ---------------------------------------------------------------------------


class ServiceRegistry:
    """JSON-backed registry of service definitions.

    Built-ins are seeded on first load. The file is written atomically with
    owner-only permissions. Corrupt files are quarantined, not silently
    dropped.
    """

    def __init__(self, path: Optional[str] = None):
        self.path = path or _registry_path()
        self._services: Dict[str, ServiceDefinition] = {}
        self._load()

    # -- persistence ----------------------------------------------------

    def _load(self) -> None:
        if not os.path.exists(self.path):
            for svc in _builtin_definitions():
                self._services[svc.name] = svc
            self._save()
            return
        try:
            with open(self.path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            self._quarantine("unreadable JSON")
            self._seed_builtins()
            return
        if not isinstance(raw, dict) or not isinstance(raw.get("services"), list):
            self._quarantine("top level is not {services: [...]}")
            self._seed_builtins()
            return
        for item in raw["services"]:
            try:
                svc = ServiceDefinition.from_dict(item)
            except ServiceError:
                continue  # skip bad records, keep the good ones
            self._services[svc.name] = svc
        # Built-ins removed by hand get re-seeded; user services are kept.
        for svc in _builtin_definitions():
            self._services.setdefault(svc.name, svc)

    def _seed_builtins(self) -> None:
        self._services = {s.name: s for s in _builtin_definitions()}
        self._save()

    def _quarantine(self, reason: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = "%s.corrupt-%s" % (self.path, ts)
        try:
            os.replace(self.path, backup)
        except OSError:
            pass

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "services": [s.to_dict() for s in self._services.values()],
        }
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, self.path)

    # -- operations -----------------------------------------------------

    def add(self, definition: ServiceDefinition) -> ServiceDefinition:
        """Add (or replace) a service definition. Validates fail-closed."""
        if not isinstance(definition, ServiceDefinition):
            raise ServiceError(
                "add: expected ServiceDefinition, got %r" % (definition,)
            )
        self._services[definition.name] = definition
        self._save()
        return definition

    def remove(self, name: str) -> bool:
        """Remove a service by name. Built-ins refuse removal (disable them).

        Returns True when something was removed.
        """
        validate_name(name)
        svc = self._services.get(name)
        if svc is None:
            return False
        if svc.builtin:
            raise ServiceError(
                "remove: '%s' is a built-in service; disable it instead "
                "(not supported yet — leave it enabled and ignore its schedule)"
                % name
            )
        del self._services[name]
        self._save()
        return True

    def get(self, name: str) -> Optional[ServiceDefinition]:
        validate_name(name)
        return self._services.get(name)

    def list(self, *, include_disabled: bool = True) -> List[ServiceDefinition]:
        services = sorted(self._services.values(), key=lambda s: s.name)
        if not include_disabled:
            services = [s for s in services if s.enabled]
        return services


# ---------------------------------------------------------------------------
# Service results
# ---------------------------------------------------------------------------


@dataclass
class ServiceResult:
    """Outcome of one service execution."""

    ok: bool
    report: str
    files: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def summary(self, limit: int = 280) -> str:
        text = self.report.strip().replace("\n", " ")
        return text if len(text) <= limit else text[: limit - 1] + "…"


# ---------------------------------------------------------------------------
# Built-in handlers (lazy imports, honest degradation)
# ---------------------------------------------------------------------------


def _unavailable(module: str) -> str:
    return "unavailable (%s could not be imported)" % module


def _handle_morning_briefing(params: Dict[str, Any]) -> ServiceResult:
    """Compose the daily digest from existing LEVI modules (read-only)."""
    sections: List[str] = []
    notes: List[str] = []
    limit = int(params.get("headlines", 8) or 8)

    # News digest: latest ingested day file (no network).
    try:
        from levi.knowledge.news.refresh import DAYS

        day_files = sorted(DAYS.glob("*.jsonl")) if DAYS.exists() else []
        if day_files:
            latest = day_files[-1]
            headlines = []
            with open(latest, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    headlines.append(
                        "- %s (%s)" % (rec.get("title", "?"), rec.get("source", "?"))
                    )
                    if len(headlines) >= limit:
                        break
            sections.append(
                "NEWS (%s):\n%s"
                % (
                    latest.stem,
                    "\n".join(headlines) if headlines else "(no headlines recorded)",
                )
            )
        else:
            notes.append("news: no ingested days yet — run `levi news refresh`")
    except Exception:
        notes.append("news: " + _unavailable("levi.knowledge.news"))

    # Growth status.
    try:
        from levi.growth.cycle import status as growth_status

        st = growth_status()
        sections.append(
            "GROWTH: %s learnings banked, stage=%s"
            % (st.get("learnings", "?"), st.get("stage", "?"))
        )
    except Exception:
        notes.append("growth: " + _unavailable("levi.growth.cycle"))

    # Academy progress.
    try:
        from levi.academy.run_session import (
            get_streaks,
            load_progress,
            next_uncompleted,
        )

        progress = load_progress()
        done = len(progress.get("completed", []))
        nxt = next_uncompleted(progress)
        streaks = get_streaks(progress)
        sections.append(
            "ACADEMY: %d/120 sessions done, next is #%d, streaks=%s"
            % (done, nxt, streaks or "none yet")
        )
    except Exception:
        notes.append("academy: " + _unavailable("levi.academy.run_session"))

    # Demand highlights.
    try:
        pulse_path = os.path.join(os.path.expanduser("~"), ".levi", "demand_pulse.json")
        if os.path.exists(pulse_path):
            with open(pulse_path, encoding="utf-8") as fh:
                pulse = json.load(fh)
            cards = pulse.get("score_cards", []) if isinstance(pulse, dict) else []
            top = sorted(
                (c for c in cards if isinstance(c, dict)),
                key=lambda c: c.get("composite", 0),
                reverse=True,
            )[:3]
            if top:
                sections.append(
                    "DEMAND: "
                    + "; ".join(
                        "%s (%.0f)" % (c.get("title", "?"), c.get("composite", 0))
                        for c in top
                    )
                )
            else:
                notes.append("demand: no scored opportunities yet")
        else:
            notes.append("demand: no demand_pulse.json yet")
    except Exception:
        notes.append("demand: unreadable demand_pulse.json")

    body = "\n\n".join(sections) if sections else "(no sections produced a report)"
    report = "MORNING BRIEFING — %s\n\n%s" % (
        datetime.now(timezone.utc).date().isoformat(),
        body,
    )
    if notes:
        report += "\n\nNotes: " + "; ".join(notes)
    return ServiceResult(ok=True, report=report, notes=notes)


def _handle_bounty_watch(params: Dict[str, Any]) -> ServiceResult:
    """Report new bounty findings since the last run (no network by default)."""
    notes: List[str] = []
    try:
        from levi.bounty.pipeline import run_monitor
        from levi.bounty.store import FindingStore

        if params.get("live"):
            # Consequential: touches the network against enrolled scopes.
            # Scope gating is enforced inside run_monitor itself.
            run_monitor()
            notes.append("live recon pass completed first")
        store = FindingStore()
        new = store.new_since_last_run()
    except Exception as exc:
        return ServiceResult(
            ok=False,
            report="BOUNTY WATCH failed: %s: %s" % (type(exc).__name__, exc),
            notes=[_unavailable("levi.bounty")],
        )
    if not new:
        return ServiceResult(
            ok=True,
            report="BOUNTY WATCH: no new findings since the last run. Quiet out there.",
            notes=notes,
        )
    lines = ["BOUNTY WATCH: %d new finding(s)" % len(new)]
    for f in new[:15]:
        lines.append(
            "- [%s] %s: %s" % (f.severity, f.target, (f.detail or "")[:120])
        )
    if len(new) > 15:
        lines.append("…and %d more (see `levi bounty findings`)" % (len(new) - 15))
    return ServiceResult(ok=True, report="\n".join(lines), notes=notes)


def _handle_backup_status(params: Dict[str, Any]) -> ServiceResult:
    """Report backup snapshot status (read-only)."""
    try:
        from levi.backup.snapshot import list_snapshots
    except Exception:
        return ServiceResult(
            ok=False,
            report="BACKUP STATUS failed: backup module unavailable",
            notes=[_unavailable("levi.backup.snapshot")],
        )
    try:
        snaps = list_snapshots()
    except Exception as exc:
        return ServiceResult(
            ok=False,
            report="BACKUP STATUS failed: %s: %s" % (type(exc).__name__, exc),
        )
    if not snaps:
        return ServiceResult(
            ok=True,
            report=(
                "BACKUP STATUS: no snapshots yet. Run `levi backup now` to "
                "take the first one."
            ),
        )
    latest = snaps[-1]
    lines = [
        "BACKUP STATUS: %d snapshot(s) kept" % len(snaps),
        "latest: %s (%s, %s files)"
        % (
            latest.get("id", "?"),
            latest.get("created_at", "?"),
            latest.get("file_count", "?"),
        ),
    ]
    if params.get("verify"):
        from levi.backup.snapshot import verify_snapshot

        ok, problems = verify_snapshot(latest.get("id", ""))
        lines.append(
            "verify latest: %s" % ("OK" if ok else "FAILED: %s" % "; ".join(problems))
        )
    return ServiceResult(ok=True, report="\n".join(lines))


def _handle_research_brief(params: Dict[str, Any]) -> ServiceResult:
    """Deep-dive a topic with the agent runtime; write a dated brief file.

    Requires ``params.topic``. Honors ``LEVI_BOT_OFFLINE=1``: refuses
    honestly instead of inventing research.
    """
    topic = params.get("topic")
    if not isinstance(topic, str) or not topic.strip():
        raise ServiceError(
            "research-brief: params.topic is required "
            "(e.g. --params '{\"topic\": \"post-quantum TLS\"}')"
        )
    topic = topic.strip()
    if os.environ.get("LEVI_BOT_OFFLINE", "").strip().lower() in {"1", "true", "yes"}:
        return ServiceResult(
            ok=False,
            report=(
                "RESEARCH BRIEF: refused — offline mode is on "
                "(LEVI_BOT_OFFLINE=1), and I won't invent research. Unset it "
                "or run with the agent runtime available."
            ),
        )
    try:
        from levi.agent.loop import run_subtask
    except Exception:
        return ServiceResult(
            ok=False,
            report="RESEARCH BRIEF: agent runtime unavailable",
            notes=[_unavailable("levi.agent.loop")],
        )
    provider = os.environ.get("LEVI_BOT_PROVIDER") or os.environ.get("LEVI_PROVIDER")
    prompt = (
        "Write a concise research brief on: %s\n\n"
        "Structure: 1) TL;DR (3 bullets) 2) Key facts 3) What LEVI should "
        "do about it (concrete, local-first) 4) Open questions. "
        "Defensive framing only. Do not invent citations or statistics; "
        "mark anything uncertain as uncertain." % topic
    )
    try:
        transcript = run_subtask(
            prompt, provider=provider or "local", max_steps=8
        )
    except Exception as exc:
        return ServiceResult(
            ok=False,
            report="RESEARCH BRIEF failed: %s: %s" % (type(exc).__name__, exc),
        )
    body = (getattr(transcript, "final", "") or "").strip()
    if not body:
        return ServiceResult(
            ok=False, report="RESEARCH BRIEF: runtime returned an empty brief"
        )
    out_dir = _services_out_dir()
    os.makedirs(out_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:40] or "brief"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(out_dir, "research-brief-%s-%s.md" % (stamp, slug))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Research brief: %s\n\n" % topic)
        fh.write("_Generated %s (LEVI bot, provider=%s)_\n\n"
                 % (datetime.now(timezone.utc).isoformat(), provider or "local"))
        fh.write(body + "\n")
    summary = body.split("\n\n")[0][:280]
    return ServiceResult(
        ok=True,
        report="RESEARCH BRIEF on '%s':\n\n%s\n\nFull brief saved to %s"
        % (topic, summary, path),
        files=[path],
    )


def _handle_custom(params: Dict[str, Any]) -> ServiceResult:
    """User-defined services carry their own handler note; no default action."""
    return ServiceResult(
        ok=False,
        report=(
            "Custom service '%s' has no built-in handler. Attach one via "
            "the services API (see docs/BOT.md) or convert it to a "
            "briefing/monitor/research type."
        )
        % params.get("name", "?"),
        notes=["custom services need a handler registered in code"],
    )


# Handler dispatch table. Tests may monkeypatch entries with stubs.
_HANDLERS: Dict[str, Callable[[Dict[str, Any]], ServiceResult]] = {}


def _handlers() -> Dict[str, Callable[[Dict[str, Any]], ServiceResult]]:
    if not _HANDLERS:
        _HANDLERS.update(
            {
                "morning-briefing": _handle_morning_briefing,
                "bounty-watch": _handle_bounty_watch,
                "backup-status": _handle_backup_status,
                "research-brief": _handle_research_brief,
            }
        )
    return _HANDLERS


def get_handler(name: str) -> Callable[[Dict[str, Any]], ServiceResult]:
    """Return the handler for a service name (custom → default stub)."""
    return _handlers().get(name, _handle_custom)


def get_handler_for(definition: "ServiceDefinition") -> Callable[[Dict[str, Any]], ServiceResult]:
    """Return the handler for a service *definition*.

    Built-in names keep their dedicated handler; user-added services fall
    back by type (``research`` → the research-brief handler, which still
    requires ``params.topic``); anything else gets the honest custom stub.
    """
    handlers = _handlers()
    if definition.name in handlers:
        return handlers[definition.name]
    if definition.service_type == "research":
        return _handle_research_brief
    return _handle_custom
