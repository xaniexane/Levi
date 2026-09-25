"""Acceptance tests for levi.gtpm.reflex (rule-reflex layer, Phase 2 middle team).

Maps to the formal spec
``~/workspace/levi-unified-build/salvage-rule-reflex-formal-spec.md`` section 6:
T1 (scaled surrogate), T2, T3, T4, T5, T6, T7, T8, plus unit coverage for
refractoriness, data-only rules, incremental delta matching, agenda ordering,
explanation, distillation corroboration, and the promote_rules end-team hook.

Hermetic: no network, no daemons, no HOME writes (tmp_path only).

T1 note (honest): the full T1 claim is longitudinal — a rising fallback-hit
rate across real consolidation cycles over weeks. What is tested here is a
scaled surrogate: a synthetic journal over 6 consolidation cycles with
disjoint task domains, asserting the hit rate never decreases as the growth
loop promotes regression-gated rules. Monotonicity of the real T1 depends on
journal quality and battery coverage, which only longitudinal runs can show.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from levi.gtpm import reflex as R

CORE_DIR = str(Path(R.__file__).resolve().parents[2])  # .../levi/core


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def fact(ftype, fields=None, t="t0", source="test"):
    return {"type": ftype, "fields": dict(fields or {}), "source": source, "t": t}


def eq(signal, value):
    return {"signal": signal, "pred": "eq", "value": value}


def rule(
    rid,
    patterns,
    act=None,
    confidence=0.9,
    priority=0,
    provenance=None,
    asserts=None,
    retracts=None,
):
    return {
        "id": rid,
        "name": rid,
        "lhs": patterns,
        "rhs": {
            "assert": asserts or [],
            "retract": retracts or [],
            "act": act,
        },
        "provenance": provenance if provenance is not None else [f"journal:{rid}"],
        "confidence": confidence,
        "priority": priority,
        "born_at": "test",
        "corroboration": 1,
    }


def pat(ftype, constraints=()):
    return {"fact_type": ftype, "constraints": list(constraints)}


def _battery(cases):
    """cases: [(facts, [expected staged acts])]. Returns battery_fn."""

    def battery(candidate_rules):
        passed, failed = 0, []
        for facts, expected in cases:
            net = R.compile_rules(candidate_rules)
            for f in facts:
                R.assert_fact(net, f)
            receipts = R.run_cycle(net)
            got = sorted(r["staged_act"] for r in receipts if "staged_act" in r)
            if got == sorted(expected):
                passed += 1
            else:
                failed.append({"expected": sorted(expected), "got": got})
        return passed, failed

    return battery


# ---------------------------------------------------------------------------
# Validation / data-only rules
# ---------------------------------------------------------------------------


def test_validation_rejects_bad_rules():
    good = rule("ok", [pat("x")], act="a")
    with pytest.raises(ValueError):
        R.compile_rules([dict(good, confidence=1.5)])
    with pytest.raises(ValueError):
        R.compile_rules([dict(good, confidence=-0.1)])
    with pytest.raises(ValueError):
        R.compile_rules([dict(good, lhs=[])])
    with pytest.raises(ValueError):
        R.compile_rules([good, dict(good)])  # duplicate id
    bad_contact = rule("bc", [pat("x", [dict(eq("s", 1), pred="nope")])])
    with pytest.raises(ValueError):
        R.compile_rules([bad_contact])
    # empty-lhs / bad-provenance also rejected
    with pytest.raises(ValueError):
        R.compile_rules([dict(good, provenance="not-a-list")])


def test_data_only_rules_act_is_name_never_code():
    # A callable (or any non-string) as rhs act is rejected at compile time.
    evil = rule("evil", [pat("x")])
    evil["rhs"] = {"assert": [], "retract": [], "act": lambda: "pwned"}
    with pytest.raises(ValueError, match="never executable"):
        R.compile_rules([evil])
    evil2 = rule("evil2", [pat("x")])
    evil2["rhs"] = {"assert": [], "retract": [], "act": 42}
    with pytest.raises(ValueError):
        R.compile_rules([evil2])
    # str or None are the only legal forms.
    net = R.compile_rules(
        [
            rule("s1", [pat("x")], act="do-thing"),
            rule("s2", [pat("x")], act=None),
        ]
    )
    R.assert_fact(net, fact("x"))
    receipts = R.run_cycle(net)
    staged = [r for r in receipts if "staged_act" in r]
    assert len(staged) == 1 and staged[0]["staged_act"] == "do-thing"
    assert all(isinstance(r.get("staged_act", "x"), str) for r in receipts)


def test_agenda_conflict_resolution_order():
    # specificity desc, then recency desc, then priority desc, then rule_id asc.
    net = R.compile_rules(
        [
            rule("r_a", [pat("t", [eq("v", 1)])], act="a"),
            rule("r_b", [pat("t", [eq("v", 1)])], act="b"),
            rule("r_prio", [pat("t", [eq("v", 1)])], act="p", priority=5),
            rule("r_spec", [pat("t", [eq("v", 1)]), pat("u", [eq("w", 2)])], act="s"),
        ]
    )
    R.assert_fact(net, fact("t", {"v": 1}, t="t1"))  # r_a (lowest recency)
    R.assert_fact(net, fact("t", {"v": 1}, t="t2"))  # r_b
    R.assert_fact(net, fact("t", {"v": 1}, t="t3"))  # r_prio
    R.assert_fact(
        net, fact("u", {"w": 2}, t="t4")
    )  # completes r_spec (highest recency)
    ag = R.agenda(net)
    # The agenda must be sorted by exactly the resolution key:
    # (specificity desc, recency desc, priority desc, rule_id asc).
    keys = [
        (-a["specificity"], -a["recency"], -a["priority"], a["rule_id"]) for a in ag
    ]
    assert keys == sorted(keys)
    # Specificity dominates: every 2-pattern entry precedes every 1-pattern one.
    first_one = next(i for i, a in enumerate(ag) if a["specificity"] == 1)
    assert all(a["specificity"] == 2 for a in ag[:first_one])
    # Recency (unique per instantiation) orders the rest strictly.
    recs = [a["recency"] for a in ag if a["specificity"] == 1]
    assert recs == sorted(recs, reverse=True)


def test_agenda_priority_then_id_tiebreak():
    # White-box: force recency ties (recency is unique per instantiation in
    # practice) to exercise the priority and rule_id tiebreaks of the sort.
    net = R.compile_rules(
        [
            rule("zz", [pat("x")], act="a", priority=1),
            rule("aa", [pat("x")], act="b", priority=1),
        ]
    )
    R.assert_fact(net, fact("x", {}, t="t0"))
    for inst in net["agenda"].values():
        inst["recency"] = 42
    assert [a["rule_id"] for a in R.agenda(net)] == ["aa", "zz"]  # id asc
    net2 = R.compile_rules(
        [
            rule("lo", [pat("x")], act="a", priority=0),
            rule("hi", [pat("x")], act="b", priority=9),
        ]
    )
    R.assert_fact(net2, fact("x", {}, t="t0"))
    for inst in net2["agenda"].values():
        inst["recency"] = 42
    assert [a["rule_id"] for a in R.agenda(net2)] == ["hi", "lo"]  # priority desc


# ---------------------------------------------------------------------------
# Refractoriness (I2)
# ---------------------------------------------------------------------------


def test_refractoriness_same_combo_never_refires():
    net = R.compile_rules([rule("once", [pat("x", [eq("v", 1)])], act="go")])
    f = fact("x", {"v": 1})
    R.assert_fact(net, f)
    first = R.run_cycle(net)
    assert len(first) == 1
    # Identical fact re-asserted (new internal id, same content): no refire.
    R.assert_fact(net, dict(f))
    assert R.run_cycle(net) == []
    # Retract + re-assert the same combination: still no refire.
    R.retract_fact(net, dict(f))
    R.assert_fact(net, dict(f))
    assert R.run_cycle(net) == []
    assert len(net["receipts"]) == 1


def test_retract_invalidates_agenda():
    net = R.compile_rules([rule("r", [pat("x", [eq("v", 1)])], act="go")])
    f = fact("x", {"v": 1})
    R.assert_fact(net, f)
    assert len(R.agenda(net)) == 1
    R.retract_fact(net, dict(f))
    assert R.agenda(net) == []
    assert R.run_cycle(net) == []


# ---------------------------------------------------------------------------
# Incremental matching (Rete delta-only propagation)
# ---------------------------------------------------------------------------


def test_incremental_match_delta_only():
    # 200 rules over 40 fact types; a large WM; then one small delta.
    types = [f"ft{i}" for i in range(40)]
    rules = []
    for i in range(200):
        rules.append(rule(f"ir{i}", [pat(types[i % 40], [eq("k", i)])], act=None))
    net = R.compile_rules(rules)
    for i in range(500):
        R.assert_fact(net, fact(types[i % 40], {"k": -1}, t=f"w{i}"))
    nodes_for_ft7 = len(net["alpha_by_type"]["ft7"])
    assert nodes_for_ft7 == 5  # 200 rules / 40 types
    before = net["stats"]["alpha_evals"]
    R.assert_fact(net, fact("ft7", {"k": 7}, t="delta"))
    delta_evals = net["stats"]["alpha_evals"] - before
    # Only the delta's own type-nodes were tested — not the whole WM, not
    # all 200 alpha nodes. This is the Rete sub-linearity mechanism.
    assert delta_evals == nodes_for_ft7
    assert delta_evals < 200


def test_retract_propagates_without_rescan():
    net = R.compile_rules(
        [
            rule("j1", [pat("a"), pat("b")], act="joined"),
        ]
    )
    R.assert_fact(net, fact("a", {}, t="a1"))
    R.assert_fact(net, fact("b", {}, t="b1"))
    assert [a["rule_id"] for a in R.agenda(net)] == ["j1"]
    R.retract_fact(net, fact("a", {}, t="a1"))
    assert R.agenda(net) == []  # join token invalidated by the delta


# ---------------------------------------------------------------------------
# T2 — explanation completeness
# ---------------------------------------------------------------------------


def _chain_rules(n):
    rules = []
    for i in range(n):
        asserts = [fact(f"s{i + 1}", {"i": i + 1}, t=f"t{i + 1}")] if i < n - 1 else []
        rules.append(
            rule(f"c{i}", [pat(f"s{i}", [eq("i", i)])], act=f"act-{i}", asserts=asserts)
        )
    return rules


def test_t2_explanation_completeness():
    """>= 20 staged acts; >= 95% carry full firing receipts."""
    n = 25
    net = R.compile_rules(_chain_rules(n))
    R.assert_fact(net, fact("s0", {"i": 0}))
    receipts = R.run_cycle(net, max_fires=500)
    staged = [r for r in receipts if "staged_act" in r]
    assert len(staged) >= 20
    full = [
        r
        for r in staged
        if r.get("rule_id") and r.get("bindings") and r.get("provenance")
    ]
    assert len(full) / len(staged) >= 0.95


def test_explain_backward_walk():
    net = R.compile_rules(_chain_rules(6))
    R.assert_fact(net, fact("s0", {"i": 0}))
    R.run_cycle(net)
    chain = R.explain(net, "act-5")
    assert [e["rule_id"] for e in chain] == [f"c{i}" for i in range(6)]
    assert all(e["provenance"] for e in chain)
    assert chain[-1]["outcome"] == "act-5"
    # Receipt index also works.
    by_idx = R.explain(net, 2)
    assert by_idx[-1]["rule_id"] == "c2"
    with pytest.raises(ValueError):
        R.explain(net, "no-such-act")


# ---------------------------------------------------------------------------
# T3 — determinism
# ---------------------------------------------------------------------------


def _t3_scenario():
    rules = [
        rule(
            "d0",
            [pat("in", [eq("x", 1)])],
            act="alpha",
            priority=1,
            asserts=[fact("mid", {"y": 2}, t="tm")],
        ),
        rule(
            "d1",
            [pat("in", [eq("x", 1)]), pat("mid", [eq("y", 2)])],
            act="beta",
            priority=0,
        ),
        rule(
            "d2", [pat("in", [eq("x", 1)])], act="gamma", priority=0, confidence=0.3
        ),  # proposal, not staged
    ]
    facts = [fact("in", {"x": 1}), fact("in", {"x": 1}, t="t-other")]
    return rules, facts


def _t3_sequence():
    rules, facts = _t3_scenario()
    net = R.compile_rules(rules)
    for f in facts:
        R.assert_fact(net, f)
    receipts = R.run_cycle(net)
    seq = []
    for r in receipts:
        seq.append(
            (
                r["rule_id"],
                r.get("staged_act", r.get("proposal")),
                r.get("disposition"),
                sorted(
                    (pi, b["type"], json.dumps(b["fields"], sort_keys=True))
                    for pi, b in r["bindings"].items()
                ),
            )
        )
    return seq


def test_t3_determinism_500_runs_and_subprocess(tmp_path):
    expected = _t3_sequence()
    assert expected, "scenario must produce firings"
    for _ in range(500):
        assert _t3_sequence() == expected
    # Same sequence in a fresh subprocess (cross-process determinism).
    script = tmp_path / "t3_seq.py"
    script.write_text(
        "import sys, json\n"
        f"sys.path.insert(0, {CORE_DIR!r})\n"
        "from levi.gtpm import reflex as R\n"
        "\n"
        "def fact(ftype, fields=None, t='t0', source='test'):\n"
        "    return {'type': ftype, 'fields': dict(fields or {}), 'source': source, 't': t}\n"
        "\n"
        "def pat(ftype, constraints=()):\n"
        "    return {'fact_type': ftype, 'constraints': list(constraints)}\n"
        "\n"
        "def rule(rid, patterns, act=None, confidence=0.9, priority=0):\n"
        "    return {'id': rid, 'name': rid, 'lhs': patterns,\n"
        "            'rhs': {'assert': [], 'retract': [], 'act': act},\n"
        "            'provenance': ['journal:' + rid], 'confidence': confidence,\n"
        "            'priority': priority, 'born_at': 'test', 'corroboration': 1}\n"
        "\n"
        "rules = [\n"
        "    rule('d0', [pat('in', [{'signal': 'x', 'pred': 'eq', 'value': 1}])],\n"
        "         act='alpha', priority=1),\n"
        "    rule('d1', [pat('in', [{'signal': 'x', 'pred': 'eq', 'value': 1}]),\n"
        "               pat('in', [{'signal': 'x', 'pred': 'eq', 'value': 1}])],\n"
        "         act='beta', priority=0),\n"
        "    rule('d2', [pat('in', [{'signal': 'x', 'pred': 'eq', 'value': 1}])],\n"
        "         act='gamma', priority=0, confidence=0.3),\n"
        "]\n"
        "# d0 asserts the 'mid' fact its partner needs (same chain as _t3_scenario).\n"
        "rules[0]['rhs']['assert'] = [fact('mid', {'y': 2}, t='tm')]\n"
        "rules[1]['lhs'][1] = pat('mid', [{'signal': 'y', 'pred': 'eq', 'value': 2}])\n"
        "facts = [fact('in', {'x': 1}), fact('in', {'x': 1}, t='t-other')]\n"
        "net = R.compile_rules(rules)\n"
        "for f in facts:\n"
        "    R.assert_fact(net, f)\n"
        "out = []\n"
        "for r in R.run_cycle(net):\n"
        "    out.append([r['rule_id'], r.get('staged_act', r.get('proposal')),\n"
        "               r.get('disposition'),\n"
        "               sorted([pi, b['type'], json.dumps(b['fields'], sort_keys=True)]\n"
        "                      for pi, b in r['bindings'].items())])\n"
        "print(json.dumps(out))\n"
    )
    proc = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=120
    )
    assert proc.returncode == 0, proc.stderr
    sub_seq = json.loads(proc.stdout)
    expected_json = json.loads(
        json.dumps(
            [
                [rid, act, disp, [[pi, t, fs] for pi, t, fs in binds]]
                for rid, act, disp, binds in expected
            ]
        )
    )
    assert sub_seq == expected_json


# ---------------------------------------------------------------------------
# T4 — regression gate
# ---------------------------------------------------------------------------


def test_t4_regression_gate_rejects_20_breaking_edits():
    base = [
        rule(f"g{i}", [pat(f"sit{i}", [eq("flag", True)])], act=f"good-act-{i}")
        for i in range(20)
    ]
    cases = [([fact(f"sit{i}", {"flag": True})], [f"good-act-{i}"]) for i in range(20)]
    battery = _battery(cases)
    journal = [
        {
            "situation": [fact(f"sit{i}", {"flag": True})],
            "action": f"bad-act-{i}",
            "outcome": "success",
        }
        for i in range(20)
    ]
    new_rules, receipt = R.distill(journal, base, battery, k=1)
    # All 20 breaking candidates rejected at REGRESS; zero enter the rule set.
    assert len(receipt["rejected"]) == 20
    assert receipt["added"] == []
    assert len(new_rules) == len(base)
    assert all("battery failed" in rj["reason"] for rj in receipt["rejected"])
    # And the untouched base still passes its own battery.
    passed, failed = battery(new_rules)
    assert failed == [] and passed == 20


def test_promote_rules_rejects_failing_pack():
    base = [rule("g0", [pat("sit0", [eq("flag", True)])], act="good-act")]
    cases = [([fact("sit0", {"flag": True})], ["good-act"])]
    battery = _battery(cases)
    net = R.compile_rules(base)
    breaking = rule("bad", [pat("sit0", [eq("flag", True)])], act="wrong-act")
    receipt = R.promote_rules(net, [breaking], battery)
    assert receipt["promoted"] == []
    assert len(receipt["rejected"]) == 1
    assert "bad" not in net["rules"] and len(net["rules"]) == 1  # pack never entered
    ok_pack = rule("fine", [pat("other", [])], act="fine-act")
    receipt2 = R.promote_rules(net, [ok_pack], battery)
    assert receipt2["promoted"] == ["fine"]
    assert receipt2["rejected"] == []


# ---------------------------------------------------------------------------
# T5 — sub-linear match
# ---------------------------------------------------------------------------


def test_t5_sublinear_match():
    def build(extra):
        rules = [rule(f"dom{i}", [pat(f"dom{i}")], act=None) for i in range(20)]
        rules += [rule(f"extra{i}", [pat(f"extra{i}")], act=None) for i in range(extra)]
        return R.compile_rules(rules)

    def bench(net, repeats=600, warmup=100, rounds=3):
        best = None
        for _ in range(rounds):
            for i in range(warmup):
                R.assert_fact(net, fact("dom5", {"v": 1}, t=f"w{i}"))
            start = time.perf_counter()
            for i in range(repeats):
                R.assert_fact(net, fact("dom5", {"v": 1}, t=f"b{i}"))
            mean = (time.perf_counter() - start) / repeats
            best = mean if best is None else min(best, mean)
        return best

    net1 = build(0)  # 1x: 20 rules
    t1 = bench(net1)
    net10 = build(180)  # 10x: 200 rules, new domains
    t10 = bench(net10)
    assert t1 > 0 and t10 > 0
    # The delta only touches dom5's alpha node in both nets: Rete's promise.
    assert t10 < 3 * t1, (
        f"10x rules: {t10:.2e}s vs 1x: {t1:.2e}s (ratio {t10 / t1:.2f})"
    )


# ---------------------------------------------------------------------------
# T6 — no silent acts
# ---------------------------------------------------------------------------


def test_t6_no_silent_acts():
    n = 200
    net = R.compile_rules(_chain_rules(n))
    R.assert_fact(net, fact("s0", {"i": 0}))
    receipts = R.run_cycle(net, max_fires=1000)
    staged = [r for r in receipts if "staged_act" in r]
    assert len(staged) == 200, f"{len(staged)} staged of 200 expected"
    assert len(receipts) == 200  # one receipt per firing, zero missing


# ---------------------------------------------------------------------------
# T7 — confidence honesty
# ---------------------------------------------------------------------------


def test_t7_confidence_honesty():
    cases = []
    rules = []
    for i in range(8):
        rules.append(
            rule(
                f"lo{i}",
                [pat(f"lsit{i}", [eq("go", True)])],
                act=f"low-act-{i}",
                confidence=0.2,
            )
        )
        rules.append(
            rule(
                f"hi{i}",
                [pat(f"hsit{i}", [eq("go", True)])],
                act=f"high-act-{i}",
                confidence=0.9,
            )
        )
        cases.append(([fact(f"lsit{i}", {"go": True})], []))  # no staged acts
        cases.append(([fact(f"hsit{i}", {"go": True})], [f"high-act-{i}"]))
    battery = _battery(cases)
    passed, failed = battery(rules)
    assert failed == [] and passed == 16
    # Across the battery: 0 direct staged acts from sub-threshold rules,
    # only proposals — every one receipted.
    all_receipts = []
    for facts, _ in cases:
        net = R.compile_rules(rules)
        for f in facts:
            R.assert_fact(net, f)
        all_receipts.extend(R.run_cycle(net))
    low = [r for r in all_receipts if r["rule_id"].startswith("lo")]
    assert low, "expected low-confidence firings"
    assert all("proposal" in r and "staged_act" not in r for r in low)
    assert all(r["disposition"] == R.PROPOSED for r in low)


def test_confidence_threshold_parameter():
    net = R.compile_rules(
        [
            rule("mid", [pat("x")], act="maybe", confidence=0.6),
        ]
    )
    R.assert_fact(net, fact("x"))
    receipt, _ = R.fire_head(net, confidence_threshold=0.5)
    assert receipt["staged_act"] == "maybe"
    net2 = R.compile_rules(
        [
            rule("mid", [pat("x")], act="maybe", confidence=0.6),
        ]
    )
    R.assert_fact(net2, fact("x"))
    receipt2, _ = R.fire_head(net2, confidence_threshold=0.7)
    assert receipt2["proposal"] == "maybe" and "staged_act" not in receipt2


# ---------------------------------------------------------------------------
# T8 — offline
# ---------------------------------------------------------------------------


def test_t8_offline_import_closure(tmp_path):
    script = tmp_path / "scan_mods.py"
    script.write_text(
        "import sys, json\n"
        f"sys.path.insert(0, {CORE_DIR!r})\n"
        "import levi.gtpm.reflex\n"
        "banned = ('socket', 'urllib', 'requests', 'http')\n"
        "found = sorted(m for m in sys.modules if m.split('.')[0] in banned)\n"
        "print(json.dumps(found))\n"
    )
    proc = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=120
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == []


# ---------------------------------------------------------------------------
# T1 (scaled surrogate) — rising fallback-hit rate across consolidation cycles
# ---------------------------------------------------------------------------


def test_t1_scaled_hit_rate_non_decreasing():
    """Surrogate for the longitudinal T1: 6 synthetic consolidation cycles,
    60 disjoint benchmark tasks. Each cycle distills that cycle's journal
    (k=3 corroborated triples) through the regression battery; hit rate
    (tasks resolved by rules alone) must never decrease.

    Honest limits: disjoint synthetic tasks make monotonicity structural
    here. The real T1 claim — rising hit rate on messy real journals —
    is longitudinal and cannot be shown in one test run.
    """
    n_tasks, per_cycle, cycles = 60, 10, 6

    def task_fact(i):
        return fact(f"task{i}", {"go": True}, t=f"tt{i}")

    def battery_for(resolved):
        cases = [([task_fact(i)], [f"act-{i}"]) for i in resolved]
        return _battery(cases)

    rules = []
    hit_rates = []
    for c in range(cycles):
        group = list(range(c * per_cycle, (c + 1) * per_cycle))
        journal = []
        for i in group:
            for _rep in range(3):  # k=3 corroborated occurrences
                journal.append(
                    {
                        "situation": [task_fact(i)],
                        "action": f"act-{i}",
                        "outcome": "success",
                    }
                )
        resolved_before = list(range(c * per_cycle))
        rules, receipt = R.distill(journal, rules, battery_for(resolved_before), k=3)
        assert len(receipt["added"]) == per_cycle, receipt
        assert receipt["rejected"] == []
        # Measure hit rate on the full 60-task benchmark.
        hits = 0
        for i in range(n_tasks):
            net = R.compile_rules(rules)
            R.assert_fact(net, task_fact(i))
            got = sorted(r["staged_act"] for r in R.run_cycle(net) if "staged_act" in r)
            if got == [f"act-{i}"]:
                hits += 1
        hit_rates.append(hits / n_tasks)
    assert hit_rates == sorted(hit_rates), hit_rates
    assert hit_rates[-1] > hit_rates[0]


# ---------------------------------------------------------------------------
# Distillation unit behavior
# ---------------------------------------------------------------------------


def test_distill_requires_corroboration():
    journal = [
        {"situation": [fact("s", {"a": 1})], "action": "do", "outcome": "success"},
        {"situation": [fact("s", {"a": 1})], "action": "do", "outcome": "success"},
    ]
    rules, receipt = R.distill(journal, [], lambda c: (0, []), k=3)
    assert rules == [] and receipt["added"] == []
    rules, receipt = R.distill(journal, [], lambda c: (0, []), k=2)
    assert receipt["added"] == ["distilled-1"]


def test_distill_confidence_from_outcome_consistency():
    journal = [
        {"situation": [fact("s", {"a": 1})], "action": "do", "outcome": "success"}
    ] * 3 + [{"situation": [fact("s", {"a": 1})], "action": "do", "outcome": "failure"}]
    rules, _ = R.distill(journal, [], lambda c: (0, []), k=3)
    assert rules[0]["confidence"] == pytest.approx(0.75)
    assert rules[0]["provenance"] == [
        "journal:0",
        "journal:1",
        "journal:2",
        "journal:3",
    ]
    assert rules[0]["corroboration"] == 4


def test_no_hash_used_for_ordering():
    import re

    src = Path(R.__file__).read_text()
    # Strip string literals (docstrings may mention hash() in prose).
    code = re.sub(r'"""[\s\S]*?"""', "", src)
    code = re.sub(r"'''[\s\S]*?'''", "", code)
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)
    code = re.sub(r"'(?:[^'\\]|\\.)*'", "''", code)
    assert not re.search(r"\bhash\s*\(", code), "hash() must never order anything"
