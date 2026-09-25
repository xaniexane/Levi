"""Tests for revival batch B06: objects, data models, control."""

import pytest

from core.levi.revival import leapfind, catgrid, objvault, manyfields
from core.levi.revival import navsets, reciprocity, controltree, namedmesh


# -- leapfind: modeless search-as-navigation ---------------------------------


def _stream():
    return leapfind.LeapStream(
        "alpha line\nbuy milk\nbravo line\nmilk and honey\ncharlie line"
    )


def test_leapfind_typing_narrows_live():
    s = _stream()
    s.type("milk")
    cands = s.candidates
    assert len(cands) == 2
    assert all("milk" in text for _, text in cands)
    assert s.selection == cands[0]  # selection IS the search result


def test_leapfind_backspace_widens_again():
    s = _stream()
    s.type("milk")
    assert len(s.candidates) == 2
    s.backspace(4)
    assert s.query == ""
    assert len(s.candidates) == 5


def test_leapfind_leap_jumps_and_commands_hit_selection():
    s = _stream()
    sel = s.leap("honey")
    assert sel[1] == "milk and honey"
    assert s.caret == sel[0]
    s.replace_selection("oat milk forever")
    assert "oat milk forever" in s.text
    s.leap("bravo")
    s.delete_selection()
    assert "bravo line" not in s.text
    with pytest.raises(LookupError):
        s.leap("zzz-no-such-line")
        s.delete_selection()


def test_leapfind_step_and_yank_paste():
    s = _stream()
    s.type("line")
    first = s.selection
    s.step(1)
    assert s.selection != first
    s.step(-1)
    assert s.selection == first
    yanked = s.yank()
    s.paste_below()
    assert s.text.count(yanked) == 2


# -- catgrid: categories, not cells -------------------------------------------


def _grid():
    g = catgrid.CatGrid()
    g.add_dimension("Region", ["North", "South"])
    g.add_dimension("Quarter", ["Q1", "Q2"])
    g.set({"Region": "North", "Quarter": "Q1"}, "Sales", 100)
    g.set({"Region": "North", "Quarter": "Q2"}, "Sales", 200)
    g.set({"Region": "South", "Quarter": "Q1"}, "Sales", 300)
    g.set({"Region": "South", "Quarter": "Q2"}, "Sales", 400)
    return g


def test_catgrid_natively_multidimensional():
    g = _grid()
    assert g.get({"Region": "North", "Quarter": "Q1"}, "Sales") == 100
    assert g.get({"Region": "South", "Quarter": "Q2"}, "Sales") == 400
    with pytest.raises(KeyError):
        g.set({"Region": "East", "Quarter": "Q1"}, "Sales", 1)


def test_catgrid_formulas_reference_meaning_not_coordinates():
    g = _grid()
    g.define("north_total", "SUM(Sales) WHERE Region = 'North'")
    assert g.evaluate("north_total") == 300
    g.define("q1_avg", "AVG(Sales) WHERE Quarter = 'Q1'")
    assert g.evaluate("q1_avg") == 200
    g.define("by_region", "SUM(Sales) BY Region")
    assert g.evaluate("by_region") == {"North": 300, "South": 700}
    g.define("how_many", "COUNT(Sales) WHERE Region = 'South'")
    assert g.evaluate("how_many") == 2


def test_catgrid_view_and_render_separate_presentation():
    g = _grid()
    rows = g.view("Region", "Quarter", measures=["Sales"])
    assert len(rows) == 4
    assert rows[0] == {"Region": "North", "Quarter": "Q1", "Sales": 100}
    text = catgrid.CatGrid.render(rows)
    assert "Region" in text and "100" in text
    assert catgrid.CatGrid.render([]) == "(empty)"


# -- objvault: objects + transactions ------------------------------------------


def test_objvault_live_objects_and_versions():
    v = objvault.Vault()
    o = v.create("acct", owner="chauncey", balance=100)
    assert o.owner == "chauncey"
    assert o.version == 0
    o.balance = 150  # direct write auto-commits
    assert v.get("acct").balance == 150
    assert o.version == 1


def test_objvault_transaction_commits_atomically():
    v = objvault.Vault()
    v.create("a", x=1)
    v.create("b", x=2)
    with v.begin() as txn:
        txn.write("a", {"x": 10})
        txn.write("b", {"x": 20})
        assert v.get("a").x == 1  # invisible until commit
    assert v.get("a").x == 10
    assert v.get("b").x == 20


def test_objvault_write_write_conflict_aborts():
    v = objvault.Vault()
    v.create("a", x=1)
    t1 = v.begin()
    t2 = v.begin()
    t1.write("a", {"x": 10})
    t2.write("a", {"x": 99})
    t1.commit()
    with pytest.raises(objvault.ConflictError):
        t2.commit()
    assert v.get("a").x == 10  # loser's write never landed


def test_objvault_abort_discards_and_snapshot_roundtrips():
    v = objvault.Vault()
    v.create("a", x=1)
    txn = v.begin()
    txn.write("a", {"x": 42})
    txn.abort()
    assert v.get("a").x == 1
    snap = v.snapshot()
    v2 = objvault.Vault()
    v2.restore(snap)
    assert v2.get("a").x == 1


# -- manyfields: multivalued attributes ----------------------------------------


def _mdb():
    db = manyfields.MultiDB()
    db.define_file(
        "contacts",
        {
            "name": {"multivalued": False, "note": "full name"},
            "phone": {"multivalued": True, "note": "all numbers"},
            "tag": {"multivalued": True, "note": "labels"},
        },
    )
    db.add("contacts", name="Ann", phone=["555-1234", "555-9999"], tag=["friend"])
    db.add("contacts", name="Bob", phone=["555-1234"], tag=["work", "friend"])
    db.add("contacts", name="Cy", phone=["777-0000"], tag=["family"])
    return db


def test_manyfields_attribute_holds_n_values():
    db = _mdb()
    rows = db.query("LIST contacts name phone")
    ann = next(r for r in rows if r["name"] == ["Ann"])
    assert ann["phone"] == ["555-1234", "555-9999"]  # genuinely N values, no join


def test_manyfields_english_like_conditions():
    db = _mdb()
    assert db.count("LIST contacts WITH phone CONTAINING 555") == 2
    rows = db.query(
        "LIST contacts name WITH tag CONTAINING friend AND phone STARTING 555"
    )
    assert sorted(r["name"][0] for r in rows) == ["Ann", "Bob"]
    rows = db.query("LIST contacts name WITH name = Bob")
    assert rows[0]["name"] == ["Bob"]
    rows = db.query('LIST contacts name WITH phone != "555-1234"')
    assert [r["name"] for r in rows] == [["Cy"]]


def test_manyfields_dictionary_is_data():
    db = _mdb()
    assert db.dictionary("contacts")["phone"]["multivalued"] is True
    rows = db.query("LIST DICT.contacts attribute multivalued WITH multivalued = True")
    attrs = sorted(r["attribute"][0] for r in rows)
    assert attrs == ["phone", "tag"]
    with pytest.raises(ValueError):
        db.add("contacts", name=["Too", "Many"], phone=["1"])


# -- navsets: CODASYL network navigation (with caution) -------------------------


def _ndb():
    schema = navsets.Schema("company")
    schema.define_record("Dept", ["name"])
    schema.define_record("Emp", ["name"])
    schema.define_set("staff", owner="Dept", member="Emp")
    db = navsets.Database(schema)
    d1 = db.add_record("Dept", name="eng")
    d2 = db.add_record("Dept", name="ops")
    e1 = db.add_record("Emp", name="ann")
    e2 = db.add_record("Emp", name="bob")
    e3 = db.add_record("Emp", name="cy")
    db.link("staff", d1, e1)
    db.link("staff", d1, e2)
    db.link("staff", d2, e3)
    return db, d1, d2


def test_navsets_first_next_prior_last_walk():
    db, d1, _ = _ndb()
    first = db.first("staff", d1)
    assert first.fields["name"] == "ann"
    assert db.next("staff", d1).fields["name"] == "bob"
    assert db.next("staff", d1) is None  # fell off the end: honest None
    db.first("staff", d1)
    db.next("staff", d1)
    assert db.prior("staff", d1).fields["name"] == "ann"
    assert db.last("staff", d1).fields["name"] == "bob"
    assert db.current("staff").fields["name"] == "bob"


def test_navsets_find_owner_walks_backward():
    db, d1, d2 = _ndb()
    e3 = db.first("staff", d2)
    owner = db.find_owner("staff", e3.rid)
    assert owner.rid == d1 or owner.rid == d2
    assert owner.fields["name"] == "ops"


def test_navsets_schema_rigidity_and_subschema_vocabulary():
    schema = navsets.Schema("s")
    schema.define_record("A", [])
    schema.define_record("B", [])
    schema.define_set("ab", owner="A", member="B")
    sub = navsets.Subschema("limited", schema, record_types=["A"], set_types=["ab"])
    assert sub.allows_record("A") and not sub.allows_record("B")
    assert sub.allows_set("ab")
    db = navsets.Database(schema)
    a = db.add_record("A")
    b = db.add_record("B")
    with pytest.raises(TypeError):  # wrong member type: the rigidity, enforced
        db.link("ab", b, a)
    with pytest.raises(KeyError):
        db.add_record("Nope")


# -- reciprocity: earn by serving -----------------------------------------------


def test_reciprocity_content_addressed_blocks():
    s = reciprocity.Swarm()
    addr = s.publish("ann", b"hello levi", key=b"k1")
    assert addr == reciprocity.address(b"hello levi")
    assert len(addr) == 64


def test_reciprocity_earn_by_serving_spend_by_consuming():
    s = reciprocity.Swarm(price_per_kb=1024.0)  # 1 credit per byte, easy math
    key = b"secret"
    data = b"x" * 100
    addr = s.publish("ann", data, key=key)
    s.grant("bob", 1000.0)
    fetched = s.fetch("bob", addr, key)
    assert fetched == data
    assert s.balance("bob") == 900.0
    assert s.balance("ann") == 100.0
    assert s.audit()["served"] == {"ann": 1}


def test_reciprocity_antifreeloading_blocks_the_broke():
    s = reciprocity.Swarm(price_per_kb=1024.0)
    addr = s.publish("ann", b"data", key=b"k")
    with pytest.raises(reciprocity.FreeloadError):
        s.fetch("broke_bob", addr, b"k")
    assert s.balance("broke_bob") == 0.0
    # sealing is illustration-grade: wrong key gives garbage, not the data
    sealed = s.blocks[addr]["sealed"]
    assert reciprocity.unseal(sealed, b"wrong") != b"data"
    assert reciprocity.unseal(sealed, b"k") == b"data"


# -- controltree: decompose down, fuse up ----------------------------------------


def _tree():
    root = controltree.ControlNode("levi", horizon="mission")
    mid = controltree.ControlNode("planner", horizon="phase")
    a = controltree.ControlNode("arm-a", horizon="action")
    b = controltree.ControlNode("arm-b", horizon="action")
    mid.add_child(a)
    mid.add_child(b)
    root.add_child(mid)
    return root


def test_controltree_decompose_down_fuse_up():
    report = _tree().run("raise the organism")
    assert report["verdict"] == "nominal"
    assert report["node"] == "levi"
    kids = report["children"][0]["children"]
    assert {k["node"] for k in kids} == {"arm-a", "arm-b"}
    assert all(k["done"] for k in kids)


def test_controltree_horizon_discipline():
    parent = controltree.ControlNode("p", horizon="phase")
    with pytest.raises(ValueError):  # child must plan finer than parent
        parent.add_child(controltree.ControlNode("q", horizon="mission"))
    with pytest.raises(KeyError):
        controltree.ControlNode("q", horizon="eon")
    leaf = controltree.ControlNode("leaf", horizon="reflex")
    assert leaf.depth() == 1
    assert _tree().depth() == 3


def test_controltree_custom_triple_and_degraded_verdict():
    def sad_judge(statuses):
        return "degraded"

    root = controltree.ControlNode("r", horizon="mission", judge=sad_judge)
    root.add_child(controltree.ControlNode("c", horizon="action"))
    report = root.run("doomed task")
    assert report["verdict"] == "degraded"
    assert root.world["total"] == 1  # world modeling recorded the fusion


# -- namedmesh: user@group@org ----------------------------------------------------


def test_namedmesh_register_resolve_lookup():
    d = namedmesh.Directory()
    d.register("ann@eng@levi", endpoint="queue-1")
    d.register("bob@eng@levi", endpoint="queue-2")
    d.register("cy@ops@levi", endpoint="queue-3")
    assert d.resolve("ann@eng@levi") == "queue-1"
    assert d.lookup(group="eng") == ["ann@eng@levi", "bob@eng@levi"]
    assert d.lookup(org="levi") == ["ann@eng@levi", "bob@eng@levi", "cy@ops@levi"]
    assert d.members(group="ops") == ["cy@ops@levi"]
    with pytest.raises(ValueError):
        d.register("not-a-name", endpoint="x")
    with pytest.raises(namedmesh.UnknownName):
        d.resolve("ghost@eng@levi")


def test_namedmesh_send_and_read_delivery():
    d = namedmesh.Directory()
    d.register("ann@eng@levi", endpoint="q1")
    d.register("bob@eng@levi", endpoint="q2")
    r1 = d.send("ann@eng@levi", "bob@eng@levi", "rise and shine")
    r2 = d.send("ann@eng@levi", "bob@eng@levi", "second wave")
    assert r2["seq"] == r1["seq"] + 1
    assert len(d.inbox("bob@eng@levi")) == 2
    first = d.read("bob@eng@levi")
    assert first["message"] == "rise and shine"
    assert first["from"] == "ann@eng@levi"
    assert len(d.inbox("bob@eng@levi")) == 1
    assert d.read("ann@eng@levi") is None  # dry inbox: honest None


def test_namedmesh_unknown_recipient_fails_loudly():
    d = namedmesh.Directory()
    d.register("ann@eng@levi", endpoint="q1")
    with pytest.raises(namedmesh.UnknownName):
        d.send("ann@eng@levi", "nobody@eng@levi", "hello?")
    assert len(d) == 1
    d.unregister("ann@eng@levi")
    assert len(d) == 0
