"""CLI: python -m levi.academy

Thin entry point over the Defensive Security Analyst Academy
(30-day x 4-block training program). Mirrors ``levi academy``:
progress status, corpus stats, and topic research (which always
falls back to local materials when the network is unavailable).
"""

from __future__ import annotations

import argparse


def cmd_status(args) -> int:
    from levi.academy import run_session as rs

    syllabus = rs.load_syllabus()
    progress = rs.load_progress()
    done = progress.get("completed", [])
    day = min(len(done) // 4 + 1, 30)
    phase = rs.week_phase_for(syllabus, day)
    streaks = rs.get_streaks(progress)
    try:
        from levi.academy import corpus_ingest as aci

        cstats = aci.corpus_stats()
    except Exception:
        cstats = {}
    print("LEVI Boot Camp — 30-day 24/7 program")
    print(f"  day: {day}/30 ({phase})")
    print(f"  sessions completed: {len(done)}/120")
    print("  pass streaks (current/best): " + "  ".join(
        f"{t} {streaks[t]['current']}/{streaks[t]['best']}"
        for t in ("A", "B", "C", "S")))
    if cstats:
        print(f"  corpus: {cstats.get('records', 0)} records, "
              f"{cstats.get('chars', 0)} chars")
    return 0


def cmd_corpus(args) -> int:
    from levi.academy import corpus_ingest as aci

    stats = aci.corpus_stats()
    print(f"corpus: {stats.get('records', 0)} records, "
          f"{stats.get('chars', 0)} chars")
    for k, v in sorted(stats.items()):
        if k not in ("records", "chars"):
            print(f"  {k}: {v}")
    return 0


def cmd_research(args) -> int:
    from levi.academy.research import research_topic

    if args.track not in ("A", "B", "C", "S"):
        print("track must be one of A/B/C/S", __import__("sys").stderr)
        return 2
    result = research_topic(args.topic, track=args.track,
                            budget_seconds=args.budget)
    print(f"topic: {args.topic} (track {args.track})")
    print(f"sources tried: {result.get('sources')}")
    for fact in (result.get("facts") or [])[:8]:
        print(f"  - {fact}")
    terms = result.get("key_terms") or []
    if terms:
        print("key terms: " + ", ".join(terms[:12]))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.academy",
        description="LEVI Defensive Security Analyst Academy "
        "(mirrors `levi academy`)",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="program progress and streaks") \
        .set_defaults(func=cmd_status)

    sub.add_parser("corpus", help="ingested lesson corpus stats") \
        .set_defaults(func=cmd_corpus)

    p_res = sub.add_parser("research", help="research a session topic "
                           "(web or local fallback)")
    p_res.add_argument("topic")
    p_res.add_argument("--track", default="A", help="A|B|C|S")
    p_res.add_argument("--budget", type=float, default=150.0,
                       help="max seconds before local fallback")
    p_res.set_defaults(func=cmd_research)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
