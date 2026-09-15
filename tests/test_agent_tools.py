"""Hermetic tests for levi.agent.tools (the Tool-execution registry).

No network, no user HOME writes: HOME is monkeypatched to a tmp dir and
the network-dependent tools are tested with LEVI_OFFLINE=1 plus a
monkeypatched urlopen that fails loudly if any call slips through.
"""

import pytest

from levi.agent.tools import (
    ConfirmationRequired,
    ExecContext,
    Tool,
    ToolResult,
    build_default_registry,
)


def _reg(tmp_path, **kwargs):
    kwargs.setdefault("workspace_root", tmp_path / "ws")
    kwargs.setdefault("memory_dir", tmp_path / "mem")
    kwargs.setdefault("skills_dir", tmp_path / "skills")
    return build_default_registry(**kwargs)


# -- registry basics --------------------------------------------------------


def test_register_get_list(tmp_path):
    reg = _reg(tmp_path)
    tool = Tool(
        name="t", description="d", parameters={}, handler=lambda a: ToolResult(ok=True)
    )
    reg.register(tool)
    assert reg.get("t") is tool
    assert reg.get("missing") is None
    names = [t.name for t in reg.list()]
    assert "t" in names and "shell_exec" in names


def test_register_requires_name(tmp_path):
    reg = _reg(tmp_path)
    with pytest.raises(ValueError):
        reg.register(
            Tool(
                name="",
                description="d",
                parameters={},
                handler=lambda a: ToolResult(ok=True),
            )
        )


def test_execute_unknown_tool_never_raises(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute("nope_not_a_tool", {}, ExecContext())
    assert isinstance(res, ToolResult)
    assert res.ok is False
    assert "unknown tool" in res.error


def test_execute_basic_ok(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute("memory_write", {"name": "note", "content": "hi"}, ExecContext())
    assert res.ok is True
    res2 = reg.execute("memory_read", {"name": "note"}, ExecContext())
    assert res2.ok is True and res2.output == "hi"


def test_handler_exception_becomes_ok_false(tmp_path):
    reg = _reg(tmp_path)

    def boom(args):
        raise RuntimeError("kablam")

    reg.register(Tool(name="boom", description="d", parameters={}, handler=boom))
    res = reg.execute("boom", {}, ExecContext())
    assert res.ok is False and "kablam" in res.error


# -- confirmation gate ------------------------------------------------------


def test_gate_blocks_without_consent(tmp_path):
    reg = _reg(tmp_path)
    with pytest.raises(ConfirmationRequired):
        reg.execute("shell_exec", {"cmd": "echo hi"}, ExecContext())


def test_gate_passes_with_consent(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute("shell_exec", {"cmd": "echo hi"}, ExecContext(consent=True))
    assert res.ok is True and "hi" in res.output


def test_gate_confirm_callback_approve(tmp_path):
    reg = _reg(tmp_path)
    seen = []

    def confirm(preview):
        seen.append(preview)
        return True

    res = reg.execute("shell_exec", {"cmd": "echo hi"}, ExecContext(confirm=confirm))
    assert res.ok is True
    assert seen and "shell_exec" in seen[0]


def test_gate_confirm_callback_decline_raises(tmp_path):
    reg = _reg(tmp_path)
    with pytest.raises(ConfirmationRequired):
        reg.execute(
            "shell_exec", {"cmd": "echo hi"}, ExecContext(confirm=lambda p: False)
        )


def test_default_consent_from_builder(tmp_path):
    reg = _reg(tmp_path, consent=True)
    # execute with ctx=None falls back to builder defaults
    res = reg.execute("shell_exec", {"cmd": "echo hi"})
    assert res.ok is True


# -- sandboxing -------------------------------------------------------------


def test_file_write_absolute_refused(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute(
        "file_write",
        {"path": "/etc/evil.txt", "content": "x"},
        ExecContext(consent=True),
    )
    assert res.ok is False and "absolute" in res.error.lower()


def test_file_write_dotdot_escape_refused(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute(
        "file_write",
        {"path": "../../escape.txt", "content": "x"},
        ExecContext(consent=True),
    )
    assert res.ok is False and "escape" in res.error.lower()


def test_shell_cwd_escape_refused(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute(
        "shell_exec", {"cmd": "echo hi", "cwd": "../../.."}, ExecContext(consent=True)
    )
    assert res.ok is False and "escape" in res.error.lower()


def test_file_write_and_read_round_trip(tmp_path):
    reg = _reg(tmp_path)
    ctx = ExecContext(consent=True)
    w = reg.execute("file_write", {"path": "sub/note.txt", "content": "hello"}, ctx)
    assert w.ok is True
    r = reg.execute("file_read", {"path": "sub/note.txt"}, ctx)
    assert r.ok is True and r.output == "hello"
    # the file really landed inside the workspace root
    assert (tmp_path / "ws" / "sub" / "note.txt").read_text() == "hello"


def test_file_read_missing(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute("file_read", {"path": "nope.txt"}, ExecContext())
    assert res.ok is False and "no such file" in res.error


# -- destructive shell denylist ---------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        "rm -rf /",
        "rm -rf /*",
        "sudo rm -rf /",
        "rm -rf ~",
        "rm -rf $HOME",
        "mkfs.ext4 /dev/sda1",
        "mkfs /dev/sda",
        ":(){ :|:& };:",
        "dd if=/dev/zero of=/dev/sda bs=1M",
        "echo start; rm -rf /",
        "echo ok && mkfs /dev/sdb",
    ],
)
def test_destructive_patterns_blocked_even_with_consent(tmp_path, cmd):
    reg = _reg(tmp_path)
    res = reg.execute("shell_exec", {"cmd": cmd}, ExecContext(consent=True))
    assert res.ok is False, cmd
    assert "blocked" in res.error.lower() or "destructive" in res.error.lower()


def test_shell_timeout(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute(
        "shell_exec", {"cmd": "sleep 5", "timeout": 1}, ExecContext(consent=True)
    )
    assert res.ok is False and "timed out" in res.error


# -- file_edit exact-once ----------------------------------------------------


def test_file_edit_exact_once(tmp_path):
    reg = _reg(tmp_path)
    ctx = ExecContext(consent=True)
    reg.execute("file_write", {"path": "e.txt", "content": "alpha beta alpha"}, ctx)
    # two occurrences -> refused
    r = reg.execute(
        "file_edit", {"path": "e.txt", "old_text": "alpha", "new_text": "A"}, ctx
    )
    assert r.ok is False and "exactly once" in r.error
    # zero occurrences -> refused
    r = reg.execute(
        "file_edit", {"path": "e.txt", "old_text": "gamma", "new_text": "G"}, ctx
    )
    assert r.ok is False and "not found" in r.error
    # exactly once -> ok
    r = reg.execute(
        "file_edit", {"path": "e.txt", "old_text": "beta", "new_text": "BETA"}, ctx
    )
    assert r.ok is True
    r = reg.execute("file_read", {"path": "e.txt"}, ctx)
    assert r.output == "alpha BETA alpha"


# -- memory ------------------------------------------------------------------


def test_memory_round_trip_tmp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    # build with defaults -> dirs resolve under the patched HOME
    reg = build_default_registry()
    ctx = ExecContext()
    w = reg.execute(
        "memory_write", {"name": "scratch-pad_1", "content": "# hello"}, ctx
    )
    assert w.ok is True
    assert (tmp_path / ".levi" / "agent_memory" / "scratch-pad_1.md").exists()
    r = reg.execute("memory_read", {"name": "scratch-pad_1"}, ctx)
    assert r.ok is True and r.output == "# hello"


def test_memory_name_sanitized(tmp_path):
    reg = _reg(tmp_path)
    r = reg.execute("memory_write", {"name": "../evil", "content": "x"}, ExecContext())
    assert r.ok is False
    r = reg.execute("memory_write", {"name": "a b", "content": "x"}, ExecContext())
    assert r.ok is False


def test_memory_read_missing(tmp_path):
    reg = _reg(tmp_path)
    r = reg.execute("memory_read", {"name": "ghost"}, ExecContext())
    assert r.ok is False and "no such entry" in r.error


def test_memory_write_needs_no_confirmation(tmp_path):
    reg = _reg(tmp_path)
    assert reg.get("memory_write").requires_confirmation is False
    assert reg.get("shell_exec").requires_confirmation is True
    assert reg.get("file_write").requires_confirmation is True


# -- skills ------------------------------------------------------------------


def test_skill_list_bridges_canonical_registry(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute("skill_list", {}, ExecContext())
    assert res.ok is True
    assert "status" in res.output


def test_skill_load_missing(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute("skill_load", {"name": "nope"}, ExecContext())
    assert res.ok is False and "no playbook" in res.error


def test_skill_load_ok(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "demo.md").write_text("# Demo playbook")
    reg = _reg(tmp_path)
    res = reg.execute("skill_load", {"name": "demo"}, ExecContext())
    assert res.ok is True and "Demo playbook" in res.output


# -- schedules (canonical AutomationRegistry backend) ------------------------


def test_automation_create_accepts_trigger_config(tmp_path):
    from levi.daemon.automation import AutomationRegistry, TriggerKind

    reg = AutomationRegistry(data_dir=tmp_path / "auto")
    auto = reg.create(
        name="n",
        description="d",
        actions=[],
        trigger=TriggerKind.SCHEDULE,
        trigger_config={"cron": "* * * * *", "task": "t"},
    )
    assert auto.trigger_config == {"cron": "* * * * *", "task": "t"}
    # reload from disk keeps it
    reg2 = AutomationRegistry(data_dir=tmp_path / "auto")
    assert reg2.get(auto.id).trigger_config["cron"] == "* * * * *"


def test_automation_remove(tmp_path):
    from levi.daemon.automation import AutomationRegistry

    reg = AutomationRegistry(data_dir=tmp_path / "auto")
    assert reg.remove("auto.doesnotexist") is False
    auto = reg.create(name="n", description="d", actions=[])
    assert reg.remove(auto.id) is True
    assert reg.get(auto.id) is None


def test_schedule_add_list_remove(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_AUTOMATIONS_DIR", str(tmp_path / "auto"))
    reg = _reg(tmp_path)
    ctx = ExecContext(consent=True)
    # gated: without consent it raises
    with pytest.raises(ConfirmationRequired):
        reg.execute(
            "schedule_add",
            {"name": "m", "cron": "* * * * *", "task": "t"},
            ExecContext(),
        )
    added = reg.execute(
        "schedule_add",
        {"name": "morning", "cron": "0 9 * * *", "task": "say hi"},
        ctx,
    )
    assert added.ok is True
    listed = reg.execute("schedule_list", {}, ctx)
    assert listed.ok is True
    assert "morning" in listed.output and "0 9 * * *" in listed.output
    # extract the id from the listing
    auto_id = listed.output.splitlines()[0].split(" | ")[0]
    removed = reg.execute("schedule_remove", {"schedule_id": auto_id}, ctx)
    assert removed.ok is True
    listed2 = reg.execute("schedule_list", {}, ctx)
    assert "morning" not in listed2.output
    # unknown id refused honestly
    bad = reg.execute("schedule_remove", {"schedule_id": "auto.nope"}, ctx)
    assert bad.ok is False and "unknown" in bad.error


def test_schedule_add_uses_canonical_registry_store(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_AUTOMATIONS_DIR", str(tmp_path / "auto"))
    reg = _reg(tmp_path)
    reg.execute(
        "schedule_add",
        {"name": "x", "cron": "* * * * *", "task": "t"},
        ExecContext(consent=True),
    )
    from levi.daemon.automation import AutomationRegistry

    reg2 = AutomationRegistry(data_dir=tmp_path / "auto")
    items = reg2.list()
    assert len(items) == 1
    assert items[0].trigger.value == "schedule"
    assert items[0].trigger_config == {"cron": "* * * * *", "task": "t"}


# -- web tools: honest offline ----------------------------------------------


def _block_network(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("network must not be touched in this test")

    monkeypatch.setenv("LEVI_OFFLINE", "1")
    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", _boom)


@pytest.mark.parametrize(
    "tool,args",
    [
        ("web_search", {"query": "levi"}),
        ("web_fetch", {"url": "https://example.com"}),
        ("http_request", {"method": "GET", "url": "https://example.com"}),
    ],
)
def test_web_tools_offline_honest(tmp_path, monkeypatch, tool, args):
    _block_network(monkeypatch)
    reg = _reg(tmp_path)
    res = reg.execute(tool, args, ExecContext(consent=True))
    assert res.ok is False
    assert "offline" in res.error.lower()


def test_http_request_blocks_non_http_scheme(tmp_path, monkeypatch):
    monkeypatch.delenv("LEVI_OFFLINE", raising=False)
    import urllib.request

    def _boom(*a, **k):
        raise AssertionError("network must not be touched")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    reg = _reg(tmp_path)
    res = reg.execute(
        "http_request",
        {"method": "GET", "url": "file:///etc/passwd"},
        ExecContext(consent=True),
    )
    assert res.ok is False and "non-http" in res.error.lower()
    res = reg.execute(
        "web_fetch", {"url": "ftp://example.com/x"}, ExecContext(consent=True)
    )
    assert res.ok is False and "non-http" in res.error.lower()


# -- delegate ----------------------------------------------------------------


def test_delegate_without_loop_is_honest(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute("delegate", {"task": "do a thing"}, ExecContext(consent=True))
    # levi.agent.loop may exist in the future; either way the result must
    # be honest, never fabricated
    assert isinstance(res, ToolResult)
    if not res.ok:
        assert "loop" in res.error.lower() or "delegate" in res.error.lower()


def test_delegate_requires_task(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute("delegate", {}, ExecContext(consent=True))
    assert res.ok is False and "task" in res.error.lower()


def test_delegate_propagates_subtask_failure(tmp_path, monkeypatch):
    """A delegated subtask whose transcript reports ok=False must surface
    as a failed tool call — reporting ok=True would misrepresent failure
    as success (blueprint §1.7 honesty)."""
    import levi.agent.loop as agent_loop
    from levi.agent.loop import AgentTranscript

    def _failing_subtask(*a, **k):
        return AgentTranscript(
            task="do a failing thing",
            provider_name="fake",
            steps=[],
            final="the subtask broke",
            ok=False,
            error="boom",
        )

    monkeypatch.setattr(agent_loop, "run_subtask", _failing_subtask)
    reg = _reg(tmp_path)
    res = reg.execute(
        "delegate", {"task": "do a failing thing"}, ExecContext(consent=True)
    )
    assert res.ok is False
    assert "the subtask broke" in (res.output + res.error)


def test_delegate_reports_subtask_success(tmp_path, monkeypatch):
    import levi.agent.loop as agent_loop
    from levi.agent.loop import AgentTranscript

    def _ok_subtask(*a, **k):
        return AgentTranscript(
            task="do an ok thing",
            provider_name="fake",
            steps=[],
            final="all good",
            ok=True,
        )

    monkeypatch.setattr(agent_loop, "run_subtask", _ok_subtask)
    reg = _reg(tmp_path)
    res = reg.execute("delegate", {"task": "do an ok thing"}, ExecContext(consent=True))
    assert res.ok is True
    assert "all good" in res.output
