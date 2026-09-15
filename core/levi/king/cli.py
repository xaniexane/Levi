"""``levi king`` — the King control plane command surface.

Ten actions (blueprint §4):

* ``status``        — ledger rank/totals, engine availability, review depth, ROM locks.
* ``pulse``         — drive StoryFabric one beat; harvest into the ledger.
* ``manuscript``    — drive the model engine (expand scenes); harvest into the ledger.
* ``social``        — generate a sanitized social pack; queue it for review (no network).
* ``social-post``   — post an APPROVED pack through the plugin connector
                      contract. Confirmation-gated: ``--yes`` required,
                      refused with a clear message otherwise.
* ``reim``          — pass-through: manuscript engine REIM forks.
* ``deny``          — pass-through: manuscript engine deny (or deny a review
                      item when given an id).
* ``approve``       — pass-through: manuscript engine approve (or approve a
                      review item when given an id).
* ``rupture``       — pass-through: manuscript engine wyrd_rupture (single-
                      manuscript ROM; see rom.py for King's own session ROM).
* ``d5``            — documented baseline promotion for demoing rank
                      progression (demo override + King session-ROM lock).

Semantics where the blueprint is terse (documented in docs/KING.md):
``pulse`` never auto-creates a story (creation needs explicit confirm,
blueprint §1.5) — it pulses the latest story or explains how to create
one. ``deny``/``approve`` with an id operate on the review queue;
without an id they pass through to the manuscript engine and log the
decision. ``d5`` floors the derived rank at D5 as a *recorded demo
override* and seals the session with King's own ROM.
"""

from __future__ import annotations

import sys

from levi.king import King
from levi.king.social import PLATFORMS


def register_king(sub) -> None:
    """Add the ``king`` command and its ten action subparsers."""
    king_p = sub.add_parser(
        "king",
        help="King control plane: ledger, engines, social, review (default: status)",
    )
    ksub = king_p.add_subparsers(dest="king_action")

    ksub.add_parser("status", help="Ledger rank/totals, engines, review, ROM locks").add_argument(
        "--visual", action="store_true", help="Include visual checkpoint URL(s)"
    )

    pulse_p = ksub.add_parser("pulse", help="Drive StoryFabric one beat (harvests to ledger)")
    pulse_p.add_argument("--story-id", default=None, help="Story id (default: latest)")

    man_p = ksub.add_parser("manuscript", help="Drive the model engine (harvests to ledger)")
    man_p.add_argument("--scenes", type=int, default=1, help="Scenes to expand (1-8)")

    soc_p = ksub.add_parser("social", help="Generate a sanitized social pack (queued for review)")
    soc_p.add_argument("--platform", default="x", choices=sorted(PLATFORMS))
    soc_p.add_argument("--title", default="", help="Optional pack title")

    post_p = ksub.add_parser(
        "social-post", help="Post an APPROVED pack via the plugin connector (needs --yes)"
    )
    post_p.add_argument("--id", required=True, help="Review item id (must be approved)")
    post_p.add_argument("--platform", default=None, choices=sorted(PLATFORMS))
    post_p.add_argument(
        "--yes",
        action="store_true",
        help="Explicit confirmation — required; without it the post is refused",
    )

    reim_p = ksub.add_parser("reim", help="Pass-through: manuscript engine REIM forks")
    reim_p.add_argument("--tracks", type=int, default=3, help="Fork tracks (2-4)")
    reim_p.add_argument("--seed", default=None, help="Seed text for the forks")

    deny_p = ksub.add_parser("deny", help="Deny: manuscript scene, or review item with id")
    deny_p.add_argument("id", nargs="?", default=None, help="Review item id (omit: deny last scene)")
    deny_p.add_argument("--note", default="", help="Decision note")

    appr_p = ksub.add_parser("approve", help="Approve: manuscript scene, or review item with id")
    appr_p.add_argument("id", nargs="?", default=None, help="Review item id (omit: approve last scene)")
    appr_p.add_argument("--note", default="", help="Decision note")

    rup_p = ksub.add_parser("rupture", help="Pass-through: manuscript engine wyrd-rupture")
    rup_p.add_argument("--lens", default="mccarthy", help="ROM lens style")

    d5_p = ksub.add_parser("d5", help="Baseline promotion: demo the D2→D5 rank progression")
    d5_p.add_argument("--reset", action="store_true", help="Clear the demo promotion")


def cmd_king(args) -> None:
    """Dispatch ``levi king <action>``."""
    king = King()
    action = getattr(args, "king_action", None) or "status"

    if action == "status":
        print(king.status(visual=bool(getattr(args, "visual", False))))
    elif action == "pulse":
        print(king.pulse(story_id=getattr(args, "story_id", None)))
    elif action == "manuscript":
        print(king.pulse_manuscript(n=int(getattr(args, "scenes", 1) or 1)))
    elif action == "social":
        print(king.social(platform=getattr(args, "platform", "x") or "x",
                          title=getattr(args, "title", "") or ""))
    elif action == "social-post":
        res = king.social_post(
            pack_id=args.id,
            platform=getattr(args, "platform", None),
            confirm=bool(getattr(args, "yes", False)),
        )
        if res["ok"]:
            print(res["message"])
        elif res.get("gate") == "confirmation":
            print(res["message"], file=sys.stderr)
            sys.exit(2)
        else:
            print(res["message"], file=sys.stderr)
            sys.exit(1)
    elif action == "reim":
        print(king.reim(tracks=int(getattr(args, "tracks", 3) or 3),
                        seed=getattr(args, "seed", None)))
    elif action == "deny":
        print(king.deny(review_id=getattr(args, "id", None),
                        note=getattr(args, "note", "") or ""))
    elif action == "approve":
        print(king.approve(review_id=getattr(args, "id", None),
                           note=getattr(args, "note", "") or ""))
    elif action == "rupture":
        print(king.rupture(lens=getattr(args, "lens", None) or "mccarthy"))
    elif action == "d5":
        print(king.d5(reset=bool(getattr(args, "reset", False))))
    else:
        print(f"Unknown king action {action!r}. Try: levi king --help")
        sys.exit(2)
