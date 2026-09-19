"""Hermetic tests for revival batch B02: memory/document systems + simplicity."""

from __future__ import annotations

import pytest

from levi.revival.morphoutline import Node, Outline
from levi.revival.fragpile import FragPile
from levi.revival.sparksense import Detection, SparkSense
from levi.revival.livedoc import LiveDoc
from levi.revival.livewire import Responder, Wireboard
from levi.revival.everkeep import DeleteCommand, EverKeep, SetCommand
from levi.revival.simplicity import Budget, audit_paths, audit_source, summarize
from levi.revival.plumber import Plumber


# -- morphoutline -------------------------------------------------------


def _sample_outline() -> Outline:
    out = Outline(title="plan")
    ship = out.add_root(Node("ship it"))
    ship.add(Node("code"))
    ship.add(Node("test"))
    docs = out.add_root(Node("docs"))
    docs.add(Node("readme"))
    return out


def test_hoist_focuses_subtree():
    out = _sample_outline()
    out.hoist(out.find("ship it"))
    assert out.flatten() == [(0, "ship it"), (1, "code"), (1, "test")]
    out.unhoist()
    assert len(out.flatten()) == 5


def test_clone_is_shared_reference():
    out = _sample_outline()
    code = out.find("code")
    docs = out.find("docs")
    out.clone(code, docs)
    assert out.appears(code) == 2
    code.text = "write the code"
    assert docs.children[1] is code  # same object, second appearance
    assert docs.children[1].text == "write the code"  # edits reflect in both


def test_transforms_cover_shapes():
    out = _sample_outline()
    flat = out.flatten()
    assert all(isinstance(d, int) and isinstance(t, str) for d, t in flat)
    rows = out.tabulate()
    assert rows[0]["path"] == "1" and rows[0]["children"] == 2
    slides = out.slides()
    assert slides[0] == {"title": "ship it", "bullets": ["code", "test"]}
    assert slides[1]["title"] == "docs"


# -- fragpile -----------------------------------------------------------


def test_recall_narrows_with_each_character():
    pile = FragPile()
    pile.dump("the quick brown fox jumps over the lazy dog")
    pile.dump("buy milk and eggs on the way home")
    pile.dump("fox news is not about foxes")
    pile.begin_typing()
    step1 = pile.narrow("fox")
    step2 = pile.narrow("fox j")
    assert len(step2) <= len(step1)
    assert all("fox j" in f.text.lower() for f in step2)


def test_recency_breaks_ties():
    pile = FragPile()
    pile.dump("same fragment here")
    newer = pile.dump("same fragment here")
    hits = pile.narrow("same fragment")
    assert hits[0] is newer  # newest wins on equal match quality


def test_empty_query_returns_newest_first():
    pile = FragPile()
    pile.dump("first in")
    pile.dump("second in")
    assert [f.text for f in pile.narrow("")] == ["second in", "first in"]


def test_dump_rejects_empty():
    with pytest.raises(ValueError):
        FragPile().dump("   ")


# -- sparksense ---------------------------------------------------------


def test_senses_all_four_kinds():
    sense = SparkSense()
    text = "Meet on Sep 17 for 2 hours. Budget is $1,250. Office at 123 Main St."
    dets = sense.sense(text)
    kinds = {d.kind for d in dets}
    assert kinds == {"date", "duration", "money", "address"}
    assert sense.kinds_present(text)[0] == "date"


def test_detections_carry_spans_and_described_actions():
    sense = SparkSense()
    dets = sense.sense("Pay $42.50 tomorrow")
    det = next(d for d in dets if d.kind == "money")
    assert isinstance(det, Detection)
    assert det.span[1] - det.span[0] == len(det.text)
    assert det.actions, "every detection must offer action descriptors"
    assert dets[0].span[0] <= dets[1].span[0]  # ordered by position


def test_sensing_is_pure_no_side_effects():
    sense = SparkSense()
    text = "call 555-1234 on 2026-09-17"
    before = text
    sense.sense(text)
    assert text == before
    assert sense.sense("nothing actionable here at all") == []


# -- livedoc ------------------------------------------------------------


def test_document_holds_live_components():
    doc = LiveDoc(title="day")
    doc.append("text", body="morning notes")
    doc.append("checklist", items=["coffee", "code"])
    doc.append("table", columns=["a", "b"])
    assert [p.kind for p in doc.parts] == ["text", "checklist", "table"]
    assert doc.outline()[1] == "checklist 0/2 done"


def test_swap_replaces_component_in_place():
    doc = LiveDoc()
    doc.append("note", body="scratch")
    doc.append("text", body="stays")
    swapped = doc.swap(0, "checklist", items=["one"])
    assert swapped.kind == "checklist"
    assert doc.parts[0].kind == "checklist"
    assert doc.parts[1].kind == "text"  # neighbors untouched


def test_components_stay_live_and_round_trip():
    doc = LiveDoc()
    check = doc.append("checklist", items=["a", "b"])
    check.check(0)
    table = doc.append("table", columns=["x"])
    table.add_row("1")
    revived = LiveDoc.from_dict(doc.to_dict())
    assert revived.parts[0].items[0]["done"] is True
    assert revived.parts[1].rows == [["1"]]
    with pytest.raises(ValueError):
        doc.append("hologram")


# -- livewire -----------------------------------------------------------


class _Sink:
    def __init__(self):
        self.calls = []

    def on_ping(self, *args):
        self.calls.append(("ping", args))
        return "pong"


def test_wire_fires_direct_call():
    board = Wireboard()
    sink = _Sink()
    board.wire("button", "click", sink, "on_ping")
    report = board.emit(sink, "button", "click", 1, 2)
    assert report == {"fired": 1, "results": ["pong"], "chain_handled": False}
    assert sink.calls == [("ping", (1, 2))]


def test_unhandled_event_walks_responder_chain():
    handled = []

    class Child(Responder):
        def respond(self, event, *a, **k):
            return False  # pass it up

    class Parent(Responder):
        def respond(self, event, *a, **k):
            handled.append(event)
            return True

    parent = Parent()
    child = Child(parent=parent)
    board = Wireboard()
    report = board.emit(child, "orphan", "save")
    assert report["chain_handled"] is True
    assert handled == ["save"]


def test_unwired_unhandled_reports_honestly():
    board = Wireboard()
    report = board.emit(object(), "ghost", "nope")
    assert report == {"fired": 0, "results": [], "chain_handled": False}
    with pytest.raises(AttributeError):
        board.wire("x", "y", object(), "missing_method")


# -- everkeep -----------------------------------------------------------


def test_journaled_state_rehydrates(tmp_path):
    journal = str(tmp_path / "keep.jsonl")
    keep = EverKeep(journal_path=journal)
    keep.set("a", 1)
    keep.set("b", [1, 2])
    keep.delete("a")
    revived = EverKeep(journal_path=journal)
    assert revived.state == {"b": [1, 2]}
    assert revived.depth() == 3


def test_unlimited_undo_redo_round_trip(tmp_path):
    keep = EverKeep(journal_path=str(tmp_path / "k.jsonl"))
    keep.set("x", 1)
    keep.set("x", 2)
    keep.set("y", "z")
    assert keep.undo() and keep.undo() and keep.undo()
    assert keep.state == {}
    assert not keep.undo()  # stack exhausted
    assert keep.redo() and keep.redo() and keep.redo()
    assert keep.state == {"x": 2, "y": "z"}
    assert not keep.redo()


def test_undo_survives_restart(tmp_path):
    journal = str(tmp_path / "k.jsonl")
    keep = EverKeep(journal_path=journal)
    keep.set("x", 1)
    keep.set("x", 2)
    keep.undo()  # journaled as inverse -> x back to 1
    revived = EverKeep(journal_path=journal)
    assert revived.state == {"x": 1}


def test_no_explicit_save_concept():
    keep = EverKeep()
    assert not hasattr(keep, "save")
    keep.execute(SetCommand("k", "v"))
    keep.execute(DeleteCommand("k"))
    assert keep.state == {}


# -- simplicity ---------------------------------------------------------


def test_clean_module_passes_budget():
    src = "def add(a, b):\n    return a + b\n"
    report = audit_source("tiny.py", src)
    assert report.passed
    assert report.functions == 1
    assert report.max_nesting == 1


def test_bloated_module_fails_with_reasons():
    src = "\n".join(["import os"] * 20 + [f"def f{i}():\n    pass" for i in range(30)])
    report = audit_source("blob.py", src, Budget(max_imports=5, max_functions=10))
    assert not report.passed
    assert any("imports" in f for f in report.failures)
    assert any("functions" in f for f in report.failures)


def test_nesting_and_surface_are_measured():
    src = (
        "CONSTANT_A = 1\nCONSTANT_B = 2\n"
        "def f():\n    if True:\n        for i in range(3):\n"
        "            while False:\n                pass\n"
    )
    report = audit_source("nest.py", src)
    assert report.max_nesting == 4  # def > if > for > while
    assert report.public_names == 3  # f + two constants


def test_audits_real_files_and_summarizes(tmp_path):
    target = tmp_path / "mod.py"
    target.write_text("X = 1\n")
    reports = audit_paths([target])
    summary = summarize(reports)
    assert summary == {"modules": 1, "passed": 1, "failed": 0}


# -- plumber ------------------------------------------------------------


def test_plumb_routes_to_matching_ports():
    plumb = Plumber()
    plumb.add_rule("invoice", "finance")
    plumb.add_rule("invoice", "archive")
    plumb.add_rule("urgent", "alerts")
    delivery = plumb.plumb("please review this INVOICE today")
    assert delivery.delivered
    assert delivery.ports == ["finance", "archive"]
    assert plumb.read("finance") == ["please review this INVOICE today"]
    assert plumb.read("alerts") == []


def test_rules_editable_at_runtime():
    plumb = Plumber()
    plumb.add_rule(r"\berr(or)?\b", "errors", regex=True)
    assert plumb.plumb("an error occurred").ports == ["errors"]
    assert plumb.remove_rule(r"\berr(or)?\b", "errors") is True
    assert plumb.plumb("an error occurred").ports == []
    assert plumb.list_rules() == []


def test_drain_empties_inbox():
    plumb = Plumber()
    plumb.add_rule("ping", "inbox")
    plumb.plumb("ping one")
    plumb.plumb("ping two")
    assert plumb.drain("inbox") == ["ping one", "ping two"]
    assert plumb.read("inbox") == []
    assert plumb.port_names() == ["inbox"]
