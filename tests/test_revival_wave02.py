"""Hermetic tests for revival wave 02 (gaps-b): dialects, declarative_build,
replicated_compute, ambient_overlay, graph_batch, paged_attn,
small_model_recipe, page_memory.

Pure reference-scale implementations; stdlib only, deterministic, no network.
"""

from __future__ import annotations

import dataclasses
import json
import math

import pytest

from levi.revival import (
    ambient_overlay,
    declarative_build,
    dialects,
    graph_batch,
    paged_attn,
    page_memory,
    replicated_compute,
    small_model_recipe,
)


# ---------------------------------------------------------------------------
# dialects
# ---------------------------------------------------------------------------


class TestDialects:
    def test_parse_nesting_and_roundtrip(self):
        block = dialects.parse('[draw box 10 20] [seq [lit "a"] [lit "b"]]')
        assert block == [["draw", "box", 10, 20], ["seq", ["lit", "a"], ["lit", "b"]]]
        assert dialects.parse(dialects.render(block)) == block

    def test_parse_errors(self):
        with pytest.raises(SyntaxError):
            dialects.parse("[unclosed")
        with pytest.raises(SyntaxError):
            dialects.parse("extra]")

    def test_parlex_matchers(self):
        p = dialects.make_parlex()
        env = {"text": "aab"}
        assert (
            p.run(dialects.parse('[match seq [[lit "a"] [lit "a"] [lit "b"]]]'), env)
            == "aab"
        )
        assert p.run(dialects.parse('[match seq [[lit "x"]]]'), env) is None
        assert (
            p.run(dialects.parse('[match many [lit "a"]]'), {"text": "aaab"}) == "aaa"
        )
        assert p.run(dialects.parse('[match either [[lit "x"] [lit "a"]]]'), env) == "a"

    def test_sigil_builds_tree(self):
        s = dialects.make_sigil()
        tree = s.run(
            dialects.parse(
                '[build col [[label "hi"] [button "ok"] [row [[label "x"]]]]]'
            )
        )
        assert tree["kind"] == "col"
        assert [c["kind"] for c in tree["children"]] == ["label", "button", "row"]
        assert tree["children"][0]["text"] == "hi"

    def test_sketch_display_list(self):
        s = dialects.make_sketch()
        cmds = s.run(dialects.parse('[draw pen "red" box 1 2 3 4 circle 5 6 7]'))
        assert cmds[0] == {"op": "box", "pen": "red", "args": [1.0, 2.0, 3.0, 4.0]}
        assert cmds[1]["op"] == "circle"

    def test_custom_dialect_registration(self):
        d = dialects.Dialect("calc")
        d.on("add", lambda _d, args, _e: sum(args))
        assert d.run(["add", 1, 2, 3]) == 6
        assert d.knows("add") and not d.knows("sub")


# ---------------------------------------------------------------------------
# declarative_build
# ---------------------------------------------------------------------------


class TestDeclarativeBuild:
    def _model(self):
        db = declarative_build
        return (
            db.SystemModel("web")
            .with_package(db.Package("app", "2.0", requires=("lib",)))
            .with_package(db.Package("lib", "1.0"))
            .with_file(db.FileEntry("/etc/app.conf", "port=80"))
            .with_env("MODE", "prod")
        )

    def test_install_order_respects_deps(self):
        steps = declarative_build.plan(self._model())
        installs = [s.detail for s in steps if s.kind == "install"]
        assert installs == ["lib==1.0", "app==2.0"]
        kinds = [s.kind for s in steps]
        assert kinds == ["install", "install", "write", "export"]

    def test_fingerprint_stable_and_order_free(self):
        db = declarative_build
        m1 = self._model()
        m2 = (
            db.SystemModel("web")
            .with_env("MODE", "prod")
            .with_file(db.FileEntry("/etc/app.conf", "port=80"))
            .with_package(db.Package("lib", "1.0"))
            .with_package(db.Package("app", "2.0", requires=("lib",)))
        )
        assert db.fingerprint(m1) == db.fingerprint(m2)
        m3 = m1.with_env("MODE", "dev")
        assert db.fingerprint(m1) != db.fingerprint(m3)

    def test_cycle_and_unknown_dep_rejected(self):
        db = declarative_build
        cyc = db.SystemModel(
            "c", packages=(db.Package("a", "1", ("b",)), db.Package("b", "1", ("a",)))
        )
        with pytest.raises(ValueError, match="cycle"):
            db.plan(cyc)
        missing = db.SystemModel("m", packages=(db.Package("a", "1", ("ghost",)),))
        with pytest.raises(ValueError, match="unknown dependency"):
            db.plan(missing)

    def test_build_sandbox_and_diff(self):
        db = declarative_build
        m = self._model()
        sb = db.build(m, db.Sandbox())
        assert sb.files["/etc/app.conf"] == "port=80"
        assert sb.env["MODE"] == "prod"
        assert "app==2.0" in sb.installed
        m2 = m.with_package(db.Package("extra", "0.1"))
        d = db.diff(m, m2)
        assert d["packages_added"] == ["extra==0.1"]
        assert d["files_added"] == []

    def test_manifests_immutable(self):
        m = self._model()
        with pytest.raises(dataclasses.FrozenInstanceError):
            m.name = "changed"  # frozen dataclass
        m2 = m.with_env("A", "b")
        assert ("A", "b") not in m.env and ("A", "b") in m2.env


# ---------------------------------------------------------------------------
# replicated_compute
# ---------------------------------------------------------------------------


class TestReplicatedCompute:
    def _mesh2(self):
        rc = replicated_compute
        mesh = rc.Mesh()
        a, b = rc.Replica("a"), rc.Replica("b")
        mesh.join(a)
        mesh.join(b)
        return mesh, a, b

    def test_replicas_converge_on_same_log(self):
        rc = replicated_compute
        mesh, a, b = self._mesh2()
        mesh.broadcast(rc.Op("set", {"key": "x", "value": 1}))
        mesh.broadcast(rc.Op("add", {"key": "x", "delta": 4}))
        mesh.broadcast(rc.Op("append", {"key": "log", "value": "hi"}))
        assert a.state == b.state == {"x": 5, "log": ["hi"]}
        assert mesh.converged()

    def test_deterministic_randomness_matches(self):
        rc = replicated_compute
        mesh, a, b = self._mesh2()
        mesh.broadcast(rc.Op("roll", {"key": "d6", "sides": 6}))
        assert a.state["d6"] == b.state["d6"]
        assert 1 <= a.state["d6"] <= 6

    def test_partition_and_catch_up(self):
        rc = replicated_compute
        mesh, a, b = self._mesh2()
        mesh.broadcast(rc.Op("set", {"key": "x", "value": 1}))
        mesh.simulate_partition("b", [rc.Op("add", {"key": "x", "delta": 10})])
        assert not mesh.converged()
        assert mesh.catch_up("b") == 1
        assert mesh.converged()
        assert b.state["x"] == 11

    def test_snapshot_restore(self):
        rc = replicated_compute
        mesh, a, b = self._mesh2()
        mesh.broadcast(rc.Op("set", {"key": "k", "value": "v"}))
        snap = a.snapshot()
        c = rc.replica_from_snapshot("c", snap)
        assert c.state_digest() == a.state_digest()
        assert c.tick == a.tick

    def test_unknown_op_rejected(self):
        rc = replicated_compute
        r = rc.Replica("solo")
        with pytest.raises(ValueError, match="unknown op"):
            r.apply(rc.Op("teleport", {}))


# ---------------------------------------------------------------------------
# ambient_overlay
# ---------------------------------------------------------------------------


class TestAmbientOverlay:
    def test_summon_captures_context(self):
        ao = ambient_overlay
        ov = ao.Overlay()
        ctx = ao.ScreenContext(app="editor", window="notes.txt", selection="buy milk")
        s = ov.summon(ctx)
        assert ov.current is s
        assert ov.run_panel("glance") == (
            "context: app='editor' window='notes.txt' selection='buy milk' | notes: 0"
        )

    def test_nested_summon_suspends(self):
        ao = ambient_overlay
        ov = ao.Overlay()
        first = ov.summon(ao.ScreenContext(app="a"))
        second = ov.summon(ao.ScreenContext(app="b"))
        assert ov.depth() == 2
        ov.dismiss()
        assert ov.current is first
        assert ov.depth() == 1
        assert second is not first

    def test_panels_clip_and_scratch(self):
        ao = ambient_overlay
        ov = ao.Overlay()
        ov.summon(ao.ScreenContext(app="browser", selection="  key insight  "))
        assert ov.run_panel("clip2note") == "clipped 11 chars"
        assert (
            ov.run_panel("scratch", {"jot": "todo: write it up"}) == "jotted (2 notes)"
        )
        out = ov.run_panel("scratch")
        assert "[browser] key insight" in out and "todo: write it up" in out

    def test_unknown_panel_and_empty_dismiss(self):
        ao = ambient_overlay
        ov = ao.Overlay()
        ov.summon()
        with pytest.raises(KeyError):
            ov.run_panel("nope")
        assert ao.Overlay().dismiss() is None
        with pytest.raises(RuntimeError):
            ao.Overlay().run_panel("glance")

    def test_serialization_roundtrip(self):
        ao = ambient_overlay
        ov = ao.Overlay()
        s = ov.summon(ao.ScreenContext(app="mail", selection="deadline friday"))
        ov.run_panel("clip2note")
        restored = ao.load_json(ao.dump_json(s))
        assert restored.context.app == "mail"
        assert restored.notes == s.notes
        assert json.loads(ao.dump_json(s))["notes"] == ["[mail] deadline friday"]


# ---------------------------------------------------------------------------
# graph_batch
# ---------------------------------------------------------------------------


class TestGraphBatch:
    def test_forward_matches_manual_math(self):
        gb = graph_batch
        g = gb.Graph()
        g.add(gb.Node("w", "const", payload=[[2.0, 0.0], [0.0, 3.0]]))
        g.add(gb.Node("x", "const", payload=[[1.0, 1.0]]))
        g.add(gb.Node("y", "matmul", inputs=("x", "w")))
        g.add(gb.Node("z", "relu", inputs=("y",)))
        vals = g.forward()
        assert vals["y"] == [[2.0, 3.0]]
        assert vals["z"] == [[2.0, 3.0]]

    def test_softmax_rows_sum_to_one(self):
        gb = graph_batch
        g = gb.Graph()
        g.add(gb.Node("x", "const", payload=[[1.0, 2.0, 3.0]]))
        g.add(gb.Node("s", "softmax", inputs=("x",)))
        row = g.forward()["s"][0]
        assert math.isclose(sum(row), 1.0)
        assert row[2] > row[1] > row[0]

    def test_mlp_builder_and_feed(self):
        gb = graph_batch
        g, out = gb.build_mlp(batch=2, dims=[3, 4, 2])
        vals = gb.feed_input(g, "x", [[1.0, 0.0, -1.0], [0.5, 0.5, 0.5]])
        assert len(vals[out]) == 2 and len(vals[out][0]) == 2
        # deterministic weights: same graph rebuilt gives same output
        g2, out2 = gb.build_mlp(batch=2, dims=[3, 4, 2])
        vals2 = gb.feed_input(g2, "x", [[1.0, 0.0, -1.0], [0.5, 0.5, 0.5]])
        assert vals[out] == vals2[out2]

    def test_offload_placement(self):
        gb = graph_batch
        g, _ = gb.build_mlp(batch=1, dims=[2, 2, 2, 2])
        sched = gb.Scheduler(g).place(default=gb.GPU, offload_every=2)
        lin_places = {n: p for n, p in sched.placement.items() if n.startswith("lin")}
        assert lin_places["lin1"] == gb.CPU  # every 2nd linear layer offloaded
        assert lin_places["lin0"] == gb.GPU
        assert sched.bytes_cpu > 0 and sched.bytes_gpu > 0

    def test_mixed_precision_accounting(self):
        gb = graph_batch
        g, _ = gb.build_mlp(batch=1, dims=[4, 4, 4])
        before = g.memory_bytes()
        gb.Scheduler(g).quantize(layer_from=1, dtype="fp16")
        after = g.memory_bytes()
        assert after < before  # fp16 halves the quantized layers' bytes

    def test_cycle_rejected(self):
        gb = graph_batch
        g = gb.Graph()
        g.add(gb.Node("a", "relu", inputs=("b",)))
        g.add(gb.Node("b", "relu", inputs=("a",)))
        with pytest.raises(ValueError, match="cycle"):
            g.topo()


# ---------------------------------------------------------------------------
# paged_attn
# ---------------------------------------------------------------------------


def _tok_vecs(layers, heads, dim, seed):
    import random

    rng = random.Random(seed)
    k = [[rng.uniform(-1, 1) for _ in range(heads * dim)] for _ in range(layers)]
    v = [[rng.uniform(-1, 1) for _ in range(heads * dim)] for _ in range(layers)]
    return k, v


class TestPagedAttn:
    def _engine(self):
        return paged_attn.PagedEngine(
            layers=2, n_heads=2, head_dim=4, block_size=4, pool_blocks=32
        )

    def test_prefill_and_gather_lengths(self):
        eng = self._engine()
        eng.new_sequence("s")
        toks = [_tok_vecs(2, 2, 4, i) for i in range(10)]
        eng.prefill("s", toks)
        assert eng.seqs["s"]["len"] == 10
        rows = eng.gather("s", layer=0)
        assert len(rows) == 10
        assert rows[0][0] == toks[0][0][0]

    def test_fork_shares_blocks(self):
        eng = self._engine()
        eng.new_sequence("a")
        eng.prefill("a", [_tok_vecs(2, 2, 4, i) for i in range(8)])
        used_before = eng.used_blocks()
        eng.fork("a", "b", 8)
        assert eng.used_blocks() == used_before  # sharing costs nothing
        assert eng.shared_blocks("a", "b") > 0

    def test_cow_on_write_to_shared_block(self):
        eng = self._engine()
        eng.new_sequence("a")
        eng.prefill("a", [_tok_vecs(2, 2, 4, i) for i in range(6)])
        eng.fork("a", "b", 6)  # b's tail block is mid-block and shared
        copies_before = eng.cow_copies
        eng.append_token("b", *_tok_vecs(2, 2, 4, 99))  # writes into shared tail block
        assert eng.cow_copies > copies_before
        # a's rows unchanged, b diverged
        assert eng.gather("a", 0)[-1][0] != eng.gather("b", 0)[-1][0]

    def test_decode_step_attends_over_cache(self):
        eng = self._engine()
        eng.new_sequence("s")
        eng.prefill("s", [_tok_vecs(2, 2, 4, i) for i in range(3)])
        q, _ = _tok_vecs(2, 2, 4, 123)
        outs = eng.decode_step("s", q)
        assert len(outs) == 2 and all(len(o) == 8 for o in outs)
        assert eng.seqs["s"]["len"] == 3  # decode does not itself append

    def test_eviction_frees_blocks(self):
        eng = self._engine()
        eng.new_sequence("low", priority=0)
        eng.new_sequence("high", priority=5)
        eng.prefill("low", [_tok_vecs(2, 2, 4, i) for i in range(8)])
        used = eng.used_blocks()
        victim = eng.evict_lowest_priority()
        assert victim == "low"
        assert eng.used_blocks() < used
        assert not eng.seqs["low"]["alive"]
        assert eng.preemptions == 1

    def test_stats_accounting(self):
        eng = self._engine()
        eng.new_sequence("s")
        eng.prefill("s", [_tok_vecs(2, 2, 4, i) for i in range(6)])
        st = eng.stats()
        assert st["used_blocks"] == 4  # 6 tokens, bs=4, 2 layers -> 2+2 blocks
        # kv bytes: 6 tokens * 2 layers * 2(K/V) * 2 heads * 4 dim * 4 bytes
        assert eng.kv_bytes() == 6 * 2 * 2 * 2 * 4 * 4
        assert st["wasted_slots"] == 4  # two half-full tail blocks

    def test_batch_scheduler_steps(self):
        eng = self._engine()
        sched = paged_attn.BatchScheduler(eng)
        for sid in ("s1", "s2"):
            eng.new_sequence(sid)
            eng.prefill(sid, [_tok_vecs(2, 2, 4, i) for i in range(2)])
        q, _ = _tok_vecs(2, 2, 4, 7)
        outs = sched.step(["s1", "s2"], {"s1": q, "s2": q})
        assert set(outs) == {"s1", "s2"}
        assert eng.seqs["s1"]["len"] == 3


# ---------------------------------------------------------------------------
# small_model_recipe
# ---------------------------------------------------------------------------


class TestSmallModelRecipe:
    def _recipe(self):
        r = small_model_recipe
        return r.Recipe(
            "tiny-synth",
            params=100_000_000,
            stages=(
                r.Stage(
                    "warm", 1_000_000_000, (("web", 0.7), ("books", 0.3)), 3e-4, 1e-4
                ),
                r.Stage(
                    "refine",
                    500_000_000,
                    (("web", 0.3), ("books", 0.5), ("code", 0.2)),
                    1e-4,
                    1e-5,
                ),
            ),
        )

    def test_overtrain_factor(self):
        r = self._recipe()
        # 1.5B tokens / (100M params * 20 tok/param) = 0.75x
        assert r.overtrain_factor() == pytest.approx(0.75)

    def test_mix_normalization_and_token_split(self):
        s = small_model_recipe.Stage("s", 1000, (("a", 2.0), ("b", 1.0)), 1e-3, 1e-4)
        assert s.normalized_mix() == {
            "a": pytest.approx(2 / 3),
            "b": pytest.approx(1 / 3),
        }
        split = s.tokens_per_dataset()
        assert sum(split.values()) == 1000

    def test_combined_mix_weighted_by_tokens(self):
        combined = self._recipe().combined_mix()
        assert math.isclose(sum(combined.values()), 1.0)
        assert combined["web"] > combined["code"]  # web dominates token mass

    def test_refine_produces_new_recipe(self):
        r = self._recipe()
        r2 = r.refine("refine", {"books": 2.0})
        assert (
            r2.stages[1].normalized_mix()["books"]
            > r.stages[1].normalized_mix()["books"]
        )
        assert (
            r.stages[1].normalized_mix() != r2.stages[1].normalized_mix()
        )  # original untouched

    def test_validate_catches_problems(self):
        r = small_model_recipe
        bad = r.Recipe(
            "bad", params=0, stages=(r.Stage("z", 0, (("a", 0.0),), 1e-3, 2e-3),)
        )
        problems = bad.validate()
        assert any("params" in p for p in problems)
        assert any("tokens" in p for p in problems)
        assert any("rises after decay" in p for p in problems)
        assert self._recipe().validate() == []

    def test_lr_schedule_shape(self):
        rows = small_model_recipe.learning_rate_schedule(
            self._recipe(), steps_per_stage=10
        )
        assert len(rows) == 20
        first_stage = [lr for name, _, lr in rows if name == "warm"]
        assert first_stage[0] >= first_stage[-1]  # decays within stage
        assert all(lr >= 0 for _, _, lr in rows)

    def test_brief_mentions_overtrain(self):
        brief = small_model_recipe.brief(self._recipe())
        assert "overtrain factor: 0.75x" in brief
        assert "stage warm" in brief and "stage refine" in brief


# ---------------------------------------------------------------------------
# page_memory
# ---------------------------------------------------------------------------


class TestPageMemory:
    def _mos(self, budget=100):
        pm = page_memory
        mos = pm.MemoryOS(token_budget=budget)
        mos.remember("p1", "levi is a synthetic organism", ("identity",))
        mos.remember("p2", "chauncey builds local-first systems", ("user",))
        mos.remember("p3", "the sky is blue and vast today", ("misc",))
        return mos

    def test_page_in_and_pressure(self):
        mos = self._mos()
        mos.main.page_in("p1")
        assert mos.main.is_resident("p1")
        assert 0 < mos.main.pressure() <= 1.0

    def test_lru_eviction_under_budget(self):
        pm = page_memory
        mos = pm.MemoryOS(token_budget=20)  # tiny budget
        mos.remember("a", "x" * 40)  # 10 tokens
        mos.remember("b", "y" * 40)
        mos.remember("c", "z" * 40)
        mos.main.page_in("a")
        mos.main.page_in("b")
        mos.main.page_in("c")  # must evict a (LRU)
        assert not mos.main.is_resident("a")
        assert mos.main.is_resident("c")
        assert mos.main.evictions >= 1
        # archive still holds it
        assert mos.archive.fetch("a").text == "x" * 40

    def test_read_faults_auto_page_in(self):
        mos = self._mos()
        assert mos.main.faults == 0
        text = mos.main.read("p2")
        assert "chauncey" in text
        assert mos.main.faults == 1
        assert mos.main.is_resident("p2")

    def test_page_out_and_pin(self):
        mos = self._mos()
        mos.main.page_in("p1")
        mos.main.pin("p1")
        assert mos.main.page_out("p1")  # explicit page-out still works
        assert not mos.main.is_resident("p1")
        assert mos.main.page_out("p1") is False  # already out

    def test_pinned_blocks_eviction(self):
        pm = page_memory
        mos = pm.MemoryOS(token_budget=20)
        mos.remember("a", "x" * 40)  # 10 tokens
        mos.remember("b", "y" * 80)  # 20 tokens: won't fit beside pinned a
        mos.main.page_in("a")
        mos.main.pin("a")
        with pytest.raises(MemoryError):
            mos.main.page_in("b")  # cannot evict pinned a, b doesn't fit

    def test_recall_ranks_relevant_pages(self):
        mos = self._mos()
        hits = mos.recall.recall("synthetic organism")
        assert hits[0][0] == "p1"
        assert mos.recall.recall("quantum zebra") == []

    def test_stats(self):
        mos = self._mos()
        mos.main.read("p1")
        st = mos.stats()
        assert st["archived_pages"] == 3
        assert st["resident_pages"] == 1
        assert st["page_faults"] == 1
