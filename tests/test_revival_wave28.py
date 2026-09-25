"""Wave 28 tests: offline mail routing, graded spooling, mesh overlays."""

from datetime import datetime, time

import pytest

from core.levi.revival import poll_window as pw
from core.levi.revival import netmail as nm
from core.levi.revival import echomail as em
from core.levi.revival import spool_grade_poll as sp
from core.levi.revival import remote_queued_exec as rq
from core.levi.revival import mesh_relay as mr
from core.levi.revival import supernode_overlay as so


# ---------------------------------------------------------------------------
# poll_window
# ---------------------------------------------------------------------------


def _windows():
    return [
        pw.PollWindow("night", time(1, 0), time(5, 0), "cheap"),
        pw.PollWindow("day", time(9, 0), time(17, 0), "peak"),
    ]


def test_poll_window_bulk_waits_for_cheap(tmp_path):
    q = pw.PollWindowQueue(_windows())
    q.queue(pw.QueuedItem("a", "bulk data", pw.WindowKind.BULK))
    q.queue(pw.QueuedItem("b", "normal data", pw.WindowKind.NORMAL))
    day = datetime(2026, 9, 16, 10, 0)
    released = q.tick(day)
    assert {r.item_id for r in released} == {"b"}
    assert q.pending()[0].item_id == "a"
    night = datetime(2026, 9, 17, 2, 0)
    released = q.tick(night)
    assert {r.item_id for r in released} == {"a"}
    assert q.pending() == []


def test_poll_window_urgent_leaves_in_peak():
    q = pw.PollWindowQueue(_windows())
    q.queue(pw.QueuedItem("u", "urgent", pw.WindowKind.URGENT))
    assert [r.item_id for r in q.tick(datetime(2026, 9, 16, 10, 0))] == ["u"]


def test_poll_window_midnight_crossing_and_next():
    w = pw.PollWindow("owl", time(23, 0), time(2, 0), "cheap")
    assert w.contains(datetime(2026, 9, 17, 0, 30))
    assert not w.contains(datetime(2026, 9, 16, 12, 0))
    nxt = w.next_open(datetime(2026, 9, 16, 12, 0))
    assert (nxt.hour, nxt.day) == (23, 16)
    assert w.next_open(datetime(2026, 9, 17, 0, 30)) <= datetime(2026, 9, 17, 0, 30)


def test_poll_window_save_load_roundtrip(tmp_path):
    q = pw.PollWindowQueue(_windows())
    q.queue(pw.QueuedItem("x", "data", pw.WindowKind.NORMAL, "hub"))
    path = tmp_path / "q.json"
    q.save(path)
    q2 = pw.PollWindowQueue.load(path)
    assert len(q2.pending()) == 1
    assert q2.pending()[0].destination == "hub"
    assert q2.next_window(datetime(2026, 9, 16, 10, 0)).name == "day"


# ---------------------------------------------------------------------------
# netmail
# ---------------------------------------------------------------------------


def _net():
    a = nm.NetmailNode(nm.NetAddress.parse("1:100/1"))
    b = nm.NetmailNode(nm.NetAddress.parse("1:100/2"))
    c = nm.NetmailNode(nm.NetAddress.parse("2:200/1"))
    a.add_neighbor("b", b.address)
    a.add_neighbor("c", c.address)
    b.add_neighbor("a", a.address)
    c.add_neighbor("a", a.address)
    return a, b, c


def test_netmail_address_parse_and_str():
    addr = nm.NetAddress.parse("3:77/9.4")
    assert (addr.zone, addr.network, addr.node, addr.point) == (3, 77, 9, 4)
    assert str(addr) == "3:77/9.4"
    assert str(nm.NetAddress.parse("1/2")) == "0:1/2"
    with pytest.raises(nm.NetmailError):
        nm.NetAddress.parse("not-an-address")


def test_netmail_local_delivery_receipt():
    a, b, _ = _net()
    msg = nm.NetmailMessage("m1", a.address, b.address, "hi", "hello")
    a.send(msg)
    a.connect("b", b)
    assert len(b.unread()) == 1
    assert b.unread()[0].receipt is not None
    assert a.outbox == []


def test_netmail_forwarding_path():
    a, b, c = _net()
    msg = nm.NetmailMessage("m2", b.address, c.address, "relay", "via a")
    b.send(msg)
    b.connect("a", a)  # b -> a (a holds it for c)
    assert a.pending_for(c.address)
    a.connect("c", c)  # a -> c
    assert len(c.unread()) == 1
    assert c.unread()[0].path == [str(b.address), str(a.address), str(c.address)]


def test_netmail_next_hop_prefers_same_hub():
    a, b, c = _net()
    assert a.next_hop(nm.NetAddress.parse("1:100/2")) == "b"
    assert a.next_hop(nm.NetAddress.parse("9:900/1")) == "c"


# ---------------------------------------------------------------------------
# echomail
# ---------------------------------------------------------------------------


def _hubs():
    h1, h2 = em.EchoHub("site-a"), em.EchoHub("site-b")
    for h in (h1, h2):
        area = h.ensure_area("levi.dev", "dev talk")
        area.add_member("chauncey")
    return h1, h2


def test_echomail_exchange_syncs_both_ways():
    h1, h2 = _hubs()
    h1.areas["levi.dev"].post(em.EchoMessage("m1", "levi.dev", "chauncey", "a", "one"))
    h2.areas["levi.dev"].post(em.EchoMessage("m2", "levi.dev", "chauncey", "b", "two"))
    gained = h1.exchange(h2)
    assert gained == {"levi.dev": 1}
    assert set(h1.areas["levi.dev"].messages) == {"m1", "m2"}
    assert set(h2.areas["levi.dev"].messages) == {"m1", "m2"}


def test_echomail_duplicates_suppressed():
    h1, h2 = _hubs()
    msg = em.EchoMessage("m1", "levi.dev", "chauncey", "a", "one")
    assert h1.areas["levi.dev"].post(msg) is True
    assert h1.areas["levi.dev"].post(msg) is False  # same id, twice
    h1.exchange(h2)
    h1.exchange(h2)  # second exchange adds nothing
    assert len(h1.areas["levi.dev"].messages) == 1
    assert len(h2.areas["levi.dev"].messages) == 1


def test_echomail_read_order_and_missing_area():
    h1, h2 = _hubs()
    area = h1.areas["levi.dev"]
    area.post(
        em.EchoMessage(
            "m2", "levi.dev", "x", "b", "two", written_at="2026-09-16T10:00:00"
        )
    )
    area.post(
        em.EchoMessage(
            "m1", "levi.dev", "x", "a", "one", written_at="2026-09-16T09:00:00"
        )
    )
    assert [m.msg_id for m in h1.read("levi.dev")] == ["m1", "m2"]
    with pytest.raises(em.EchomailError):
        h1.read("no.such.echo")


# ---------------------------------------------------------------------------
# spool_grade_poll
# ---------------------------------------------------------------------------


def test_spool_grade_order_transfer():
    spool = sp.Spool()
    spool.spool(sp.SpoolJob("low", "big file", "z", payload="..."))
    spool.spool(sp.SpoolJob("high", "urgent mail", "0", payload="!"))
    spool.spool(sp.SpoolJob("mid", "mail", "d", payload="?"))
    done = spool.poll()
    assert [j.job_id for j in done] == ["high", "mid", "low"]
    assert all(j.state == sp.JobState.DONE for j in done)
    assert spool.pending_count() == 0


def test_spool_poll_budget_leaves_rest():
    spool = sp.Spool(max_per_poll=2)
    for i in range(4):
        spool.spool(sp.SpoolJob(f"j{i}", f"job {i}", "d"))
    first = spool.poll()
    assert len(first) == 2
    assert spool.pending_count() == 2
    spool.poll()
    assert spool.pending_count() == 0
    assert len(spool.poll_log) == 2


def test_spool_grade_validation_and_fail():
    with pytest.raises(sp.SpoolError):
        sp.grade_rank("!!")
    spool = sp.Spool()
    spool.spool(sp.SpoolJob("j", "x", "A"))
    spool.fail("j", "remote refused")
    assert spool.jobs["j"].state == sp.JobState.FAILED
    with pytest.raises(sp.SpoolError):
        spool.spool(sp.SpoolJob("j", "dup", "A"))  # duplicate id


def test_spool_seal_writes_files(tmp_path):
    spool = sp.Spool()
    spool.spool(sp.SpoolJob("j1", "desc", "c", payload="body", destination="hub"))
    spool.seal(tmp_path)
    assert (tmp_path / "j1.desc").read_text().startswith("grade=c")
    assert (tmp_path / "j1.data").read_text() == "body"


# ---------------------------------------------------------------------------
# remote_queued_exec
# ---------------------------------------------------------------------------


def _host_pair():
    allow = rq.Allowlist()
    allow.register("wordcount", lambda job: str(len(job.stdin_data.split())))
    allow.register("shout", lambda job: job.stdin_data.upper())
    a = rq.QueuedExecHost("alpha", rq.Allowlist())  # requester, nothing permitted
    b = rq.QueuedExecHost("beta", allow)
    return a, b


def test_queued_exec_roundtrip():
    a, b = _host_pair()
    job = rq.ExecJob("j1", "wordcount", stdin_data="hello brave world")
    a.request(job)
    assert a.link(b) == 1
    assert a.outbox == []
    finished = b.execute_pending()
    assert finished[0].state == rq.ExecState.DONE
    assert finished[0].result == "3"
    assert a.link(b) == 0  # return link carries results back
    results = a.results_for("alpha")
    assert len(results) == 1 and results[0].result == "3"


def test_queued_exec_denies_unlisted():
    a, b = _host_pair()
    a.request(rq.ExecJob("j2", "format-disk"))
    a.link(b)
    finished = b.execute_pending()
    assert finished[0].state == rq.ExecState.DENIED
    assert "not allow-listed" in finished[0].error


def test_queued_exec_handler_error_does_not_kill_host():
    allow = rq.Allowlist()

    def boom(job):
        raise RuntimeError("kaput")

    allow.register("boom", boom)
    b = rq.QueuedExecHost("beta", allow)
    a = rq.QueuedExecHost("alpha")
    a.request(rq.ExecJob("j3", "boom"))
    a.link(b)
    finished = b.execute_pending()
    assert finished[0].state == rq.ExecState.FAILED
    assert "kaput" in finished[0].error
    # host still works afterwards
    allow.register("ok", lambda job: "fine")
    a.request(rq.ExecJob("j4", "ok"))
    a.link(b)
    assert b.execute_pending()[0].state == rq.ExecState.DONE


# ---------------------------------------------------------------------------
# mesh_relay
# ---------------------------------------------------------------------------


def _line_mesh():
    mesh = mr.Mesh()
    nodes = [mr.MeshNode(f"n{i}") for i in range(4)]
    for n in nodes:
        mesh.add(n)
    for x, y in zip(nodes, nodes[1:], strict=False):
        x.link(y)
    return mesh


def test_mesh_flood_delivers_and_records_path():
    mesh = _line_mesh()
    mesh.send("n0", "n3", "hello", "p1")
    stats = mesh.rounds()
    assert stats["delivered"] == 1
    assert mesh.path_of("p1") == ["n0", "n1", "n2", "n3"]


def test_mesh_duplicate_suppressed_ttl_expires():
    mesh = _line_mesh()
    mesh.send("n0", "n3", "x", "p2", ttl=2)  # needs 3 hops, has 2
    stats = mesh.rounds()
    assert stats["delivered"] == 0
    assert stats["dropped_ttl"] >= 1
    assert mesh.path_of("p2") is None
    # duplicates never double-deliver: same id injected twice
    mesh2 = _line_mesh()
    mesh2.send("n0", "n3", "x", "p3")
    mesh2.send("n0", "n3", "x", "p3")
    stats2 = mesh2.rounds()
    assert stats2["delivered"] == 1


def test_mesh_no_route_stays_inflight_free():
    mesh = mr.Mesh()
    lone = mr.MeshNode("lone")
    other = mr.MeshNode("other")
    mesh.add(lone)
    mesh.add(other)
    # unlinked: packet has nowhere to go, TTL drains at the source
    mesh.send("lone", "other", "hi", "p4", ttl=1)
    stats = mesh.rounds()
    assert stats["delivered"] == 0


# ---------------------------------------------------------------------------
# supernode_overlay
# ---------------------------------------------------------------------------


def _overlay():
    ov = so.SupernodeOverlay()
    ov.join(so.Peer("backbone-1", reachable=True, uptime_rounds=10, bandwidth=10))
    ov.join(so.Peer("backbone-2", reachable=True, uptime_rounds=8, bandwidth=8))
    ov.join(so.Peer("weak-1", reachable=False, uptime_rounds=5, bandwidth=1))
    ov.join(so.Peer("weak-2", reachable=True, uptime_rounds=1, bandwidth=1))
    ov.elect(target=2)
    return ov


def test_supernode_election_picks_eligible():
    ov = _overlay()
    supers = ov.supernodes()
    assert supers == ["backbone-1", "backbone-2"]  # deterministic order
    assert all(ov.peers[p].role == so.PeerRole.SUPERNODE for p in supers)


def test_supernode_relay_for_unreachable():
    ov = _overlay()
    assert ov.route("weak-1", "weak-2") in ("backbone-1", "backbone-2")
    assert ov.route("backbone-1", "backbone-2") == "direct"
    assert ov.lookup("weak-1")  # weak peers get index records
    stats = ov.stats()
    assert stats["relayed"] == 1 and stats["direct"] == 1


def test_supernode_missed_heartbeats_demotes():
    ov = _overlay()
    for _ in range(3):
        ov.heartbeat("backbone-1", alive=False)
    assert ov.peers["backbone-1"].role == so.PeerRole.ORDINARY
    assert "backbone-1" not in ov.supernodes()


def test_supernode_leave_repairs_backbone_and_unknowns():
    ov = _overlay()
    ov.leave("backbone-1")
    assert "backbone-1" not in ov.supernodes()
    with pytest.raises(so.OverlayError):
        ov.leave("ghost")
    with pytest.raises(so.OverlayError):
        ov.route("weak-1", "ghost")
