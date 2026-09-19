"""Hermetic tests for wave 17 revival modules (cost-cutting b)."""

from __future__ import annotations

import pytest

from levi.revival import (
    agent_sandbox,
    batch_inference_discount,
    llm_cache,
    microvm,
    namespace_isolation,
    p2p_cdn,
    p2p_sync,
    scratch_images,
)
from levi.revival.agent_sandbox import SandboxSpec, recommended
from levi.revival.batch_inference_discount import (
    BatchWindow,
    InferenceRequest,
    discount_for,
    price,
    report,
)
from levi.revival.llm_cache import LLMCache, SemanticCache
from levi.revival.microvm import Fleet, MicroVM, Workload, pick_lane
from levi.revival.namespace_isolation import JobSpec, plan, validate
from levi.revival.p2p_cdn import Swarm, flash_crowd
from levi.revival.p2p_sync import Peer, make_manifest, sync_mesh, verify_manifest


def test_origins():
    pairs = {
        batch_inference_discount: "levi-revival/batch_inference_discount",
        llm_cache: "levi-revival/llm_cache",
        namespace_isolation: "levi-revival/namespace_isolation",
        agent_sandbox: "levi-revival/agent_sandbox",
        microvm: "levi-revival/microvm",
        scratch_images: "levi-revival/scratch_images",
        p2p_sync: "levi-revival/p2p_sync",
        p2p_cdn: "levi-revival/p2p_cdn",
    }
    for module, slug in pairs.items():
        assert module.ORIGIN == slug


# --- batch_inference_discount ---


def test_discount_tiers():
    assert discount_for(0) == 0.0
    assert discount_for(9.9) == 0.0
    assert discount_for(10) == 0.3
    assert discount_for(60) == 0.4
    assert discount_for(240) == 0.5
    assert discount_for(10_000) == 0.5


def test_price_math():
    assert price(1000, 0.0) == pytest.approx(1.00)
    assert price(1000, 0.5) == pytest.approx(0.50)
    assert price(0, 0.5) == 0.0
    with pytest.raises(ValueError):
        price(-1, 0.0)
    with pytest.raises(ValueError):
        price(100, 1.5)


def test_realtime_never_waits():
    window = BatchWindow(target_batch_size=8)
    window.submit(InferenceRequest("rt", 100, 50, tolerance_min=0, submitted_at=0))
    window.submit(InferenceRequest("slow", 100, 50, tolerance_min=240, submitted_at=0))
    released = window.collect(now_min=1)
    assert [r.request_id for b in released for r in b.requests] == ["rt"]
    assert released[0].discount == 0.0
    assert window.pending() == 1  # the delay-tolerant one keeps waiting


def test_batch_releases_at_target_size_and_reports_savings():
    window = BatchWindow(target_batch_size=2)
    for i in range(2):
        window.submit(
            InferenceRequest(f"b{i}", 1000, 0, tolerance_min=300, submitted_at=0)
        )
    released = window.collect(now_min=1)
    assert len(released) == 1
    assert released[0].discount == 0.5
    rep = report(released)
    assert rep.requests == 2 and rep.batched == 2
    assert rep.savings_fraction == pytest.approx(0.5)
    assert rep.realtime_cost == pytest.approx(2.0)
    assert rep.scheduled_cost == pytest.approx(1.0)


# --- llm_cache ---


def test_exact_hit_normalizes_cosmetics():
    cache = LLMCache(capacity=8, ttl_seconds=60)
    assert cache.get("Hello,  World?") is None
    cache.put("Hello, World?", "hi there", tokens=40, now=1000.0)
    assert cache.get("hello   world", now=1001.0) == "hi there"
    assert cache.get("  HELLO   WORLD! ", now=1002.0) == "hi there"
    assert cache.stats.hits == 2
    assert cache.stats.tokens_saved == 80


def test_ttl_expiry_and_purge():
    cache = LLMCache(capacity=8, ttl_seconds=10)
    cache.put("prompt", "resp", tokens=5, now=0.0)
    assert cache.get("prompt", now=5.0) == "resp"
    assert cache.get("prompt", now=11.0) is None
    assert cache.stats.misses == 1
    cache.put("old", "x", tokens=1, now=0.0)
    assert cache.purge_expired(now=100.0) == 1
    assert len(cache) == 0


def test_lru_eviction_counts():
    cache = LLMCache(capacity=2, ttl_seconds=3600)
    cache.put("a", "A", tokens=1, now=0.0)
    cache.put("b", "B", tokens=1, now=0.0)
    cache.get("a", now=1.0)  # a becomes most-recent
    cache.put("c", "C", tokens=1, now=2.0)  # evicts b
    assert cache.stats.evictions == 1
    assert cache.get("b", now=3.0) is None
    assert cache.get("a", now=3.0) == "A"


def test_semantic_similarity_hit_and_miss():
    cache = SemanticCache(capacity=8, ttl_seconds=3600, similarity_threshold=0.7)
    cache.put("how do i reset my password", "use the reset link", tokens=25, now=0.0)
    hit = cache.get_similar("how can i reset my password", now=1.0)
    assert hit is not None
    response, score = hit
    assert response == "use the reset link"
    assert score >= 0.7
    assert cache.stats.semantic_hits == 1
    assert cache.stats.tokens_saved == 25
    assert cache.get_similar("quantum tunneling explained simply", now=2.0) is None


# --- namespace_isolation ---


def test_offline_job_gets_minimal_namespaces():
    job = JobSpec(name="worker", readonly_paths=["/data"])
    recipe = plan(job)
    assert recipe.namespaces == ["user", "mount", "pid", "ipc", "uts"]
    assert "net" not in recipe.namespaces
    assert recipe.footprint_kb == 6
    assert recipe.unshare_argv[:2] == ["unshare", "-U"]
    assert "--map-root-user" in recipe.unshare_argv
    assert validate(recipe, job) == []


def test_network_job_gets_net_namespace():
    job = JobSpec(name="fetcher", needs_network=True)
    recipe = plan(job)
    assert "net" in recipe.namespaces
    assert "-n" in recipe.unshare_argv
    assert validate(recipe, job) == []


def test_validate_catches_network_leak_and_missing_userns():
    offline = JobSpec(name="offline")
    netted = JobSpec(name="netted", needs_network=True)
    recipe = plan(netted)
    violations = validate(recipe, offline)
    assert any("no network need" in v for v in violations)
    broken = plan(offline)
    broken.namespaces.remove("user")
    assert any("user namespace" in v for v in validate(broken, offline))
    # frugal: thousands of times cheaper than a container runtime
    assert plan(offline).savings_factor > 1000


# --- agent_sandbox ---


def test_recommended_profiles_validate():
    for profile in ("agent-exec", "agent-exec-network", "interactive-shell"):
        spec = recommended(profile)
        assert agent_sandbox.validate(spec) == [], profile
    offline = recommended("agent-exec")
    assert not offline.allow_network
    assert offline.has("no_new_privs") and offline.has("non_root")


def test_build_refuses_missing_mandatory_primitive():
    spec = SandboxSpec(
        name="bad",
        primitives=["bubblewrap", "landlock"],  # no no_new_privs / non_root
    )
    with pytest.raises(ValueError, match="no_new_privs"):
        agent_sandbox.build(spec)


def test_network_without_seccomp_refused():
    spec = recommended("agent-exec-network")
    spec.primitives.remove("seccomp")
    violations = agent_sandbox.validate(spec)
    assert any("seccomp" in v for v in violations)


def test_bwrap_argv_and_dry_run():
    spec = recommended("agent-exec", allowed_paths=["/work"], memory_mb=256)
    argv = agent_sandbox.to_bwrap_argv(spec)
    assert argv[0] == "bwrap"
    assert "--unshare-net" in argv
    assert "--ro-bind" in argv and "/" in argv
    assert "/work" in argv
    steps = agent_sandbox.dry_run(spec)
    assert any("never root" in s for s in steps)
    assert any("zero egress" in s for s in steps)
    # unknown profiles and duplicate-safe names
    with pytest.raises(KeyError):
        recommended("nope")


# --- microvm ---


def test_default_vm_clears_cold_start_budget():
    vm = MicroVM(name="v0")
    assert vm.meets_budget()
    assert vm.estimated_cold_start_ms() < microvm.COLD_START_BUDGET_MS
    big = MicroVM(name="big", vcpu=8, memory_mb=8192)
    assert not big.meets_budget()
    with pytest.raises(ValueError):
        MicroVM(name="x", vcpu=0)


def test_pick_lane_cheapest_satisfying():
    assert pick_lane(Workload("w", False, 1000)).lane == "namespace"
    placed = pick_lane(Workload("w", True, 1000))
    assert placed.lane == "microvm"
    assert placed.cold_start_ms <= 1000
    # impossibly tight budget: microVM can't make it, full VM is fallback
    tight = pick_lane(Workload("w", True, 1.0))
    assert tight.lane == "fullvm"


def test_burst_refuses_over_budget_template():
    fleet = Fleet()
    template = MicroVM(name="t", vcpu=8, memory_mb=8192)
    with pytest.raises(ValueError, match="budget"):
        fleet.burst(4, template)
    good = MicroVM(name="g")
    burst = fleet.burst(3, good)
    assert [v.name for v in burst] == ["g-0", "g-1", "g-2"]
    for vm in burst:
        fleet.add(vm)
    assert fleet.total_memory_mb() == 3 * 128
    with pytest.raises(ValueError):
        fleet.add(MicroVM(name="g-0"))


def test_fleet_cost_and_over_budget():
    fleet = Fleet([MicroVM(name="a"), MicroVM(name="b")])
    assert fleet.cost_per_hour("microvm") == pytest.approx(
        2 * microvm.LANE_PRICE_PER_HOUR["microvm"]
    )
    assert fleet.over_budget() == []
    with pytest.raises(KeyError):
        fleet.cost_per_hour("blimp")


# --- scratch_images ---


DOCKERFILE = """\
FROM golang:1.22 AS builder
RUN go build -o /app/server ./cmd/server
FROM scratch
COPY --from=builder /app/server /server
"""


def test_parse_multi_stage():
    model = scratch_images.parse(DOCKERFILE)
    assert len(model.stages) == 2
    assert model.stages[0].name == "builder"
    assert model.final_stage.base == "scratch"
    assert model.final_stage.copies_from == ["builder"]


def test_analyze_reduction_factor():
    model = scratch_images.parse(DOCKERFILE)
    rep = scratch_images.analyze(
        model,
        base_sizes_mb={"golang:1.22": 1300.0, "scratch": 0.5},
        artifact_sizes_mb={"builder": 15.0},
    )
    assert rep.naive_mb == pytest.approx(1300.0)
    assert rep.final_mb == pytest.approx(15.5)
    assert rep.reduction_factor == pytest.approx(1300.0 / 15.5)
    assert rep.saved_mb == pytest.approx(1284.5)
    assert "83.9x" in rep.summary()


def test_lint_flags_waste():
    single = "FROM python:3.11\nRUN pip install -r reqs.txt\n"
    findings = scratch_images.lint(single)
    assert any("single-stage" in f for f in findings)
    assert any("installs packages" in f for f in findings)
    assert scratch_images.lint(DOCKERFILE) == []
    assert scratch_images.lint("FROM x\nCOPY --from=ghost /a /b") == [
        "unparseable: line 2: COPY --from unknown stage 'ghost'"
    ]


def test_analyze_needs_sizes_and_rejects_unknown():
    model = scratch_images.parse(DOCKERFILE)
    with pytest.raises(KeyError):
        scratch_images.analyze(model, base_sizes_mb={"scratch": 0.5})
    with pytest.raises(ValueError):
        scratch_images.parse("RUN echo hi\n")


# --- p2p_sync ---


def test_mesh_converges_and_verifies():
    data = b"levi says hello " * 1000
    a, b = Peer("a"), Peer("b")
    manifest = a.ingest(data)
    rep = sync_mesh([a, b], manifest)
    assert rep.converged
    assert b.has_all(manifest)
    assert verify_manifest(manifest, b.store)
    assert rep.rounds >= 1


def test_content_dedup_shares_identical_chunks():
    data = b"ABCD" * 4096  # every chunk identical
    manifest = make_manifest(data, chunk_size=64)
    assert len(manifest.unique_chunks) == 1
    assert len(manifest.chunk_hashes) > 1
    a, b = Peer("a"), Peer("b")
    m = a.ingest(data, chunk_size=64)
    rep = sync_mesh([a, b], m)
    assert rep.converged
    assert rep.unique_bytes == 64


def test_tampered_chunk_rejected():
    a, b = Peer("a"), Peer("b")
    manifest = a.ingest(b"secret data here", chunk_size=4)
    good_hash = manifest.chunk_hashes[0]
    accepted = b.receive({good_hash: b"XXXX"})  # wrong bytes, right hash
    assert accepted == 0
    assert b.rejected == 1
    assert not b.has_all(manifest)


def test_want_lists_only_missing():
    a, b = Peer("a"), Peer("b")
    manifest = a.ingest(b"0123456789abcdef", chunk_size=4)
    assert b.want(manifest) == manifest.unique_chunks
    b.exchange(a, manifest)
    assert b.want(manifest) == set()
    with pytest.raises(ValueError):
        sync_mesh([], manifest)


# --- p2p_cdn ---


def test_swarm_converges_with_high_offload():
    swarm = Swarm(n_segments=8)
    swarm.add_peer("seed", seeder=True)
    for i in range(6):
        swarm.add_peer(f"viewer-{i}")
    rep = swarm.run()
    assert all(swarm.is_complete(p) for p in swarm.peers)
    assert rep.offload_ratio == pytest.approx(1.0)  # seeder present from tick 0
    assert rep.total_bytes == 6 * 8 * swarm.segment_bytes


def test_no_seeders_means_origin_serves_all():
    swarm = Swarm(n_segments=4)
    swarm.add_peer("lonely")
    rep = swarm.run()
    assert rep.offload_ratio == pytest.approx(0.0)
    assert rep.origin_served_bytes == 4 * swarm.segment_bytes


def test_freeloaders_serve_last():
    swarm = Swarm(n_segments=4)
    giver = swarm.add_peer("giver", seeder=True)
    taker = swarm.add_peer("taker")
    taker.took = 100  # history: takes a lot, gives nothing
    assert taker.freeloader_score() > giver.freeloader_score()
    rep = swarm.run()
    assert rep.offload_ratio > 0.5


def test_flash_crowd_at_scale_offloads_most_bandwidth():
    rep = flash_crowd(n_viewers=200, n_segments=16, n_seeders=2)
    assert rep.ticks > 0
    # studied shape: 55-75% peer offload at scale; the sim should land near it
    assert 0.4 <= rep.offload_ratio <= 1.0
    assert rep.peer_served_bytes > rep.origin_served_bytes
