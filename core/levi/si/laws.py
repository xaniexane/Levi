"""SI layer LAWS — declared up front, machine-checked in tests/test_si_layer.py.

L1 HONEST-TIER
    Every SIResult names the tier that produced it: "rules" or "brain".
    Brain output is labeled "not reasoning" everywhere it appears —
    in result.limits, in chat prefixes, in completion labels. The layer
    never claims the tiny brain reasons, plans, or understands.

L2 LOCAL-RUNTIME
    No network calls in any SI runtime path. Big-provider models may be
    used ONLY as offline teachers (training signal for future operator
    brains), never as runtime seats. He is the provider, not the renter.

L3 GRACEFUL-DEGRADE
    A missing or broken brain never kills the layer. consult(),
    analyze(), decide(), and the Builder generator all fall back to the
    rules tier and say so in the result. consult() never raises on a
    backend failure (programmer errors like an unknown kind still raise).

L4 NO-FAKE-CAPABILITY
    Docs and result.limits state what the layer cannot do: the tiny brain
    cannot reliably write code, JSON, or plans; the focus-flow audio is
    synthesized ambience, not licensed music; buzztunes orders and
    receipts, it does not render audio. Nothing here pretends otherwise.

L5 CONTRACT-SAFE
    Brain text never forms a contract payload. The Builder-facing planner
    generator emits only schema-valid JSON (parseable by
    levi.builder.scaffolds.spec.parse_spec_json); if SI cannot produce
    valid JSON it raises GenerationError so the pipeline's honest
    heuristic fallback runs instead of a corrupt spec.

L6 ADDITIVE
    The SI layer never modifies Builder, Hicomb, buzztunes, or brain
    core files. Integration happens only through their public seams:
    the Generator callable, the ModelBackend protocol, the tricombs
    manifest contract. New files only, under core/levi/si/.
"""

LAWS = {
    "L1": "HONEST-TIER — every result names its tier; brain output labeled not-reasoning",
    "L2": "LOCAL-RUNTIME — no network in any SI runtime path; providers are teachers only",
    "L3": "GRACEFUL-DEGRADE — broken brain falls back to rules; consult() never raises on backend failure",
    "L4": "NO-FAKE-CAPABILITY — limits stated in docs and in result.limits",
    "L5": "CONTRACT-SAFE — brain text never a contract payload; planner JSON must parse",
    "L6": "ADDITIVE — no core files modified; public seams only",
}

# law -> test names in tests/test_si_layer.py (the proof map; keep honest)
LAW_TESTS = {
    "L1": ["test_every_result_names_tier", "test_brain_results_labeled_not_reasoning"],
    "L2": ["test_no_network_imports_in_si_modules"],
    "L3": ["test_consult_survives_broken_brain", "test_backend_unavailable_degrades_pair_programmer"],
    "L4": ["test_limits_documented", "test_focus_flow_receipt_states_synth_not_music"],
    "L5": ["test_planner_json_parses_across_descriptions", "test_run_build_static_completes_offline"],
    "L6": ["test_layer_additive_no_core_patching"],
}
