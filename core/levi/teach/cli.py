"""``levi teach`` CLI: plan / prepare / stats.

* ``teach plan`` — dry run: what would be taught (corpus stats,
  curriculum stages, sequence counts, data mix, teachback coverage).
* ``teach prepare --out DIR`` — write the v2-trainer bundle
  (sequences JSONL + corpus manifests + curriculum + train.yaml +
  versioned teach manifest). The teach manifest is also registered in
  ``~/.levi/teach/manifests/``.
* ``teach stats`` — what has been taught across runs (from the registry).

``--sources`` selects among: courses, academy, growth, seed (or all).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from levi.teach import registry_dir
from levi.teach.converters import SOURCES, repo_root
from levi.teach.prepare import TeachError, plan_teaching, prepare
from levi.teach.teachback import TeachbackError, teachback_report
from levi.teach.verify import check_bundle

__all__ = ["register_teach_parser", "cmd_teach"]


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--sources",
        nargs="+",
        default=["all"],
        choices=list(SOURCES) + ["all"],
        help="teaching sources (default: all)",
    )
    p.add_argument("--name", default="teach", help="run name (default: teach)")
    p.add_argument("--seed", type=int, default=1337, help="deterministic seed")
    p.add_argument(
        "--stages", type=int, default=4, help="curriculum stages (default: 4)"
    )
    p.add_argument(
        "--max-seq-len",
        type=int,
        default=128,
        help="training sequence length in words (default: 128)",
    )
    p.add_argument(
        "--repo",
        default="",
        help="repo root override (default: auto-detect, LEVI_REPO)",
    )
    p.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="min growth-learning confidence 0..1 (default: 0.0)",
    )
    p.add_argument(
        "--no-teachback",
        action="store_true",
        help="skip the teachback coverage check",
    )
    p.add_argument(
        "--teachback-fail-under",
        type=float,
        default=None,
        metavar="0-1",
        help="fail if teachback coverage is below this fraction (quality gate)",
    )


def register_teach_parser(sub) -> None:
    tc = sub.add_parser(
        "teach", help="turn approved corpora into curriculum-ordered training data"
    )
    cmds = tc.add_subparsers(dest="teach_cmd")

    plan_p = cmds.add_parser("plan", help="dry run: show what would be taught")
    _add_common(plan_p)

    prep_p = cmds.add_parser("prepare", help="write the v2-trainer bundle")
    _add_common(prep_p)
    prep_p.add_argument("--out", required=True, help="output directory for the bundle")
    prep_p.add_argument(
        "--no-register",
        action="store_true",
        help="do not record this run in ~/.levi/teach/manifests/",
    )

    cmds.add_parser("stats", help="what has been taught across runs (registry)")

    check_p = cmds.add_parser(
        "check", help="verify a prepared bundle is intact and consumable"
    )
    check_p.add_argument("dir", help="bundle directory from `teach prepare`")


def _resolve_sources(args) -> list[str]:
    raw = list(getattr(args, "sources", None) or ["all"])
    if "all" in raw:
        return list(SOURCES)
    return raw


def _fmt_num(n: int) -> str:
    return f"{n:,}"


def _print_plan(summary) -> None:
    print(f"teach plan: {summary.name}@{summary.version}  (seed {summary.seed})")
    print("policy: news-excluded (hard gate, enforced per source + union)")
    print()
    print("  source      docs      chars")
    print("  ------      ----      -----")
    for name, st in summary.per_source.items():
        print(f"  {name:<10} {_fmt_num(st['n_docs']):>8} {_fmt_num(st['n_chars']):>9}")
    print(f"  {'total(raw)':<10} {_fmt_num(summary.n_docs_raw):>8}")
    print(f"  dedup removed: {_fmt_num(summary.n_dedup_removed)}")
    print(f"  unique docs:   {_fmt_num(summary.n_docs_unique)}")
    print()
    print(f"  curriculum: {summary.n_stages} stages, simple -> complex")
    for st in summary.stages:
        print(
            f"    stage {st['stage']}: {_fmt_num(st['n_docs'])} docs "
            f"(difficulty {st['difficulty_min']}..{st['difficulty_max']})"
        )
    print()
    print("  splits (seeded):")
    for split, n in summary.split_counts.items():
        print(
            f"    {split:<5}: {_fmt_num(n)} docs -> "
            f"{_fmt_num(summary.sequence_counts.get(split, 0))} sequences "
            f"(@{summary.max_seq_len}w)"
        )
    print()
    print("  data mix:")
    for src, w in sorted(summary.mix.items(), key=lambda kv: -kv[1]):
        bar = "█" * max(1, round(w * 20)) if w > 0 else ""
        print(f"    {src:<8}: {w:.1%} {bar}")
    tb = summary.teachback
    if tb.get("skipped"):
        print()
        print(f"  teachback skipped: {tb['skipped']}")
    elif tb:
        print()
        print(
            f"  teachback (data-side only): {tb['n_covered']}/{tb['n_probes']} "
            f"probes covered ({tb['coverage']:.0%})"
        )
        print("    -> coverage = probe vocabulary present in prepared data,")
        print("       NOT a claim about model capability.")


def cmd_teach(args: argparse.Namespace) -> int:
    cmd = getattr(args, "teach_cmd", None) or "plan"
    root = Path(args.repo).expanduser() if getattr(args, "repo", "") else repo_root()
    sources = _resolve_sources(args)

    if cmd == "stats":
        return _cmd_stats()

    if cmd == "check":
        return _cmd_check(args.dir)

    try:
        kwargs = dict(
            name=args.name,
            sources=sources,
            root=root,
            seed=args.seed,
            n_stages=args.stages,
            max_seq_len=args.max_seq_len,
            min_confidence=args.min_confidence,
            run_teachback=not args.no_teachback,
            teachback_fail_under=args.teachback_fail_under,
        )
        if cmd == "plan":
            summary = plan_teaching(**kwargs)
            _print_plan(summary)
            return 0
        if cmd == "prepare":
            manifest_path = prepare(args.out, register=not args.no_register, **kwargs)
            print(f"teach: bundle prepared at {Path(args.out).expanduser()}")
            print(f"teach: manifest {manifest_path}")
            # Teachback detail after prepare: per-probe table, probes
            # filtered to the chosen sources (see prepare._teachback_for_sources).
            if not args.no_teachback:
                from levi.teach.probes import PROBES

                src_probes = [p for p in PROBES if p.source in sources]
                if not src_probes:
                    print(
                        "teach: teachback skipped: no probes for sources: "
                        + ", ".join(sources)
                    )
                    return 0
                try:
                    report = teachback_report(args.out, probes=src_probes)
                except TeachbackError as exc:
                    print(f"teach: teachback skipped: {exc}")
                    return 0
                print()
                print(
                    f"teachback: {report['n_covered']}/{report['n_probes']} "
                    f"probes covered ({report['coverage']:.0%})"
                )
                for row in report["probes"]:
                    mark = "ok " if row["covered"] else "MISS"
                    print(
                        f"  [{mark}] {row['id']:<18} "
                        f"{row['matched']}/{row['keywords']} keywords"
                    )
                    if not row["covered"]:
                        missing = ", ".join(row["missing"][:5])
                        print(f"         missing: {missing}")
                print(f"  ({report['disclaimer']})")
            return 0
    except TeachError as exc:
        print(f"teach {cmd} failed: {exc}")
        return 2
    except Exception as exc:  # policy errors surface here too
        print(f"teach {cmd} failed: {type(exc).__name__}: {exc}")
        return 2
    print(f"teach: unknown command {cmd!r}")
    return 2


def _cmd_check(bundle_dir: str) -> int:
    report = check_bundle(bundle_dir)
    stats = report["stats"]
    if report["ok"]:
        print(f"teach check: OK — {bundle_dir}")
        bits = []
        for split in ("train", "val", "test"):
            d = stats.get(f"{split}_docs")
            s = stats.get(f"{split}_sequences")
            if d is not None:
                bits.append(f"{split} {d:,} docs / {s:,} seqs")
        if bits:
            print("  " + " · ".join(bits))
        if stats.get("manifest"):
            print(f"  manifest: {stats['manifest']}")
        if stats.get("config"):
            print(f"  config: {stats['config']} (validates)")
        return 0
    print(f"teach check: FAILED — {bundle_dir}")
    for p in report["problems"][:20]:
        print(f"  ! {p}")
    if len(report["problems"]) > 20:
        print(f"  … and {len(report['problems']) - 20} more")
    return 2


def _cmd_stats() -> int:
    reg = registry_dir()
    files = sorted(reg.glob("*.json")) if reg.is_dir() else []
    if not files:
        print("teach stats: no runs registered yet (run `levi teach prepare`)")
        return 0
    print(f"teach stats: {len(files)} run(s) in {reg}")
    print()
    print("  run                    docs     seqs   stages  teachback  created")
    print("  ---                    ----     ----   ------  ---------  -------")
    for f in files:
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            print(f"  {f.stem:<22} (unreadable manifest)")
            continue
        seqs = sum(m.get("sequence_counts", {}).values())
        tb = m.get("teachback", {}) or {}
        tb_str = f"{tb.get('n_covered', '?')}/{tb.get('n_probes', '?')}" if tb else "—"
        print(
            f"  {f.stem:<22} {_fmt_num(m.get('n_docs_unique', 0)):>8} "
            f"{_fmt_num(seqs):>8} {m.get('n_stages', '?'):>6}  "
            f"{tb_str:>9}  {str(m.get('created_at', ''))[:10]}"
        )
    print()
    print("  totals across runs are per-run snapshots (runs may overlap).")
    return 0
