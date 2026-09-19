"""CLI: `levi creator ...` — both tracks.

SI commands are gate-locked by the underlying modules (the gate raises
before anything happens when Plaiground is not enabled). `--home` scopes
all storage for testing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from levi.creator.ai import chats as ai_chats
from levi.creator.ai import creators as ai_creators
from levi.creator.ai import dating as ai_dating
from levi.creator.ai import media as ai_media
from levi.creator.money import MoneyAuthorization
from levi.creator import safety as creator_safety
from levi.creator.si import chats as si_chats
from levi.creator.si import dating as si_dating
from levi.creator.si import drops as si_drops
from levi.creator.si import media as si_media
from levi.creator.si import messaging as si_messaging
from levi.creator.si import privacy as si_privacy
from levi.creator.si import profiles as si_profiles
from levi.creator.si import subscriptions as si_subscriptions


def _home(args) -> Optional[Path]:
    return Path(args.home) if getattr(args, "home", None) else None


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, default=str))


def _auth(args) -> MoneyAuthorization:
    return MoneyAuthorization(
        authorized_by=args.authorized_by,
        plan_id="",
        operation="charge",
        note=getattr(args, "note", "") or "",
    )


def cmd_creator(args) -> int:
    home = _home(args)
    cmd = args.creator_cmd

    try:
        if cmd == "si-profile-create":
            _print(si_profiles.create_profile(args.handle, args.display_name, args.bio, home))
        elif cmd == "si-profile-list":
            _print(si_profiles.list_profiles(home))
        elif cmd == "si-tier-add":
            _print(si_subscriptions.add_tier(args.creator, args.name, args.price_minor, args.perk or [], home))
        elif cmd == "si-tier-list":
            _print(si_subscriptions.list_tiers(args.creator, home))
        elif cmd == "si-subscribe":
            _print(si_subscriptions.subscribe(args.creator, args.tier_id, args.subscriber, _auth(args), home))
        elif cmd == "si-msg-send":
            _print(si_messaging.send(args.sender, args.recipient, args.body, home))
        elif cmd == "si-msg-inbox":
            _print(si_messaging.inbox(args.user, home))
        elif cmd == "si-drop-post":
            _print(si_drops.post_drop(args.creator, args.title, args.body, args.tier_id, home))
        elif cmd == "si-drop-list":
            _print(si_drops.list_drops(args.creator, home))
        elif cmd == "si-listing-post":
            _print(si_dating.post_listing(args.poster, args.headline, args.seeking, args.terms, home))
        elif cmd == "si-listing-search":
            _print(si_dating.search_listings(args.query or "", home))
        elif cmd == "si-listing-respond":
            _print(si_dating.respond(args.listing_id, args.responder, args.message, home))
        elif cmd == "si-media-post":
            _print(si_media.post_media(
                args.creator, args.kind, args.title, args.filename, args.data_b64,
                args.tier_id, args.grant or [], home))
        elif cmd == "si-media-view":
            _print(si_media.view(args.media_id, args.user, home))
        elif cmd == "si-media-grant":
            _print(si_media.grant_access(args.media_id, args.creator, args.subscriber, home))
        elif cmd == "si-media-revoke":
            _print({"revoked": si_media.revoke_access(args.media_id, args.creator, args.subscriber, home)})
        elif cmd == "si-media-list":
            _print(si_media.list_media(args.creator, args.user, home))
        elif cmd == "si-chat-create":
            _print(si_chats.create_chat(args.creator, args.other, home))
        elif cmd == "si-group-create":
            _print(si_chats.create_group(args.creator, args.name, args.member or [], home))
        elif cmd == "si-chat-send":
            _print(si_chats.send_chat_message(args.chat_id, args.sender, args.body, home))
        elif cmd == "si-chat-thread":
            _print(si_chats.chat_thread(args.chat_id, args.user, home))
        elif cmd == "si-chat-list":
            _print(si_chats.list_chats(args.user, home))
        elif cmd == "si-group-add":
            _print(si_chats.add_member(args.chat_id, args.owner, args.member, home))
        elif cmd == "si-group-remove":
            _print(si_chats.remove_member(args.chat_id, args.owner, args.member, home))
        elif cmd == "si-chat-close":
            _print(si_chats.close_chat(args.chat_id, args.owner, home))
        elif cmd == "si-listing-public":
            _print(si_privacy.public_search(args.query or "", home))
        elif cmd == "si-respond-private":
            _print(si_privacy.respond(
                args.listing_id, args.responder, args.message, home,
                reveal_profile=not args.anonymous))
        elif cmd == "si-responses-read":
            _print(si_privacy.read_responses_for_listing(args.listing_id, args.poster, home))
        elif cmd == "ai-media-post":
            _print(ai_media.post_media(
                args.creator, args.kind, args.title, args.filename, args.data_b64,
                args.tier_id, args.grant or [], home))
        elif cmd == "ai-media-view":
            _print(ai_media.view(args.media_id, args.user, home))
        elif cmd == "ai-media-grant":
            _print(ai_media.grant_access(args.media_id, args.creator, args.subscriber, home))
        elif cmd == "ai-media-list":
            _print(ai_media.list_media(args.creator, args.user, home))
        elif cmd == "ai-chat-create":
            _print(ai_chats.create_chat(args.creator, args.other, home))
        elif cmd == "ai-group-create":
            _print(ai_chats.create_group(args.creator, args.name, args.member or [], home))
        elif cmd == "ai-chat-send":
            _print(ai_chats.send_chat_message(args.chat_id, args.sender, args.body, home))
        elif cmd == "ai-chat-thread":
            _print(ai_chats.chat_thread(args.chat_id, args.user, home))
        elif cmd == "ai-chat-list":
            _print(ai_chats.list_chats(args.user, home))
        elif cmd == "ai-group-add":
            _print(ai_chats.add_member(args.chat_id, args.owner, args.member, home))
        elif cmd == "ai-group-remove":
            _print(ai_chats.remove_member(args.chat_id, args.owner, args.member, home))
        elif cmd == "ai-chat-close":
            _print(ai_chats.close_chat(args.chat_id, args.owner, home))
        elif cmd == "safety-contact-add":
            _print(creator_safety.add_contact(args.user, args.name, args.ref, args.track, home))
        elif cmd == "safety-contact-list":
            _print(creator_safety.list_contacts(args.user, args.track, home))
        elif cmd == "safety-plan-create":
            _print(creator_safety.create_plan(
                args.user, args.who, args.where, args.when, args.check_in_minutes,
                args.contact or [], args.track, args.disclosure or "", home))
        elif cmd == "safety-checkin":
            _print(creator_safety.check_in(args.plan_id, args.user, args.track, home))
        elif cmd == "safety-plan-status":
            _print(creator_safety.plan_status(args.plan_id, args.user, args.track, home))
        elif cmd == "safety-plan-end":
            _print(creator_safety.end_plan(args.plan_id, args.user, args.track, home))
        elif cmd == "safety-escalation-run":
            _print(creator_safety.run_escalation_check(args.track, home))
        elif cmd == "safety-escalations":
            _print(creator_safety.list_escalations(args.user, args.track, home))
        elif cmd == "ai-profile-create":
            _print(ai_dating.create_profile(args.handle, args.display_name, args.bio, args.interest or [], home))
        elif cmd == "ai-profile-list":
            _print(ai_dating.list_profiles(home))
        elif cmd == "ai-match":
            _print(ai_dating.find_matches(args.handle, home))
        elif cmd == "ai-msg-send":
            _print(ai_dating.send_message(args.sender, args.recipient, args.body, home))
        elif cmd == "ai-msg-inbox":
            _print(ai_dating.inbox(args.user, home))
        elif cmd == "ai-creator-create":
            _print(ai_creators.create_creator(args.handle, args.display_name, args.bio, args.category, home))
        elif cmd == "ai-creator-list":
            _print(ai_creators.list_creators(home))
        elif cmd == "ai-tier-add":
            _print(ai_creators.add_tier(args.creator, args.name, args.price_minor, args.perk or [], home))
        elif cmd == "ai-subscribe":
            _print(ai_creators.subscribe(args.creator, args.tier_id, args.subscriber, _auth(args), home))
        elif cmd == "ai-drop-post":
            _print(ai_creators.post_drop(args.creator, args.title, args.body, home))
        elif cmd == "ai-drop-list":
            _print(ai_creators.list_drops(args.creator, home))
        else:
            print("unknown creator command: %s" % cmd)
            return 2
    except Exception as exc:  # gate, bounds, rules, money refusals surface as errors
        print("creator %s failed: %s: %s" % (cmd, type(exc).__name__, exc))
        return 1
    return 0


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--home", default=None, help="scope storage under this home dir")


def _register_subcommands(csub) -> None:
    """Register every creator subcommand on a subparsers object."""
    def sp(name: str, help: str, **kw):
        s = csub.add_parser(name, help=help, **kw)
        _add_common(s)
        return s

    # SI track
    s = sp("si-profile-create", "create an adult creator profile (gated)")
    s.add_argument("handle"); s.add_argument("display_name"); s.add_argument("bio")
    sp("si-profile-list", "list adult creator profiles (gated)")
    s = sp("si-tier-add", "add a subscription tier (gated)")
    s.add_argument("creator"); s.add_argument("name"); s.add_argument("price_minor", type=int)
    s.add_argument("--perk", action="append", default=[])
    s = sp("si-tier-list", "list tiers (gated)"); s.add_argument("creator")
    s = sp("si-subscribe", "subscribe to a tier — Cybrus only, fail-closed (gated)")
    s.add_argument("creator"); s.add_argument("tier_id"); s.add_argument("subscriber")
    s.add_argument("--authorized-by", required=True); s.add_argument("--note", default="")
    s = sp("si-msg-send", "send a sealed message (gated)")
    s.add_argument("sender"); s.add_argument("recipient"); s.add_argument("body")
    s = sp("si-msg-inbox", "read inbox (gated)"); s.add_argument("user")
    s = sp("si-drop-post", "post a content drop (gated)")
    s.add_argument("creator"); s.add_argument("title"); s.add_argument("body")
    s.add_argument("--tier-id", default=None)
    s = sp("si-drop-list", "list drops (gated)"); s.add_argument("creator")
    s = sp("si-listing-post", "post a dating listing (gated)")
    s.add_argument("poster"); s.add_argument("headline"); s.add_argument("seeking"); s.add_argument("terms")
    s = sp("si-listing-search", "search listings (gated)")
    s.add_argument("--query", default="")
    s = sp("si-listing-respond", "respond to a listing (gated)")
    s.add_argument("listing_id"); s.add_argument("responder"); s.add_argument("message")

    # SI media + chats (gated, sealed)
    s = sp("si-media-post", "post a private photo/video drop (gated)")
    s.add_argument("creator"); s.add_argument("kind", choices=["photo", "video"])
    s.add_argument("title"); s.add_argument("filename"); s.add_argument("data_b64")
    s.add_argument("--tier-id", default=None); s.add_argument("--grant", action="append", default=[])
    s = sp("si-media-view", "view a media drop if entitled (gated)")
    s.add_argument("media_id"); s.add_argument("user")
    s = sp("si-media-grant", "grant a subscriber media access (gated, creator only)")
    s.add_argument("media_id"); s.add_argument("creator"); s.add_argument("subscriber")
    s = sp("si-media-revoke", "revoke a subscriber's media access (gated, creator only)")
    s.add_argument("media_id"); s.add_argument("creator"); s.add_argument("subscriber")
    s = sp("si-media-list", "list viewable media metadata (gated)")
    s.add_argument("creator"); s.add_argument("user")
    s = sp("si-chat-create", "open a private 1:1 chat (gated)")
    s.add_argument("creator"); s.add_argument("other")
    s = sp("si-group-create", "create an owner-moderated group chat (gated)")
    s.add_argument("creator"); s.add_argument("name"); s.add_argument("--member", action="append", default=[])
    s = sp("si-chat-send", "send a chat message (gated, members only)")
    s.add_argument("chat_id"); s.add_argument("sender"); s.add_argument("body")
    s = sp("si-chat-thread", "read a chat thread (gated, members only)")
    s.add_argument("chat_id"); s.add_argument("user")
    s = sp("si-chat-list", "list your chats (gated)"); s.add_argument("user")
    s = sp("si-group-add", "add a group member (gated, owner only)")
    s.add_argument("chat_id"); s.add_argument("owner"); s.add_argument("member")
    s = sp("si-group-remove", "remove a group member (gated, owner only)")
    s.add_argument("chat_id"); s.add_argument("owner"); s.add_argument("member")
    s = sp("si-chat-close", "close a chat (gated, owner only)")
    s.add_argument("chat_id"); s.add_argument("owner")

    # SI dating privacy (gated, airtight)
    s = sp("si-listing-public", "search listings — redacted public view (gated)")
    s.add_argument("--query", default="")
    s = sp("si-respond-private", "respond with explicit disclosure gate (gated)")
    s.add_argument("listing_id"); s.add_argument("responder"); s.add_argument("message")
    s.add_argument("--anonymous", action="store_true", help="hide identity from the poster")
    s = sp("si-responses-read", "read responses to your listing (gated, poster only)")
    s.add_argument("listing_id"); s.add_argument("poster")

    # AI track
    s = sp("ai-profile-create", "create an SFW dating profile")
    s.add_argument("handle"); s.add_argument("display_name"); s.add_argument("bio")
    s.add_argument("--interest", action="append", default=[])
    sp("ai-profile-list", "list SFW dating profiles")
    s = sp("ai-match", "find matches by shared interests"); s.add_argument("handle")
    s = sp("ai-msg-send", "send a message (SFW rules)")
    s.add_argument("sender"); s.add_argument("recipient"); s.add_argument("body")
    s = sp("ai-msg-inbox", "read inbox"); s.add_argument("user")
    s = sp("ai-creator-create", "create a general-audience creator")
    s.add_argument("handle"); s.add_argument("display_name"); s.add_argument("bio"); s.add_argument("category")
    sp("ai-creator-list", "list general-audience creators")
    s = sp("ai-tier-add", "add a subscription tier")
    s.add_argument("creator"); s.add_argument("name"); s.add_argument("price_minor", type=int)
    s.add_argument("--perk", action="append", default=[])
    s = sp("ai-subscribe", "subscribe to a tier — Cybrus only, fail-closed")
    s.add_argument("creator"); s.add_argument("tier_id"); s.add_argument("subscriber")
    s.add_argument("--authorized-by", required=True); s.add_argument("--note", default="")
    s = sp("ai-drop-post", "post a content drop (SFW rules)")
    s.add_argument("creator"); s.add_argument("title"); s.add_argument("body")
    s = sp("ai-drop-list", "list drops"); s.add_argument("creator")

    # AI media + chats (SFW rules, no gate)
    s = sp("ai-media-post", "post an SFW photo/video drop")
    s.add_argument("creator"); s.add_argument("kind", choices=["photo", "video"])
    s.add_argument("title"); s.add_argument("filename"); s.add_argument("data_b64")
    s.add_argument("--tier-id", default=None); s.add_argument("--grant", action="append", default=[])
    s = sp("ai-media-view", "view a media drop if entitled")
    s.add_argument("media_id"); s.add_argument("user")
    s = sp("ai-media-grant", "grant a subscriber media access (creator only)")
    s.add_argument("media_id"); s.add_argument("creator"); s.add_argument("subscriber")
    s = sp("ai-media-list", "list viewable media metadata")
    s.add_argument("creator"); s.add_argument("user")
    s = sp("ai-chat-create", "open a private 1:1 chat")
    s.add_argument("creator"); s.add_argument("other")
    s = sp("ai-group-create", "create an owner-moderated group chat")
    s.add_argument("creator"); s.add_argument("name"); s.add_argument("--member", action="append", default=[])
    s = sp("ai-chat-send", "send a chat message (members only)")
    s.add_argument("chat_id"); s.add_argument("sender"); s.add_argument("body")
    s = sp("ai-chat-thread", "read a chat thread (members only)")
    s.add_argument("chat_id"); s.add_argument("user")
    s = sp("ai-chat-list", "list your chats"); s.add_argument("user")
    s = sp("ai-group-add", "add a group member (owner only)")
    s.add_argument("chat_id"); s.add_argument("owner"); s.add_argument("member")
    s = sp("ai-group-remove", "remove a group member (owner only)")
    s.add_argument("chat_id"); s.add_argument("owner"); s.add_argument("member")
    s = sp("ai-chat-close", "close a chat (owner only)")
    s.add_argument("chat_id"); s.add_argument("owner")

    # Meetup safety (both tracks; --track si|ai)
    def _track_arg(p):
        p.add_argument("--track", required=True, choices=["si", "ai"])
    s = sp("safety-contact-add", "add a trusted contact (owner only)")
    s.add_argument("user"); s.add_argument("name"); s.add_argument("ref"); _track_arg(s)
    s = sp("safety-contact-list", "list your trusted contacts")
    s.add_argument("user"); _track_arg(s)
    s = sp("safety-plan-create", "create a meetup plan (opt-in, owner only)")
    s.add_argument("user"); s.add_argument("who"); s.add_argument("where"); s.add_argument("when")
    s.add_argument("check_in_minutes", type=int)
    s.add_argument("--contact", action="append", default=[])
    s.add_argument("--disclosure", default=""); _track_arg(s)
    s = sp("safety-checkin", "check in on a plan (owner only)")
    s.add_argument("plan_id"); s.add_argument("user"); _track_arg(s)
    s = sp("safety-plan-status", "plan status (owner only)")
    s.add_argument("plan_id"); s.add_argument("user"); _track_arg(s)
    s = sp("safety-plan-end", "end a plan (owner only)")
    s.add_argument("plan_id"); s.add_argument("user"); _track_arg(s)
    s = sp("safety-escalation-run", "fire escalation for missed check-ins (keeper/daemon)")
    _track_arg(s)
    s = sp("safety-escalations", "list your escalation records")
    s.add_argument("user"); _track_arg(s)


def register_creator_parser(sub) -> None:
    """Hook for the top-level `levi` CLI: adds the `creator` command."""
    p = sub.add_parser("creator", help="dating + creator platform (AI reformed / SI gated)")
    _add_common(p)
    csub = p.add_subparsers(dest="creator_cmd", required=True)
    _register_subcommands(csub)


def main(argv=None) -> int:
    top = argparse.ArgumentParser(prog="levi creator")
    top.add_argument("--home", default=None, help="scope storage under this home dir")
    topsub = top.add_subparsers(dest="creator_cmd", required=True)
    _register_subcommands(topsub)
    args = top.parse_args(argv)
    return cmd_creator(args)
