"""Tests for levi.revival.soar — impasse/subgoal/chunking (hermetic)."""

from __future__ import annotations

import pytest

from levi.revival.soar import (
    Deliberation,
    Procedure,
    ProcedureLibrary,
    demo,
)


def _deploy_deliberation(service: str = "api", version: str = "3") -> Deliberation:
    d = Deliberation(f"deploy service {service} version {version}")
    d.record(f"service {service} version {version} is stopped",
             f"resolve-deps {service} version {version}",
             f"deps for {service} version {version} resolved")
    d.record(f"deps for {service} version {version} resolved",
             f"build {service} version {version}",
             f"{service} version {version} built")
    d.record(f"{service} version {version} built",
             f"smoke-test {service} version {version}",
             f"{service} version {version} healthy")
    d.succeed()
    return d


def test_chunk_abstracts_constants_into_variables():
    proc = _deploy_deliberation().chunk()
    assert proc.goal_pattern == "deploy service api version $x1"
    assert proc.variables == ["$x1"]
    # plain words stay literal; constants become variables in steps too
    assert proc.steps[0]["operator"] == "resolve-deps api version $x1"
    assert proc.steps[2]["result"] == "api version $x1 healthy"


def test_chunk_multiple_constants_in_order_of_appearance():
    d = Deliberation("migrate db shard 7 to node 2")
    d.record("shard 7 is primary", "copy shard 7 to node 2", "shard 7 copied to node 2")
    d.succeed()
    proc = d.chunk()
    assert proc.goal_pattern == "migrate db shard $x1 to node $x2"
    assert proc.variables == ["$x1", "$x2"]


def test_chunk_requires_success():
    d = Deliberation("do the thing")
    d.record("s", "op", "r")
    d.fail()
    with pytest.raises(RuntimeError, match="successful deliberation"):
        d.chunk()


def test_chunk_requires_nonempty_trace():
    d = Deliberation("do the thing")
    d.succeed()
    with pytest.raises(RuntimeError, match="empty trace"):
        d.chunk()


def test_no_constants_means_no_variables_documented():
    """Conservative by design: plain-word goals generalize to themselves."""
    d = Deliberation("restart the web tier")
    d.record("web tier is down", "restart web tier", "web tier is up")
    d.succeed()
    proc = d.chunk()
    assert proc.variables == []
    assert proc.goal_pattern == "restart the web tier"


def test_recall_matches_second_problem_with_bindings():
    lib = ProcedureLibrary()
    lib.add(_deploy_deliberation().chunk())
    hit = lib.recall("deploy service api version 4")
    assert hit is not None
    proc, bindings, score = hit
    assert bindings == {"$x1": "4"}
    assert score == 1.0
    assert proc.goal_pattern == "deploy service api version $x1"


def test_recall_rejects_unrelated_goal():
    lib = ProcedureLibrary()
    lib.add(_deploy_deliberation().chunk())
    assert lib.recall("bake a chocolate cake") is None
    assert lib.recall("deploy service api") is None  # arity mismatch
    assert lib.recall("deploy database api version 4") is None  # literal mismatch


def test_recall_rejects_inconsistent_variable_binding():
    lib = ProcedureLibrary()
    d = Deliberation("sync 5 to 5")
    d.record("s", "op", "r")
    d.succeed()
    lib.add(d.chunk())  # pattern: "sync $x1 to $x1"
    assert lib.recall("sync 5 to 5") is not None
    assert lib.recall("sync 5 to 6") is None  # $x1 cannot be both 5 and 6


def test_recall_threshold_filters():
    lib = ProcedureLibrary()
    lib.add(_deploy_deliberation().chunk())
    assert lib.recall("deploy service api version 4", threshold=1.0) is not None
    assert lib.recall("deploy service api version 4", threshold=1.1) is None


def test_instantiate_substitutes_bindings():
    proc = _deploy_deliberation().chunk()
    steps = proc.instantiate({"$x1": "9"})
    assert steps[0]["operator"] == "resolve-deps api version 9"
    assert steps[1]["result"] == "api version 9 built"


def test_persistence_roundtrip(tmp_path):
    lib = ProcedureLibrary()
    lib.add(_deploy_deliberation().chunk(provenance="test"))
    path = tmp_path / "procs.json"
    lib.save(path)
    lib2 = ProcedureLibrary(path)
    assert len(lib2) == 1
    hit = lib2.recall("deploy service api version 2")
    assert hit is not None
    proc, bindings, score = hit
    assert bindings == {"$x1": "2"}
    assert proc.provenance == "test"


def test_save_without_path_raises():
    lib = ProcedureLibrary()
    with pytest.raises(ValueError, match="no path"):
        lib.save()


def test_demo_second_problem_solved_from_chunk():
    out = demo()
    assert out["goal_pattern"] == "deploy service api version $x1"
    assert out["variables"] == ["$x1"]
    assert out["bindings"] == {"$x1": "4"}
    assert out["score"] == 1.0
    assert out["deliberated_problem_2"] is False
    # replayed operators carry the NEW constants, old shape
    assert out["replayed_operators"] == [
        "resolve-deps api version 4",
        "build api version 4",
        "smoke-test api version 4",
    ]


def test_deliberation_record_validation():
    d = Deliberation("g")
    with pytest.raises(ValueError, match="non-empty string"):
        d.record("", "op", "r")
    with pytest.raises(ValueError, match="goal must be"):
        Deliberation("")
    d.succeed()
    with pytest.raises(RuntimeError, match="already concluded"):
        d.record("s", "op", "r")


def test_procedure_serialization():
    proc = _deploy_deliberation().chunk()
    d = proc.to_dict()
    proc2 = Procedure.from_dict(d)
    assert proc2.goal_pattern == proc.goal_pattern
    assert proc2.steps == proc.steps
    assert proc2.variables == proc.variables
