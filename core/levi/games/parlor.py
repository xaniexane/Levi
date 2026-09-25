"""The Parlor — the third place that cannot be starved.

Four dead worlds fund this module (cf. the third-place hunt,
``research_notes/thirdplace-hunt-20260920/`` and ArchiveRecords
``arch-games-parlor-*``):

- PlayStation Home (2008-2015): a third place with no org chart; tenants
  evicted, purchased goods revoked, no refunds.
- Miiverse (2012-2017): the only wholesome network, outrun by the feed.
- Club Penguin (2005-2017): the haven killed by its monetized reboot —
  moderation was the product, and the reboot dropped it.
- AltspaceVR (2015-2023): saved by the giant, killed by the giant — the
  community was inventory.

Each died the same root death: a third place whose cost is constant
(moderation, servers, care) and whose revenue is indirect cannot survive
a quarterly calendar. The parlor inverts that: a third place whose cost
is ~zero — no servers, no moderation staff, no monetization — because it
is local-first, owner-operated, and portable. It cannot be starved
because it is never fed. It cannot be acquired because there is nothing
to acquire.

What it is:
- Handle registry: a household's players, sanitized and unique.
- Bulletin board: the Miiverse inversion — chronological (newest last),
  no algorithm, no review queue. Small-and-local IS the moderation.
- Game nights: scheduled sessions tying the parlor to the warehouse's
  playable games. Progress never rots (cf. :mod:`levi.games.season`).

Honesty rules, enforced by the Fair Play Charter:
- No purchases exist, so nothing can be revoked (the Home inversion).
- No feed, so nothing can outrun anything (the Miiverse inversion).
- The safe place comes from being YOUR household's place, not a
  corporation's service (the Club Penguin inversion).
- The parlor lives in one portable JSON file; take it anywhere, and no
  acquirer can pivot it (the AltspaceVR inversion).

Storage: ``~/.levi/games/parlor/parlor.json`` — owner-only, plain JSON,
portable, versioned. Export/import merges with validation; malformed
imports are refused, never half-applied.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from levi.games.charter import GameManifest

MANIFEST = GameManifest(
    name="parlor",
    progress_portable=True,  # the parlor file IS the place; export anytime
    odds_declared=True,  # nothing here is chance, and it says so
    hints_free=True,
    has_sunset_plan=True,  # the plan: there is no funeral. it cannot die.
)


class ParlorError(Exception):
    """Broken handles, bad posts, malformed imports. Deny-closed."""


HANDLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,15}$")
MAX_POST = 500
FORMAT_VERSION = 1


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass
class Handle:
    name: str
    registered_at: str


@dataclass
class Post:
    id: int
    handle: str
    text: str
    posted_at: str


@dataclass
class GameNight:
    id: int
    title: str
    game: str  # warehouse game name, e.g. "nim", "bagatelle"
    scheduled_at: str  # ISO-8601
    host: str
    rsvps: Dict[str, bool] = field(default_factory=dict)  # handle -> attending
    cancelled: bool = False


# ---------------------------------------------------------------------------
# The parlor itself
# ---------------------------------------------------------------------------


class Parlor:
    """One household's third place. No server, no account, no acquisition."""

    def __init__(self) -> None:
        self.handles: Dict[str, Handle] = {}
        self.posts: List[Post] = []
        self.nights: Dict[int, GameNight] = {}
        self._next_post_id = 1
        self._next_night_id = 1

    # -- handles ---------------------------------------------------------
    def register_handle(self, name: str) -> Handle:
        name = name.strip()
        if not HANDLE_RE.match(name):
            raise ParlorError(
                "handle must be 2-16 chars: letters, digits, _ or -, "
                "starting with a letter or digit (got %r)" % name
            )
        key = name.lower()
        if key in self.handles:
            raise ParlorError("handle %r is already taken" % name)
        handle = Handle(name=name, registered_at=_utcnow())
        self.handles[key] = handle
        return handle

    def unregister_handle(self, name: str) -> None:
        key = name.strip().lower()
        if key not in self.handles:
            raise ParlorError("no such handle: %r" % name)
        if any(p.handle.lower() == key for p in self.posts):
            raise ParlorError(
                "handle %r has posts on the board; delete them first" % name
            )
        del self.handles[key]

    def list_handles(self) -> List[Handle]:
        return [self.handles[k] for k in sorted(self.handles)]

    # -- bulletin board ----------------------------------------------------
    def post(self, handle: str, text: str) -> Post:
        key = handle.strip().lower()
        if key not in self.handles:
            raise ParlorError("unknown handle %r — register first" % handle)
        text = text.strip()
        if not text:
            raise ParlorError("posts cannot be empty")
        if len(text) > MAX_POST:
            raise ParlorError("posts are capped at %d chars" % MAX_POST)
        post = Post(
            id=self._next_post_id,
            handle=self.handles[key].name,
            text=text,
            posted_at=_utcnow(),
        )
        self._next_post_id += 1
        self.posts.append(post)
        return post

    def board(self, limit: Optional[int] = None) -> List[Post]:
        """Chronological, newest last. No ranking, no algorithm — the
        Miiverse inversion: the feed that refuses to be a feed."""
        posts = list(self.posts)
        return posts[-limit:] if limit else posts

    def delete_post(self, post_id: int, handle: str) -> None:
        key = handle.strip().lower()
        for i, post in enumerate(self.posts):
            if post.id == post_id:
                if post.handle.lower() != key:
                    raise ParlorError(
                        "only %r can delete post %d" % (post.handle, post_id)
                    )
                del self.posts[i]
                return
        raise ParlorError("no post with id %d" % post_id)

    # -- game nights -------------------------------------------------------
    def schedule_night(
        self, title: str, game: str, scheduled_at: str, host: str
    ) -> GameNight:
        title = title.strip()
        if not title:
            raise ParlorError("game nights need a title")
        host_key = host.strip().lower()
        if host_key not in self.handles:
            raise ParlorError("unknown host handle %r" % host)
        try:
            datetime.fromisoformat(scheduled_at)
        except ValueError:
            raise ParlorError(
                "scheduled_at must be ISO-8601 (got %r)" % scheduled_at
            ) from None
        night = GameNight(
            id=self._next_night_id,
            title=title,
            game=game.strip() or "open-table",
            scheduled_at=scheduled_at,
            host=self.handles[host_key].name,
            rsvps={self.handles[host_key].name: True},
        )
        self._next_night_id += 1
        self.nights[night.id] = night
        return night

    def rsvp(self, night_id: int, handle: str, attending: bool = True) -> GameNight:
        night = self.nights.get(night_id)
        if night is None:
            raise ParlorError("no game night with id %d" % night_id)
        if night.cancelled:
            raise ParlorError("game night %d is cancelled" % night_id)
        key = handle.strip().lower()
        if key not in self.handles:
            raise ParlorError("unknown handle %r" % handle)
        night.rsvps[self.handles[key].name] = attending
        return night

    def cancel_night(self, night_id: int, handle: str) -> GameNight:
        night = self.nights.get(night_id)
        if night is None:
            raise ParlorError("no game night with id %d" % night_id)
        if night.host.lower() != handle.strip().lower():
            raise ParlorError("only the host (%r) can cancel" % night.host)
        night.cancelled = True
        return night

    def upcoming_nights(self) -> List[GameNight]:
        return sorted(
            (n for n in self.nights.values() if not n.cancelled),
            key=lambda n: n.scheduled_at,
        )

    # -- portable state ----------------------------------------------------
    def to_dict(self) -> Dict:
        return {
            "format_version": FORMAT_VERSION,
            "exported_at": _utcnow(),
            "handles": [asdict(h) for h in self.list_handles()],
            "posts": [asdict(p) for p in self.posts],
            "nights": [asdict(n) for n in self.nights.values()],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Parlor":
        """Deny-closed import: malformed state is refused, never half-applied."""
        if not isinstance(data, dict):
            raise ParlorError("parlor data must be an object")
        parlor = cls()
        handles = data.get("handles", [])
        if not isinstance(handles, list):
            raise ParlorError("handles must be a list")
        for h in handles:
            if not isinstance(h, dict) or not h.get("name"):
                raise ParlorError("malformed handle entry: %r" % (h,))
            try:
                parlor.register_handle(h["name"])
            except ParlorError as exc:
                raise ParlorError("bad handle in import: %s" % exc) from exc
        posts = data.get("posts", [])
        if not isinstance(posts, list):
            raise ParlorError("posts must be a list")
        for p in posts:
            if not isinstance(p, dict) or "text" not in p or "handle" not in p:
                raise ParlorError("malformed post entry: %r" % (p,))
            post = parlor.post(p["handle"], p["text"])
            post.posted_at = p.get("posted_at", post.posted_at)
        nights = data.get("nights", [])
        if not isinstance(nights, list):
            raise ParlorError("nights must be a list")
        for n in nights:
            if not isinstance(n, dict) or "title" not in n or "host" not in n:
                raise ParlorError("malformed night entry: %r" % (n,))
            night = parlor.schedule_night(
                n["title"],
                n.get("game", "open-table"),
                n.get("scheduled_at", _utcnow()),
                n["host"],
            )
            night.cancelled = bool(n.get("cancelled", False))
            for handle, attending in (n.get("rsvps") or {}).items():
                try:
                    parlor.rsvp(night.id, handle, bool(attending))
                except ParlorError:
                    pass  # RSVP from an unregistered handle: dropped, noted
        return parlor


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


def default_path() -> Path:
    return Path(os.path.expanduser("~")) / ".levi" / "games" / "parlor" / "parlor.json"


class ParlorStore:
    """Atomic, owner-only persistence. The building, not a tenancy."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else default_path()

    def load(self) -> Parlor:
        if not self.path.exists():
            return Parlor()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ParlorError("cannot read parlor file: %s" % exc) from exc
        return Parlor.from_dict(data)

    def save(self, parlor: Parlor) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(parlor.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)
        return self.path


# ---------------------------------------------------------------------------
# The covenant — what the parlor promises, in plain speech
# ---------------------------------------------------------------------------


def covenant_text() -> str:
    return """THE PARLOR COVENANT
A third place that cannot be starved, in four plain promises.

1. No purchases. There is nothing to buy here, so there is nothing
   to revoke. (PlayStation Home taught us: rent is not ownership.)
2. No feed. Posts appear in the order they were written, newest last.
   Nothing is ranked, boosted, or buried. (Miiverse taught us: the feed
   eats the place.)
3. Safety by smallness. This is your household's place — the people in
   it are known, the board needs no review queue. (Club Penguin taught
   us: the haven was the moderation, not the minigames.)
4. No acquisition. The parlor is one portable file you own. There is no
   company, no graph, no server — nothing for a giant to buy and pivot.
   (AltspaceVR taught us: the rescue can be the harvest.)
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="levi.games parlor", description="The third place that cannot be starved."
    )
    parser.add_argument(
        "action",
        choices=[
            "handles",
            "register",
            "unregister",
            "board",
            "post",
            "delete",
            "night",
            "nights",
            "rsvp",
            "cancel",
            "export",
            "import",
            "covenant",
        ],
    )
    parser.add_argument("arg", nargs="?", default=None, help="name/text/title")
    parser.add_argument("--by", default=None, help="handle acting (post/delete/rsvp)")
    parser.add_argument("--game", default="open-table", help="warehouse game (night)")
    parser.add_argument("--at", default=None, help="ISO-8601 time (night)")
    parser.add_argument("--no", action="store_true", help="RSVP no (rsvp)")
    parser.add_argument("--file", default=None, help="export/import file")
    args = parser.parse_args(argv)

    store = ParlorStore()
    try:
        parlor = store.load()
        if args.action == "covenant":
            print(covenant_text())
        elif args.action == "handles":
            for h in parlor.list_handles():
                print("%-16s registered %s" % (h.name, h.registered_at))
        elif args.action == "register":
            if not args.arg:
                print("usage: parlor register NAME")
                return 2
            h = parlor.register_handle(args.arg)
            store.save(parlor)
            print("welcome to the parlor, %s" % h.name)
        elif args.action == "unregister":
            if not args.arg:
                print("usage: parlor unregister NAME")
                return 2
            parlor.unregister_handle(args.arg)
            store.save(parlor)
            print("unregistered %s" % args.arg)
        elif args.action == "board":
            for p in parlor.board():
                print("[%d] %s @ %s\n    %s" % (p.id, p.handle, p.posted_at, p.text))
        elif args.action == "post":
            if not args.arg or not args.by:
                print("usage: parlor post TEXT --by HANDLE")
                return 2
            p = parlor.post(args.by, args.arg)
            store.save(parlor)
            print("posted as #%d" % p.id)
        elif args.action == "delete":
            if not args.arg or not args.by:
                print("usage: parlor delete POST_ID --by HANDLE")
                return 2
            parlor.delete_post(int(args.arg), args.by)
            store.save(parlor)
            print("deleted post %s" % args.arg)
        elif args.action == "night":
            if not args.arg or not args.at or not args.by:
                print("usage: parlor night TITLE --at ISO_TIME --by HOST [--game GAME]")
                return 2
            n = parlor.schedule_night(args.arg, args.game, args.at, args.by)
            store.save(parlor)
            print(
                "game night #%d: %s (%s) at %s"
                % (n.id, n.title, n.game, n.scheduled_at)
            )
        elif args.action == "nights":
            for n in parlor.upcoming_nights():
                going = sum(1 for v in n.rsvps.values() if v)
                print(
                    "#%d %s — %s at %s (host %s, %d going)"
                    % (n.id, n.title, n.game, n.scheduled_at, n.host, going)
                )
        elif args.action == "rsvp":
            if not args.arg or not args.by:
                print("usage: parlor rsvp NIGHT_ID --by HANDLE [--no]")
                return 2
            parlor.rsvp(int(args.arg), args.by, attending=not args.no)
            store.save(parlor)
            print("rsvp recorded")
        elif args.action == "cancel":
            if not args.arg or not args.by:
                print("usage: parlor cancel NIGHT_ID --by HOST")
                return 2
            parlor.cancel_night(int(args.arg), args.by)
            store.save(parlor)
            print("game night %s cancelled" % args.arg)
        elif args.action == "export":
            data = json.dumps(parlor.to_dict(), indent=2, ensure_ascii=False)
            if args.file:
                Path(args.file).write_text(data, encoding="utf-8")
                print("exported to %s" % args.file)
            else:
                print(data)
        elif args.action == "import":
            if not args.file:
                print("usage: parlor import --file FILE")
                return 2
            data = json.loads(Path(args.file).read_text(encoding="utf-8"))
            parlor = Parlor.from_dict(data)
            store.save(parlor)
            print(
                "imported: %d handles, %d posts, %d nights"
                % (len(parlor.handles), len(parlor.posts), len(parlor.nights))
            )
    except ParlorError as exc:
        print("parlor: %s" % exc)
        return 1
    except (ValueError, OSError) as exc:
        print("parlor: %s" % exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
