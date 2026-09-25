"""``levi sidewinder`` and ``levi course`` — platform CLI surfaces.

Both commands are thin surfaces over the course-platform query API
(``platform/api.py``): LEVI/agents consume the same API directly, a web UI
can later do the same. No network, stdlib only.

``levi sidewinder`` surfaces:

* ``levi sidewinder``                  — doctrine + corpus stats + usage
* ``levi sidewinder doctrine``         — the five laws, verbatim
* ``levi sidewinder <task...>``       — terse field-improv answer (mode;
                                        multiword tasks need no quoting)
* ``levi sidewinder manual``          — list entries (``--domain``/``--track``)
* ``levi sidewinder show <id>``       — one full entry
* ``levi sidewinder grow``            — run the batch growth pipeline
* ``levi sidewinder stubs <n>``       — emit n writer stubs from the roadmap
* ``levi sidewinder teams``           — list registered agent teams
* ``levi sidewinder team-harvest <team> <file.jsonl>``
* ``levi sidewinder team-review <team>``
* ``levi sidewinder team-promote <team>``

``levi course`` surfaces (curriculum query):

* ``levi course``                     — tracks + usage
* ``levi course tracks``              — the six tracks with entry counts
* ``levi course editions``            — available edition packs
* ``levi course <track>``             — the track's progression in order
* ``levi course <topic...>``          — best match plus its learning path

``--edition <id>`` filters any query to an edition pack;
``--team <id>`` scopes any query to an agent team's view.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from levi.sidewinder import SIDEWINDER_DOCTRINE, TRACKS, TRACK_DESCRIPTIONS
from levi.sidewinder.platform.api import CoursePlatform

ACTION_WORDS = (
    "doctrine",
    "manual",
    "show",
    "grow",
    "stubs",
    "teams",
    "team-harvest",
    "team-review",
    "team-promote",
)


def _platform() -> CoursePlatform:
    return CoursePlatform()


def _split_flags(words):
    """Pull --domain/--track/--edition/--team flags out of a REMAINDER word list.

    Options may appear before the task (parsed by argparse) or after the
    action word (``levi sidewinder manual --track improvise``); this keeps
    both orders working. Returns (domain, track, edition, team, rest_words).
    """
    domain = track = edition = team = None
    rest: list = []
    i = 0
    while i < len(words):
        word = words[i]
        if word in ("--domain", "--track", "--edition", "--team") and i + 1 < len(words):
            value = words[i + 1]
            if word == "--domain":
                domain = value
            elif word == "--track":
                track = value
            elif word == "--edition":
                edition = value
            else:
                team = value
            i += 2
        else:
            rest.append(word)
            i += 1
    return domain, track, edition, team, rest


def _n_entries(n: int) -> str:
    return f"{n} entry" if n == 1 else f"{n} entries"


def _check_track(track):
    if track is not None and track not in TRACKS:
        print(f"Unknown track {track!r} (want one of {', '.join(TRACKS)})")
        return False
    return True


def register_sidewinder(sub) -> None:
    """Add the ``sidewinder`` command.

    The task is REMAINDER (multiword, unquoted) and the first word may be
    an action word — no subparsers, so ``levi sidewinder tub spout`` and
    ``levi sidewinder manual --track improvise`` both parse.
    """
    sw_p = sub.add_parser(
        "sidewinder",
        help="Sidewinder mode: field-improvisation guidance from the course platform",
    )
    sw_p.add_argument(
        "--domain",
        default=None,
        help="Narrow search/manual to one domain (e.g. plumbing, fasteners)",
    )
    sw_p.add_argument(
        "--track",
        default=None,
        choices=list(TRACKS),
        help="Narrow search/manual to one track (e.g. improvise, restore)",
    )
    sw_p.add_argument(
        "--edition",
        default=None,
        help="Scope to an edition pack, e.g. first-responder",
    )
    sw_p.add_argument(
        "--team",
        default=None,
        help="Scope to an agent team's view, e.g. field-crew",
    )
    sw_p.add_argument(
        "task",
        nargs=argparse.REMAINDER,
        help="Task text (multiword OK), or an action word: doctrine|manual|show|grow|stubs|teams|team-harvest|team-review|team-promote",
    )


def register_course(sub) -> None:
    """Add the ``course`` curriculum query command."""
    c_p = sub.add_parser(
        "course",
        help="Course curriculum: progressions by track, learning paths by topic",
    )
    c_p.add_argument(
        "--track",
        default=None,
        choices=list(TRACKS),
        help="Narrow a topic search to one track",
    )
    c_p.add_argument(
        "--edition",
        default=None,
        help="Filter to an edition pack, e.g. first-responder",
    )
    c_p.add_argument(
        "--team",
        default=None,
        help="Scope to an agent team's view, e.g. field-crew",
    )
    c_p.add_argument(
        "query",
        nargs=argparse.REMAINDER,
        help="A track, 'tracks', 'editions', or a topic",
    )


def _sidewinder_usage() -> str:
    return (
        "usage: levi sidewinder [doctrine|manual|show <id>|grow|stubs <n>|teams|"
        "team-harvest <team> <file>|team-review <team>|team-promote <team>|<task...>] "
        "[--domain D] [--track T] [--edition E] [--team TM]"
    )


def _cmd_manual(api: CoursePlatform, domain, track, edition, team) -> int:
    entries = api.manual(domain=domain, track=track, edition=edition, team=team)
    if not entries:
        print("No entries match.")
        return 1
    for entry in entries:
        print(f"{entry['id']}  [{'|'.join(entry['tracks'])}] {entry['title']}")
    print(f"-- {len(entries)} entries --")
    return 0


def _cmd_show(api: CoursePlatform, argv, edition, team) -> int:
    entry_id = " ".join(argv).strip()
    try:
        entry = api.get(entry_id, edition=edition, team=team)
    except KeyError as exc:
        print(exc)
        return 2
    if entry is None:
        print(f"Unknown entry id {entry_id!r}. Try: levi sidewinder manual")
        return 1
    print(api.format_entry(entry))
    return 0


def _cmd_grow(api: CoursePlatform, argv) -> int:
    batch = None
    dry_run = False
    consume = True
    i = 0
    words = list(argv)
    positional = []
    while i < len(words):
        word = words[i]
        if word == "--batch" and i + 1 < len(words):
            try:
                batch = int(words[i + 1])
            except ValueError:
                print(f"grow: --batch wants an integer, got {words[i + 1]!r}")
                return 2
            i += 2
        elif word == "--dry-run":
            dry_run = True
            i += 1
        elif word == "--no-consume":
            consume = False
            i += 1
        else:
            positional.append(word)
            i += 1
    if positional:
        print(f"grow: unexpected arguments: {' '.join(positional)}")
        return 2
    report = api.grow(batch=batch, dry_run=dry_run, consume=consume)
    print(
        "grow: seeds={seeds_read} valid={valid} invalid={invalid} "
        "dup={duplicates} appended={appended}{dry}".format(
            dry=" (DRY RUN)" if report["dry_run"] else "", **report
        )
    )
    if report["per_domain"]:
        print("  per domain: " + ", ".join(f"{d}+{n}" for d, n in sorted(report["per_domain"].items())))
    for err in report["errors"][:10]:
        print(f"  ! {err}")
    if len(report["errors"]) > 10:
        print(f"  ! ... and {len(report['errors']) - 10} more")
    return 0 if report["invalid"] == 0 and report["seeds_json_bad"] == 0 else 2


def _cmd_stubs(api: CoursePlatform, argv) -> int:
    if not argv:
        print("stubs: give a count, e.g. levi sidewinder stubs 5")
        return 2
    try:
        count = int(argv[0])
    except ValueError:
        print(f"stubs: count must be an integer, got {argv[0]!r}")
        return 2
    report = api.emit_stubs(count)
    print(f"stubs: wrote {report['stubs_written']} writer stubs -> {report['stubs_file']}")
    print("Fill the FILL sections, move finished lines into seeds/topics.jsonl, then: levi sidewinder grow")
    return 0


def _cmd_team_harvest(api: CoursePlatform, argv) -> int:
    if len(argv) != 2:
        print("usage: levi sidewinder team-harvest <team-id> <entries.jsonl>")
        return 2
    team_id, file = argv
    path = Path(file)
    if not path.is_file():
        print(f"team-harvest: no such file {file!r}")
        return 2
    entries = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as exc:
            print(f"team-harvest: line {lineno}: bad JSON: {exc}")
            return 2
    try:
        report = api.harvest(team_id, entries)
    except KeyError as exc:
        print(exc)
        return 2
    print(
        f"harvest: team={report['team']} received={report['received']} "
        f"valid={report['valid']} invalid={report['invalid']} -> {report['intake']}"
    )
    for err in report["errors"][:10]:
        print(f"  ! {err}")
    return 0


def _cmd_team_review(api: CoursePlatform, argv) -> int:
    if len(argv) != 1:
        print("usage: levi sidewinder team-review <team-id>")
        return 2
    try:
        report = api.review_intake(argv[0])
    except KeyError as exc:
        print(exc)
        return 2
    print(
        f"review: team={report['team']} seeds={report['seeds_read']} "
        f"valid={report['valid']} invalid={report['invalid']} "
        f"dup={report['duplicates']} would_append={report['valid'] - report['duplicates']} (DRY RUN)"
    )
    for err in report["errors"][:10]:
        print(f"  ! {err}")
    return 0


def _cmd_team_promote(api: CoursePlatform, argv) -> int:
    if len(argv) != 1:
        print("usage: levi sidewinder team-promote <team-id>")
        return 2
    try:
        report = api.promote_intake(argv[0])
    except KeyError as exc:
        print(exc)
        return 2
    print(
        f"promote: team={report['team']} valid={report['valid']} "
        f"invalid={report['invalid']} dup={report['duplicates']} appended={report['appended']}"
    )
    if report["per_domain"]:
        print("  per domain: " + ", ".join(f"{d}+{n}" for d, n in sorted(report["per_domain"].items())))
    for err in report["errors"][:10]:
        print(f"  ! {err}")
    return 0 if report["invalid"] == 0 and report["seeds_json_bad"] == 0 else 2


def cmd_sidewinder(args) -> int:
    """Dispatch ``levi sidewinder``. Returns a process exit code."""
    words = list(getattr(args, "task", None) or [])
    domain = getattr(args, "domain", None)
    track = getattr(args, "track", None)
    edition = getattr(args, "edition", None)
    team = getattr(args, "team", None)
    f_domain, f_track, f_edition, f_team, rest = _split_flags(words)
    domain = domain or f_domain
    track = track or f_track
    edition = edition or f_edition
    team = team or f_team
    if not _check_track(track):
        return 2

    try:
        api = _platform()
    except ValueError as exc:
        print(exc)
        return 2

    action = None
    argv: list = []
    if rest and rest[0] in ACTION_WORDS:
        action, argv = rest[0], rest[1:]

    if action == "doctrine":
        print(SIDEWINDER_DOCTRINE)
        return 0
    if action == "manual":
        try:
            return _cmd_manual(api, domain, track, edition, team)
        except KeyError as exc:
            print(exc)
            return 2
    if action == "show":
        return _cmd_show(api, argv, edition, team)
    if action == "grow":
        return _cmd_grow(api, argv)
    if action == "stubs":
        return _cmd_stubs(api, argv)
    if action == "teams":
        print(api.format_teams())
        return 0
    if action == "team-harvest":
        return _cmd_team_harvest(api, argv)
    if action == "team-review":
        return _cmd_team_review(api, argv)
    if action == "team-promote":
        return _cmd_team_promote(api, argv)

    task = " ".join(rest).strip()
    if task:
        try:
            hits = api.search(task, domain=domain, track=track, edition=edition, team=team, limit=3)
        except KeyError as exc:
            print(exc)
            return 2
        if not hits:
            scope = " ".join(
                x
                for x in (
                    f"in domain {domain!r}" if domain else "",
                    f"on track {track!r}" if track else "",
                    f"in edition {edition!r}" if edition else "",
                    f"for team {team!r}" if team else "",
                )
                if x
            )
            print(f"No course entries match {task!r}" + (f" {scope}." if scope else "."))
            print("Doctrine still applies: see the mechanism, substitute from on-hand, protect the work, know the stop.")
            return 1
        print("\n\n---\n\n".join(api.format_entry(e) for e in hits))
        return 0

    # Bare `levi sidewinder`: doctrine + platform state + usage (the mode card).
    print(SIDEWINDER_DOCTRINE)
    print()
    try:
        view_entries = api._view(edition, team).entries
    except KeyError as exc:
        print(exc)
        return 2
    scope_note = " ".join(
        x
        for x in (
            f"edition: {edition}" if edition else "",
            f"team: {team}" if team else "",
        )
        if x
    )
    counts = api.track_counts(edition=edition, team=team)
    print(f"course{' (' + scope_note + ')' if scope_note else ''}: {len(view_entries)} entries")
    print("tracks: " + ", ".join(f"{t}={counts[t]}" for t in TRACKS))
    print(f"editions: {', '.join(api.edition_ids())} | teams: {', '.join(t.id for t in api.list_teams())}")
    print()
    print(_sidewinder_usage())
    return 0


def cmd_course(args) -> int:
    """Dispatch ``levi course``. Returns a process exit code."""
    words = list(getattr(args, "query", None) or [])
    track = getattr(args, "track", None)
    edition = getattr(args, "edition", None)
    team = getattr(args, "team", None)
    _, f_track, f_edition, f_team, rest = _split_flags(words)
    track = track or f_track
    edition = edition or f_edition
    team = team or f_team
    if not _check_track(track):
        return 2
    query = " ".join(rest).strip().lower()

    try:
        api = _platform()
    except ValueError as exc:
        print(exc)
        return 2

    def scope_note() -> str:
        bits = [f"edition: {edition}" if edition else "", f"team: {team}" if team else ""]
        bits = [b for b in bits if b]
        return f" ({', '.join(bits)})" if bits else ""

    if not query:
        if edition and not team:
            try:
                print(api.format_edition(edition))
            except KeyError as exc:
                print(exc)
                return 2
            return 0
        try:
            counts = api.track_counts(edition=edition, team=team)
        except KeyError as exc:
            print(exc)
            return 2
        print(f"SIDEWINDER COURSE — six tracks{scope_note()}:")
        for trk in TRACKS:
            print(f"  {trk:9s} {_n_entries(counts[trk]):>10s} — {TRACK_DESCRIPTIONS[trk]}")
        print()
        print("editions: " + ", ".join(api.edition_ids()))
        print("teams: " + ", ".join(t.id for t in api.list_teams()))
        print()
        print("usage: levi course [--edition E] [--team TM] [<track>|<topic...>|tracks|editions]")
        return 0

    if query == "tracks":
        try:
            counts = api.track_counts(edition=edition, team=team)
        except KeyError as exc:
            print(exc)
            return 2
        print(f"SIDEWINDER COURSE — six tracks{scope_note()}:")
        for trk in TRACKS:
            print(f"  {trk:9s} {_n_entries(counts[trk]):>10s} — {TRACK_DESCRIPTIONS[trk]}")
        return 0

    if query == "editions":
        for eid in api.edition_ids():
            manifest = api.edition_manifest(eid)
            print(f"  {eid}  {manifest['name']} — {manifest['blurb']}")
        return 0

    if query in TRACKS:
        try:
            print(api.format_progression(query, edition=edition, team=team))
        except (KeyError, ValueError) as exc:
            print(exc)
            return 2
        return 0

    # Topic: best match plus its learning path (prerequisites in order).
    try:
        hits = api.search(query, track=track, edition=edition, team=team, limit=1)
    except KeyError as exc:
        print(exc)
        return 2
    if not hits:
        print(f"No course entries match {query!r}. Try: levi course tracks")
        return 1
    try:
        print(api.format_learning_path(hits[0]["id"], edition=edition, team=team))
    except (KeyError, ValueError) as exc:
        print(exc)
        return 2
    return 0
