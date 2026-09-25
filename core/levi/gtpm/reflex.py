"""The rule-reflex layer: Rete-compiled production rules, self-maintained.

Working module name — **naming is Chauncey's**.

GTPM framing (Chauncey): "Basically analyzing but pure deterministic. I call
it goal targeted predator mentality." This module is the predator's reflex
arc: the fast path inside the scan cycle. Recurring situations resolve by
compiled reflex — no heavyweight reasoner, no drift, no probabilistic
wandering. Deterministic match-select-act, every time.

What this is NOT: rules here are compiled reflexes, not instincts. There
are no sentience or subjective-experience claims anywhere in this module.

Staged acts are NEVER executed here. ``fire_head`` on a rule whose ``rhs``
names an ``act`` only *stages* an intent (or, below the confidence
threshold, a *proposal* to the blackboard). Execution is the scan-mind's
FLUSH job — this layer stops at the receipt.

Formal spec: ``~/workspace/levi-unified-build/salvage-rule-reflex-formal-spec.md``
(sections 2-4 implemented here). The contact-predicate language is shared
with the scan-mind: :mod:`levi.gtpm.predicates` (one closed predicate
language across the substrate, not two).

Stdlib-only at import. No network. No clock. No randomness.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from levi.gtpm.predicates import eval_contact

ORIGIN = "levi-gtpm/reflex"

__all__ = [
    "ORIGIN",
    "ReteNet",
    "compile_rules",
    "assert_fact",
    "retract_fact",
    "agenda",
    "fire_head",
    "run_cycle",
    "explain",
    "distill",
    "promote_rules",
]

# The closed action set for rule bodies. A rule's ``rhs.act`` must be one of
# these — data-only rules, never arbitrary code (spec I5).
STAGED = "staged"
PROPOSED = "proposed"

ReteNet = Dict[str, Any]


# ---------------------------------------------------------------------------
# Validation (fail-closed at compile time)
# ---------------------------------------------------------------------------


def _validate_contact(contact: Dict[str, Any], where: str) -> None:
    # Raises ValueError on a malformed or unknown contact. Probe against an
    # empty image; predicates are total over it, so only structural errors
    # surface here.
    try:
        eval_contact(contact, {})
    except ValueError as exc:
        raise ValueError(f"{where}: bad contact {contact!r}: {exc}") from exc


def _validate_fact(fact: Dict[str, Any], where: str) -> None:
    if not isinstance(fact, dict):
        raise ValueError(f"{where}: fact must be a dict, got {type(fact).__name__}")
    for key in ("type", "fields", "source", "t"):
        if key not in fact:
            raise ValueError(f"{where}: fact missing {key!r}: {fact!r}")
    if not isinstance(fact["type"], str) or not fact["type"]:
        raise ValueError(f"{where}: fact 'type' must be a non-empty string")
    if not isinstance(fact["fields"], dict):
        raise ValueError(f"{where}: fact 'fields' must be a dict")
    for key in ("source", "t"):
        if not isinstance(fact[key], str):
            raise ValueError(f"{where}: fact {key!r} must be a string")


def _validate_pattern(pattern: Dict[str, Any], where: str) -> None:
    if not isinstance(pattern, dict):
        raise ValueError(f"{where}: pattern must be a dict")
    ftype = pattern.get("fact_type")
    if not isinstance(ftype, str) or not ftype:
        raise ValueError(f"{where}: pattern needs a non-empty 'fact_type'")
    constraints = pattern.get("constraints", [])
    if not isinstance(constraints, list):
        raise ValueError(f"{where}: pattern 'constraints' must be a list")
    for contact in constraints:
        _validate_contact(contact, where)


def _validate_rule(rule: Dict[str, Any]) -> Dict[str, Any]:
    where = f"rule {rule.get('id', '?')!r}"
    if not isinstance(rule, dict):
        raise ValueError(f"{where}: rule must be a dict")
    rid = rule.get("id")
    if not isinstance(rid, str) or not rid:
        raise ValueError(f"{where}: rule needs a non-empty string 'id'")
    if not isinstance(rule.get("name"), str):
        raise ValueError(f"{where}: rule needs a string 'name'")
    lhs = rule.get("lhs")
    if not isinstance(lhs, list) or not lhs:
        raise ValueError(f"{where}: 'lhs' must be a non-empty list of patterns")
    for pattern in lhs:
        _validate_pattern(pattern, f"{where} lhs")
    rhs = rule.get("rhs")
    if not isinstance(rhs, dict):
        raise ValueError(f"{where}: 'rhs' must be a dict")
    for fact in rhs.get("assert", []):
        _validate_fact(fact, f"{where} rhs.assert")
    for pattern in rhs.get("retract", []):
        _validate_pattern(pattern, f"{where} rhs.retract")
    act = rhs.get("act")
    # Data-only rules (spec I5): the act is a NAME string, never code.
    if act is not None and not isinstance(act, str):
        raise ValueError(
            f"{where}: rhs 'act' must be a name string or null, "
            f"never executable code (got {type(act).__name__})"
        )
    if not isinstance(act, (str, type(None))):
        raise ValueError(f"{where}: rhs 'act' must be a string or null")
    if not isinstance(rule.get("provenance"), list):
        raise ValueError(f"{where}: 'provenance' must be a list")
    conf = rule.get("confidence")
    if not isinstance(conf, (int, float)) or isinstance(conf, bool):
        raise ValueError(f"{where}: 'confidence' must be a number")
    if not 0.0 <= float(conf) <= 1.0:
        raise ValueError(f"{where}: 'confidence' must be in 0..1, got {conf!r}")
    if not isinstance(rule.get("priority"), int) or isinstance(
        rule.get("priority"), bool
    ):
        raise ValueError(f"{where}: 'priority' must be an int")
    if not isinstance(rule.get("born_at"), str):
        raise ValueError(f"{where}: 'born_at' must be a string")
    if not isinstance(rule.get("corroboration"), int) or isinstance(
        rule.get("corroboration"), bool
    ):
        raise ValueError(f"{where}: 'corroboration' must be an int")
    return rule


# ---------------------------------------------------------------------------
# Rete network construction
# ---------------------------------------------------------------------------


def _pattern_matches(
    pattern: Dict[str, Any], fact: Dict[str, Any], net: ReteNet
) -> bool:
    """Alpha test: single-pattern constraint check against one fact."""
    if "stats" in net:
        net["stats"]["alpha_evals"] += 1
    image = fact["fields"]
    for contact in pattern.get("constraints", []):
        if not eval_contact(contact, image):
            return False
    return True


def _binding_key(bindings: Dict[int, Dict[str, Any]]) -> Tuple[Tuple, ...]:
    """Refractoriness key: (pattern idx, fact t, fact type, canonical fields).

    Content-based, so the same fact *combination* never refires even if the
    fact is retracted and re-asserted under a new internal id.
    """
    return tuple(
        sorted(
            (pi, fact["t"], fact["type"], json.dumps(fact["fields"], sort_keys=True))
            for pi, fact in bindings.items()
        )
    )


def _new_net() -> ReteNet:
    return {
        "rules": {},  # rule_id -> rule dict
        "rule_order": [],  # insertion order (deterministic tiebreak base)
        "alpha_by_type": {},  # fact_type -> [alpha nodes]
        "alpha_node": {},  # (rule_id, pattern_idx) -> alpha node
        "beta": {},  # rule_id -> [{"memory": [token,...]} per pattern]
        "wm": [],  # [{"fid": int, "fact": fact}]
        "wm_by_fid": {},  # fid -> fact
        "next_fid": 0,
        "agenda": {},  # (rule_id, binding_key) -> instantiation
        "fired": set(),  # (rule_id, binding_key) — refractoriness
        "recency": 0,  # monotonic match-recency counter
        "seq": 0,  # firing cycle counter
        "receipts": [],  # firing receipts, in cycle order
        "match_log": [],  # per-delta match receipts
        "fact_origin": {},  # fid -> receipt index that asserted it (None = seed)
        "stats": {"alpha_evals": 0},
    }


def _add_rule_structures(net: ReteNet, rules: List[Dict[str, Any]]) -> None:
    """Create alpha/beta structures for rules (shared by compile + promote)."""
    for rule in rules:
        rid = rule["id"]
        if rid in net["rules"]:
            raise ValueError(f"duplicate rule id {rid!r}")
        net["rules"][rid] = rule
        net["rule_order"].append(rid)
        net["beta"][rid] = [{"memory": []} for _ in rule["lhs"]]
        for pi, pattern in enumerate(rule["lhs"]):
            node = {
                "rule_id": rid,
                "pattern_idx": pi,
                "fact_type": pattern["fact_type"],
                "constraints": pattern.get("constraints", []),
                "memory": set(),
            }
            net["alpha_node"][(rid, pi)] = node
            net["alpha_by_type"].setdefault(pattern["fact_type"], []).append(node)


def compile_rules(rules: List[Dict[str, Any]]) -> ReteNet:
    """Validate and compile a rule set into a genuine Rete network.

    Alpha memories are keyed by fact_type with per-node constraint tests;
    beta join nodes chain patterns left-to-right with binding consistency
    (each pattern binds a distinct fact instance).
    """
    validated = [_validate_rule(rule) for rule in rules]
    net = _new_net()
    _add_rule_structures(net, validated)
    return net


# ---------------------------------------------------------------------------
# Incremental match: assert / retract deltas
# ---------------------------------------------------------------------------


def _beta_insert(
    net: ReteNet, rule: Dict[str, Any], pi: int, token: Tuple[int, ...]
) -> int:
    """Insert a token into beta memory ``pi``; cascade joins forward.

    Returns the number of new agenda activations produced.
    """
    rid = rule["id"]
    beta = net["beta"][rid]
    beta[pi]["memory"].append(token)
    n = len(rule["lhs"])
    if pi == n - 1:
        return _activate(net, rule, token)
    new_activations = 0
    next_node = net["alpha_node"][(rid, pi + 1)]
    for fid in sorted(next_node["memory"]):
        if fid not in token:
            new_activations += _beta_insert(net, rule, pi + 1, token + (fid,))
    return new_activations


def _activate(net: ReteNet, rule: Dict[str, Any], token: Tuple[int, ...]) -> int:
    """A complete token -> one agenda instantiation (unless already fired)."""
    rid = rule["id"]
    bindings = {pi: dict(net["wm_by_fid"][fid]) for pi, fid in enumerate(token)}
    key = _binding_key(bindings)
    if (rid, key) in net["fired"]:
        return 0
    if (rid, key) in net["agenda"]:
        return 0
    net["recency"] += 1
    specificity = sum(len(p.get("constraints", [])) for p in rule["lhs"])
    net["agenda"][(rid, key)] = {
        "rule_id": rid,
        "bindings": bindings,
        "_fids": token,
        "_key": key,
        "specificity": specificity,
        "recency": net["recency"],
        "priority": rule["priority"],
    }
    return 1


def _propagate_assert(
    net: ReteNet,
    fid: int,
    fact: Dict[str, Any],
    alpha_by_type: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, int]:
    """Push one asserted fact through alpha then beta memories (delta only)."""
    alpha_matches = 0
    activations = 0
    for node in alpha_by_type.get(fact["type"], []):
        if _pattern_matches(
            {"fact_type": node["fact_type"], "constraints": node["constraints"]},
            fact,
            net,
        ):
            node["memory"].add(fid)
            alpha_matches += 1
            rule = net["rules"][node["rule_id"]]
            pi = node["pattern_idx"]
            if pi == 0:
                activations += _beta_insert(net, rule, 0, (fid,))
            else:
                beta = net["beta"][rule["id"]]
                for token in list(beta[pi - 1]["memory"]):
                    if fid not in token:
                        activations += _beta_insert(net, rule, pi, token + (fid,))
    return {"alpha_matches": alpha_matches, "activations": activations}


def assert_fact(net: ReteNet, fact: Dict[str, Any]) -> Dict[str, Any]:
    """Assert a fact; propagate ONLY the delta through alpha then beta.

    Updates the agenda (adds new instantiations). Returns delta info.
    """
    _validate_fact(fact, "assert_fact")
    fid = net["next_fid"]
    net["next_fid"] += 1
    fact = dict(fact)
    net["wm"].append({"fid": fid, "fact": fact})
    net["wm_by_fid"][fid] = fact
    net["fact_origin"][fid] = None  # seed facts have no firing parent
    delta = _propagate_assert(net, fid, fact, net["alpha_by_type"])
    net["match_log"].append(
        {
            "kind": "assert",
            "fid": fid,
            "fact_type": fact["type"],
            "alpha_matches": delta["alpha_matches"],
            "activations": delta["activations"],
        }
    )
    return {"asserted": fid, "activations": delta["activations"]}


def _retract_fid(net: ReteNet, fid: int) -> int:
    """Remove one fact by internal id; cascade token/agenda invalidation."""
    fact = net["wm_by_fid"].get(fid)
    if fact is None:
        return 0
    # Drop tokens containing this fid from every beta memory of affected rules.
    touched_rules = set()
    for node in net["alpha_by_type"].get(fact["type"], []):
        if fid in node["memory"]:
            node["memory"].discard(fid)
            touched_rules.add(node["rule_id"])
    for rid in touched_rules:
        for bnode in net["beta"][rid]:
            bnode["memory"] = [t for t in bnode["memory"] if fid not in t]
    # Invalidate agenda instantiations bound to this fact.
    invalidated = 0
    for akey in list(net["agenda"]):
        if fid in net["agenda"][akey]["_fids"]:
            del net["agenda"][akey]
            invalidated += 1
    net["wm"] = [e for e in net["wm"] if e["fid"] != fid]
    del net["wm_by_fid"][fid]
    net["fact_origin"].pop(fid, None)
    return 1


def retract_fact(net: ReteNet, fact_or_matcher: Dict[str, Any]) -> Dict[str, Any]:
    """Retract facts; propagate ONLY the delta (remove invalidated agenda).

    ``fact_or_matcher`` is either a Fact (retract content-equal facts) or a
    Pattern ``{"fact_type", "constraints"}`` (retract matching facts).
    """
    targets: List[int] = []
    if isinstance(fact_or_matcher, dict) and "fact_type" in fact_or_matcher:
        _validate_pattern(fact_or_matcher, "retract_fact matcher")
        for entry in net["wm"]:
            f = entry["fact"]
            if f["type"] == fact_or_matcher["fact_type"] and _pattern_matches(
                fact_or_matcher, f, net
            ):
                targets.append(entry["fid"])
    else:
        _validate_fact(fact_or_matcher, "retract_fact")
        for entry in net["wm"]:
            f = entry["fact"]
            if (
                f["type"] == fact_or_matcher["type"]
                and f["fields"] == fact_or_matcher["fields"]
                and f["t"] == fact_or_matcher["t"]
            ):
                targets.append(entry["fid"])
    removed = 0
    for fid in targets:
        removed += _retract_fid(net, fid)
    net["match_log"].append(
        {
            "kind": "retract",
            "facts": removed,
            "activations": 0,
        }
    )
    return {"retracted": removed, "activations": 0}


# ---------------------------------------------------------------------------
# Conflict resolution: the agenda
# ---------------------------------------------------------------------------


def agenda(net: ReteNet) -> List[Dict[str, Any]]:
    """Instantiations sorted by (specificity desc, recency desc,
    priority desc, rule_id asc). Deterministic — no randomness, no hash()."""
    entries = []
    for inst in net["agenda"].values():
        entries.append(
            {
                "rule_id": inst["rule_id"],
                "bindings": {pi: dict(f) for pi, f in inst["bindings"].items()},
                "specificity": inst["specificity"],
                "recency": inst["recency"],
                "priority": inst["priority"],
            }
        )
    entries.sort(
        key=lambda e: (-e["specificity"], -e["recency"], -e["priority"], e["rule_id"])
    )
    return entries


# ---------------------------------------------------------------------------
# Fire: match-select-act
# ---------------------------------------------------------------------------


def fire_head(
    net: ReteNet, confidence_threshold: float = 0.5
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Pop the agenda head and fire it. Returns (receipt, delta_info).

    Applies the rhs: asserts propagate, retracts propagate. If the rhs names
    an act: confidence >= threshold -> staged intent (STAGED, never executed
    here); confidence < threshold -> a proposal (never acts — spec I6).
    Every act/proposal produces a receipt: no silent acts.
    """
    heads = agenda(net)
    if not heads:
        return None, {}
    head = heads[0]
    rid = head["rule_id"]
    rule = net["rules"][rid]
    akey = next(
        k
        for k in net["agenda"]
        if k[0] == rid and k[1] == _binding_key(head["bindings"])
    )
    inst = net["agenda"].pop(akey)
    net["fired"].add(akey)

    asserted: List[Dict[str, Any]] = []
    retracted: List[Dict[str, Any]] = []
    for fact in rule["rhs"].get("assert", []):
        assert_fact(net, dict(fact))
        asserted.append(dict(fact))
    for pattern in rule["rhs"].get("retract", []):
        doomed = [
            dict(e["fact"])
            for e in net["wm"]
            if e["fact"]["type"] == pattern["fact_type"]
            and _pattern_matches(pattern, e["fact"], net)
        ]
        retract_fact(net, pattern)
        retracted.extend(doomed)

    net["seq"] += 1
    cycle = net["seq"]
    receipt: Dict[str, Any] = {
        "kind": "firing",
        "cycle": cycle,
        "rule_id": rid,
        "bindings": {pi: dict(f) for pi, f in inst["bindings"].items()},
        "wm_delta": {"asserted": asserted, "retracted": retracted},
        "provenance": list(rule["provenance"]),
        "confidence": float(rule["confidence"]),
    }
    parents = []
    for _pi, fid in enumerate(inst["_fids"]):
        origin = net["fact_origin"].get(fid)
        if origin is not None and origin not in parents:
            parents.append(origin)
    # Facts this firing asserts are parented to this receipt.
    receipt_index = len(net["receipts"])
    receipt["parents"] = sorted(parents)

    act = rule["rhs"].get("act")
    if act is not None:
        if float(rule["confidence"]) >= confidence_threshold:
            receipt["staged_act"] = act  # STAGED: the scan-mind's FLUSH executes
            receipt["disposition"] = STAGED
        else:
            receipt["proposal"] = act  # proposes to the blackboard; never acts (I6)
            receipt["disposition"] = PROPOSED
    net["receipts"].append(receipt)
    # Parent this firing's asserted facts to this receipt (assert_fact stamps
    # seed facts with origin None; re-stamp the matching fids).
    _reparent_asserted(net, asserted, receipt_index)
    delta_info = {"asserted": asserted, "retracted": retracted}
    return receipt, delta_info


def _reparent_asserted(
    net: ReteNet, asserted: List[Dict[str, Any]], receipt_index: int
) -> None:
    # assert_fact stamps origin None (seed); re-stamp the newest matching fids.
    remaining = list(asserted)
    for entry in reversed(net["wm"]):
        if not remaining:
            break
        for i, fact in enumerate(remaining):
            f = entry["fact"]
            if (
                f["type"] == fact["type"]
                and f["fields"] == fact["fields"]
                and f["t"] == fact["t"]
                and net["fact_origin"].get(entry["fid"]) is None
            ):
                net["fact_origin"][entry["fid"]] = receipt_index
                remaining.pop(i)
                break


def run_cycle(net: ReteNet, max_fires: int = 100) -> List[Dict[str, Any]]:
    """Fire agenda heads until the agenda is empty or max_fires. Returns receipts."""
    receipts = []
    for _ in range(max_fires):
        receipt, _ = fire_head(net)
        if receipt is None:
            break
        receipts.append(receipt)
    return receipts


# ---------------------------------------------------------------------------
# Explanation: the backward walk
# ---------------------------------------------------------------------------


def explain(net: ReteNet, ref: str) -> List[Dict[str, Any]]:
    """Backward walk: given a staged_act name (or proposal name, or a receipt
    index as int/digit-string), return the firing chain that led to it —
    receipts with rule ids + provenance, in cycle order."""
    receipts = net["receipts"]
    if isinstance(ref, int):
        target_idx = ref
    elif isinstance(ref, str) and ref.lstrip("-").isdigit():
        target_idx = int(ref)
    else:
        matches = [
            i
            for i, r in enumerate(receipts)
            if r.get("staged_act") == ref or r.get("proposal") == ref
        ]
        if not matches:
            raise ValueError(f"explain: no receipt stages or proposes {ref!r}")
        target_idx = matches[-1]
    if not 0 <= target_idx < len(receipts):
        raise ValueError(f"explain: receipt index {target_idx} out of range")
    seen: List[int] = []
    stack = [target_idx]
    while stack:
        idx = stack.pop()
        if idx in seen:
            continue
        seen.append(idx)
        stack.extend(p for p in receipts[idx].get("parents", []) if p not in seen)
    chain = []
    for idx in sorted(seen):
        r = receipts[idx]
        entry = {
            "cycle": r["cycle"],
            "rule_id": r["rule_id"],
            "provenance": list(r["provenance"]),
            "confidence": r["confidence"],
            "outcome": r.get("staged_act", r.get("proposal")),
            "disposition": r.get("disposition", "fired"),
        }
        chain.append(entry)
    return chain


# ---------------------------------------------------------------------------
# Distillation: journal -> candidate rules (the growth loop's job)
# ---------------------------------------------------------------------------


def _situation_sig(situation: List[Dict[str, Any]]) -> str:
    parts = []
    for fact in sorted(
        situation,
        key=lambda f: (
            f.get("type", ""),
            json.dumps(f.get("fields", {}), sort_keys=True),
        ),
    ):
        parts.append([fact.get("type", ""), fact.get("fields", {})])
    return json.dumps(parts, sort_keys=True)


def distill(
    journal: List[Dict[str, Any]], rules: List[Dict[str, Any]], battery_fn, k: int = 3
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """PROPOSE -> DRAFT -> CORROBORATE -> REGRESS -> PROMOTE.

    Mines recurring (situation -> action) pairs with >= k occurrences,
    drafts each as a production rule (provenance = journal refs, confidence =
    dominant-outcome consistency ratio), regression-tests each candidate
    against the journal battery, and promotes only zero-regression
    candidates. Returns (rules + promoted, receipt).
    """
    for entry in journal:
        if (
            not isinstance(entry, dict)
            or "situation" not in entry
            or "action" not in entry
            or "outcome" not in entry
        ):
            raise ValueError(f"distill: bad journal entry {entry!r}")

    # PROPOSE: group by (situation-signature, action).
    groups: Dict[Tuple[str, str], List[int]] = {}
    for idx, entry in enumerate(journal):
        sig = _situation_sig(entry["situation"])
        groups.setdefault((sig, str(entry["action"])), []).append(idx)
    groups = dict(sorted(groups.items()))  # deterministic candidate order

    existing_ids = {r["id"] for r in rules}
    candidates: List[Dict[str, Any]] = []
    n = 0
    for (_, action), idxs in groups.items():
        # CORROBORATE: require >= k independent journal occurrences.
        if len(idxs) < k:
            continue
        outcomes = [str(journal[i]["outcome"]) for i in idxs]
        dominant = sorted(set(outcomes), key=lambda o: (-outcomes.count(o), o))[0]
        confidence = outcomes.count(dominant) / len(outcomes)
        situation = journal[idxs[0]]["situation"]
        n += 1
        rid = f"distilled-{n}"
        while rid in existing_ids:
            n += 1
            rid = f"distilled-{n}"
        existing_ids.add(rid)
        lhs = [
            {
                "fact_type": fact["type"],
                "constraints": [
                    {"signal": s, "pred": "eq", "value": v}
                    for s, v in sorted(
                        fact.get("fields", {}).items(), key=lambda kv: kv[0]
                    )
                ],
            }
            for fact in sorted(
                situation,
                key=lambda f: (
                    f.get("type", ""),
                    json.dumps(f.get("fields", {}), sort_keys=True),
                ),
            )
        ]
        candidates.append(
            {
                "id": rid,
                "name": f"distilled:{action}",
                "lhs": lhs,
                "rhs": {"assert": [], "retract": [], "act": action},
                "provenance": [f"journal:{i}" for i in sorted(idxs)],
                "confidence": confidence,
                "priority": 0,
                "born_at": f"distill:{len(rules) + len(candidates)}",
                "corroboration": len(idxs),
            }
        )

    # REGRESS + PROMOTE: each candidate compiled with R and battery-tested.
    added: List[str] = []
    rejected: List[Dict[str, Any]] = []
    total_passed = 0
    promoted = list(rules)
    for cand in candidates:
        try:
            _validate_rule(cand)
        except ValueError as exc:
            rejected.append({"rule_id": cand["id"], "reason": f"invalid: {exc}"})
            continue
        try:
            passed, failed = battery_fn(promoted + [cand])
        except Exception as exc:  # fail-closed: battery errors reject
            rejected.append({"rule_id": cand["id"], "reason": f"battery error: {exc}"})
            continue
        total_passed += int(passed)
        if failed:
            rejected.append(
                {
                    "rule_id": cand["id"],
                    "reason": f"battery failed: {failed}",
                }
            )
        else:
            promoted.append(cand)
            added.append(cand["id"])
    receipt = {
        "kind": "distillation",
        "added": added,
        "battery": {"passed": total_passed, "failed": []},
        "rejected": rejected,
    }
    return promoted, receipt


def promote_rules(
    net: ReteNet, rules_pack: List[Dict[str, Any]], battery_fn
) -> Dict[str, Any]:
    """End-team hook: regression-gated promotion of a rule pack into a live net.

    Validates the pack, runs the battery over (current rules + pack), and
    either extends the live Rete network (existing WM facts propagate through
    the new alpha/beta structures) or rejects the whole pack with reasons.
    Returns a receipt; never commits silently.
    """
    rejected: List[Dict[str, Any]] = []
    valid: List[Dict[str, Any]] = []
    for rule in rules_pack:
        try:
            valid.append(_validate_rule(rule))
        except ValueError as exc:
            rejected.append(
                {
                    "rule_id": rule.get("id", "?") if isinstance(rule, dict) else "?",
                    "reason": f"invalid: {exc}",
                }
            )
    if rejected:
        return {
            "kind": "promotion",
            "promoted": [],
            "rejected": rejected,
            "battery": {"passed": 0, "failed": ["validation"]},
        }
    current = [net["rules"][rid] for rid in net["rule_order"]]
    try:
        passed, failed = battery_fn(current + valid)
    except Exception as exc:
        return {
            "kind": "promotion",
            "promoted": [],
            "rejected": [
                {"rule_id": r["id"], "reason": f"battery error: {exc}"} for r in valid
            ],
            "battery": {"passed": 0, "failed": ["battery error"]},
        }
    if failed:
        return {
            "kind": "promotion",
            "promoted": [],
            "rejected": [
                {"rule_id": r["id"], "reason": f"battery failed: {failed}"}
                for r in valid
            ],
            "battery": {"passed": int(passed), "failed": list(failed)},
        }
    # Promote: build structures for the pack, then run the existing WM
    # through the new alpha nodes only (incremental — old structures untouched).
    _add_rule_structures(net, valid)
    new_by_type: Dict[str, List[Dict[str, Any]]] = {}
    for rule in valid:
        for pi, pattern in enumerate(rule["lhs"]):
            node = net["alpha_node"][(rule["id"], pi)]
            new_by_type.setdefault(pattern["fact_type"], []).append(node)
    for entry in list(net["wm"]):
        _propagate_assert(net, entry["fid"], entry["fact"], new_by_type)
    return {
        "kind": "promotion",
        "promoted": [r["id"] for r in valid],
        "rejected": [],
        "battery": {"passed": int(passed), "failed": []},
    }
