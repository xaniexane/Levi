"""CLI stub for the social platform contracts.

STATUS: AWAITING KEEPER REVIEW — this CLI only inspects and validates
manifest bundles. Nothing here creates platform state.
"""

from __future__ import annotations

import argparse
import sys

from .manifests import ManifestBundle, SocialManifestError


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.social",
        description="Social platform manifest tools (AWAITING KEEPER REVIEW).",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify", help="verify a sealed manifest bundle")
    v.add_argument("bundle", help="path to a levi-social-manifest JSON file")

    s = sub.add_parser("seal", help="seal stdin JSON sections into a manifest bundle")
    s.add_argument(
        "--sections",
        required=True,
        help="JSON object mapping section name -> list of records",
    )

    args = ap.parse_args(argv)
    try:
        if args.cmd == "verify":
            with open(args.bundle, encoding="utf-8") as fh:
                bundle = ManifestBundle.from_json(fh.read())
            bundle.verify()
            print("OK: bundle verified (%s)" % bundle.manifest[:16])
        elif args.cmd == "seal":
            import json

            sections = json.loads(args.sections)
            bundle = ManifestBundle(sections=sections).seal()
            print(bundle.to_json())
        return 0
    except SocialManifestError as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
