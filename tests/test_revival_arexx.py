"""Hermetic tests for revival.arexx (named application command ports).

No network (socketpair is loopback-local), no HOME dependence, deterministic.
"""

import threading

import pytest

from core.levi.revival import arexx


def _registry():
    reg = arexx.PortRegistry()
    reg.register_port(
        "memory",
        {
            "store": lambda key, value: f"stored:{key}={value}",
            "recall": lambda key: f"recalled:{key}",
        },
    )
    return reg


# -- basic dispatch -----------------------------------------------------------


def test_register_and_send_command():
    reg = _registry()
    assert reg.send_command("memory", "store", args=["k", "v"]) == "stored:k=v"
    assert reg.send_command("memory", "recall", kwargs={"key": "k"}) == "recalled:k"


def test_unknown_port_refused():
    reg = _registry()
    with pytest.raises(arexx.UnknownPort, match="nope"):
        reg.send_command("nope", "store")


def test_unknown_verb_refused():
    reg = _registry()
    with pytest.raises(arexx.UnknownVerb, match="delete"):
        reg.send_command("memory", "delete")


def test_unregister_then_unknown():
    reg = _registry()
    reg.unregister_port("memory")
    assert not reg.has_port("memory")
    with pytest.raises(arexx.UnknownPort):
        reg.send_command("memory", "store")
    with pytest.raises(arexx.UnknownPort):
        reg.unregister_port("memory")


def test_list_ports_introspection():
    reg = _registry()
    assert reg.list_ports() == {"memory": ["recall", "store"]}


def test_invalid_registration_rejected():
    reg = arexx.PortRegistry()
    with pytest.raises(ValueError):
        reg.register_port("", {"a": lambda: 1})
    with pytest.raises(ValueError):
        reg.register_port("p", {})
    with pytest.raises(ValueError):
        reg.register_port("p", {"a": "not-callable"})


# -- ACLs (deny-closed) --------------------------------------------------------


def test_acl_allows_listed_caller():
    reg = arexx.PortRegistry()
    reg.register_port("vault", {"open": lambda: "opened"}, acl=["root"])
    assert reg.send_command("vault", "open", caller="root") == "opened"


def test_acl_denies_unlisted_caller():
    reg = arexx.PortRegistry()
    reg.register_port("vault", {"open": lambda: "opened"}, acl=["root"])
    with pytest.raises(arexx.AccessDenied):
        reg.send_command("vault", "open", caller="mallory")


def test_acl_denies_anonymous_caller():
    reg = arexx.PortRegistry()
    reg.register_port("vault", {"open": lambda: "opened"}, acl=["root"])
    with pytest.raises(arexx.AccessDenied):
        reg.send_command("vault", "open")


def test_no_acl_means_open():
    reg = _registry()
    assert (
        reg.send_command("memory", "recall", args=["k"], caller="anyone")
        == "recalled:k"
    )


# -- script runner --------------------------------------------------------------


def test_run_script_sequential_with_results():
    reg = _registry()
    steps = [
        {"port": "memory", "verb": "store", "args": ["a", "1"]},
        ("memory", "recall", ["a"]),
        {"port": "memory", "verb": "recall", "kwargs": {"key": "b"}},
    ]
    results = arexx.run_script(reg, steps)
    assert [r.ok for r in results] == [True, True, True]
    assert results[0].result == "stored:a=1"
    assert results[1].result == "recalled:a"
    assert [r.index for r in results] == [0, 1, 2]


def test_run_script_stops_on_error_by_default():
    reg = _registry()
    ran = []
    reg.register_port("spy", {"touch": lambda: ran.append(True) or "touched"})
    steps = [
        ("memory", "recall", ["a"]),
        ("memory", "nope", []),  # unknown verb
        ("spy", "touch", []),
    ]
    results = arexx.run_script(reg, steps)
    assert [r.ok for r in results] == [True, False]
    assert "UnknownVerb" in (results[1].error or "")
    assert ran == []  # third step never ran


def test_run_script_continues_when_asked():
    reg = _registry()
    steps = [
        ("memory", "nope", []),
        ("memory", "recall", ["a"]),
        ("ghost", "verb", []),
    ]
    results = arexx.run_script(reg, steps, stop_on_error=False)
    assert [r.ok for r in results] == [False, True, False]
    assert "UnknownVerb" in (results[0].error or "")
    assert "UnknownPort" in (results[2].error or "")


def test_run_script_captures_verb_exceptions():
    reg = arexx.PortRegistry()

    def boom():
        raise RuntimeError("verb impl failed")

    reg.register_port("bad", {"boom": boom})
    results = arexx.run_script(reg, [{"port": "bad", "verb": "boom"}])
    assert results[0].ok is False
    assert "RuntimeError" in (results[0].error or "")


def test_run_script_applies_caller_to_all_steps():
    reg = arexx.PortRegistry()
    reg.register_port("vault", {"open": lambda: "opened"}, acl=["root"])
    ok_results = arexx.run_script(reg, [("vault", "open", [])], caller="root")
    assert ok_results[0].ok is True
    denied = arexx.run_script(reg, [("vault", "open", [])], caller="mallory")
    assert denied[0].ok is False
    assert "AccessDenied" in (denied[0].error or "")


# -- socketpair-backed remote registry ------------------------------------------


def test_remote_registry_round_trip():
    from core.levi.revival import plan9

    reg = _registry()
    client, server = plan9.create_channel()
    t = threading.Thread(target=arexx.serve_registry, args=(reg, server), daemon=True)
    t.start()
    remote = arexx.RemoteRegistry(client)
    try:
        assert remote.send_command("memory", "store", args=["k", "v"]) == "stored:k=v"
        with pytest.raises(arexx.UnknownVerb):
            remote.send_command("memory", "nope")
        with pytest.raises(arexx.UnknownPort):
            remote.send_command("ghost", "verb")
    finally:
        remote.close()
        t.join(timeout=5)


def test_remote_registry_acl_denial():
    from core.levi.revival import plan9

    reg = arexx.PortRegistry()
    reg.register_port("vault", {"open": lambda: "opened"}, acl=["root"])
    client, server = plan9.create_channel()
    t = threading.Thread(target=arexx.serve_registry, args=(reg, server), daemon=True)
    t.start()
    remote = arexx.RemoteRegistry(client)
    try:
        assert remote.send_command("vault", "open", caller="root") == "opened"
        with pytest.raises(arexx.AccessDenied):
            remote.send_command("vault", "open", caller="mallory")
    finally:
        remote.close()
        t.join(timeout=5)
