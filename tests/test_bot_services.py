"""Hermetic tests for bot services, automation, context, and intent routing.

Hermetic: no network, no user HOME writes. ``LEVI_BOT_HOME`` points at a
tmp dir, ``LEVI_BOT_OFFLINE=1`` forces the deterministic fallback, and
``LEVI_GROWTH_DIR`` points at a tmp dir so the learning write-back never
touches the real growth journal. Handlers that would reach into real LEVI
modules are monkeypatched with stubs.
"""

import json
import os

import pytest

from levi.bot import automation, chat, context
from levi.bot.services import (
    ServiceDefinition,
    ServiceError,
    ServiceRegistry,
    ServiceResult,
    get_handler_for,
    normalize_schedule,
)


@pytest.fixture()
def hermetic_env(tmp_path, monkeypatch):
    """Isolate bot state, growth journal, and force offline mode."""
    bot_home = tmp_path / "bothome"
    growth_dir = tmp_path / "growth"
    monkeypatch.setenv("LEVI_BOT_HOME", str(bot_home))
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(growth_dir))
    monkeypatch.setenv("LEVI_BOT_OFFLINE", "1")
    monkeypatch.delenv("LEVI_BOT_PROVIDER", raising=False)
    monkeypatch.delenv("LEVI_PROVIDER", raising=False)
    return tmp_path


def _stub_handler(report="STUB REPORT"):
    def _handler(params):
        assert isinstance(params, dict)
        return ServiceResult(ok=True, report=report, files=["/tmp/x.md"])

    return _handler


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_seeds_builtins(hermetic_env):
    reg = ServiceRegistry()
    names = {s.name for s in reg.list()}
    assert {"morning-briefing", "bounty-watch", "backup-status", "research-brief"} <= names


def test_registry_add_remove_round_trip(hermetic_env):
    reg = ServiceRegistry()
    svc = ServiceDefinition(
        name="my-watch",
        description="a test watch",
        service_type="monitor",
        schedule="daily",
        params={"live": False},
    )
    reg.add(svc)
    assert reg.get("my-watch").description == "a test watch"
    # Survives a reload from disk.
    reg2 = ServiceRegistry()
    assert reg2.get("my-watch").schedule == "0 7 * * *"
    assert reg2.remove("my-watch") is True
    assert ServiceRegistry().get("my-watch") is None


def test_registry_rejects_invalid_definitions(hermetic_env):
    with pytest.raises(ServiceError):
        ServiceDefinition(name="Bad Name!", description="d", service_type="monitor",
                          schedule="daily")
    with pytest.raises(ServiceError):
        ServiceDefinition(name="ok-name", description="d", service_type="nope",
                          schedule="daily")
    with pytest.raises(ServiceError):
        ServiceDefinition(name="ok-name", description="d", service_type="monitor",
                          schedule="every now and then")
    with pytest.raises(ServiceError):
        ServiceDefinition(name="ok-name", description="d", service_type="monitor",
                          schedule="99 99 99 99 99")
    with pytest.raises(ServiceError):
        ServiceDefinition(name="ok-name", description="d", service_type="monitor",
                          schedule="daily", params=["not", "a", "dict"])
    with pytest.raises(ServiceError):
        ServiceDefinition(name="ok-name", description=" ", service_type="monitor",
                          schedule="daily")


def test_registry_refuses_builtin_removal(hermetic_env):
    reg = ServiceRegistry()
    with pytest.raises(ServiceError):
        reg.remove("morning-briefing")
    assert reg.get("morning-briefing") is not None


def test_registry_quarantines_corrupt_file(hermetic_env):
    reg = ServiceRegistry()
    with open(reg.path, "w", encoding="utf-8") as fh:
        fh.write("{ not json")
    reg2 = ServiceRegistry()
    assert reg2.get("morning-briefing") is not None  # builtins re-seeded


def test_schedule_keywords_normalize():
    assert normalize_schedule("daily") == "0 7 * * *"
    assert normalize_schedule("@hourly") == "0 * * * *"
    assert normalize_schedule("*/15 9 * * 1-5") == "*/15 9 * * 1-5"


# ---------------------------------------------------------------------------
# Automation runner
# ---------------------------------------------------------------------------


def test_run_service_with_stubbed_handler(hermetic_env, monkeypatch):
    from levi.bot import services

    monkeypatch.setitem(services._HANDLERS, "morning-briefing", _stub_handler())
    record = automation.run_service("morning-briefing")
    assert record.ok is True
    assert "STUB REPORT" in record.report
    assert record.files == ["/tmp/x.md"]
    runs = automation.read_run_log()
    assert len(runs) == 1
    assert runs[0]["service"] == "morning-briefing"
    assert runs[0]["ok"] is True


def test_run_service_unknown_raises(hermetic_env):
    with pytest.raises(ServiceError):
        automation.run_service("does-not-exist")


def test_run_service_handler_crash_is_logged_not_raised(hermetic_env, monkeypatch):
    from levi.bot import services

    def _boom(params):
        raise RuntimeError("kaput")

    monkeypatch.setitem(services._HANDLERS, "bounty-watch", _boom)
    record = automation.run_service("bounty-watch")
    assert record.ok is False
    assert "kaput" in record.summary
    assert automation.read_run_log()[-1]["ok"] is False


def test_run_service_params_override(hermetic_env, monkeypatch):
    from levi.bot import services

    seen = {}

    def _capture(params):
        seen.update(params)
        return ServiceResult(ok=True, report="ok")

    monkeypatch.setitem(services._HANDLERS, "bounty-watch", _capture)
    automation.run_service("bounty-watch", params_override={"live": True})
    assert seen["live"] is True


def test_narrate_marks_on_demand_and_scheduled():
    rec = automation.RunRecord(service="x", ok=True, summary="s", report="R")
    text = automation.narrate(rec)
    assert "R" in text and "cron" in text  # scheduler-absent path is honest
    sched = automation.narrate(rec, scheduled=True)
    assert "on schedule" in sched


def test_get_handler_for_research_type_fallback(hermetic_env):
    svc = ServiceDefinition(
        name="deep-dive", description="d", service_type="research", schedule="weekly"
    )
    assert get_handler_for(svc) is not _stub_handler  # the real research handler
    custom = ServiceDefinition(
        name="whatever", description="d", service_type="custom", schedule="daily"
    )
    result = get_handler_for(custom)({})
    assert result.ok is False  # honest stub, no invented action


# ---------------------------------------------------------------------------
# Chat intent routing
# ---------------------------------------------------------------------------


def test_intent_run_morning_briefing(hermetic_env, monkeypatch):
    from levi.bot import services

    monkeypatch.setitem(services._HANDLERS, "morning-briefing", _stub_handler())
    reply = chat.say("run my morning briefing")
    assert "STUB REPORT" in reply


def test_intent_list_services(hermetic_env):
    reply = chat.say("list services")
    assert "morning-briefing" in reply and "bounty-watch" in reply


def test_intent_service_log_empty_then_filled(hermetic_env, monkeypatch):
    from levi.bot import services

    assert "empty" in chat.say("show me the service log").lower()
    monkeypatch.setitem(services._HANDLERS, "backup-status", _stub_handler("BKUP OK"))
    chat.say("check backup status")
    log_reply = chat.say("service log")
    assert "backup-status" in log_reply


def test_intent_research_routes_with_topic(hermetic_env, monkeypatch):
    from levi.bot import services

    seen = {}

    def _research(params):
        seen.update(params)
        return ServiceResult(ok=True, report="BRIEF DONE")

    monkeypatch.setitem(services._HANDLERS, "research-brief", _research)
    reply = chat.say("research post-quantum TLS")
    assert "BRIEF DONE" in reply
    assert seen.get("topic") == "post-quantum TLS"


def test_intent_schedule_setup_adds_service(hermetic_env):
    reply = chat.say("set up a daily bounty watch")
    assert "bounty-watch-daily" in reply
    assert "0 7 * * *" in reply  # the cron line, since the bot has no scheduler
    reg = ServiceRegistry()
    assert reg.get("bounty-watch-daily").schedule == "0 7 * * *"


def test_pure_chat_still_works(hermetic_env):
    reply = chat.say("tell me something interesting")
    assert "offline mode" in reply  # deterministic fallback, no intent matched


# ---------------------------------------------------------------------------
# Context loading (read-only on MemoryStore)
# ---------------------------------------------------------------------------


class _FakeEntry:
    def __init__(self, eid, mtype, content, importance=0.9):
        self.id = eid
        self.memory_type = mtype
        self.content = content
        self.importance = importance


class _FakeType:
    def __init__(self, value):
        self.value = value


class _FakeStore:
    def __init__(self, entries):
        self._entries = entries

    def list(self, memory_type=None, limit=50, **kwargs):
        items = list(self._entries)
        if memory_type is not None:
            items = [e for e in items if e.memory_type.value == memory_type.value]
        return items[:limit]


def _patch_store(monkeypatch, entries):
    import levi.memory.store as store_mod

    monkeypatch.setattr(store_mod, "MemoryStore", lambda *a, **k: _FakeStore(entries))


def test_load_user_context_empty_store(hermetic_env, monkeypatch):
    _patch_store(monkeypatch, [])
    assert context.load_user_context() == ""


def test_load_user_context_renders_preferences(hermetic_env, monkeypatch):
    _patch_store(
        monkeypatch,
        [
            _FakeEntry("1", _FakeType("preference"), "likes dark mode"),
            _FakeEntry("2", _FakeType("fact"), "timezone is America/Chicago"),
        ],
    )
    block = context.load_user_context()
    assert "likes dark mode" in block
    assert "America/Chicago" in block
    assert "correct me if I'm wrong" in block


def test_load_user_context_unavailable_store(hermetic_env, monkeypatch):
    import levi.memory.store as store_mod

    def _boom(*a, **k):
        raise RuntimeError("nope")

    monkeypatch.setattr(store_mod, "MemoryStore", _boom)
    assert context.load_user_context() == ""  # fail-soft, never raises


def test_build_system_prompt_has_assistant_core(hermetic_env, monkeypatch):
    _patch_store(monkeypatch, [])
    prompt = context.build_system_prompt()
    assert "Assistant core" in prompt
    assert "spark" in prompt.lower()
    # No provider branding leaks into the prompt.
    for brand in ("xai", "openai", "anthropic"):
        assert brand not in prompt.lower()


def test_build_system_prompt_includes_context(hermetic_env, monkeypatch):
    _patch_store(monkeypatch, [_FakeEntry("1", _FakeType("preference"), "likes dark mode")])
    assert "likes dark mode" in context.build_system_prompt()


# ---------------------------------------------------------------------------
# Learning write-back (heuristic candidates → pending queue)
# ---------------------------------------------------------------------------


def test_extract_candidates():
    cands = context.extract_candidates("remember that my editor is neovim")
    assert any(c["kind"] == "fact" and "neovim" in c["text"] for c in cands)
    cands = context.extract_candidates("I prefer dark mode everywhere")
    assert any(c["kind"] == "preference" and "dark mode" in c["text"] for c in cands)
    cands = context.extract_candidates("call me Chauncey")
    assert any(c["kind"] == "preference" and "Chauncey" in c["text"] for c in cands)
    assert context.extract_candidates("hello there") == []
    assert context.extract_candidates("") == []
    # Every candidate is labeled heuristic — no fake-NLP claims.
    for c in context.extract_candidates("remember that x is y and I prefer z"):
        assert c["confidence"] == "heuristic"


def test_queue_learnings_writes_documented_format(hermetic_env):
    n = context.queue_learnings(
        [{"kind": "preference", "text": "likes dark mode",
          "confidence": "heuristic", "source": "levi-bot"}]
    )
    assert n == 1
    pending = context.read_pending()
    assert len(pending) == 1
    rec = pending[0]
    assert rec["kind"] == "preference"
    assert rec["text"] == "likes dark mode"
    assert rec["status"] == "pending"
    assert rec["confidence"] == "heuristic"
    assert "ts" in rec


def test_queue_learnings_flags_growth_journal(hermetic_env):
    context.queue_learnings(
        [{"kind": "fact", "text": "x is y", "confidence": "heuristic",
          "source": "levi-bot"}]
    )
    journal = os.path.join(os.environ["LEVI_GROWTH_DIR"], "journal.jsonl")
    assert os.path.exists(journal)
    with open(journal, encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh if line.strip()]
    assert any(r.get("kind") == "bot-learnings" for r in records)


def test_say_queues_learnings_best_effort(hermetic_env):
    chat.say("remember that I prefer dark mode")
    assert context.pending_count() >= 1


def test_maybe_learn_never_raises(hermetic_env, monkeypatch):
    monkeypatch.setattr(context, "queue_learnings",
                        lambda cands: (_ for _ in ()).throw(OSError("disk")))
    assert context.maybe_learn("remember that x is y") == 0
