"""Hermetic tests for revival batch B13 (SI internals 1): kvcache, tiledattn,
quant, batchsched, moerouter, steplog, toolcall, mixplan.

Pure reference-scale implementations; stdlib only, deterministic, no network.
"""

from __future__ import annotations

import math
import random

import pytest

from levi.revival import (
    batchsched,
    kvcache,
    mixplan,
    moerouter,
    quant,
    steplog,
    tiledattn,
    toolcall,
)


def _rand_matrix(rows: int, cols: int, seed: int):
    rng = random.Random(seed)
    return [[rng.uniform(-1, 1) for _ in range(cols)] for _ in range(rows)]


# ---------------------------------------------------------------------------
# kvcache
# ---------------------------------------------------------------------------


class TestKVCache:
    def test_decode_grows_cache_and_returns_vector(self):
        kv = kvcache.KVCache(layers=2, n_heads=4, head_dim=8)
        kv.prefill([1, 2, 3])
        assert kv.seq_len() == 3
        out = kv.decode_step(4)
        assert len(out) == 8
        assert all(math.isfinite(x) for x in out)
        assert kv.seq_len() == 4  # new token's K/V cached

    def test_output_is_convex_combination_of_values(self):
        kv = kvcache.KVCache(layers=1, n_heads=2, head_dim=4)
        kv.prefill([10, 20])
        out = kv.decode_step(30)
        # softmax weights in (0,1): each output dim lies within the
        # min/max span of the cached value dims (before the new append).
        vals = [v for layer_vals in [kv.values[0][:2]] for v in layer_vals]
        for d in range(4):
            lo = min(v[d] for v in vals)
            hi = max(v[d] for v in vals)
            assert lo - 1e-9 <= out[d] <= hi + 1e-9

    def test_bytes_accounting_and_evict(self):
        kv = kvcache.KVCache(layers=2, n_heads=2, head_dim=8)
        kv.prefill([1, 2, 3, 4])
        before = kv.bytes()
        assert before == 2 * 2 * 4 * 8 * 4  # layers*2(K+V)*rows*dim*fp32
        kv.evict(0, keep=2)
        assert kv.seq_len(0) == 2
        assert kv.bytes() < before


class TestPagedKVCache:
    def _fill(self, pg, seq, n, dim=8):
        rng = random.Random(42)
        for _ in range(n):
            pg.append(
                seq,
                [rng.uniform(-1, 1) for _ in range(dim)],
                [rng.uniform(-1, 1) for _ in range(dim)],
            )

    def test_prefix_sharing_and_copy_on_write(self):
        pg = kvcache.PagedKVCache(block_size=4, pool_blocks=16)
        pg.new_sequence("a")
        self._fill(pg, "a", 6)
        pg.share_prefix("a", "b", tokens=6)
        assert pg.shared_prefix_saving("a", "b") == 2  # both blocks shared
        assert pg.cow_copies == 0
        # Writing to b's second (shared) block triggers CoW.
        rng = random.Random(1)
        pg.append(
            "b",
            [rng.uniform(-1, 1) for _ in range(8)],
            [rng.uniform(-1, 1) for _ in range(8)],
        )
        assert pg.cow_copies == 1
        assert pg.shared_prefix_saving("a", "b") == 1  # first block still shared
        assert pg.lengths["a"] == 6 and pg.lengths["b"] == 7

    def test_free_returns_blocks(self):
        pg = kvcache.PagedKVCache(block_size=4, pool_blocks=16)
        pg.new_sequence("a")
        self._fill(pg, "a", 6)
        pg.share_prefix("a", "b", tokens=6)
        used = pg.used_blocks()
        assert used == 2  # shared prefix costs blocks once
        pg.free("a")
        pg.free("b")
        assert pg.used_blocks() == 0

    def test_paged_decode_matches_contiguous(self):
        kv = kvcache.KVCache(layers=1, n_heads=2, head_dim=8)
        kv.prefill([1, 2, 3])
        pg = kvcache.PagedKVCache(block_size=2, pool_blocks=16)
        pg.new_sequence("s")
        for pos, _tid in enumerate([1, 2, 3]):
            pg.append("s", kv.keys[0][pos], kv.values[0][pos])
        q = kv._project(9, 0, "q")
        ref = kv.decode_step(9, layer=0)
        got = pg.decode_step("s", q)
        assert max(abs(a - b) for a, b in zip(ref, got, strict=True)) < 1e-9


# ---------------------------------------------------------------------------
# tiledattn
# ---------------------------------------------------------------------------


class TestTiledAttn:
    def test_matches_naive(self):
        q = _rand_matrix(7, 5, 1)
        k = _rand_matrix(11, 5, 2)
        v = _rand_matrix(11, 5, 3)
        ref = tiledattn.naive_attention(q, k, v)
        got = tiledattn.tiled_attention(q, k, v, tile=4)
        assert tiledattn.max_abs_diff(ref, got) < 1e-9

    def test_tile_larger_than_sequence(self):
        q = _rand_matrix(3, 4, 4)
        k = _rand_matrix(5, 4, 5)
        v = _rand_matrix(5, 4, 6)
        ref = tiledattn.naive_attention(q, k, v)
        got = tiledattn.tiled_attention(q, k, v, tile=64)
        assert tiledattn.max_abs_diff(ref, got) < 1e-9

    def test_single_token_and_accounting(self):
        q = _rand_matrix(1, 6, 7)
        k = _rand_matrix(9, 6, 8)
        v = _rand_matrix(9, 6, 9)
        ref = tiledattn.naive_attention(q, k, v)
        got = tiledattn.tiled_attention(q, k, v, tile=3)
        assert tiledattn.max_abs_diff(ref, got) < 1e-9
        acct = tiledattn.attention_flops_saved(n=128, d=64, tile=16)
        assert acct["ratio"] == pytest.approx(128 * 128 / (16 * 64))
        assert acct["tiled_working_elements"] < acct["naive_score_elements"]


# ---------------------------------------------------------------------------
# quant
# ---------------------------------------------------------------------------


class TestQuant:
    def test_roundtrip_error_bounded_by_half_step(self):
        w = quant.demo_tensor(bits=4, n=1024, seed=3)
        qt = quant.quantize(w, bits=4)
        rec = quant.dequantize(qt)
        assert len(rec) == len(w)
        max_step = max(sb.sub_scale for sb in qt.superblocks for sb in sb.subblocks)
        err = max(abs(a - b) for a, b in zip(w, rec, strict=True))
        assert err <= max_step / 2 + 1e-12

    def test_compression_beats_fp32(self):
        w = quant.demo_tensor(n=1024)
        qt = quant.quantize(w, bits=4)
        assert qt.compression() > 1.0
        assert qt.bytes_used() < qt.fp32_bytes()

    def test_dequant_matvec_matches_float(self):
        rng = random.Random(5)
        w = [rng.gauss(0, 0.3) for _ in range(32)]  # 4x8 matrix
        x = [rng.uniform(-1, 1) for _ in range(8)]
        qt = quant.quantize(w, bits=4)
        got = quant.dequant_matvec(qt, x)
        ref = [sum(w[r * 8 + c] * x[c] for c in range(8)) for r in range(4)]
        assert max(abs(a - b) for a, b in zip(got, ref, strict=True)) < 0.5

    def test_kv_bytes_saved_and_per_tensor_bits(self):
        rows = [([0.1 * i] * 16, [0.2 * i] * 16) for i in range(4)]
        acct = quant.kv_bytes_saved(rows, bits=4)
        assert acct["ratio"] > 1.0
        assert quant.select_bits("attn") == 8
        assert quant.select_bits("mlp") == 4
        assert quant.select_bits("embed") >= quant.select_bits("mlp")


# ---------------------------------------------------------------------------
# batchsched
# ---------------------------------------------------------------------------


def _sched(pool_blocks=32):
    return batchsched.Scheduler(
        block_size=4,
        pool_blocks=pool_blocks,
        step_budget=16,
        max_running=4,
        prefill_chunk=8,
    )


class TestBatchSched:
    def test_all_requests_complete_and_decodes_never_starve(self):
        s = _sched()
        s.submit(batchsched.Request("r1", prompt_len=20, max_new_tokens=6))
        s.submit(batchsched.Request("r2", prompt_len=6, max_new_tokens=10))
        s.submit(batchsched.Request("r3", prompt_len=40, max_new_tokens=4))
        s.run_until_done()
        assert {r.req_id for r in s.finished} == {"r1", "r2", "r3"}
        assert s.decodes_never_starved()

    def test_waiting_joins_mid_flight(self):
        s = batchsched.Scheduler(
            block_size=4, pool_blocks=64, step_budget=8, max_running=2, prefill_chunk=4
        )
        s.submit(batchsched.Request("a", prompt_len=4, max_new_tokens=12))
        s.submit(batchsched.Request("b", prompt_len=4, max_new_tokens=12))
        s.submit(batchsched.Request("c", prompt_len=4, max_new_tokens=2))
        s.run_until_done()
        # 'c' was admitted at some step > 1 while others were still running.
        admit_steps = [e.step for e in s.events if "c" in e.admitted]
        assert admit_steps and admit_steps[0] > 1
        assert len(s.finished) == 3

    def test_preemption_under_pressure_still_completes(self):
        s = _sched(pool_blocks=8)  # too small for both requests at once
        s.submit(batchsched.Request("x", prompt_len=16, max_new_tokens=8, priority=1))
        s.submit(batchsched.Request("y", prompt_len=16, max_new_tokens=8, priority=0))
        s.run_until_done()
        assert {r.req_id for r in s.finished} == {"x", "y"}
        assert any(e.preempted for e in s.events)
        assert any(r.preempted > 0 for r in s.finished)

    def test_chunked_prefill_does_not_block_decodes(self):
        s = _sched()
        s.submit(batchsched.Request("big", prompt_len=64, max_new_tokens=3))
        s.submit(batchsched.Request("small", prompt_len=2, max_new_tokens=8))
        s.run_until_done()
        assert s.decodes_never_starved()
        # The giant prefill was served in chunks across many steps.
        chunks = [e.prefill_chunks.get("big", 0) for e in s.events]
        assert sum(chunks) == 64 and max(chunks) <= 8


# ---------------------------------------------------------------------------
# moerouter
# ---------------------------------------------------------------------------


class TestMoERouter:
    def test_capacity_respected(self):
        router = moerouter.MoERouter(
            n_experts=4, dim=6, top_k=2, capacity_factor=1.0, noise=0.0, seed=1
        )
        tokens = _rand_matrix(16, 6, 9)
        routing = router.route(tokens, seed=0)
        cap = math.ceil(1.0 * 16 * 2 / 4)
        assert all(h <= cap for h in routing.load_histogram(4))

    def test_forward_is_weighted_expert_mix(self):
        router = moerouter.MoERouter(
            n_experts=3, dim=4, top_k=2, capacity_factor=8.0, noise=0.0, seed=2
        )
        experts = [lambda x, s=s: [v * (s + 1) for v in x] for s in range(3)]
        tokens = _rand_matrix(5, 4, 10)
        out, routing = router.forward(tokens, experts, seed=0)
        assert len(out) == 5 and all(len(r) == 4 for r in out)
        # Weights per token renormalize to 1.
        for pairs in routing.assignments.values():
            assert sum(w for _, w in pairs) == pytest.approx(1.0)

    def test_aux_loss_punishes_collapse(self):
        balanced = moerouter.Routing(
            assignments={t: [(t % 4, 1.0)] for t in range(16)},
            gate_probs=[[0.25] * 4 for _ in range(16)],
        )
        collapsed = moerouter.Routing(
            assignments={t: [(0, 1.0)] for t in range(16)},
            gate_probs=[[1.0, 0.0, 0.0, 0.0] for _ in range(16)],
        )
        assert moerouter.MoERouter.aux_loss(balanced, 4) < moerouter.MoERouter.aux_loss(
            collapsed, 4
        )

    def test_expert_choice_balances_by_construction(self):
        scores = _rand_matrix(12, 4, 11)
        chosen = moerouter.expert_choice_route(scores, k_per_expert=3)
        loads = [0] * 4
        for pairs in chosen.values():
            for e, _ in pairs:
                loads[e] += 1
        assert loads == [3, 3, 3, 3]

    def test_bias_nudging_reduces_load_spread(self):
        bal = moerouter.AuxLossFreeBalancer(n_experts=2, gamma=0.05)
        # Half the tokens strongly prefer expert 0, half only weakly.
        probs = [[0.9, 0.1]] * 5 + [[0.55, 0.45]] * 5
        before = bal.load_std(bal.route_with_bias(probs))
        for _ in range(3):
            bal.nudge(bal.route_with_bias(probs))
        after = bal.load_std(bal.route_with_bias(probs))
        assert before > 0 and after < before


# ---------------------------------------------------------------------------
# steplog
# ---------------------------------------------------------------------------


def _tools():
    reg = steplog.ToolRegistry()
    reg.register("add", lambda a, b: a + b)
    reg.register("upper", lambda s: s.upper())
    return reg


class TestStepLog:
    def test_loop_runs_tools_and_returns_answer(self):
        policy = steplog.scripted_policy(
            [
                steplog.ActionStep(
                    tool="add", args={"a": 2, "b": 3}, thought="add them"
                ),
                steplog.ActionStep(tool="upper", args={"s": "done"}),
                steplog.StopStep(answer="DONE"),
            ]
        )
        agent = steplog.Agent(policy, tools=_tools())
        answer = agent.run("do the thing", system_prompt="be terse")
        assert answer == "DONE"
        obs = agent.log.of_type(steplog.ObservationStep)
        assert [o.result for o in obs] == [5, "DONE"]
        msgs = agent.log.write_memory_to_messages()
        roles = [m["role"] for m in msgs]
        assert roles[0] == "system" and roles[1] == "user"

    def test_planning_step_recorded_and_addressable(self):
        policy = steplog.scripted_policy(
            [
                steplog.PlanningStep(plan="1. add\n2. shout", facts=["a=2"]),
                steplog.ActionStep(tool="add", args={"a": 1, "b": 1}),
                steplog.StopStep(answer="ok"),
            ]
        )
        agent = steplog.Agent(policy, tools=_tools())
        agent.run("plan then act")
        assert agent.log.plan is not None
        assert agent.log.plan.plan.startswith("1. add")
        assert any(
            "[PLAN]" in m["content"] for m in agent.log.write_memory_to_messages()
        )

    def test_unknown_tool_becomes_error_observation(self):
        policy = steplog.scripted_policy(
            [
                steplog.ActionStep(tool="nope", args={}),
                steplog.StopStep(answer="recovered"),
            ]
        )
        agent = steplog.Agent(policy, tools=_tools())
        assert agent.run("try missing tool") == "recovered"
        obs = agent.log.of_type(steplog.ObservationStep)
        assert obs[0].error and "unknown tool" in obs[0].error

    def test_max_steps_guard(self):
        policy = steplog.scripted_policy(
            [steplog.ActionStep(tool="add", args={"a": 1, "b": 1})] * 50
        )
        agent = steplog.Agent(policy, tools=_tools(), max_steps=5)
        assert (
            agent.run("loop forever") == "(max steps reached without a stop decision)"
        )


# ---------------------------------------------------------------------------
# toolcall
# ---------------------------------------------------------------------------


def _specs():
    return {
        "add": toolcall.ToolSpec(
            name="add",
            description="add two numbers",
            parameters={
                "type": "object",
                "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                "required": ["a", "b"],
            },
            fn=lambda a, b: a + b,
        ),
        "greet": toolcall.ToolSpec(
            name="greet",
            description="greet someone",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}, "loud": {"type": "boolean"}},
                "required": ["name"],
            },
            fn=lambda name, loud=False: ("HI " if loud else "hi ") + name,
        ),
    }


class TestToolCall:
    def test_json_round_trip(self):
        specs = _specs()
        text = toolcall.JsonProtocol.emit("add", {"a": 2, "b": 3})
        name, args = toolcall.JsonProtocol.parse(text)
        assert (name, args) == ("add", {"a": 2, "b": 3})
        assert toolcall.JsonProtocol.validate(name, args, specs) == []
        assert toolcall.JsonProtocol.execute(name, args, specs) == 5

    def test_json_validation_catches_problems(self):
        specs = _specs()
        assert toolcall.JsonProtocol.validate("add", {"a": 1}, specs) != []
        assert toolcall.JsonProtocol.validate("nope", {}, specs) != []
        assert (
            toolcall.JsonProtocol.validate("greet", {"name": "x", "loud": "yes"}, specs)
            != []
        )
        with pytest.raises(toolcall.SchemaError):
            toolcall.JsonProtocol.parse("{not json")

    def test_code_composition_with_variables_and_loops(self):
        specs = _specs()
        code = toolcall.CodeProtocol.emit(
            [("add", {"a": 2, "b": 3}), ("add", {"a": 10, "b": 20})],
            assign_to=["x", "y"],
        )
        code += "\ntotal = 0\nfor v in [x, y]:\n    total = add(a=total, b=v)"
        env = toolcall.CodeProtocol.run(code, specs)
        assert env["x"] == 5 and env["y"] == 30 and env["total"] == 35

    def test_code_rejects_unsafe(self):
        specs = _specs()
        with pytest.raises(toolcall.UnsafeCode):
            toolcall.CodeProtocol.run("import os", specs)
        with pytest.raises(toolcall.UnsafeCode):
            toolcall.CodeProtocol.run("__import__('os')", specs)
        with pytest.raises(toolcall.UnsafeCode):
            toolcall.CodeProtocol.run("x = (1).__class__", specs)

    def test_react_round_trip_and_fragility(self):
        specs = _specs()
        text = toolcall.ReactProtocol.emit("think it through", "add", {"a": 4, "b": 5})
        parsed = toolcall.ReactProtocol.parse(text)
        assert parsed.thought == "think it through"
        assert parsed.action == "add"
        assert toolcall.ReactProtocol.execute(parsed, specs) == 9
        assert toolcall.ReactProtocol.FRAGILE is True
        with pytest.raises(toolcall.SchemaError):
            toolcall.ReactProtocol.parse("just some prose, no structure")
        assert toolcall.ReactProtocol.parse_lenient("garbage") is None


# ---------------------------------------------------------------------------
# mixplan
# ---------------------------------------------------------------------------


def _planner_slices():
    return [
        mixplan.DataSlice("web", tokens=1_000_000, quality=0.6, tags=["general"]),
        mixplan.DataSlice("math", tokens=50_000, quality=0.9, tags=["reasoning"]),
        mixplan.DataSlice("junk", tokens=2_000_000, quality=0.2, tags=["general"]),
    ]


class TestMixPlan:
    def test_refine_rewards_helpful_slices(self):
        slices = _planner_slices()
        by_name = {s.name: s for s in slices}
        stage = mixplan.Stage(
            name="general",
            mix={"web": 0.5, "math": 0.25, "junk": 0.25},
            eval_hooks=[mixplan.quality_coverage_hook(by_name)],
        )
        planner = mixplan.MixPlanner(slices, [stage])
        refined = planner.refine_stage(stage)
        assert refined.mix["math"] > stage.mix["math"]  # high quality earns weight
        assert refined.mix["junk"] < stage.mix["junk"]  # low quality loses weight

    def test_run_converges_and_records_history(self):
        slices = _planner_slices()
        by_name = {s.name: s for s in slices}
        stages = [
            mixplan.Stage(
                "s1",
                {"web": 0.6, "math": 0.2, "junk": 0.2},
                [mixplan.quality_coverage_hook(by_name)],
            ),
            mixplan.Stage(
                "s2",
                {"web": 0.3, "math": 0.5, "junk": 0.2},
                [mixplan.quality_coverage_hook(by_name)],
            ),
        ]
        planner = mixplan.MixPlanner(slices, stages, max_iters=6)
        refined = planner.run()
        assert len(refined) == 2
        assert len(planner.history) == 2  # one report per stage
        summary = planner.plan_summary()
        assert summary[0]["stage"] == "s1"
        top_slice = summary[1]["mix"][0][0]
        assert top_slice == "math"  # instruction-ish stage favors quality

    def test_aggressive_dedup(self):
        docs = [
            "the quick brown fox jumps over the lazy dog",
            "the quick brown fox jumps over the lazy dog",  # exact dup
            "the quick brown fox jumps over the lazy cat",  # near dup
            "a completely different sentence about synthetic minds",
        ]
        # Jaccard over 5-shingles: near-dup pair shares 4/6 shingles = 0.667.
        kept, stats = mixplan.aggressive_dedup(docs, near_dup_threshold=0.6)
        assert stats["exact_dups"] == 1
        assert stats["near_dups"] == 1
        assert stats["kept"] == 2
        assert kept[0] == docs[0] and kept[1] == docs[3]

    def test_gap_detector_flags_low_quality_and_thin(self):
        slices = _planner_slices() + [
            mixplan.DataSlice("rare_lang", tokens=500, quality=0.8, tags=["niche"]),
        ]
        gaps = mixplan.find_gaps(slices)
        by_name = {g.slice_name: g for g in gaps}
        assert "junk" in by_name and "low-quality" in by_name["junk"].reason
        assert "rare_lang" in by_name and "thin" in by_name["rare_lang"].reason
        assert "web" not in by_name  # healthy slice: no gap
        assert "math" not in by_name
