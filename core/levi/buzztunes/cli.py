"""Buzz Tunes CLI — `levi buzztunes`.

play / queue / curate / thread / providers / m3u / stack / laws.
State lives under ~/.levi/buzztunes (override with --store).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import m3u as m3u_mod
from . import spotify as spotify_mod
from .dj import pick_song
from .engine import BuzzEngine
from .forge import MAX_FORGE, export_forge, forge_playlists
from .money import rail_status, split_70_30
from .providers import LocalFileProvider, default_registry
from .stack import STACK, check_stack
from .threads import ThreadStore

DEFAULT_STORE = Path.home() / ".levi" / "buzztunes"


def _engine(args) -> BuzzEngine:
    store = Path(getattr(args, "store", None) or DEFAULT_STORE)
    reg = default_registry()
    lib = getattr(args, "library", None)
    if lib:
        reg.register(LocalFileProvider(lib))
    return BuzzEngine(store, reg)


def _catalog(engine: BuzzEngine):
    tracks = []
    for name in engine.registry.names():
        tracks.extend(engine.registry.get(name).search("", limit=10000))
    seen, out = set(), []
    for t in tracks:
        if t.id not in seen:
            seen.add(t.id)
            out.append(t)
    return out


def _threads(args, engine: BuzzEngine) -> ThreadStore:
    store = Path(getattr(args, "store", None) or DEFAULT_STORE)
    return ThreadStore(engine, store)


def register_buzztunes_parser(sub) -> None:
    bt = sub.add_parser("buzztunes", help="Buzz Tunes music player")
    bt.add_argument("--store", default=None, help="state dir")
    cmds = bt.add_subparsers(dest="buzztunes_cmd")

    p = cmds.add_parser("play", help="play a track, or queue/show a playlist")
    p.add_argument("ref", help="track id/search text, .m3u path, or @N")
    p.add_argument("--manifest", default=None,
                   help="forge output dir (for @N playlist refs)")

    q = cmds.add_parser("queue", help="the play queue")
    qcmds = q.add_subparsers(dest="queue_cmd")
    qa = qcmds.add_parser("add", help="add a track to the queue")
    qa.add_argument("ref", help="track id or search text")
    qa.add_argument("--provider", default="fake")
    qcmds.add_parser("list", help="list the queue")
    qcmds.add_parser("clear", help="clear the queue")

    c = cmds.add_parser("curate", help="KFX² curation pipeline")
    c.add_argument("query", help="vibe/search seed")
    c.add_argument("--provider", default="fake")
    c.add_argument("--curator", type=int, default=0)

    t = cmds.add_parser("thread", help="shared listening threads")
    tcmds = t.add_subparsers(dest="thread_cmd")
    tc = tcmds.add_parser("create", help="create a thread")
    tc.add_argument("name", help="thread name")
    tcmds.add_parser("list", help="list threads")
    tj = tcmds.add_parser("join", help="join a thread")
    tj.add_argument("id", help="thread id")
    tj.add_argument("member", help="member name")
    tcu = tcmds.add_parser("curate", help="agent curates into a thread")
    tcu.add_argument("id", help="thread id")
    tcu.add_argument("query", help="vibe/search seed")
    tcu.add_argument("--agent", default="Quetta-Pan¹")
    tjo = tcmds.add_parser("journey", help="echoverse journey round")
    tjo.add_argument("id", help="thread id")
    tjo.add_argument("seed", help="vibe seed")

    m = cmds.add_parser("m3u", help="M3U playlist bridge")
    mcmds = m.add_subparsers(dest="m3u_cmd")
    mi = mcmds.add_parser("import", help="import .m3u/.m3u8 into the queue")
    mi.add_argument("file", help="playlist file")
    me = mcmds.add_parser("export", help="export the queue to .m3u")
    me.add_argument("file", help="output file")

    d = cmds.add_parser("dj", help="SI DJ: pick a song or playlist")
    d.add_argument("--mood", required=True, help="mood (e.g. rainy-night)")
    d.add_argument("--activity", required=True, help="activity (e.g. coding)")
    d.add_argument("--energy", default=None, help="energy (low..peak)")
    d.add_argument("--era", default=None, help="era (e.g. 2010s)")
    d.add_argument("--library", default=None,
                   help="local music directory as the catalog")

    f = cmds.add_parser("forge",
                        help="ultimate mix engine: forge up to 20k playlists")
    f.add_argument("--count", type=int, required=True,
                   help=f"how many playlists (1..{MAX_FORGE})")
    f.add_argument("--out", required=True, help="output directory")
    f.add_argument("--seed", default="buzz", help="determinism seed")
    f.add_argument("--library", default=None,
                   help="local music directory as the catalog")

    cmds.add_parser("providers", help="list media providers")
    cmds.add_parser("stack", help="the honest stack wiring report")
    cmds.add_parser("laws", help="the Buzz Tunes laws")
    cmds.add_parser("money", help="70/30 split + rail status")


def _resolve_ref(engine: BuzzEngine, ref: str, provider: str = "fake"):
    try:
        return engine.registry.get(provider).resolve(ref)
    except KeyError:
        hits = engine.registry.get(provider).search(ref, limit=1)
        if not hits:
            raise KeyError(f"no track for {ref!r} on {provider}")
        return hits[0]


def _play_playlist(engine: BuzzEngine, args) -> int:
    """Queue and show a forged playlist (.m3u path or @N with --manifest).

    Show/queue only: real audio renders through the Spotify seam when
    Chauncey links his account. Never fakes audio.
    """
    import json
    ref = args.ref
    if ref.startswith("@"):
        idx = int(ref[1:])
        man = Path(args.manifest) / "manifest.jsonl"
        rec = None
        for line in man.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["index"] == idx:
                rec = r
                break
        if rec is None:
            print(f"no playlist @{idx} in {man}")
            return 1
        path = Path(args.manifest) / rec["file"]
        print(f"playlist: {rec['concept']} [{rec['content_hash']}]")
    else:
        path = Path(ref)
    parsed = m3u_mod.read_playlist(path)
    for t in parsed.tracks:
        engine.queue_add(t, actor="forge-play")
    if parsed.tracks:
        res = engine.play(parsed.tracks[0].id, actor="forge-play")
        t = res["now_playing"]
        print(f"queued {len(parsed.tracks)} tracks; "
              f"now: {t['artist']} — {t['title']}")
    else:
        print("playlist is empty — nothing queued")
    if not spotify_mod.configured():
        print("(audio: Spotify not linked — order shown, "
              "rendering is the open follow-up)")
    return 0


def cmd_buzztunes(args: argparse.Namespace) -> int:
    cmd = getattr(args, "buzztunes_cmd", None)
    if cmd is None:
        print("levi buzztunes: play|queue|curate|thread|m3u|providers|stack|laws|money|dj|forge")
        return 2
    engine = _engine(args)

    if cmd == "play":
        ref = args.ref
        is_playlist = (
            (ref.startswith("@") and getattr(args, "manifest", None)) or
            ref.lower().endswith((".m3u", ".m3u8"))
        )
        if is_playlist:
            return _play_playlist(engine, args)
        track = _resolve_ref(engine, ref)
        engine.queue_add(track)
        res = engine.play(track.id)
        t = res["now_playing"]
        print(f"▶ {t['artist']} — {t['title']} [{res['receipt']['receipt_id']}]")
        return 0

    if cmd == "queue":
        qcmd = getattr(args, "queue_cmd", None) or "list"
        if qcmd == "add":
            track = _resolve_ref(engine, args.ref, args.provider)
            r = engine.queue_add(track)
            print(f"queued: {track.artist} — {track.title} [{r['receipt_id']}]")
        elif qcmd == "clear":
            r = engine.queue_clear()
            print(f"cleared {r['details']['removed']} tracks")
        else:
            for i, t in enumerate(engine.queue_list(), 1):
                print(f"{i}. {t.artist} — {t.title} ({t.id})")
        return 0

    if cmd == "curate":
        res = engine.curate(args.query, provider=args.provider,
                            curator_index=args.curator)
        print(f"curation [{res['queue'][0].meta.get('kfx2_fingerprint') if res['queue'] else 'empty'}]:")
        for t in res["queue"]:
            print(f"  • {t.artist} — {t.title}")
        if res["inversion"]["gaps"]:
            print("gaps: " + "; ".join(res["inversion"]["gaps"]))
        return 0

    if cmd == "thread":
        store = _threads(args, engine)
        tcmd = getattr(args, "thread_cmd", None) or "list"
        if tcmd == "create":
            th = store.create(args.name)
            print(f"created {th.id}: {th.name}")
        elif tcmd == "join":
            th = store.get(args.id)
            th.join(args.member)
            print(f"{args.member} joined {th.id}")
        elif tcmd == "curate":
            th = store.get(args.id)
            res = engine.curate(args.query)
            th.add_curation(args.agent, res["queue"])
            print(f"{args.agent} curated {len(res['queue'])} tracks into {th.id}")
        elif tcmd == "journey":
            th = store.get(args.id)
            res = th.journey_round(args.seed)
            print(f"journey: {len(res.get('optionalPaths', []))} paths")
            for pth in res.get("optionalPaths", [])[:5]:
                print(f"  • {pth.get('label')} (q={pth.get('quality')})")
        else:
            for t in store.list():
                print(f"{t['id']}: {t['name']} "
                      f"({len(t['members'])} members, {t['curations']} curations)")
        return 0

    if cmd == "m3u":
        mcmd = getattr(args, "m3u_cmd", None)
        if mcmd == "import":
            res = engine.import_m3u(args.file)
            print(f"imported {len(res['parsed'])} tracks "
                  f"({len(res['parsed'].skipped)} skipped)")
            for s in res["parsed"].skipped[:5]:
                print(f"  skip L{s['line']}: {s['reason']}")
        elif mcmd == "export":
            r = engine.export_m3u(args.file)
            print(f"exported {r['details']['tracks']} tracks to {args.file}")
        else:
            print("levi buzztunes m3u: import|export")
            return 2
        return 0

    if cmd == "dj":
        catalog = _catalog(engine)
        pick = pick_song(args.mood, args.activity, catalog,
                         energy=args.energy, era=args.era,
                         receipts=engine.receipts)
        engine.queue_add(pick.track, actor="dj")
        print(f"concept: {pick.concept}")
        print(f"pick: {pick.track.artist} — {pick.track.title}")
        print(f"dj [{pick.voice_path}]: {pick.voice_line}")
        print(f"why: {pick.reason}")
        return 0

    if cmd == "forge":
        catalog = _catalog(engine)
        t0 = __import__("time").perf_counter()
        playlists = forge_playlists(args.count, catalog, seed=args.seed)
        summary = export_forge(playlists, args.out,
                               receipts=engine.receipts)
        wall = __import__("time").perf_counter() - t0
        print(f"forged {summary['count']} playlists "
              f"({summary['unique_hashes']} unique) in "
              f"{summary['elapsed_s']}s export, {wall:.1f}s total → {args.out}")
        for pl in playlists[:3]:
            print(f"  • {pl.concept} [{pl.content_hash}] "
                  f"({len(pl.tracks)} tracks)")
        return 0

    if cmd == "providers":
        for name in engine.registry.names():
            d = engine.registry.get(name).describe()
            print(f"{name}: {d.get('kind')} {d.get('note', '')}")
        print("(network providers: queued follow-up)")
        return 0

    if cmd == "stack":
        for row in check_stack():
            mark = {"WIRED": "●", "BUILT-HERE": "◐",
                    "MISSING": "○"}[row["status"]]
            print(f"{mark} {row['component']} [{row['status']}]"
                  f" — {row['check']}")
            print(f"    {row['note']}")
        return 0

    if cmd == "laws":
        import levi.buzztunes as pkg
        print(pkg.__doc__)
        return 0

    if cmd == "money":
        st = rail_status()
        print(f"rail: {st['mode']} (via={st['via']})")
        print(f"split on 100¢: {split_70_30(100)}")
        return 0

    print(f"unknown buzztunes command: {cmd}")
    return 2
