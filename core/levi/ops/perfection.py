"""Perfection layer score — completeness under local-first constraints."""
from __future__ import annotations

from typing import List, Tuple


def perfection_report() -> str:
    checks: List[Tuple[str, bool, str]] = []

    def add(name, fn):
        try:
            ok, detail = fn()
            checks.append((name, bool(ok), detail))
        except Exception as e:
            checks.append((name, False, str(e)[:80]))

    def organs():
        from levi.graph.organism import ORGANS, BLOODSTREAM
        return len(ORGANS) >= 28 and len(BLOODSTREAM) >= 30, f"organs={len(ORGANS)} bonds={len(BLOODSTREAM)}"

    def pairs():
        from levi.graph.symbiosis import PAIRS
        return len(PAIRS) >= 20, f"pairs={len(PAIRS)}"

    def free():
        from levi.integrations.free_lattice import free_catalog
        return len(free_catalog()) >= 18, f"free={len(free_catalog())}"

    def integrate():
        from levi.ops.integration import run_integration_audit
        out = run_integration_audit()
        return "10/10" in out or "[OK]" in out, "audit ran"

    def ladder():
        from levi.meta.ladder import format_ladder
        out = format_ladder()
        return "STEP 1: PASS" in out, "step1"

    def provenance():
        from levi.identity.provenance import PROVENANCE
        return PROVENANCE.get("closed_source") is True, "closed_source"

    def lwp():
        from levi.lwp.model_engine import LWPModelEngine
        return hasattr(LWPModelEngine, "expand"), "ssa"

    def runtime_engines():
        from levi.runtime.crucible import Crucible
        from levi.runtime.service_mesh import ServiceMesh
        r = Crucible().syntax_probe("x=1")
        return r.ok and len(ServiceMesh().list()) >= 8, "crucible+services"

    def ui():
        from pathlib import Path
        from levi.ops.serve_ui import find_static
        s = find_static()
        return (s / "levi-ops.html").exists() and (s / "lwp-model.html").exists(), str(s)

    for n, f in [
        ("organism", organs),
        ("symbiosis", pairs),
        ("free_lattice", free),
        ("integrate", integrate),
        ("ladder", ladder),
        ("provenance", provenance),
        ("lwp_model", lwp),
        ("interactive_ui", ui),
        ("runtime_engines", runtime_engines),
    ]:
        add(n, f)

    ok = sum(1 for _, o, _ in checks if o)
    n = len(checks)
    pct = int(100 * ok / n) if n else 0
    lines = [f"=== LEVI Perfection Layer  [{ok}/{n}]  ~{pct}% gates ===", ""]
    for name, o, detail in checks:
        lines.append(f"  {'OK' if o else 'GAP'}  {name:18} {detail}")
    lines.append("")
    if pct >= 90:
        lines.append("Perfection layer: production-ready under local-complete target.")
    elif pct >= 70:
        lines.append("Perfection layer: strong — close remaining gaps.")
    else:
        lines.append("Perfection layer: keep hardening.")
    lines.append("Deferred by design: fat multi-tenant UI, live multi-cloud billing, glyph compress.")
    return "\n".join(lines)
