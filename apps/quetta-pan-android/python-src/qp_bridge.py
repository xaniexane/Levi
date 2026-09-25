"""Quetta-Pan Android bridge (standalone wrapper).

JSON in/out over the quetta_pan engine:
  choose target -> dry-run -> review -> apply approved -> iterate.

Quetta-Pan never silently mutates: apply always goes through the engine's
backup -> write -> guard-evaluate flow, and this UI requires an explicit
tap before any write.
"""

from __future__ import annotations

import json
from pathlib import Path

_WORKSPACE: Path | None = None
_ENGINE = None


def _ws() -> Path:
    if _WORKSPACE is None:
        raise RuntimeError("workspace not set")
    return _WORKSPACE


def set_workspace(path: str) -> str:
    global _WORKSPACE, _ENGINE
    _WORKSPACE = Path(path)
    _WORKSPACE.mkdir(parents=True, exist_ok=True)
    _ENGINE = None  # rebind the engine to the new workspace
    return "true"


def _err(exc: BaseException) -> str:
    return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def laws() -> str:
    """The operating laws, built into the app — not just documented."""
    return json.dumps(
        [
            {
                "name": "law-guard-prove",
                "text": "Every change declares its law, passes a guard, and carries "
                "proof. Dry-run never writes; apply = backup, write, "
                "guard-evaluate; iterate stops when stable.",
            },
            {
                "name": "honesty-over-polish",
                "text": "Applied vs guard-held is always reported, with the reason. "
                "Limits are stated, not hidden.",
            },
            {
                "name": "nothing-thrown-away",
                "text": "Every apply leaves a timestamped backup. Nothing is "
                "deleted — this app has no delete action at all.",
            },
            {
                "name": "one-organism",
                "text": "All of Legion is Levi, one organism. Quetta-Pan is a limb "
                "of the same body.",
            },
        ]
    )


def _engine():
    global _ENGINE
    if _ENGINE is None:
        from levi.quetta_pan.engine import QuettaPanEngine

        ws = _ws()
        _ENGINE = QuettaPanEngine(
            project_root=str(ws), store_dir=str(ws / ".qp")
        )
    return _ENGINE


def _py_files() -> list[Path]:
    ws = _ws()
    return [
        p for p in sorted(ws.rglob("*.py"))
        if ".qp" not in p.parts and ".elite.bak" not in p.name
    ][:100]


def seed_workspace() -> str:
    try:
        ws = _ws()
        sample = ws / "sample.py"
        if not sample.exists():
            sample.write_text(
                '"""Sample file — point Quetta-Pan at it."""\n\n\n'
                'def add(a,b):\n    return a+b\n\n\n'
                'x=1\nprint( add(x,2) )\n',
                encoding="utf-8",
            )
        return json.dumps({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def scan() -> str:
    """Dry-run over the whole workspace. No writes."""
    try:
        eng = _engine()
        results = []
        for f in _py_files():
            try:
                sug = eng.suggest_upgrades(f)
                upgrades = sug.get("upgrades", [])
                if upgrades:
                    results.append(
                        {
                            "file": f.relative_to(_ws()).as_posix(),
                            "upgrades": upgrades,
                            "count": len(upgrades),
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "file": f.relative_to(_ws()).as_posix(),
                        "upgrades": [f"(scan error: {exc})"],
                        "count": 0,
                    }
                )
        return json.dumps({"ok": True, "results": results})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def detail(rel: str) -> str:
    try:
        eng = _engine()
        sug = eng.suggest_upgrades(_ws() / rel)
        safe = {
            "file": str(sug.get("file", rel)),
            "upgrades": list(sug.get("upgrades", [])),
            "suggestions": [
                {
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "desc": s.get("desc"),
                    "severity": s.get("severity"),
                }
                for s in sug.get("suggestions", [])
            ],
            "diff": str(sug.get("diff", ""))[:8000],
        }
        return json.dumps({"ok": True, "suggestion": safe})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def apply_one(rel: str) -> str:
    """Apply to one file — explicit user tap required upstream."""
    try:
        eng = _engine()
        sug = eng.suggest_upgrades(_ws() / rel)
        if not sug.get("suggestions"):
            return json.dumps({"ok": True, "applied": False, "detail": "no suggestions"})
        res = eng.apply_suggestion(sug)
        return json.dumps(
            {
                "ok": bool(res.ok),
                "applied": bool(res.ok),
                "detail": "" if res.ok else str(res.failure_reason),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def apply_all() -> str:
    try:
        eng = _engine()
        applied, failed, details = 0, 0, []
        for f in _py_files():
            try:
                sug = eng.suggest_upgrades(f)
                if not sug.get("suggestions"):
                    continue
                res = eng.apply_suggestion(sug)
                if res.ok:
                    applied += 1
                else:
                    failed += 1
                    details.append(f"{f.name}: {res.failure_reason}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                details.append(f"{f.name}: {exc}")
        return json.dumps(
            {"ok": True, "applied": applied, "failed": failed, "details": details[:20]}
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def iterate(rounds: int) -> str:
    try:
        rounds = max(1, min(int(rounds), 10))
        eng = _engine()
        log: list[str] = []
        applied_total = 0
        passes = 0
        for i in range(rounds):
            passes = i + 1
            changed = 0
            for f in _py_files():
                try:
                    sug = eng.suggest_upgrades(f)
                    if not sug.get("suggestions"):
                        continue
                    res = eng.apply_suggestion(sug)
                    name = f.relative_to(_ws()).as_posix()
                    if res.ok:
                        changed += 1
                        applied_total += 1
                        log.append(f"pass {passes}: {name} improved")
                    else:
                        log.append(f"pass {passes}: {name} guard-held ({res.failure_reason})")
                except Exception as exc:  # noqa: BLE001
                    log.append(f"pass {passes}: {f.name} error {exc}")
            if changed == 0:
                log.append(f"pass {passes}: no changes — stable")
                break
        return json.dumps(
            {"ok": True, "passes": passes, "applied": applied_total, "log": log[-40:]}
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)
