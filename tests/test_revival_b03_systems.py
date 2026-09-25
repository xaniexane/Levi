"""Batch B03 systems-internals tests: liveimage, msgports, everobjects,
minikern, capmesh, proctree, vmcell, shipcode. >=3 meaningful tests per
module, including the mandated adversarial cases."""

import pytest

from levi.revival import (
    capmesh,
    everobjects,
    liveimage,
    minikern,
    msgports,
    proctree,
    shipcode,
    vmcell,
)


# ---------------------------------------------------------------------------
# liveimage
# ---------------------------------------------------------------------------


def test_liveimage_spawn_registers_and_inspects():
    img = liveimage.Image()
    a = img.spawn("sprite", x=1, y=2)
    b = img.spawn("sprite", x=9)
    assert len(img) == 2
    assert img.lookup(a.obj_id) is a
    assert img.inspect(b.obj_id) == {
        "id": b.obj_id,
        "kind": "sprite",
        "attributes": {"x": 9},
    }
    assert img.kinds() == {"sprite": 2}
    assert img.is_running()


def test_liveimage_snapshot_restore_roundtrip():
    img = liveimage.Image()
    a = img.spawn("counter", n=41)
    a.set("n", 42)
    data = img.snapshot()
    assert isinstance(data, bytes) and len(data) > 0
    img2 = liveimage.Image.restore(data)
    assert len(img2) == 1
    back = img2.lookup(a.obj_id)
    assert back.kind == "counter"
    assert back.get("n") == 42
    # identity sequence continues — no id reuse after restore
    c = img2.spawn("fresh")
    assert c.obj_id == a.obj_id + 1


def test_liveimage_corrupt_snapshot_and_halt():
    with pytest.raises(liveimage.ImageError):
        liveimage.Image.restore(b"definitely not a snapshot")
    img = liveimage.Image()
    img.spawn("thing")
    alive = img.halt()
    assert alive == [1]
    assert not img.is_running()
    with pytest.raises(liveimage.ImageError):
        img.snapshot()
    with pytest.raises(liveimage.ImageError):
        img.lookup(999)


# ---------------------------------------------------------------------------
# msgports
# ---------------------------------------------------------------------------


def test_msgports_send_recv_roundtrip():
    def pinger():
        yield msgports.Send("pong-port", "ping")
        msg = yield msgports.Recv("ping-port")
        return msg.payload

    def ponger():
        msg = yield msgports.Recv("pong-port")
        yield msgports.Send("ping-port", msg.payload + "-pong")

    d = msgports.Dispatcher()
    d.add_task(msgports.Task("pinger", pinger()))
    d.add_task(msgports.Task("ponger", ponger()))
    results = d.run()
    assert results["pinger"] == "ping-pong"
    assert d.pending_counts() == {"pong-port": 0, "ping-port": 0}


def test_msgports_highest_priority_delivered_first():
    received = []

    def waiter():
        for _ in range(2):
            msg = yield msgports.Recv("q")
            received.append(msg.payload)

    def slow_sender():
        yield msgports.Send("q", "low", priority=1)

    def fast_sender():
        yield msgports.Send("q", "high", priority=9)

    d = msgports.Dispatcher()
    # waiter registers first so it is already blocked when both land
    d.add_task(msgports.Task("waiter", waiter()))
    d.add_task(msgports.Task("slow", slow_sender()))
    d.add_task(msgports.Task("fast", fast_sender()))
    d.run()
    assert received == ["high", "low"]


def test_msgports_deadlock_ends_cleanly():
    def lonely():
        msg = yield msgports.Recv("never")
        return msg  # pragma: no cover

    d = msgports.Dispatcher()
    t = msgports.Task("lonely", lonely())
    d.add_task(t)
    d.run(max_rounds=50)
    assert not t.done  # still waiting, but the loop did not hang
    with pytest.raises(msgports.PortError):
        d.add_task(msgports.Task("lonely", lonely()))


# ---------------------------------------------------------------------------
# everobjects
# ---------------------------------------------------------------------------


class Doc(everobjects.EverObject):
    pass


class DocV2(everobjects.EverObject):
    def words(self):
        return len(self.get("text", "").split())


def _classes():
    cr = everobjects.ClassRegistry()
    cr.register("Doc", Doc)
    return cr


def test_everobjects_identity_survives_reboot(tmp_path):
    reg = everobjects.Registry(_classes())
    obj = reg.create("Doc", text="hello world", rev=3)
    store = str(tmp_path / "store.json")
    reg.save(store)
    # the reboot: a brand-new registry loads the same store
    reg2 = everobjects.Registry(_classes())
    assert reg2.load(store) == 1
    back = reg2.get(obj.obj_id)
    assert back.obj_id == obj.obj_id
    assert back.get("text") == "hello world"
    assert back.get("rev") == 3
    assert reg2.class_of(obj.obj_id) == "Doc"


def test_everobjects_class_swap_keeps_identity_and_data():
    cr = _classes()
    reg = everobjects.Registry(cr)
    obj = reg.create("Doc", text="one two three")
    cr.swap("Doc", DocV2)
    reg.reinstantiate()
    back = reg.get(obj.obj_id)
    assert isinstance(back, DocV2)
    assert back.obj_id == obj.obj_id
    assert back.get("text") == "one two three"
    assert back.words() == 3  # new implementation, old data


def test_everobjects_derive_subclass_across_registry():
    cr = _classes()
    cr.derive("Memo", "Doc", kind="memo")
    reg = everobjects.Registry(cr)
    memo = reg.create("Memo", text="hi")
    assert isinstance(memo, Doc)
    assert type(memo).__name__ == "Memo"
    assert memo.get("kind") == "memo"
    assert memo.get("text") == "hi"
    with pytest.raises(everobjects.EverError):
        reg.get("nope")
    with pytest.raises(everobjects.EverError):
        cr.swap("Missing", Doc)


# ---------------------------------------------------------------------------
# minikern
# ---------------------------------------------------------------------------


def _echo_kernel():
    k = minikern.Kernel()

    def handler(state, req):
        state["n"] = state.get("n", 0) + 1
        if req == "boom":
            raise RuntimeError("simulated server fault")
        return f"echo:{req}:{state['n']}"

    k.register(minikern.Server("echo", handler, priority=2))
    return k


def test_minikern_synchronous_send_reply():
    k = _echo_kernel()
    assert k.send("echo", "hi") == "echo:hi:1"
    assert k.send("echo", "again") == "echo:again:2"
    assert k.names() == ["echo"]
    with pytest.raises(minikern.KernelError):
        k.send("ghost", "hi")


def test_minikern_crashed_server_restarts_without_kernel_restart():
    k = _echo_kernel()
    with pytest.raises(minikern.KernelError):
        k.send("echo", "boom")
    srv = k.lookup("echo")
    assert srv.crashes == 1
    assert srv.restarts == 1
    # same name, fresh state, kernel and naming untouched
    assert k.send("echo", "after") == "echo:after:1"
    stats = k.stats("echo")
    assert stats["restarts"] == 1 and stats["served"] == 1


def test_minikern_priority_inheritance_and_remote_naming():
    seen = {}
    k = minikern.Kernel()

    def handler(state, req):
        seen["eff"] = srv.effective_priority
        return "ok"

    srv = minikern.Server("svc", handler, priority=1, remote=True)
    k.register(srv)
    assert k.send("svc", "x", client_priority=9) == "ok"
    assert seen["eff"] == 9  # server borrowed the client's priority
    assert srv.effective_priority == 1  # and gave it back
    assert k.stats("svc")["remote"] is True


# ---------------------------------------------------------------------------
# capmesh
# ---------------------------------------------------------------------------


def _mesh_with_two():
    m = capmesh.Mesh()
    m.add_node("alpha")
    m.add_node("beta")
    full = capmesh.READ | capmesh.WRITE | capmesh.ADMIN
    ca = m.mint("alpha", {"v": 1}, rights=full)
    cb = m.mint("beta", {"v": 2}, rights=full)
    return m, ca, cb


def test_capmesh_mint_resolve_write_across_nodes():
    m, ca, cb = _mesh_with_two()
    assert m.resolve(ca.token()) == {"v": 1}
    assert m.resolve(cb.token()) == {"v": 2}  # other "machine", same space
    m.write(ca.token(), {"v": 10})
    assert m.resolve(ca.token()) == {"v": 10}


def test_capmesh_rejects_forged_capabilities():
    m, ca, _ = _mesh_with_two()
    token = ca.token()
    # tamper with the seal: flip the last hex char
    forged = token[:-1] + ("0" if token[-1] != "0" else "1")
    with pytest.raises(capmesh.CapError):
        m.verify(forged)
    # a token minted under a different secret is equally worthless
    other = capmesh.Mesh()
    with pytest.raises(capmesh.CapError):
        other.verify(token)
    with pytest.raises(capmesh.CapError):
        m.verify("not-a-token")


def test_capmesh_rights_enforced_and_attenuated():
    m = capmesh.Mesh()
    m.add_node("n1")
    ro = m.mint("n1", "data", rights=capmesh.READ)
    assert m.resolve(ro.token()) == "data"
    with pytest.raises(capmesh.CapError):
        m.write(ro.token(), "changed")
    rw = m.mint("n1", "data2")
    weak = m.attenuate(rw.token(), capmesh.READ)
    assert m.resolve(weak.token()) == "data2"
    with pytest.raises(capmesh.CapError):
        m.write(weak.token(), "nope")


def test_capmesh_blobs_content_addressed_and_immutable():
    m = capmesh.Mesh()
    d1 = m.put_blob(b"hello")
    d2 = m.put_blob(b"hello")
    assert d1 == d2  # same bytes, same name
    assert m.get_blob(d1) == b"hello"
    d3 = m.put_blob(b"other")
    assert d3 != d1
    with pytest.raises(capmesh.CapError):
        m.get_blob("0" * 64)


def test_capmesh_transaction_is_all_or_nothing():
    m, ca, cb = _mesh_with_two()
    m.write(ca.token(), "A0")
    m.write(cb.token(), "B0")
    forged = ca.token()[:-1] + ("0" if ca.token()[-1] != "0" else "1")
    with pytest.raises(capmesh.CapError):
        m.transact(
            [
                ("write", ca.token(), "A1"),
                ("write", forged, "EVIL"),
            ]
        )
    # nothing applied: the valid first op rolled back with the bad one
    assert m.resolve(ca.token()) == "A0"
    assert m.resolve(cb.token()) == "B0"
    # a clean transaction commits everything
    m.transact([("write", ca.token(), "A2"), ("write", cb.token(), "B2")])
    assert m.resolve(ca.token()) == "A2"
    assert m.resolve(cb.token()) == "B2"


# ---------------------------------------------------------------------------
# proctree
# ---------------------------------------------------------------------------


def test_proctree_spawn_grants_frozen_capabilities():
    seen = {}
    tree = proctree.Tree()
    parent = tree.spawn("parent", lambda caps: "up")
    child = tree.spawn(
        "child",
        lambda caps: seen.update(caps) or "done",
        parent=parent,
        caps={"db": "handle-1"},
    )
    assert child.parent is parent
    assert child.pid != parent.pid
    tree.supervise(child)
    assert seen == {"db": "handle-1"}  # exactly what was granted, nothing more
    with pytest.raises(proctree.ProcError):
        child.grant("root")
    assert child.grant("db") == "handle-1"


def test_proctree_one_for_one_restarts_crashed_child():
    attempts = []

    def flaky(caps):
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("flaky fault")
        return "recovered"

    tree = proctree.Tree()
    child = tree.spawn("flaky", flaky, policy=proctree.ONE_FOR_ONE)
    tree.supervise(child)
    assert child.result == "recovered"
    assert child.restarts == 2
    assert any("crashed" in e for e in tree.events)


def test_proctree_one_for_all_restarts_siblings_and_gives_up():
    runs_b = []
    calls_a = []

    def child_a(caps):
        calls_a.append(1)
        if len(calls_a) == 1:
            raise RuntimeError("a dies once")
        return "a-ok"

    def child_b(caps):
        runs_b.append(1)
        return "b-ok"

    tree = proctree.Tree()
    parent = tree.spawn("parent", lambda caps: "up")
    a = tree.spawn("a", child_a, parent=parent, policy=proctree.ONE_FOR_ALL)
    tree.spawn("b", child_b, parent=parent)
    tree.supervise_tree()
    assert a.result == "a-ok"
    assert len(runs_b) == 2  # sibling restarted alongside a, then supervised
    # hopeless child: policy gives up after max_restarts
    tree2 = proctree.Tree()
    doomed = tree2.spawn(
        "doomed",
        lambda caps: 1 / 0,
        policy=proctree.ONE_FOR_ONE,
        max_restarts=2,
    )
    tree2.supervise(doomed)
    assert doomed.restarts == 2
    assert doomed.result is None
    assert any("left dead" in e for e in tree2.events)
    with pytest.raises(proctree.ProcError):
        tree2.spawn("x", lambda caps: None, policy="bogus")


# ---------------------------------------------------------------------------
# vmcell
# ---------------------------------------------------------------------------


def test_vmcell_arithmetic_and_print():
    prog = vmcell.assemble("PUSH 7\nPUSH 6\nMUL\nPRINT\nHALT\n")
    assert vmcell.Cell().run(prog) == [42]


def test_vmcell_jumps_calls_and_locals():
    src = """
        PUSH 5
        CALL double
        PRINT
        HALT
    double:
        DUP
        ADD
        RET
    """
    assert vmcell.Cell().run(vmcell.assemble(src)) == [10]
    src2 = """
        PUSH 0
        JZ skip
        PUSH 111
        PRINT
        HALT
    skip:
        PUSH 222
        PRINT
        HALT
    """
    assert vmcell.Cell().run(vmcell.assemble(src2)) == [222]
    src3 = """
        PUSH 40
        STORE x
        LOAD x
        PUSH 2
        ADD
        PRINT
        HALT
    """
    assert vmcell.Cell().run(vmcell.assemble(src3)) == [42]


def test_vmcell_halts_runaway_programs():
    prog = vmcell.assemble("LOOP: JMP LOOP\n")
    with pytest.raises(vmcell.RunawayError):
        vmcell.Cell(max_steps=100).run(prog)
    # a bounded loop still terminates fine under the same bound
    src = """
        PUSH 3
        STORE n
    top:
        LOAD n
        JZ done
        LOAD n
        PUSH 1
        SUB
        STORE n
        JMP top
    done:
        PUSH 7
        PRINT
        HALT
    """
    assert vmcell.Cell(max_steps=100).run(vmcell.assemble(src)) == [7]


def test_vmcell_hard_errors_and_bad_assembly():
    with pytest.raises(vmcell.VMError):
        vmcell.Cell().run(vmcell.assemble("PUSH 1\nPUSH 0\nDIV\nPRINT\nHALT\n"))
    with pytest.raises(vmcell.VMError):
        vmcell.Cell().run(vmcell.assemble("ADD\nHALT\n"))  # underflow
    with pytest.raises(vmcell.AssemblyError):
        vmcell.assemble("FROBNICATE\n")
    with pytest.raises(vmcell.AssemblyError):
        vmcell.assemble("JMP nowhere\n")
    # no opcode can reach the host: the set is closed
    assert set(vmcell._OPS) <= {
        "PUSH",
        "ADD",
        "SUB",
        "MUL",
        "DIV",
        "LOAD",
        "STORE",
        "JMP",
        "JZ",
        "CALL",
        "RET",
        "PRINT",
        "HALT",
        "DUP",
        "POP",
    }


# ---------------------------------------------------------------------------
# shipcode
# ---------------------------------------------------------------------------


def _vault():
    v = shipcode.Vault()
    v.put("r1", {"kind": "apple", "n": 1})
    v.put("r2", {"kind": "apple", "n": 2})
    v.put("r3", {"kind": "secret", "n": 99})
    return v


def test_shipcode_program_runs_inside_vault():
    v = _vault()
    total = v.ship(
        lambda scope: scope.aggregate(lambda recs: sum(r["n"] for r in recs)),
        grant=["r1", "r2"],
    )
    assert total == 3
    grouped = v.ship(shipcode.summarize_by("kind"), grant=["r1", "r2", "r3"])
    assert grouped == {"apple": 2, "secret": 1}


def test_shipcode_program_cannot_exfiltrate():
    v = _vault()

    def hostile(scope):
        grabbed = {}
        # 1. ungranted records are unnamed through the public API
        try:
            scope.get("r3")
            grabbed["direct"] = True
        except shipcode.VaultError:
            grabbed["direct"] = False
        # 2. scan only yields the grant
        grabbed["scan_kinds"] = sorted(r["kind"] for r in scope.scan())
        # 3. no path back to the vault object itself
        grabbed["has_vault"] = hasattr(scope, "_vault") or hasattr(scope, "vault")
        # 4. returned copies cannot mutate the vault
        rec = scope.get("r1")
        rec["n"] = 999
        return grabbed

    report = v.ship(hostile, grant=["r1", "r2"])
    assert report["direct"] is False
    assert report["scan_kinds"] == ["apple", "apple"]
    assert report["has_vault"] is False
    # the vault's own record is untouched by the tampered copy
    assert v.ship(lambda s: s.get("r1")["n"], grant=["r1"]) == 1


def test_shipcode_grant_must_be_explicit_and_valid():
    v = _vault()
    with pytest.raises(shipcode.VaultError):
        v.ship(lambda scope: 1)  # no grant at all
    with pytest.raises(shipcode.VaultError):
        v.ship(lambda scope: 1, grant=["r1", "ghost"])
    assert v.ids() == ["r1", "r2", "r3"]
    assert len(v) == 3
