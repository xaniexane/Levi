"""Quetta-Pan engine rebuilt — v10.0 mechanics, REIM/RIEM loop wired in.

Carried forward from the v10.0 original (read-only, untouched):
scanner, the 10 heuristic rule IDs, the three safe fixes, the 10-tier
forward projections, dry-run default, per-file approval, timestamped
backups, and the approvals/rejections/runs history log.

Wired in (the honest gap v10.0 left open):
- apply_suggestion(): the guarded write path. Backup -> write ->
  evaluate -> on failure rollback + REIM compost + RIEM learn;
  on success RIEM records the win.
- suggest_upgrades(): consults the RIEM genome BEFORE generating;
  suppressed rules are withheld with a stated reason.
- Optional QuettaPanDaVinci brain: its detect_mutations feed the
  suggestion list as info-severity items.

Loop invariants (see package docstring) are enforced here, not advised.
"""

from __future__ import annotations

import ast
import difflib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .brain import QuettaPanDaVinci
from .evaluate import MutationResult, evaluate_mutation
from .reim import ReimCompost
from .riem import RiemGenome, context_key_for

EXTENSIONS = (".py", ".js", ".ts", ".jsx", ".tsx")
EXCLUDED_PARTS = ("node_modules", "dist", ".git", ".quetta_backups")

# ---- v10.0 heuristic rules, carried forward verbatim ----------------------

PY_RULES = [
    (
        "PY_FSTRING",
        "Migrate to F-Strings",
        "Traditional string formatting (.format() / %) detected. F-strings are "
        "faster, more readable, and reduce memory allocation overhead.",
        "info",
    ),
    (
        "PY_BARE_EXCEPT",
        "Hardened Exception Blocks",
        "Bare 'except:' statement caught. This catches SystemExit, "
        "KeyboardInterrupt, and other process signals, leading to stuck thread "
        "states.",
        "warning",
    ),
    (
        "PY_LIST_COMP",
        "Vectorize to List Comprehension",
        "Imperative array accumulation detected inside loop blocks. Converting "
        "to list comprehensions optimizes bytecode execution.",
        "info",
    ),
    (
        "PY_MUTABLE_DEFAULTS",
        "Mutable Default Parameters",
        "Detected dictionary or list as default function arguments. These "
        "retain state across calls, causing elusive state contamination.",
        "warning",
    ),
]

TS_RULES = [
    (
        "TS_VAR_USAGE",
        "De-Scope 'var' Assignments",
        "Lexically hoisted 'var' detected. Swapping to block-scoped 'const' or "
        "'let' avoids variable pollution and execution bugs.",
        "warning",
    ),
    (
        "TS_LOOSE_EQUALITY",
        "Use Strict Equivalence",
        "Detected non-strict comparison (== or !=). This triggers implicit "
        "runtime casting rules which leads to logic flaws.",
        "warning",
    ),
    (
        "TS_EFFECT_LOOP",
        "Infinite Re-render Vulnerability",
        "React useEffect call without dependency array detected. This causes "
        "execution cycles on every DOM repaint.",
        "error",
    ),
    (
        "TS_LOOSE_TYPING",
        "Eradicate 'any' constructs",
        "Using 'any' turns off the static type analyzer. Map explicit custom "
        "interfaces or generic limits instead.",
        "warning",
    ),
    (
        "TS_UNMEMOIZED_MATRIX",
        "Memoize Multi-Cell Computation",
        "Detected heavy inline array transformations inside a high-frequency "
        "component. Wrap in useMemo to stabilize render cycles.",
        "info",
    ),
    (
        "TS_CONSOLE_POLLUTION",
        "Purge System Log Spikes",
        "Residual debug console.logs present. These consume I/O bandwidth and "
        "can expose variable states to the browser console.",
        "info",
    ),
]

PROJECTION_TIERS = [
    (
        "Syntactic Safety Gates",
        [
            "Whitespace normalization",
            "Linter constraints align",
            "Type checking assertions",
        ],
        "Eliminates syntax drift and compilation warning blocks",
        0.05,
    ),
    (
        "Block-Level Optimization",
        [
            "Loop vectorization",
            "Strict comparisons enforcing",
            "Constant variable hoisting",
        ],
        "Up to 15% execution speed improvement via efficient bytecode generation",
        0.10,
    ),
    (
        "Temporal Decoupling",
        [
            "Asynchronous handlers integration",
            "Try-catch safety wrapping",
            "Lazy import states",
        ],
        "Decouples synchronous resource blocking and safeguards execution paths",
        0.18,
    ),
    (
        "Architecture Consolidation",
        [
            "Interface & schema extraction",
            "Component splitting",
            "Helper modularization",
        ],
        "Decreases code file weight, improving compiler build speeds",
        0.25,
    ),
    (
        "Superfluid State Pipeline",
        [
            "useMemo & useCallback memoization",
            "State action debouncing",
            "Lattice state caching",
        ],
        "Drastically lowers memory allocations and stops layout rendering flickers",
        0.35,
    ),
    (
        "Security Hardening & Encapsulation",
        [
            "Secure input escaping",
            "Private module encapsulation",
            "Secrets environment abstracting",
        ],
        "Eliminates potential credential leaks and cross-site scripting pathways",
        0.45,
    ),
    (
        "Autonomous Micro-Agent Hooks",
        [
            "Real-time self-checking blocks",
            "Adaptive diagnostic reports",
            "Error-reporting web hooks",
        ],
        "Automates live error recovery and streams status metrics directly",
        0.55,
    ),
    (
        "Concurrent Pipeline Splicer",
        [
            "Multi-threaded cluster spawners",
            "Background async task delegation",
            "Lattice worker processes",
        ],
        "Enables non-blocking multi-core computing to prevent main-thread latency",
        0.65,
    ),
    (
        "Quantum Coherence Simulation",
        [
            "Heuristic self-profiling loops",
            "Adaptive complexity scaling",
            "Predictive memory garbage collector",
        ],
        "Self-throttles intensive processes depending on available device resources",
        0.75,
    ),
    (
        "Autogenous Self-Upgrading Core",
        [
            "Recursive forward projection updates",
            "Automatic hot-patch deployment",
            "Abstract syntax tree synthesis",
        ],
        "Achieves an autogenous self-upgrading code ecosystem with zero human "
        "code intervention",
        0.88,
    ),
]

UPGRADE_PLAN = [
    "1. Real-time Static Analysis & Safety Alignment",
    "2. Type & Interface Matrix Enforcements",
    "3. Exception Boundaries & Exception Splicers",
    "4. Memoization, Rendering Optimization, and State Decoupling",
    "5. Micro-Agent Execution, Multithreaded Pipes, and Quantum Coherence",
]


class QuettaPanEngine:
    """Superfluid upgrader with the REIM/RIEM learning loop."""

    def __init__(
        self,
        project_root: str | Path = ".",
        config: Optional[Dict[str, Any]] = None,
        store_dir: Optional[str | Path] = None,
        brain: Optional[QuettaPanDaVinci] = None,
        test_cmd: Optional[List[str] | str] = None,
    ):
        self.project_root = Path(project_root).resolve()
        # Stores live beside the project by default (v10.0 layout);
        # tests pass an isolated store_dir to stay hermetic.
        self.store_dir = Path(store_dir).resolve() if store_dir else self.project_root
        self.backup_dir = self.store_dir / ".quetta_backups"
        self.history_file = self.store_dir / ".quetta_history.json"
        self.compost = ReimCompost(self.store_dir / ".quetta_compost.jsonl")
        self.genome = RiemGenome(self.store_dir / ".quetta_genome.json")
        self.brain = brain
        self.test_cmd = test_cmd
        self.config = config or {
            "max_files": 50,
            "projection_depth": 10,
            "enable_multilingual": True,
            "safe_mode": False,
        }
        self.history = {"approvals": [], "rejections": [], "runs": []}
        self._load_history()

    # ---- history ----------------------------------------------------------

    def _load_history(self) -> None:
        if self.history_file.exists():
            try:
                self.history = json.loads(self.history_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

    def _save_history(self) -> None:
        self.history_file.write_text(
            json.dumps(self.history, indent=2), encoding="utf-8"
        )

    # ---- scanner ----------------------------------------------------------

    def scan(self) -> List[Path]:
        files = []
        for path_obj in self.project_root.rglob("*"):
            if not (path_obj.is_file() and path_obj.suffix in EXTENSIONS):
                continue
            if any(ex in path_obj.parts for ex in EXCLUDED_PARTS):
                continue
            # never mutate our own stores
            if path_obj.parent == self.store_dir and path_obj.name.startswith(
                ".quetta_"
            ):
                continue
            files.append(path_obj)
        return files[: self.config["max_files"]]

    # ---- heuristics (v10.0 rules) ------------------------------------------

    def python_ast_heuristics(self, content: str, suffix: str) -> List[Dict]:
        suggestions = []
        if suffix != ".py":
            return suggestions
        try:
            ast.parse(content)
        except SyntaxError:
            return suggestions  # unparseable: no heuristic claims
        if re.search(r"\.format\(", content) or re.search(r"% \w+", content):
            suggestions.append(self._rule("PY_FSTRING"))
        if "except:" in content and "Exception" not in content:
            suggestions.append(self._rule("PY_BARE_EXCEPT"))
        if "for " in content and "append(" in content:
            suggestions.append(self._rule("PY_LIST_COMP"))
        if re.search(r"def \w+\(.*\s*=\s*(\[\]|\{\})\s*\)", content):
            suggestions.append(self._rule("PY_MUTABLE_DEFAULTS"))
        return suggestions

    def typescript_react_heuristics(self, content: str, suffix: str) -> List[Dict]:
        if suffix not in (".js", ".ts", ".jsx", ".tsx"):
            return []
        suggestions = []
        if re.search(r"\bvar\b\s+\w+", content):
            suggestions.append(self._rule("TS_VAR_USAGE"))
        if re.search(r"\s==\s(?!=)", content) or re.search(r"\s!=\s(?!=)", content):
            suggestions.append(self._rule("TS_LOOSE_EQUALITY"))
        if "useEffect(" in content and "]" not in content:
            suggestions.append(self._rule("TS_EFFECT_LOOP"))
        if ": any" in content or "as any" in content:
            suggestions.append(self._rule("TS_LOOSE_TYPING"))
        if (
            "useMemo" not in content
            and (".map(" in content or ".filter(" in content)
            and len(content) > 15000
        ):
            suggestions.append(self._rule("TS_UNMEMOIZED_MATRIX"))
        if "console.log(" in content:
            suggestions.append(self._rule("TS_CONSOLE_POLLUTION"))
        return suggestions

    @staticmethod
    def _rule(rule_id: str) -> Dict:
        for rid, title, desc, sev in PY_RULES + TS_RULES:
            if rid == rule_id:
                return {"id": rid, "title": title, "desc": desc, "severity": sev}
        raise KeyError(f"unknown rule {rule_id}")

    def all_heuristics(self, content: str, suffix: str) -> List[Dict]:
        out = self.python_ast_heuristics(content, suffix)
        out.extend(self.typescript_react_heuristics(content, suffix))
        return out

    # ---- safe fixes (v10.0) -------------------------------------------------

    def safe_fixes(
        self, content: str, suffix: str, skip: Optional[set] = None
    ) -> tuple[str, List[str]]:
        """Apply v10.0's safe fixes. Returns (new_content, fix_ids).
        ``skip`` holds rule/fix ids the genome suppressed — a withheld
        rule's fix is not applied either."""
        skip = skip or set()
        fixed = []
        if (
            suffix == ".py"
            and "except:" in content
            and "Exception" not in content
            and "PY_BARE_EXCEPT" not in skip
        ):
            content = content.replace("except:", "except Exception:")
            fixed.append("PY_BARE_EXCEPT")
        if "\t" in content and "HARMONY_TABS" not in skip:
            content = content.expandtabs(4)
            fixed.append("HARMONY_TABS")
        if (
            suffix in (".js", ".ts", ".jsx", ".tsx")
            and "debugger;" in content
            and "TS_DEBUGGER_LOCK" not in skip
        ):
            content = content.replace("debugger;", "/* debugger inactive */;")
            fixed.append("TS_DEBUGGER_LOCK")
        return content, fixed

    # ---- forward projections (v10.0 tiers) ------------------------------------

    def generate_forward_projections(
        self, file_path: Path, depth: int = 10
    ) -> List[Dict]:
        projections = []
        base_name = file_path.name
        for idx, (lvl_name, changes, benefits, risk) in enumerate(
            PROJECTION_TIERS[:depth]
        ):
            projections.append(
                {
                    "level": idx + 1,
                    "variant_name": f"{base_name}.v{idx + 1}",
                    "description": lvl_name,
                    "key_changes": list(changes),
                    "expected_benefits": [benefits],
                    "risk_level": risk,
                }
            )
        return projections

    # ---- suggestion (genome consulted BEFORE generation) -----------------------

    def suggest_upgrades(self, file_path: Path) -> Dict[str, Any]:
        content = file_path.read_text(encoding="utf-8")
        context = context_key_for(file_path)
        raw = self.all_heuristics(content, file_path.suffix)
        if self.brain is not None:
            for mut in self.brain.detect_mutations(content, file_path.suffix):
                raw.append(
                    {
                        "id": "BRAIN_" + mut["name"].upper().replace(" ", "_"),
                        "title": f"Brain: {mut['name']}",
                        "desc": mut["detail"],
                        "severity": "info",
                    }
                )

        suggestions: List[Dict] = []
        suppressed: List[Dict] = []
        for sugg in raw:
            verdict = self.genome.consult(sugg["id"], context)
            if verdict == "suppress":
                suppressed.append(
                    {
                        **sugg,
                        "suppressed_reason": self.genome.suppression_reason(
                            sugg["id"], context
                        ),
                    }
                )
            else:
                suggestions.append({**sugg, "genome": verdict})

        new_content, fix_ids = self.safe_fixes(content, file_path.suffix)
        # Genome coherence: a suppressed rule's fix is withheld too —
        # the loop must not re-apply what it has learned fails here.
        suppressed_ids = {s["id"] for s in suppressed}
        withheld_fixes = suppressed_ids & set(fix_ids)
        if withheld_fixes:
            new_content, fix_ids = self.safe_fixes(
                content, file_path.suffix, skip=withheld_fixes
            )
        diff = "".join(
            difflib.unified_diff(
                content.splitlines(keepends=True), new_content.splitlines(keepends=True)
            )
        )
        risk = min(0.02 + len(suggestions) * 0.05, 0.95)
        try:
            rel = str(file_path.relative_to(self.project_root))
        except ValueError:
            rel = str(file_path)
        return {
            "file": rel,
            "path": file_path,
            "upgrades": [s["title"] for s in suggestions],
            "suggestions": suggestions,
            "suppressed_by_genome": suppressed,
            "diff": diff,
            "new_content": new_content,
            "fix_ids": fix_ids,
            "risk": risk,
            "forward_projections": self.generate_forward_projections(
                file_path, self.config["projection_depth"]
            ),
            "upgrade_plan": list(UPGRADE_PLAN),
            "has_changes": bool(suggestions) or new_content != content,
        }

    # ---- guarded write path (the loop) ------------------------------------------

    def create_backup(self, file_path: Path) -> Path:
        """Timestamped backup of the pre-image. Invariant 1: no write
        without backup — this runs before every mutation."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        dest = self.backup_dir / f"{file_path.name}_{ts}.bak"
        shutil.copy2(file_path, dest)
        return dest

    def apply_suggestion(
        self,
        suggestion: Dict[str, Any],
        mutation_id: Optional[str] = None,
    ) -> MutationResult:
        """Backup -> write -> evaluate. On failure: rollback, REIM
        compost, RIEM learn. On success: RIEM records the win."""
        file_path: Path = suggestion["path"]
        before = file_path.read_text(encoding="utf-8")
        after = suggestion["new_content"]
        context = context_key_for(file_path)
        rule_ids = [s["id"] for s in suggestion["suggestions"]]
        rule_id = "+".join(rule_ids) if rule_ids else "NO_RULE"
        mid = mutation_id or (f"qp-{datetime.now().strftime('%Y%m%d%H%M%S%f')}")
        tried_what = (
            f"apply safe fixes {suggestion.get('fix_ids', [])} for rules {rule_ids}"
        )

        backup = self.create_backup(file_path)  # invariant 1
        try:
            file_path.write_text(after, encoding="utf-8")
        except OSError as exc:
            self._on_failure(
                mid,
                rule_id,
                file_path,
                context,
                tried_what,
                f"guard: write failed: {exc}",
                backup,
                before,
            )
            return MutationResult(
                ok=False,
                parse_ok=False,
                parse_detail="write failed",
                failure_reason=f"guard: write failed: {exc}",
            )

        result = evaluate_mutation(
            file_path,
            before,
            after,
            suggest_fn=self.all_heuristics,
            test_cmd=self.test_cmd,
        )
        result.applied_fix_ids = suggestion.get("fix_ids", [])
        if result.ok:
            self._on_success(mid, rule_id, context, suggestion)
        else:
            # fail-closed: restore the pre-image, then compost
            file_path.write_text(before, encoding="utf-8")
            self._on_failure(
                mid,
                rule_id,
                file_path,
                context,
                tried_what,
                result.failure_reason,
                backup,
                before,
            )
        return result

    def _learn_outcome(
        self,
        rule_ids: List[str],
        context: str,
        success: bool,
        lesson: str,
    ) -> None:
        """Fold one outcome into the genome per individual rule AND the
        bundle key. Consultation happens per rule, so learning must too —
        otherwise repeated bundle failures would never suppress their rules.
        """
        bundle = "+".join(rule_ids) if rule_ids else "NO_RULE"
        for rid in dict.fromkeys([bundle, *rule_ids]):
            self.genome.learn(rid, context, success, lesson)

    def _on_success(
        self, mid: str, rule_id: str, context: str, suggestion: Dict[str, Any]
    ) -> None:
        self._learn_outcome(
            [s["id"] for s in suggestion["suggestions"]],
            context,
            True,
            f"{mid}: applied cleanly on {suggestion['file']}",
        )
        self.history["approvals"].append(
            {
                "ts": datetime.now().isoformat(),
                "mutation_id": mid,
                "rule_id": rule_id,
                "file": suggestion["file"],
            }
        )
        self._save_history()

    def _on_failure(
        self,
        mid: str,
        rule_id: str,
        file_path: Path,
        context: str,
        tried_what: str,
        failed_why: str,
        backup: Path,
        before: str,
    ) -> None:
        # invariant 3: failures always composted, never dropped silently
        entry = self.compost.compost(
            {
                "mutation_id": mid,
                "rule_id": rule_id,
                "file": str(file_path),
                "context": context,
                "tried_what": tried_what,
                "failed_why": failed_why,
                "backup": str(backup),
            }
        )
        # invariant: compost -> genome, per rule and bundle alike
        rule_ids = [r for r in rule_id.split("+") if r] if rule_id != "NO_RULE" else []
        self._learn_outcome(
            rule_ids, context, False, str(entry.get("inverse_lesson", ""))
        )
        self.history["rejections"].append(
            {
                "ts": datetime.now().isoformat(),
                "mutation_id": mid,
                "rule_id": rule_id,
                "file": str(file_path),
                "failed_why": failed_why,
            }
        )
        self._save_history()

    # ---- run ---------------------------------------------------------------------

    def show_review(self, suggestion: Dict[str, Any]) -> None:
        print("\n" + "=" * 100)
        print(f"QUETTA-PAN rebuilt -> {suggestion['file']}")
        print(
            f"Risk: {suggestion['risk']:.2f} | "
            f"Heuristics: {len(suggestion['suggestions'])} | "
            f"Suppressed by genome: {len(suggestion['suppressed_by_genome'])}"
        )
        for idx, s in enumerate(suggestion["suggestions"], 1):
            tag = f"[{s['severity'].upper()}]"
            g = s.get("genome", "unknown")
            print(f"   {idx}. {tag} {s['title']} (genome: {g})\n      -> {s['desc']}")
        for s in suggestion["suppressed_by_genome"]:
            print(f"   [WITHHELD] {s['title']}\n      -> {s['suppressed_reason']}")
        print("\n10-TIER FORWARD PROJECTIONS:")
        for p in suggestion.get("forward_projections", []):
            print(
                f"   Level {p['level']:02d}: {p['description']} "
                f"(Risk: {int(p['risk_level'] * 100)}%)"
            )
        if suggestion.get("diff"):
            preview = suggestion["diff"][:800]
            print("\nDIFF PREVIEW:\n" + preview)
        print("=" * 100)

    def run(
        self, dry_run: bool = True, approve: Optional[Callable[[Dict], str]] = None
    ) -> Dict[str, int]:
        """Scan -> suggest -> review -> (apply with per-file approval).

        dry_run=True (default): nothing is written, ever.
        approve: callback(suggestion) -> 'y' | 'n' | 'q'; default prompts.
        """
        stats = {
            "scanned": 0,
            "suggested": 0,
            "applied": 0,
            "rolled_back": 0,
            "composted": 0,
        }
        files = self.scan()
        stats["scanned"] = len(files)
        for file_path in files:
            suggestion = self.suggest_upgrades(file_path)
            if not suggestion.get("has_changes"):
                continue
            stats["suggested"] += 1
            self.show_review(suggestion)
            if dry_run:
                print("   [DRY-RUN: no writes]")
                continue
            choice = (
                approve(suggestion)
                if approve
                else input("\nApply this upgrade? (y/n/q): ").strip().lower()
            )
            if choice == "q":
                break
            if choice != "y":
                continue
            result = self.apply_suggestion(suggestion)
            if result.ok:
                stats["applied"] += 1
                print(f"Applied to {suggestion['file']}")
            else:
                stats["rolled_back"] += 1
                stats["composted"] += 1
                print(f"FAILED -> rolled back + composted: {result.failure_reason}")
        self.history["runs"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "mode": "quetta_pan_rebuilt_reim_riem",
                "stats": stats,
            }
        )
        self._save_history()
        return stats
