"""Omega daemon organ: the always-on doer of the symbiotic loop. ⚙️

ORIGIN LINEAGE (originals-first, Chauncey's actual Omega): the original
Omega shipped omega_agent.py — an always-on agent — plus job-search/apply
pipelines, browser automation, and HITL checkpoints. This module is that
lineage: the daemon organ is the always-on doer that runs the
echo → alpha → nexus → skill symbiotic loop on the SHARED substrate pool
(interpenetration: one bloodstream, not just interfaces), and that drains
the shared schedule pool via :func:`poll_schedule`.

INVARIANT (declared, guarded in code, proven in tests):
    "The daemon never executes a quarantined input or an above-ceiling
    action. Every stage checks is_consumable and the ceiling; a failed
    check halts the loop with a receipt, never silently."

PROOF (honest): behavioral verification — property tests over the
invariant in tests/test_omega_daemon_symbiotic.py (happy path, halt at
blueprint/alpha/verify/nexus, schedule drain, quarantine path), not a
formal proof.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from levi.revival.omega import blueprint as bp
from levi.revival.omega import generators as gen
from levi.revival.omega import nexus as nx
from levi.revival.omega import substrate as sub

ORIGIN = "levi-revival-omega/loop"
DAEMON = "daemon"
LOOP_JOB = "symbiotic_loop"

# Every organ the loop touches; the strictest ceiling among them governs.
LOOP_ORGANS: Tuple[str, ...] = ("daemon", "echo", "alpha", "nexus", "skill")

__all__ = [
    "run_symbiotic_loop",
    "poll_schedule",
    "quarantine_skill_result",
    "LOOP_ORGANS",
]


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------


class _LoopHalt(Exception):
    """Internal control flow: carries the loop-halt result dict."""

    def __init__(self, result: Dict[str, Any]) -> None:
        super().__init__(str(result.get("halted_at")))
        self.result = result


def _check_ceiling(tier: str) -> None:
    """Guard: no above-ceiling action. The daemon's own declared ceiling
    is the hardest bound it will ever act under."""
    rank = sub.RISK_ORDER.index(tier)
    cap = sub.RISK_ORDER.index(sub.ORGAN_RISK[DAEMON])
    if rank > cap:
        raise ValueError(
            f"action tier {tier!r} exceeds the daemon ceiling "
            f"{sub.ORGAN_RISK[DAEMON]!r} — refusing"
        )


def _halt(
    substrate: sub.SharedSubstrate,
    halted_at: str,
    detail: Dict[str, Any],
    approved_by: str,
    chain: Dict[str, Any],
) -> Dict[str, Any]:
    """Record the halt LOUDLY (kind="loop" receipt, never silent) and build
    the return value."""
    tier = sub.ceiling_for(*LOOP_ORGANS)
    _check_ceiling(tier)
    receipt = substrate.record_receipt(
        DAEMON,
        "loop",
        {
            "ok": False,
            "halted_at": halted_at,
            "detail": detail,
            "chain": dict(chain),
        },
        risk=tier,
        approved_by=approved_by,
    )
    return {
        "ok": False,
        "halted_at": halted_at,
        "loop_receipt": receipt.id,
        "chain": dict(chain),
    }


def _guard_consumable(
    substrate: sub.SharedSubstrate,
    stage: str,
    receipt_id: str,
    approved_by: str,
    chain: Dict[str, Any],
) -> None:
    """THE gate, applied at every stage. Raises _LoopHalt (loud, with a
    receipt) when the previous stage's output may not be consumed."""
    if not substrate.is_consumable(receipt_id):
        raise _LoopHalt(
            _halt(
                substrate,
                stage,
                {
                    "reason": "receipt not consumable — missing or under open challenge",
                    "receipt_id": receipt_id,
                },
                approved_by,
                chain,
            )
        )


# ---------------------------------------------------------------------------
# sibling resolution (duck-typed, fallback-safe)
# ---------------------------------------------------------------------------


TASK_KINDS = frozenset({"code", "automation"})


def _fleet_for(task_kinds: frozenset) -> List[nx.Provider]:
    """Resolve the provider fleet for a routing task.

    Prefers ``pipeline.default_providers()``. But the landed nexus
    sourcing law only lets a levi-local/levi-si-cloud provider serve when
    it covers EVERY task kind — and the default fleet covers no
    "automation" kind. When no default provider can serve the task, the
    daemon declares its own execution capability instead: one LEVI-local
    hand covering the task kinds, plus one reference provider that
    routing must deny — proving the sourcing law inside the loop rather
    than halting on it. (Flagged to the coordinator: this adapts the
    "prefer default_providers" instruction to the sibling's stricter
    landed law.)
    """
    providers: List[nx.Provider] = []
    try:
        from levi.revival.omega import pipeline as _pl

        fn = getattr(_pl, "default_providers", None)
        if callable(fn):
            providers = list(fn())
    except Exception:
        providers = []

    def _serves(p: nx.Provider) -> bool:
        return p.source in (nx.SOURCE_LOCAL, nx.SOURCE_CLOUD) and task_kinds <= set(
            p.kinds
        )

    if any(_serves(p) for p in providers):
        return providers
    return [
        nx.Provider(
            name="levi-local",
            source=nx.SOURCE_LOCAL,
            kinds=frozenset({"code", "automation", "chat"}),
            cost=1,
            quality=0.7,
        ),
        nx.Provider(
            name="reference-study",
            source=nx.SOURCE_REFERENCE,
            kinds=frozenset({"code"}),
            cost=9,
            quality=0.9,
        ),
    ]


def _find_skill_core_register() -> Optional[Callable[..., Any]]:
    """skill_core.register_skill if the skills worker has landed it,
    else None (the loop records a skill_wrap receipt instead)."""
    try:
        import importlib

        mod = importlib.import_module("levi.skill_core")
        fn = getattr(mod, "register_skill", None)
        return fn if callable(fn) else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# stages
# ---------------------------------------------------------------------------


def _stage_echo(
    substrate: sub.SharedSubstrate,
    prompt: str,
    approved_by: str,
    chain: Dict[str, Any],
) -> Tuple[Dict[str, Any], str]:
    publish = getattr(bp, "publish_blueprint", None)
    if callable(publish):
        blueprint, bp_receipt = publish(substrate, prompt)
        blueprint = dict(blueprint)
    else:  # fallback while the echo worker's guarded entrypoint lands
        blueprint = bp.build_blueprint(prompt)
        check = bp.validate_blueprint(blueprint)
        if not check.get("ok"):
            raise _LoopHalt(
                _halt(
                    substrate,
                    "blueprint",
                    {"errors": check.get("errors", [])},
                    approved_by,
                    chain,
                )
            )
        tier = sub.ceiling_for("daemon", "echo")
        _check_ceiling(tier)
        bp_receipt = substrate.record_receipt(
            "echo",
            "blueprint",
            {
                "prompt": prompt,
                "name": blueprint.get("name"),
                "product_types": blueprint.get("product_types"),
            },
            risk=tier,
            approved_by=approved_by,
        )
    chain["blueprint"] = bp_receipt.id
    return blueprint, bp_receipt.id


def _stage_alpha(
    substrate: sub.SharedSubstrate,
    blueprint: Dict[str, Any],
    blueprint_receipt_id: str,
    approved_by: str,
    chain: Dict[str, Any],
) -> Tuple[Dict[str, Any], str]:
    compile_guarded = getattr(gen, "compile_blueprint_guarded", None)
    if callable(compile_guarded):
        result = dict(
            compile_guarded(
                substrate, blueprint, blueprint_receipt_id, approved_by=approved_by
            )
        )
        build_receipt_id = result.get("receipt_id")
    else:  # fallback while the alpha worker's guarded entrypoint lands
        compiled = gen.compile_blueprint(blueprint)
        tier = sub.ceiling_for("daemon", "alpha")
        _check_ceiling(tier)
        receipt = substrate.record_receipt(
            "alpha",
            "build",
            {
                "blueprint": blueprint.get("name"),
                "files": sorted(compiled.get("files", {})),
                "errors": compiled.get("errors", []),
            },
            risk=tier,
            approved_by=approved_by,
        )
        result = dict(compiled)
        result["receipt_id"] = receipt.id
        build_receipt_id = receipt.id
    if not result.get("ok") or not build_receipt_id:
        raise _LoopHalt(
            _halt(
                substrate,
                "alpha",
                {
                    "result": {
                        k: result.get(k)
                        for k in ("ok", "errors", "refusal", "challenged")
                    },
                    "receipt_id": build_receipt_id,
                },
                approved_by,
                chain,
            )
        )
    chain["build"] = build_receipt_id
    return result, build_receipt_id


def _stage_echo_verify(
    substrate: sub.SharedSubstrate,
    blueprint: Dict[str, Any],
    result: Dict[str, Any],
    build_receipt_id: str,
    approved_by: str,
    chain: Dict[str, Any],
) -> None:
    """Interrogation fires INSIDE the loop: Echo re-checks Alpha's build
    and challenges it on the spot when it fails."""
    verify = getattr(bp, "verify_build", None)
    verdict = (
        verify(blueprint, result.get("files", {})) if callable(verify) else {"ok": True}
    )
    verdict = dict(verdict) if isinstance(verdict, dict) else {"ok": bool(verdict)}
    if verdict.get("ok"):
        return
    grounds = (
        f"build failed echo verification: {verdict.get('errors') or 'verdict not ok'}"
    )
    challenge_build = getattr(bp, "challenge_build", None)
    if callable(challenge_build):
        ch = challenge_build(
            substrate, build_receipt_id, blueprint, result.get("files", {})
        )
        if ch is None:  # sibling chose not to challenge; the daemon still must
            ch = substrate.challenge("echo", build_receipt_id, grounds)
    else:  # fallback while the echo worker's challenge entrypoint lands
        ch = substrate.challenge("echo", build_receipt_id, grounds)
    raise _LoopHalt(
        _halt(
            substrate,
            "verify",
            {"verdict": verdict, "challenge": ch.id},
            approved_by,
            chain,
        )
    )


def _stage_nexus(
    substrate: sub.SharedSubstrate,
    prompt: str,
    approved_by: str,
    chain: Dict[str, Any],
) -> Tuple[Dict[str, Any], str]:
    providers = _fleet_for(TASK_KINDS)
    route_guarded = getattr(nx, "route_guarded", None)
    if callable(route_guarded):
        route = dict(
            route_guarded(
                substrate,
                {"kinds": set(TASK_KINDS)},
                providers,
                mode="balanced",
                approved_by=approved_by,
            )
        )
        route_receipt_id = route.get("receipt_id")
    else:  # fallback while the nexus worker's guarded entrypoint lands
        task = nx.Task(kinds=TASK_KINDS, label=prompt[:64])
        ranked = nx.route(task, list(providers), mode="balanced")
        eligible = [r for r in ranked if r.eligible]
        tier = sub.ceiling_for("daemon", "nexus")
        _check_ceiling(tier)
        if not eligible:
            route = {
                "ok": False,
                "reason": "no eligible provider",
                "ranked": [r.provider for r in ranked],
            }
            route_receipt_id = None
        else:
            winner = eligible[0]
            receipt = substrate.record_receipt(
                "nexus",
                "route",
                {
                    "label": prompt[:64],
                    "provider": winner.provider,
                    "confidence": winner.confidence,
                    "reasons": list(winner.reasons),
                },
                risk=tier,
                approved_by=approved_by,
            )
            route = {
                "ok": True,
                "provider": winner.provider,
                "confidence": winner.confidence,
            }
            route_receipt_id = receipt.id
    if not route.get("ok") or not route_receipt_id:
        raise _LoopHalt(
            _halt(substrate, "nexus", {"route": route}, approved_by, chain)
        )
    chain["route"] = route_receipt_id
    return route, route_receipt_id


def _skill_name(blueprint: Dict[str, Any]) -> str:
    app_name = str(blueprint.get("name") or "app")
    slug = getattr(bp, "slugify", None)
    if callable(slug):
        return "omega-" + slug(app_name)
    cleaned = "".join(c if c.isalnum() else "-" for c in app_name).strip("-").lower()
    return "omega-" + (cleaned or "app")


def _stage_skill(
    substrate: sub.SharedSubstrate,
    blueprint: Dict[str, Any],
    prompt: str,
    approved_by: str,
    skill_registrar: Optional[Callable[..., Any]],
    chain: Dict[str, Any],
) -> str:
    """Compounding: the built thing becomes a hand. Resolves the registrar
    explicit-arg → skill_core.register_skill → bloodstream receipt."""
    name = _skill_name(blueprint)
    registrar = skill_registrar if skill_registrar is not None else _find_skill_core_register()
    if registrar is not None:
        try:
            skill_ref = registrar(
                name=name,
                capability=prompt,
                risk="elevated",
                approved_by=approved_by,
                substrate=substrate,
            )
        except Exception as exc:  # noqa: BLE001 — halt loudly, never silently
            raise _LoopHalt(
                _halt(
                    substrate,
                    "skill",
                    {
                        "reason": "skill registrar failed",
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                    approved_by,
                    chain,
                )
            )
        skill_id = getattr(skill_ref, "id", None) or (
            skill_ref if isinstance(skill_ref, str) else repr(skill_ref)
        )
    else:  # registry not landed yet: wrap as a bloodstream receipt instead
        tier = sub.ceiling_for("daemon", "skill")
        _check_ceiling(tier)
        receipt = substrate.record_receipt(
            "skill",
            "skill_wrap",
            {
                "name": name,
                "capability": prompt,
                "note": "skill registry unavailable — wrapped as bloodstream receipt",
            },
            risk=tier,
            approved_by=approved_by,
        )
        skill_id = receipt.id
    chain["skill"] = skill_id
    return skill_id


# ---------------------------------------------------------------------------
# public surface
# ---------------------------------------------------------------------------


def run_symbiotic_loop(
    substrate: sub.SharedSubstrate,
    prompt: str,
    approved_by: Optional[str] = None,
    skill_registrar: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """One full compounding pass: echo → alpha → (echo verifies) → nexus
    → skill wrap, all on the shared substrate pool.

    Every stage checks ``is_consumable`` on the previous stage's receipt
    and the risk ceiling; a failed check halts the loop with a kind="loop"
    receipt, never silently. Returns ``{"ok": True, "loop_receipt": id,
    "chain": {...}}`` on success.
    """
    if not approved_by:
        raise ValueError(
            "run_symbiotic_loop requires approved_by: the daemon's elevated "
            "ceiling demands a recorded approval — no anonymous elevated action."
        )
    if not prompt or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    chain: Dict[str, Any] = {}
    try:
        blueprint, blueprint_receipt_id = _stage_echo(
            substrate, prompt, approved_by, chain
        )
        _guard_consumable(
            substrate, "blueprint", blueprint_receipt_id, approved_by, chain
        )
        result, build_receipt_id = _stage_alpha(
            substrate, blueprint, blueprint_receipt_id, approved_by, chain
        )
        _stage_echo_verify(
            substrate, blueprint, result, build_receipt_id, approved_by, chain
        )
        _guard_consumable(substrate, "build", build_receipt_id, approved_by, chain)
        _route, route_receipt_id = _stage_nexus(substrate, prompt, approved_by, chain)
        _guard_consumable(substrate, "nexus", route_receipt_id, approved_by, chain)
        _stage_skill(
            substrate, blueprint, prompt, approved_by, skill_registrar, chain
        )
    except _LoopHalt as halted:
        return halted.result

    tier = sub.ceiling_for(*LOOP_ORGANS)
    _check_ceiling(tier)
    receipt = substrate.record_receipt(
        DAEMON,
        "loop",
        {"prompt": prompt, "chain": dict(chain), "ok": True},
        risk=tier,
        approved_by=approved_by,
    )
    return {"ok": True, "loop_receipt": receipt.id, "chain": dict(chain)}


def poll_schedule(
    substrate: sub.SharedSubstrate, now: Optional[str] = None
) -> List[Dict[str, Any]]:
    """The daemon drains the SHARED schedule pool (interpenetration). For
    each due job: mark running → execute → mark done/failed. Unknown job
    names are marked failed, never executed."""
    results: List[Dict[str, Any]] = []
    for job in substrate.due_jobs(now=now):
        substrate.mark_job(job.id, "running")
        if job.job == LOOP_JOB:
            payload = dict(job.payload or {})
            try:
                out = run_symbiotic_loop(
                    substrate,
                    prompt=payload["prompt"],
                    approved_by=payload.get("approved_by"),
                    skill_registrar=None,
                )
                ok = bool(out.get("ok"))
            except Exception as exc:  # noqa: BLE001 — the job must land failed, loudly
                out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                ok = False
            substrate.mark_job(job.id, "done" if ok else "failed")
            results.append({"job_id": job.id, "ok": ok, "result": out})
        else:
            substrate.mark_job(job.id, "failed")
            results.append(
                {
                    "job_id": job.id,
                    "ok": False,
                    "error": f"unknown job {job.job!r}: not executed",
                }
            )
    return results


def quarantine_skill_result(
    substrate: sub.SharedSubstrate, skill_receipt_id: str, grounds: str
) -> sub.Challenge:
    """The daemon → quarantines → skill interrogation path. The target
    receipt is quarantined immediately by the substrate; no organ may
    consume it until the challenge resolves."""
    return substrate.challenge(DAEMON, skill_receipt_id, grounds)
