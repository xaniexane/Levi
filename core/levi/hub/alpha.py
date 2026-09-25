"""hub.alpha: the creation lab INSIDE the hub.

Proven shape from the original: ``omega_cli alpha "prompt"`` →
Echo (blueprint architect) designs the spec → Alpha (no-code compiler)
compiles it through template generators → build dir + manifest.
We follow that shape exactly; only the machinery is ours
(``levi.revival.omega`` organs, stdlib file writes).

Non-interactive by design: the forge pipeline's permission stage becomes
a HITL record here. ``approve=False`` (default) writes nothing — it
returns the blueprint + preview and opens an approval request. The
founder's word (or ``approve=True`` with an approved HITL id) lets it
materialize.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from . import hitl
from levi.revival.omega import blueprint as echo
from levi.revival.omega import generators as alpha_gen


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def design(prompt: str) -> Dict[str, Any]:
    """Echo: prompt → validated blueprint. Pure, no side effects."""
    bp = echo.build_blueprint(prompt)
    check = echo.validate_blueprint(bp)
    return {
        "ok": bool(check.get("ok", True)),
        "blueprint": bp,
        "validation": check,
        "detected_types": echo.detect_product_types(prompt),
        "label": "INFERENCE",
    }


def preview(prompt: str) -> Dict[str, Any]:
    """Echo + Alpha compile, no writes. What WOULD be built."""
    d = design(prompt)
    if not d["ok"]:
        return d
    compiled = alpha_gen.compile_blueprint(d["blueprint"])
    if not compiled["ok"]:
        return {"ok": False, "errors": compiled["errors"], "blueprint": d["blueprint"]}
    files = compiled["files"]
    return {
        "ok": True,
        "blueprint": d["blueprint"],
        "files": sorted(files.keys()),
        "sizes": {k: len(v) for k, v in files.items()},
        "label": "INFERENCE",
    }


def create(
    prompt: str,
    dest: str,
    *,
    approve: bool = False,
    hitl_id: Optional[int] = None,
    overwrite: bool = False,
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Alpha: blueprint → generators → build dir + manifest.

    Without approval this writes nothing and opens a HITL request
    (the forge pipeline's permission stage, non-interactive).
    """
    d = design(prompt)
    if not d["ok"]:
        return d
    compiled = alpha_gen.compile_blueprint(d["blueprint"])
    if not compiled["ok"]:
        return {"ok": False, "errors": compiled["errors"], "blueprint": d["blueprint"]}
    if not dest or not str(dest).strip():
        raise ValueError("dest is required — give me a real directory")
    files = compiled["files"]
    dest_p = Path(dest)
    if not approve:
        req = hitl.request_approval(
            "alpha.create",
            {
                "prompt": prompt,
                "dest": str(dest_p),
                "files": sorted(files.keys()),
                "product_types": d["blueprint"].get("product_types"),
            },
            path=path,
        )
        return {
            "ok": False,
            "blocked": "approval_required",
            "hitl_id": req["id"],
            "preview": {"files": sorted(files.keys())},
            "note": "nothing written — approve HITL request to materialize",
            "label": "OBSERVED",
        }
    hitl.require(hitl_id, path=path)
    if dest_p.exists() and not overwrite and any(dest_p.iterdir()):
        return {
            "ok": False,
            "error": f"{dest} exists and is not empty (pass overwrite)",
        }
    dest_p.mkdir(parents=True, exist_ok=True)
    written = []
    for name, content in files.items():
        target = dest_p / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(name)
    manifest = {
        "app": d["blueprint"].get("app_name", dest_p.name),
        "prompt": prompt,
        "product_types": d["blueprint"].get("product_types"),
        "files": written,
        "built_at": _now(),
        "built_by": "levi.hub alpha (Echo→Alpha, ours-only)",
        "hitl_id": hitl_id,
        "label": "OBSERVED",
    }
    (dest_p / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return {"ok": True, "dest": str(dest_p), "files": written, "manifest": manifest}
