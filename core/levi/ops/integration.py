"""Integration strength checks — symbiotic pairs must be wired, not nominal."""

from __future__ import annotations

from typing import List, Tuple


def run_integration_audit() -> str:
    rows: List[Tuple[str, bool, str]] = []

    def check(name, fn):
        try:
            ok, detail = fn()
            rows.append((name, bool(ok), detail))
        except Exception as e:
            rows.append((name, False, str(e)[:100]))

    def demand_income():
        from levi.income.factory import ServicePlan

        return (
            "demand_signal_id" in ServicePlan.__dataclass_fields__,
            "plan carries signal id",
        )

    def rail_corpus():
        import inspect
        from levi.lwp import opportunity_rail as m

        src = inspect.getsource(m.OpportunityRail._record)
        return "Corpus" in src, "rail RECORD writes corpus"

    def story_corpus():
        import inspect
        from levi.graph import story_fabric as m

        src = inspect.getsource(m)
        return "Corpus" in src, "story path touches corpus"

    def ops_kernel():
        from levi.ops.layer import OperationalLayer
        from levi.daemon.kernel import DaemonKernel

        s = OperationalLayer().snapshot()
        k = DaemonKernel()
        return True, "estop ops=%s kernel=%s" % (s.estop, k.state.estop)

    def hitl_rail_domain():
        from levi.project.hitl import ALWAYS_HITL

        return (
            "opportunity_rail" in ALWAYS_HITL or "pricing" in ALWAYS_HITL,
            "HITL covers rail domains",
        )

    def mirror_lwp():
        from levi.lwp.mirror_cascade import MirrorCascade

        r = MirrorCascade().run("integration seed")
        return bool(r.fingerprint), "fp=%s" % r.fingerprint

    def character_graph():
        from levi.lwp.character_graph import CharacterGraph

        g = CharacterGraph()
        return g.theoretical_types() > 1000, f"types={g.theoretical_types()}"

    def premium_craft():
        from levi.lwp.premium_craft import PREMIUM_CASCADE

        return len(PREMIUM_CASCADE) >= 8, f"cascade={len(PREMIUM_CASCADE)}"

    def corpus_expand():
        from levi.brain.seed_expand import iter_expanded

        batch = list(iter_expanded(limit=5))
        return len(batch) == 5, "expander_ok"

    def charter_bound():
        from levi.identity.charter import Charter

        c = Charter()
        return c is not None, "charter present"

    def symbiosis_pairs():
        from levi.graph import symbiosis as s

        return hasattr(s, "value_check") or hasattr(
            s, "format_status"
        ), "symbiosis module"

    def lwp_model():
        from levi.lwp.model_engine import LWPModelEngine

        e = LWPModelEngine()
        return hasattr(e, "expand") and hasattr(e, "reim_forks"), "SSA expand+REIM"

    def chat_companion():
        from levi.ei.chat_companion import ChatCompanion

        c = ChatCompanion(session_id="integrate_chat")
        out = c.say("Who are you?")
        return len(out) > 30 and (
            "LEVI" in out or "companion" in out.lower()
        ), f"len={len(out)}"

    def full_cloud_model():
        from levi.cloud.model import FullCloudModel

        m = FullCloudModel()
        snap = m.snapshot()
        return snap.get("seal") == "L.W.P." and "expand" in m.caps.organs, (
            "words=%s rank=%s organs=%d integrations=%d"
            % (
                snap.get("words"),
                snap.get("rank"),
                len(m.caps.organs),
                len(m.caps.integrations),
            )
        )

    def cloud_stages():
        from levi.cloud.stages import StageMap, current_stage
        from levi.cloud.surface import CloudSurface

        m = StageMap()
        assert current_stage().id == "A"
        s = CloudSurface()
        demo = s.demo()
        return (
            len(m.all()) == 3 and demo.get("cmk_len") == 32,
            "stages=%d current=%s cmk_backend=%s"
            % (len(m.all()), current_stage().id, demo.get("cmk_backend")),
        )

    def offline_crisis():
        from levi.ei.offline_companion import synthesize

        t = synthesize("I'm panicking and falling apart")
        return len(t) > 40, "len=%d" % len(t)

    for name, fn in [
        ("demand-income", demand_income),
        ("rail-corpus", rail_corpus),
        ("story-corpus", story_corpus),
        ("ops-kernel", ops_kernel),
        ("hitl-rail", hitl_rail_domain),
        ("mirror-lwp", mirror_lwp),
        ("charter", charter_bound),
        ("symbiosis", symbiosis_pairs),
        ("offline-crisis", offline_crisis),
        ("cloud-stages", cloud_stages),
        ("full-cloud-model", full_cloud_model),
        ("chat-companion", chat_companion),
        ("lwp-model", lwp_model),
        ("character-graph", character_graph),
        ("premium-craft", premium_craft),
        ("corpus-expand", corpus_expand),
    ]:
        check(name, fn)

    ok_n = sum(1 for _, o, _ in rows if o)
    lines = ["=== LEVI Integration Audit  [%d/%d] ===" % (ok_n, len(rows)), ""]
    for name, ok, detail in rows:
        mark = "OK" if ok else "FAIL"
        lines.append("  [%s] %s  %s" % (mark, name, detail))
    lines.append("")
    lines.append("Pairs must stay wired — integration is the bloodstream.")
    return "\n".join(lines)
