"""The scan-mind: deterministic scan cycles over a frozen process image.

Working module name — **naming is Chauncey's**.

GTPM framing (Chauncey): "Basically analyzing but pure deterministic. I
call it goal targeted predator mentality." This module is the flagship
GTPM mind implemented as a deterministic decision procedure, not a mind
that feels anything: freeze the world into an immutable process image,
evaluate an ordered rung program against it (branch = AND of contacts,
rung = OR of branches, mode-adjusted), stage coil intents, and flush
them through a permission gate once per cycle. No sentience or
subjective-experience claims are made or implied anywhere here.

Formal spec: ``~/workspace/levi-unified-build/plc-scanmind-formal-spec.md``
(sections 2-5 implemented here).

Explicit semantic decisions (all deterministic, all tested):

- ``evaluate`` is pure: no I/O, no clock reads, no randomness.
  Determinism is structural. ``run_scan_cycle`` is the impure shell
  (timing, gate, executor) around it.
- Rung 0 is the safety interlock by construction: ``make_program``
  rejects any program whose first rung lacks ``"safety": True``, and
  ``run_scan_cycle`` discards the whole output image when rung 0 trips.
- Latch-bit writes take effect for rungs later in the same cycle
  (immediate, PLC-style seal-in semantics). This resolves the spec's
  open unlatch question: an unlatch rung placed before its target latch
  rung suppresses the target's coil in the same cycle. The returned
  ``latch_updates`` are the net delta, applied in rung order.
- Coil identity is the coil's ``intent`` name. On conflict the later
  rung in program order wins; the earlier rung's state entry records
  ``overridden_by`` with the winner's rung name.
- ``"$signal"`` coil args resolve against the frozen image; a missing
  signal raises ``ValueError`` (fail-closed), never a guessed value.
- Faults are typed: EVAL (frozen/evaluate failure), INTERLOCK (rung 0
  tripped), DENIED (gate denial), FAILED (executor raised), OVERRUN
  (watchdog budget exceeded). The safe state is always: discard
  uncommitted staged intents, record the fault, write the receipt,
  return.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from typing import Any, Dict, List, Tuple

from levi.gtpm.predicates import eval_contact

ORIGIN = "levi-gtpm/scanmind"

MODES = ("normal", "latch", "unlatch", "one_shot")

_ABSENT = object()

__all__ = [
    "ORIGIN",
    "MODES",
    "make_program",
    "freeze_image",
    "evaluate",
    "run_scan_cycle",
    "render_rung",
    "compose_program",
]


# ---------------------------------------------------------------------------
# Program construction
# ---------------------------------------------------------------------------


def _normalize_rung(rung: Any, index: int, seen: set) -> Dict[str, Any]:
    """Validate one rung dict and return its canonical form.

    Raises ``ValueError`` on anything malformed — fail-closed at build
    time, never a guessed rung.
    """
    where = f"rungs[{index}]"
    if not isinstance(rung, dict):
        raise ValueError(f"{where} must be a rung dict")
    name = rung.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError(f"{where} needs a non-empty string 'name'")
    if name in seen:
        raise ValueError(f"{where}: duplicate rung name {name!r}")
    seen.add(name)

    mode = rung.get("mode", "normal")
    if mode not in MODES:
        raise ValueError(
            f"{where} {name!r}: unknown mode {mode!r}; expected one of {MODES}"
        )

    branches_in = rung.get("branches") or []
    if not isinstance(branches_in, list):
        raise ValueError(
            f"{where} {name!r}: 'branches' must be a list of contact lists"
        )
    branches = []
    for bi, branch in enumerate(branches_in):
        if not isinstance(branch, list):
            raise ValueError(
                f"{where} {name!r}: branch {bi} must be a list of contacts"
            )
        norm_branch = []
        for ci, contact in enumerate(branch):
            if not isinstance(contact, dict):
                raise ValueError(
                    f"{where} {name!r}: contact {ci} in branch {bi} must be a dict"
                )
            signal = contact.get("signal")
            pred = contact.get("pred")
            if not isinstance(signal, str) or not signal:
                raise ValueError(
                    f"{where} {name!r}: contact needs a non-empty string 'signal'"
                )
            if not isinstance(pred, str) or not pred:
                raise ValueError(f"{where} {name!r}: contact needs a string 'pred'")
            norm_contact = {"signal": signal, "pred": pred}
            if "value" in contact:
                norm_contact["value"] = copy.deepcopy(contact["value"])
            norm_branch.append(norm_contact)
        branches.append(norm_branch)

    coil_in = rung.get("coil")
    coil = None
    if coil_in is not None:
        if not isinstance(coil_in, dict):
            raise ValueError(f"{where} {name!r}: 'coil' must be a dict")
        intent = coil_in.get("intent")
        if not isinstance(intent, str) or not intent:
            raise ValueError(
                f"{where} {name!r}: coil needs a non-empty string 'intent'"
            )
        args = coil_in.get("args") or {}
        if not isinstance(args, dict):
            raise ValueError(f"{where} {name!r}: coil 'args' must be a dict")
        risk = coil_in.get("risk", 0)
        if isinstance(risk, bool) or not isinstance(risk, int) or not 0 <= risk <= 4:
            raise ValueError(f"{where} {name!r}: coil 'risk' must be an int 0-4")
        coil = {"intent": intent, "args": copy.deepcopy(args), "risk": risk}

    unlatch_target = rung.get("unlatch_target")
    if mode == "unlatch":
        if not isinstance(unlatch_target, str) or not unlatch_target:
            raise ValueError(
                f"{where} {name!r}: mode 'unlatch' needs a non-empty 'unlatch_target'"
            )
    else:
        unlatch_target = None

    return {
        "name": name,
        "safety": bool(rung.get("safety", False)),
        "branches": branches,
        "coil": coil,
        "mode": mode,
        "unlatch_target": unlatch_target,
    }


def make_program(rungs: Any) -> dict:
    """Build and validate a rung program.

    ``rungs`` is a list of rung dicts (a mapping with ``"version"`` and
    ``"rungs"`` keys is also accepted, honoring the version). Returns
    ``{"version": int, "rungs": [...]}`` with ``version`` defaulting to 1.

    Rung 0 must carry ``"safety": True`` — the unreorderable safety
    interlock — otherwise ``ValueError``. Rung names must be unique,
    modes must be one of ``MODES``, ``unlatch`` rungs need an
    ``unlatch_target``, and coil risk must be an int 0-4.
    """
    if isinstance(rungs, dict):
        version = rungs.get("version", 1)
        rung_list = rungs.get("rungs")
    elif isinstance(rungs, (list, tuple)):
        version = 1
        rung_list = list(rungs)
    else:
        raise ValueError("make_program needs a list of rungs (or a program mapping)")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError("program 'version' must be an int")
    if not isinstance(rung_list, list) or not rung_list:
        raise ValueError(
            "program needs at least one rung (rung 0 is the safety interlock)"
        )
    first = rung_list[0]
    if not isinstance(first, dict) or first.get("safety") is not True:
        raise ValueError(
            "rungs[0] must be the safety interlock: a rung dict with 'safety': True"
        )
    seen: set = set()
    return {
        "version": version,
        "rungs": [_normalize_rung(r, i, seen) for i, r in enumerate(rung_list)],
    }


def compose_program(base_program: dict, extra_rungs: list) -> dict:
    """Append ``extra_rungs`` AFTER rung 0 of ``base_program``.

    Rung-0 supremacy is preserved by construction: the safety interlock
    keeps index 0 no matter what is appended. The result is re-validated
    via :func:`make_program` and its version is bumped by one. This is
    the end-team hook for extending a program without touching rung 0.
    """
    if not isinstance(base_program, dict):
        raise ValueError("base_program must be a program dict")
    base_rungs = base_program.get("rungs") or []
    if not base_rungs:
        raise ValueError("base_program has no rungs")
    version = base_program.get("version", 1)
    combined = [base_rungs[0]] + list(extra_rungs or []) + list(base_rungs[1:])
    return make_program({"version": version + 1, "rungs": combined})


# ---------------------------------------------------------------------------
# FREEZE
# ---------------------------------------------------------------------------


def freeze_image(world: dict) -> Tuple[dict, str]:
    """Deep-freeze ``world`` into an immutable process image.

    Returns ``(image, image_hash)`` where ``image_hash`` is the sha256
    hex of ``json.dumps(image, sort_keys=True)`` — deterministic for
    equal content regardless of dict insertion order. Raises
    ``ValueError`` if the world is not JSON-serializable (fail-closed).
    Pure: no I/O, no clock.
    """
    if not isinstance(world, dict):
        raise ValueError(f"world must be a dict, got {type(world).__name__}")
    image = copy.deepcopy(world)
    try:
        canonical = json.dumps(image, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"process image is not JSON-serializable: {exc}") from exc
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return image, digest


# ---------------------------------------------------------------------------
# EXECUTE (pure)
# ---------------------------------------------------------------------------


def _resolve_args(args: Dict[str, Any], image: dict, rung_name: str) -> Dict[str, Any]:
    """Resolve coil args against the frozen image.

    A string value of the form ``"$signal"`` is a signal reference;
    a missing signal raises ``ValueError`` (fail-closed).
    """
    if not isinstance(args, dict):
        raise ValueError(f"rung {rung_name!r}: coil 'args' must be a dict")
    resolved = {}
    for key, value in args.items():
        if isinstance(value, str) and value.startswith("$") and len(value) > 1:
            signal = value[1:]
            if signal not in image:
                raise ValueError(
                    f"rung {rung_name!r}: $signal {signal!r} missing from image "
                    "(fail-closed)"
                )
            resolved[key] = copy.deepcopy(image[signal])
        else:
            resolved[key] = copy.deepcopy(value)
    return resolved


def _evaluate(
    program: Any,
    image: dict,
    latch_bits: dict,
    prev_image: Any = None,
) -> Tuple[list, dict, dict, int]:
    """Internal evaluation returning ``(rung_states, output_image, latch_updates, ops)``.

    ``ops`` counts contact evaluations (the watchdog's deterministic
    budget unit). Every contact in every branch is evaluated — no
    short-circuit — so ``ops`` is a pure function of the inputs.
    """
    rungs = program.get("rungs") if isinstance(program, dict) else program
    if not isinstance(rungs, (list, tuple)) or not rungs:
        raise ValueError("program needs a non-empty rung list")

    base = dict(latch_bits) if latch_bits else {}
    working = dict(base)  # latch-bit writes are visible to later rungs this cycle
    rung_states: List[Dict[str, Any]] = []
    staged: List[Tuple[str, str, Dict[str, Any], Dict[str, Any]]] = []
    ops = 0

    for rung in rungs:
        if not isinstance(rung, dict):
            raise ValueError("rung must be a dict")
        name = rung.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("rung needs a non-empty string 'name'")
        mode = rung.get("mode", "normal")
        if mode not in MODES:
            raise ValueError(f"rung {name!r}: unknown mode {mode!r}")

        raw = False
        for branch in rung.get("branches") or []:
            if not isinstance(branch, list):
                raise ValueError(f"rung {name!r}: branch must be a list of contacts")
            branch_true = True
            for contact in branch:
                ops += 1
                if not eval_contact(contact, image, prev_image):
                    branch_true = False
            if branch_true:
                raw = True

        if mode == "normal":
            state = bool(raw)
        elif mode == "latch":
            state = bool(raw or working.get(name, False))
            if raw:
                working[name] = True
        elif mode == "unlatch":
            target = rung.get("unlatch_target")
            if not isinstance(target, str) or not target:
                raise ValueError(
                    f"rung {name!r}: mode 'unlatch' needs 'unlatch_target'"
                )
            state = bool(raw)
            if raw:
                working[target] = False
        else:  # one_shot: true exactly one cycle on the rising edge
            state = bool(raw and not working.get(name, False))
            working[name] = bool(raw)

        entry = {"name": name, "state": state, "mode": mode, "overridden_by": None}
        rung_states.append(entry)

        if state:
            coil = rung.get("coil") or {}
            coil_name = coil.get("intent")
            if coil_name:
                args = _resolve_args(coil.get("args") or {}, image, name)
                risk = coil.get("risk", 0)
                staged.append(
                    (
                        coil_name,
                        name,
                        {"intent": coil_name, "args": args, "risk": risk},
                        entry,
                    )
                )

    # Last-rung-wins on coil conflict; record the override on the loser.
    output_image: Dict[str, Dict[str, Any]] = {}
    winner_entry: Dict[str, Dict[str, Any]] = {}
    for coil_name, rung_name, intent, entry in staged:
        if coil_name in output_image:
            winner_entry[coil_name]["overridden_by"] = rung_name
        winner_entry[coil_name] = entry
        output_image[coil_name] = intent

    latch_updates = {
        key: value
        for key, value in working.items()
        if key not in base or base[key] != value
    }
    return rung_states, output_image, latch_updates, ops


def evaluate(
    program: Any,
    image: dict,
    latch_bits: dict,
    prev_image: Any = None,
) -> Tuple[list, dict, dict]:
    """Evaluate ``program`` against the frozen ``image``. PURE.

    Returns ``(rung_states, output_image, latch_updates)``:

    - ``rung_states``: one ``{"name", "state", "mode", "overridden_by"}``
      entry per rung, in program order.
    - ``output_image``: ``{coil_intent_name: staged_intent}`` for rungs
      true this cycle; last-rung-wins on coil conflict.
    - ``latch_updates``: net latch-bit delta to persist cross-cycle.

    No I/O, no clock, no randomness — identical inputs give identical
    outputs, in this process or any other.
    """
    rung_states, output_image, latch_updates, _ops = _evaluate(
        program, image, latch_bits, prev_image
    )
    return rung_states, output_image, latch_updates


# ---------------------------------------------------------------------------
# The operational scan (§3.2)
# ---------------------------------------------------------------------------


def run_scan_cycle(
    world: dict,
    program: dict,
    *,
    gate,
    executor,
    budget_ms: float = 100,
    ops_budget: int = 100000,
    state: dict | None = None,
    scan_id: Any = None,
) -> Tuple[dict, dict]:
    """Run one full scan cycle: FREEZE → EXECUTE → FLUSH → HOUSEKEEPING.

    - ``gate(intent) -> bool``: permission gate over each staged intent
      (the staged intent dict ``{"intent", "args", "risk"}``). Denial —
      or a gate raising — halts the flush and records fault DENIED.
    - ``executor(intent)``: commits one allowed intent; may raise, which
      records fault FAILED and halts the flush.
    - ``state``: ``{"latch_bits", "prev_image", "scan_count"}``; never
      mutated — a new state dict is returned.

    Returns ``(receipt, new_state)``. The receipt is
    ``{"kind", "scan_id", "t", "image_hash", "program_version",
    "rung_states", "commits", "faults", "duration_ms", "watchdog_ok"}``
    with ``commits`` as ``[{"intent", "ok"}]`` and ``faults`` as
    ``[{"type", "detail"}]``.

    Fault policy (fail-closed): any exception during FREEZE/EXECUTE →
    fault EVAL; rung 0 true → fault INTERLOCK with the output image
    discarded and zero commits; gate denial / executor failure halts
    the flush; a blown time or ops budget appends fault OVERRUN. Every
    path writes a receipt and returns — there are no silent hangs and
    no silent skips.
    """
    t0 = time.perf_counter()
    faults: List[Dict[str, Any]] = []
    commits: List[Dict[str, Any]] = []

    prior = state or {}
    latch_bits = dict(prior.get("latch_bits") or {})
    prev_image = prior.get("prev_image")
    scan_count = int(prior.get("scan_count") or 0)

    # 1. FREEZE
    image = None
    image_hash = None
    try:
        image, image_hash = freeze_image(world)
    except Exception as exc:  # fail-closed: an unwritten receipt is itself a fault
        faults.append({"type": "EVAL", "detail": f"freeze failed: {exc}"})

    # 2. EXECUTE (pure)
    rung_states: List[Dict[str, Any]] = []
    output_image: Dict[str, Dict[str, Any]] = {}
    latch_updates: Dict[str, Any] = {}
    ops = 0
    evaluated_ok = False
    if image is not None:
        try:
            rung_states, output_image, latch_updates, ops = _evaluate(
                program, image, latch_bits, prev_image
            )
            evaluated_ok = True
        except Exception as exc:
            faults.append({"type": "EVAL", "detail": f"evaluate failed: {exc}"})
            rung_states, output_image, latch_updates, ops = [], {}, {}, 0

    halted = bool(faults)

    # Rung-0 supremacy: a tripped interlock discards the output image.
    if not halted and rung_states and rung_states[0]["state"]:
        faults.append(
            {
                "type": "INTERLOCK",
                "detail": (
                    f"safety interlock rung {rung_states[0]['name']!r} tripped; "
                    "output image discarded, zero commits"
                ),
            }
        )
        output_image = {}
        halted = True

    # 3. FLUSH staged intents in rung order (last-wins already applied).
    if not halted:
        rungs = program.get("rungs") if isinstance(program, dict) else program
        if not isinstance(rungs, (list, tuple)):
            rungs = []
        committed_coils: set = set()
        for rung, entry in zip(rungs, rung_states, strict=False):
            if not entry.get("state"):
                continue
            coil_name = (
                (rung.get("coil") or {}).get("intent")
                if isinstance(rung, dict)
                else None
            )
            if not coil_name or coil_name in committed_coils:
                continue
            if coil_name not in output_image:
                continue
            committed_coils.add(coil_name)
            intent = output_image[coil_name]
            try:
                verdict = gate(intent)
            except Exception as exc:
                verdict = False
                gate_detail = f"gate raised on {coil_name!r}: {exc}"
            else:
                gate_detail = f"gate denied intent {coil_name!r}"
            if not verdict:
                faults.append({"type": "DENIED", "detail": gate_detail})
                halted = True
                break
            try:
                executor(intent)
            except Exception as exc:
                commits.append({"intent": coil_name, "ok": False})
                faults.append(
                    {
                        "type": "FAILED",
                        "detail": f"executor failed on {coil_name!r}: {exc}",
                    }
                )
                halted = True
                break
            commits.append({"intent": coil_name, "ok": True})

    # 4. HOUSEKEEPING
    duration_ms = (time.perf_counter() - t0) * 1000.0
    watchdog_ok = bool(duration_ms <= budget_ms and ops <= ops_budget)
    if not watchdog_ok:
        faults.append(
            {
                "type": "OVERRUN",
                "detail": (
                    f"budget exceeded: {duration_ms:.3f}ms vs {budget_ms}ms budget, "
                    f"{ops} contact-evaluations vs {ops_budget} ops budget"
                ),
            }
        )
        halted = True

    if evaluated_ok:
        new_latch = dict(latch_bits)
        new_latch.update(latch_updates)
    else:
        new_latch = dict(latch_bits)
    new_state = {
        "latch_bits": new_latch,
        "prev_image": copy.deepcopy(image) if image is not None else None,
        "scan_count": scan_count + 1,
    }

    receipt = {
        "kind": "scan",
        "scan_id": scan_id if scan_id is not None else f"scan-{scan_count + 1:06d}",
        "t": time.time(),
        "image_hash": image_hash,
        "program_version": program.get("version", 1)
        if isinstance(program, dict)
        else 1,
        "rung_states": copy.deepcopy(rung_states),
        "commits": commits,
        "faults": faults,
        "duration_ms": duration_ms,
        "watchdog_ok": watchdog_ok,
    }
    return receipt, new_state


# ---------------------------------------------------------------------------
# Rendering (readability without ladder glyphs)
# ---------------------------------------------------------------------------


def render_rung(rung: dict) -> str:
    """Render one rung as a readable card line.

    Example: ``rung "pump_seal": [start_cmd is_true] → coil: pump (latch)``.
    No ladder glyphs (no XIC/XIO/OTE, no box drawing) — the stored form
    is the data; this is only the human-readable line.
    """
    rung = rung or {}
    name = rung.get("name", "?")
    mode = rung.get("mode", "normal")
    branch_texts = []
    for branch in rung.get("branches") or []:
        contacts = []
        for contact in branch or []:
            contact = contact or {}
            signal = contact.get("signal", "?")
            pred = contact.get("pred", "?")
            value = contact.get("value")
            if value is None:
                contacts.append(f"{signal} {pred}")
            else:
                contacts.append(f"{signal} {pred} {value!r}")
        branch_texts.append("[" + " AND ".join(contacts) + "]")
    condition = " OR ".join(branch_texts) if branch_texts else "[never]"
    coil = rung.get("coil") or {}
    intent = coil.get("intent", "?")
    safety = " safety" if rung.get("safety") else ""
    return f'rung "{name}"{safety}: {condition} → coil: {intent} ({mode})'
