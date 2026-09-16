"""`python -m levi.identity` — identity variant engine CLI.

Subcommands: reflect | variants | compost | compress | cycle | genome.
`reflect --scope all` and `cycle --scope all` run across every
manifest-declared module (interpenetrating the whole organism).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, List


def _read_json(args) -> Any:
    if args.json:
        return json.loads(args.json)
    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            return json.load(fh)
    data = sys.stdin.read()
    if not data.strip():
        raise SystemExit("no input: pass --json, --file, or pipe JSON on stdin")
    return json.loads(data)


def _emit(obj: Any) -> int:
    print(json.dumps(obj, indent=2, sort_keys=True))
    return 0


def _cmd_reflect(args) -> int:
    from levi.identity import EchoEngine, iter_module_identities, reflection_to_dict
    from levi.identity.scope import module_fracture_notes

    engine = EchoEngine()
    if args.scope == "all":
        out = []
        for ident in iter_module_identities():
            r = engine.reflect(ident)
            extra = module_fracture_notes(ident)
            r.fractures.extend(extra)
            r.coherence = round(
                max(0.0, min(1.0, r.coherence - sum(f["penalty"] for f in extra))), 4
            )
            d = reflection_to_dict(r)
            d["module_meta"] = ident.get("module_meta", {})
            out.append(d)
        return _emit(out)
    return _emit(reflection_to_dict(engine.reflect(_read_json(args))))


def _cmd_variants(args) -> int:
    from levi.identity import EchoEngine, MandellaEngine

    reflection = EchoEngine().reflect(_read_json(args))
    variants = MandellaEngine(args.seed).reconstruct(
        reflection, n_variants=args.n, seed=args.seed
    )
    return _emit(variants)


def _cmd_compost(args) -> int:
    from levi.identity import REIM

    return _emit(REIM().compost(_read_json(args)))


def _cmd_compress(args) -> int:
    from levi.identity import RIEM, GenomeStore

    lessons = _read_json(args)
    if not isinstance(lessons, list):
        raise SystemExit("compress input must be a JSON list of lessons")
    genome = GenomeStore().load()
    return _emit(RIEM().compress(lessons, genome))


def _cmd_cycle(args) -> int:
    from levi.identity import GenomeStore, IdentityCycle

    cycle = IdentityCycle(store=GenomeStore())
    if args.scope == "all":
        return _emit(
            cycle.run_scope_all(
                n_variants=args.n,
                seed=args.seed,
                cross_pollenate=not args.no_cross,
            )
        )
    return _emit(
        cycle.run(_read_json(args), n_variants=args.n, seed=args.seed, notes=args.notes)
    )


def _cmd_genome(args) -> int:
    from levi.identity import GenomeStore

    store = GenomeStore()
    genome = store.load()
    if args.reset:
        from levi.identity.genome import _default_genome

        genome = _default_genome()
        store.save(genome)
    if args.module:
        genome = {args.module: genome.get("candidates", {}).get(args.module, [])}
    return _emit(genome)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="levi identity",
        description="Identity variant engine: Echo/Mandella/REIM/RIEM.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def _in(sp):
        sp.add_argument("--json", default=None, help="identity JSON string")
        sp.add_argument("--file", default=None, help="identity JSON file")
        return sp

    r = sub.add_parser("reflect", help="reflect an identity (coherence + fractures)")
    _in(r)
    r.add_argument("--scope", default=None, help="'all' reflects every manifest module")
    r.set_defaults(func=_cmd_reflect)

    v = sub.add_parser("variants", help="reconstruct reflection into N variants")
    _in(v)
    v.add_argument("--n", type=int, default=3)
    v.add_argument("--seed", default="")
    v.set_defaults(func=_cmd_variants)

    c = sub.add_parser("compost", help="compost an outcome into lessons")
    _in(c)
    c.set_defaults(func=_cmd_compost)

    k = sub.add_parser("compress", help="compress lessons into genome deltas")
    _in(k)
    k.set_defaults(func=_cmd_compress)

    y = sub.add_parser("cycle", help="full loop: reflect->variants->compost->genome")
    _in(y)
    y.add_argument("--n", type=int, default=3)
    y.add_argument("--seed", default="")
    y.add_argument("--notes", default="")
    y.add_argument("--scope", default=None, help="'all' cycles every manifest module")
    y.add_argument("--no-cross", action="store_true", help="disable cross-pollination")
    y.set_defaults(func=_cmd_cycle)

    g = sub.add_parser("genome", help="show the heritable genome")
    g.add_argument("--reset", action="store_true")
    g.add_argument("--module", default=None, help="show candidates for one module")
    g.set_defaults(func=_cmd_genome)
    return p


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
