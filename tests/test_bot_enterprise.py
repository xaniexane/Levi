"""Enterprise hardening tests for the LEVI bot (``core/levi/bot/``).

Wave E1. These tests lock in the enterprise contract:

1. Honest capability reporting — unavailable backends produce clean
   failure reports, never fake success.
2. Clean failures — every exception path yields a structured error plus a
   receipt entry; never a traceback to the user, never a swallowed error.
3. Receipts — every consequential act (service run, rejected dispatch,
   HITL decision) lands in ``runs.jsonl`` / ``hitl.jsonl`` carrying the
   planned / approved / executed / verified rail fields.
4. HITL fail-closed — dead responders, empty answers, and unknown
   decision strings all resolve to ``denied``, and the denial is receipted.
5. Intent routing — every chat route is exercised; action-looking
   utterances with no capability get a clean "I can't do that".

Hermetic: no network, no user HOME writes. ``LEVI_BOT_HOME`` points at a
tmp dir, ``LEVI_BOT_OFFLINE=1`` forces the deterministic fallback, and
``LEVI_GROWTH_DIR`` points at a tmp dir.
"""

import json
import os
import sys

import pytest

from levi.bot import automation, chat, hitl
from levi.bot import services as services_mod
from levi.bot.services import (
    ServiceDefinition,
    ServiceError,
    ServiceRegistry,
    ServiceResult,
    get_handler_for,
)
from levi.automation.hitl import GateKind, GateRequest


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


def _stub_handler(report="ENTERPRISE STUB"):
    def _handler(params):
        assert isinstance(params, dict)
        return ServiceResult(ok=True, report=report)

    return _handler


def _runs():
    return automation.read_run_log(limit=100)


def _block_modules(monkeypatch, *names):
    """Force ImportError for the named modules (simulates missing backends)."""
    for name in names:
        monkeypatch.setitem(sys.modules, name, None)


def _gate_request(kind=GateKind.APPROVAL):
    return GateRequest(
        minion_id="test-minion-99",
        kind=kind,
        prompt="run the demo plan",
    )


# ---------------------------------------------------------------------------
# Receipts: planned / approved / executed / verified on every path
# ---------------------------------------------------------------------------


def test_receipt_carries_rail_fields_on_success(hermetic_env, monkeypatch):
    monkeypatch.setitem(services_mod._HANDLERS, "morning-briefing", _stub_handler())
    record = automation.run_service("morning-briefing")
    assert record.ok is True
    rec = _runs()[-1]
    for field in ("planned", "approved", "executed", "verified"):
        assert rec[field], "receipt missing rail field: %s" % field
    assert "morning-briefing" in rec["planned"]
    assert "on-demand" in rec["approved"]
    assert "completed" in rec["executed"]


def test_rejected_unknown_service_is_receipted(hermetic_env):
    with pytest.raises(ServiceError):
        automation.run_service("no-such-service")
    rec = _runs()[-1]
    assert rec["service"] == "no-such-service"
    assert rec["ok"] is False
    assert "unknown service" in rec["summary"]
    assert rec["planned"]  # what was attempted
    assert rec["approved"]  # on what authority
    assert "rejected before handler dispatch" in rec["executed"]
    assert rec["verified"]


def test_rejected_invalid_name_is_receipted(hermetic_env):
    with pytest.raises(ServiceError):
        automation.run_service("Bad Name!")
    rec = _runs()[-1]
    assert rec["ok"] is False
    assert "rejected" in rec["summary"]


def test_rejected_bad_params_override_is_receipted(hermetic_env):
    with pytest.raises(ServiceError):
        automation.run_service("morning-briefing", params_override=["not", "a", "dict"])
    rec = _runs()[-1]
    assert rec["ok"] is False
    assert "params_override" in rec["summary"]


def test_disabled_service_is_rejected_with_hint_and_receipt(hermetic_env, monkeypatch):
    reg = ServiceRegistry()
    reg.set_enabled("bounty-watch", False)
    try:
        with pytest.raises(ServiceError, match="disabled"):
            automation.run_service("bounty-watch")
    finally:
        reg.set_enabled("bounty-watch", True)
    rec = _runs()[-1]
    assert rec["ok"] is False
    assert "disabled" in rec["summary"]
    assert "service enable" in rec["summary"]  # the recovery hint


def test_scheduled_flag_records_cron_authority(hermetic_env, monkeypatch):
    monkeypatch.setitem(services_mod._HANDLERS, "backup-status", _stub_handler())
    automation.run_service("backup-status", scheduled=True)
    rec = _runs()[-1]
    assert "cron" in rec["approved"]


def test_handler_crash_receipt_names_handler(hermetic_env, monkeypatch):
    def _boom(params):
        raise RuntimeError("kaput")

    monkeypatch.setitem(services_mod._HANDLERS, "bounty-watch", _boom)
    record = automation.run_service("bounty-watch")
    assert record.ok is False
    rec = _runs()[-1]
    assert "crashed" in rec["summary"]
    assert "kaput" in rec["summary"]
    assert "_boom" in rec["executed"]
    assert rec["verified"]  # never claims an unknown outcome


# ---------------------------------------------------------------------------
# Honest capability reporting in built-in handlers
# ---------------------------------------------------------------------------


def test_morning_briefing_fails_honestly_when_all_sources_down(
    hermetic_env, monkeypatch, tmp_path
):
    """No section produced a report → ok=False, never fake success."""
    _block_modules(
        monkeypatch,
        "levi.knowledge.news.refresh",
        "levi.growth.cycle",
        "levi.academy.run_session",
    )
    # The demand section reads the real ~/.levi/demand_pulse.json; point
    # expanduser("~") at the empty tmp dir so it is "unavailable" too.
    real_expanduser = os.path.expanduser
    monkeypatch.setattr(
        os.path,
        "expanduser",
        lambda p: str(tmp_path) if p == "~" else real_expanduser(p),
    )
    record = automation.run_service("morning-briefing")
    assert record.ok is False
    assert "No briefing available" in record.report
    assert "won't invent" in record.report
    # The receipt still records *why*.
    assert "unavailable" in record.report


def test_morning_briefing_partial_sources_still_ok(hermetic_env, monkeypatch):
    """Some sections down → ok=True with honest notes, not silent gaps."""
    _block_modules(monkeypatch, "levi.knowledge.news.refresh")
    record = automation.run_service("morning-briefing")
    assert record.ok is True
    assert "Notes:" in record.report
    assert "news:" in record.report


def test_backup_verify_failure_is_advisory_not_crash(hermetic_env, monkeypatch):
    import levi.backup.snapshot as snap_mod

    def _boom_verify(snap_id):
        raise RuntimeError("checksum backend offline")

    monkeypatch.setattr(snap_mod, "verify_snapshot", _boom_verify)
    record = automation.run_service("backup-status", params_override={"verify": True})
    assert record.ok is True  # status itself was fine
    assert "could not verify" in record.report
    assert "checksum backend offline" in record.report


def test_research_brief_refuses_offline_instead_of_inventing(hermetic_env):
    record = automation.run_service(
        "research-brief", params_override={"topic": "post-quantum TLS"}
    )
    assert record.ok is False
    assert "refused" in record.report
    assert "won't invent research" in record.report


# ---------------------------------------------------------------------------
# Registry: enable/disable completes the old "not supported yet" stub
# ---------------------------------------------------------------------------


def test_set_enabled_round_trip_and_persists(hermetic_env):
    reg = ServiceRegistry()
    reg.set_enabled("morning-briefing", False)
    assert ServiceRegistry().get("morning-briefing").enabled is False
    reg.set_enabled("morning-briefing", True)
    assert ServiceRegistry().get("morning-briefing").enabled is True


def test_set_enabled_unknown_name_raises(hermetic_env):
    with pytest.raises(ServiceError, match="unknown service"):
        ServiceRegistry().set_enabled("ghost-service", False)


def test_remove_builtin_points_at_disable(hermetic_env):
    with pytest.raises(ServiceError, match="service disable"):
        ServiceRegistry().remove("morning-briefing")


# ---------------------------------------------------------------------------
# HITL: fail-closed resolution + receipted decisions
# ---------------------------------------------------------------------------


def test_resolve_gate_approved_is_receipted(hermetic_env):
    req = _gate_request()
    answer = hitl.resolve_gate(req, lambda r: {"decision": "approved"})
    assert answer["decision"] == "approved"
    entries = hitl.read_gate_log()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["minion_id"] == "test-minion-99"
    assert entry["kind"] == "approval"
    assert entry["planned"] == "run the demo plan"
    assert entry["approved"] == "approved"
    assert "records the human's decision" in entry["executed"]
    assert "fail-closed" in entry["verified"]


def test_resolve_gate_responder_raises_means_denied(hermetic_env):
    req = _gate_request()

    def _dead(responder_request):
        raise RuntimeError("chat link down")

    answer = hitl.resolve_gate(req, _dead)
    assert answer["decision"] == "denied"
    assert "responder failed" in answer["note"]
    entry = hitl.read_gate_log()[-1]
    assert entry["approved"] == "denied"
    assert "responder failed" in entry["note"]


def test_resolve_gate_empty_answer_means_denied(hermetic_env):
    req = _gate_request()
    assert hitl.resolve_gate(req, lambda r: {})["decision"] == "denied"
    assert hitl.resolve_gate(req, lambda r: None)["decision"] == "denied"
    assert hitl.read_gate_log()[-1]["approved"] == "denied"


def test_resolve_gate_unknown_decision_coerced_to_denied(hermetic_env):
    req = _gate_request()
    answer = hitl.resolve_gate(req, lambda r: {"decision": "maybe-later"})
    assert answer["decision"] == "denied"
    assert "coerced to denied" in answer["note"]
    assert hitl.read_gate_log()[-1]["approved"] == "denied"


def test_resolve_gate_non_dict_answer_denied(hermetic_env):
    req = _gate_request()
    answer = hitl.resolve_gate(req, lambda r: "yes definitely")
    assert answer["decision"] == "denied"


def test_resolve_gate_notification_is_noted_not_blocking(hermetic_env):
    req = _gate_request(GateKind.NOTIFICATION)
    answer = hitl.resolve_gate(req, lambda r: {"decision": "denied"})
    assert answer["decision"] == "noted"
    assert hitl.read_gate_log()[-1]["approved"] == "noted"


def test_resolve_gate_denial_is_receipted(hermetic_env):
    req = _gate_request(GateKind.CONFIRM)
    hitl.resolve_gate(req, lambda r: hitl.chat_responder(r, "no, absolutely not"))
    entry = hitl.read_gate_log()[-1]
    assert entry["approved"] == "denied"
    assert entry["kind"] == "confirm"


def test_resolve_gate_edit_approve_carries_edits(hermetic_env):
    req = _gate_request(GateKind.EDIT_APPROVE)
    answer = hitl.resolve_gate(
        req, lambda r: hitl.chat_responder(r, "use the staging scope, approve")
    )
    assert answer["decision"] == "edited"
    assert answer["edited_payload"] == {"human_edits": "use the staging scope"}
    assert hitl.read_gate_log()[-1]["approved"] == "edited"


def test_read_gate_log_tolerates_corruption(hermetic_env):
    req = _gate_request()
    hitl.resolve_gate(req, lambda r: {"decision": "approved"})
    path = os.path.join(str(hermetic_env), "bothome", "bot", "hitl.jsonl")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("{ not json\n")
        fh.write("\n")
    entries = hitl.read_gate_log()
    assert len(entries) == 1
    assert entries[0]["approved"] == "approved"


def test_present_gate_covers_all_kinds():
    for kind in GateKind:
        text = hitl.present_gate(_gate_request(kind))
        assert "test-minion-99" in text
        assert "run the demo plan" in text


def test_parse_reply_edge_cases():
    req = _gate_request(GateKind.ACKNOWLEDGE)
    assert hitl.parse_reply("ack, seen it", req)["decision"] == "acknowledged"
    assert hitl.parse_reply("whatever", req) is None
    assert hitl.parse_reply("", req) is None
    # chat_responder never presumes consent.
    assert hitl.chat_responder(req, "")["decision"] == "denied"


# ---------------------------------------------------------------------------
# Chat intent routing: every route + the honest "I can't do that"
# ---------------------------------------------------------------------------


def test_route_run_morning_briefing(hermetic_env, monkeypatch):
    monkeypatch.setitem(
        services_mod._HANDLERS, "morning-briefing", _stub_handler("BRIEF OK")
    )
    reply = chat.say("run my morning briefing")
    assert "BRIEF OK" in reply


def test_route_run_bounty_watch(hermetic_env, monkeypatch):
    monkeypatch.setitem(
        services_mod._HANDLERS, "bounty-watch", _stub_handler("BOUNTY OK")
    )
    reply = chat.say("check the bounty watch")
    assert "BOUNTY OK" in reply


def test_route_run_backup_status(hermetic_env, monkeypatch):
    monkeypatch.setitem(
        services_mod._HANDLERS, "backup-status", _stub_handler("BACKUP OK")
    )
    reply = chat.say("check backup status")
    assert "BACKUP OK" in reply


def test_route_run_backup_status_plural(hermetic_env, monkeypatch):
    monkeypatch.setitem(
        services_mod._HANDLERS, "backup-status", _stub_handler("BACKUP OK")
    )
    assert "BACKUP OK" in chat.say("check my backups")


def test_route_research_with_topic(hermetic_env, monkeypatch):
    seen = {}

    def _research(params):
        seen.update(params)
        return ServiceResult(ok=True, report="BRIEF DONE")

    monkeypatch.setitem(services_mod._HANDLERS, "research-brief", _research)
    reply = chat.say("research post-quantum TLS")
    assert "BRIEF DONE" in reply
    assert seen["topic"] == "post-quantum TLS"


def test_route_list_services_shows_state(hermetic_env):
    reply = chat.say("list services")
    assert "morning-briefing" in reply
    assert "bounty-watch" in reply
    assert "backup-status" in reply
    assert "research-brief" in reply


def test_route_list_services_survives_registry_failure(hermetic_env, monkeypatch):
    class _Boom:
        def __init__(self, *a, **k):
            raise OSError("disk gone")

    monkeypatch.setattr(services_mod, "ServiceRegistry", _Boom)
    reply = chat.say("list services")
    assert "Couldn't list services" in reply
    assert "disk gone" in reply


def test_route_service_log(hermetic_env, monkeypatch):
    assert "empty" in chat.say("show me the service log").lower()
    monkeypatch.setitem(
        services_mod._HANDLERS, "backup-status", _stub_handler("BKUP OK")
    )
    chat.say("check backup status")
    assert "backup-status" in chat.say("service log")


def test_route_schedule_setup(hermetic_env):
    reply = chat.say("set up a daily bounty watch")
    assert "bounty-watch-daily" in reply
    assert "0 7 * * *" in reply
    assert ServiceRegistry().get("bounty-watch-daily").schedule == "0 7 * * *"


def test_route_schedule_setup_failure_is_clean_and_receipted(hermetic_env, monkeypatch):
    real_registry = services_mod.ServiceRegistry

    class _NoBuiltins(real_registry):
        def get(self, name):
            return None  # built-in lookup misses -> clean ServiceError

    monkeypatch.setattr(services_mod, "ServiceRegistry", _NoBuiltins)
    reply = chat.say("set up a daily bounty watch")
    assert "Couldn't set that up" in reply
    assert "Traceback" not in reply
    rec = _runs()[-1]
    assert rec["service"] == "scheduler-setup"
    assert rec["ok"] is False


@pytest.mark.parametrize(
    "utterance",
    [
        "send an email to Dave about the meeting",
        "write an email to support",
        "text me when it's done",
        "make a phone call to the office",
        "call my mom",
        "delete all my backups",
        "remove the snapshot files",
        "buy a pizza",
        "order a new keyboard",
        "book a flight to Chicago",
        "remind me to water the plants",
        "set an alarm for 7am",
        "schedule a meeting with Dave tomorrow",
    ],
)
def test_unsupported_action_gets_clean_refusal(hermetic_env, utterance):
    reply = chat.say(utterance)
    assert "I can't do that" in reply
    assert "Traceback" not in reply
    # The refusal must not claim a capability it lacks.
    assert "no way to" in reply


def test_naming_turn_is_not_a_phone_call_refusal(hermetic_env):
    """'call me X' is a naming/learning turn, not a call request."""
    reply = chat.say("call me Chauncey")
    assert "I can't do that" not in reply


def test_pure_chat_still_falls_through(hermetic_env):
    reply = chat.say("tell me something interesting")
    assert "offline mode" in reply
    assert "I can't do that" not in reply


# ---------------------------------------------------------------------------
# CLI: enable/disable commands and the no-traceback guarantee
# ---------------------------------------------------------------------------


def _cli_main(monkeypatch, tmp_path, *argv):
    from levi.bot.__main__ import main

    monkeypatch.setenv("LEVI_BOT_HOME", str(tmp_path))
    monkeypatch.setenv("LEVI_BOT_OFFLINE", "1")
    return main(list(argv))


def test_cli_disable_then_run_refuses(hermetic_env, monkeypatch, tmp_path, capsys):
    assert _cli_main(monkeypatch, tmp_path, "service", "disable", "bounty-watch") == 0
    assert "disabled" in capsys.readouterr().out
    code = _cli_main(monkeypatch, tmp_path, "service", "run", "bounty-watch")
    assert code == 1
    err = capsys.readouterr().err
    assert "disabled" in err
    assert "service enable" in err  # recovery hint
    assert "Traceback" not in err
    # Re-arm for other tests sharing nothing (hermetic dir is per-test anyway).
    assert _cli_main(monkeypatch, tmp_path, "service", "enable", "bounty-watch") == 0
    assert ServiceRegistry().get("bounty-watch").enabled is True


def test_cli_enable_unknown_service_is_clean(
    hermetic_env, monkeypatch, tmp_path, capsys
):
    code = _cli_main(monkeypatch, tmp_path, "service", "enable", "ghost-service")
    assert code == 1
    err = capsys.readouterr().err
    assert "unknown service" in err
    assert "Traceback" not in err


def test_cli_never_shows_traceback_on_unexpected_error(
    hermetic_env, monkeypatch, tmp_path, capsys
):
    """main() converts any unexpected failure into a one-line stderr error."""
    import levi.bot.__main__ as cli_mod

    def _boom(_args):
        raise RuntimeError("something deeply weird")

    real_build_parser = cli_mod.build_parser

    def _broken_parser():
        parser = real_build_parser()

        class _NS:
            func = staticmethod(_boom)

        parser.parse_args = lambda argv=None: _NS()
        return parser

    monkeypatch.setattr(cli_mod, "build_parser", _broken_parser)
    code = cli_mod.main(["say", "hello"])
    assert code == 1
    err = capsys.readouterr().err
    assert "internal error" in err
    assert "something deeply weird" in err
    assert "Traceback" not in err
