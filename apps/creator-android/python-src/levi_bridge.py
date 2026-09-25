"""LEVI mega-app bridge — one app, the whole organism.

JSON in/out wrappers over the on-device engines, via Chaquopy:
  - creator.ai.*   : SFW dating + general-audience creator platform (DEFAULT)
  - creator.*      : content publish/gate/list/revoke, subscriptions, safety,
                     pricing (two-track shared layer; track passed per call)
  - creator.si.*   : adult dating + creator platform — GATE-LOCKED behind the
                     Plaiground adult gate (default OFF, minors hard-locked
                     out). The PIN ceremony runs THROUGH the real gate
                     (set_pin / enable_adult_mode / disable_adult_mode) —
                     there is no bypass path in this bridge.
  - voidbox.payments: tier-scaled platform cut (confirmed-delegated
                     table: his tier names, Rex's rates on his word, reversible),
                     Cash App / PayPal plugins.
  - cybrus.*       : on top of everything — money gateway, audit, veil.
  - operators      : Cybrus status, device alerter laws, DemandPulse status,
                     alerts inbox.
  - neighborhood   : NeighborOS surfaces + neighbor nudges.
  - dispatch       : transportation edition — HOS co-pilot, load shortlist.
  - daemons        : daemon colony status.
  - hicomb         : the house code editor — real buffer engine (open/edit/
                     save, undo/redo) over an on-device workspace.
  - legion         : "for we are many" — the umbrella roster: product, packs,
                     operators, hive.
  - systems        : every other major system — the full MASTER_INVENTORY
                     module map, importable on-device or honest about the
                     gate (dynasty never ships: eyes-only; brain/knowledge
                     not on device).

Every function returns a JSON string. The Java side never touches Python
objects directly.

MONEY LAW: Cybrus is the only one ever allowed to handle money. No rail
configured -> every charge is blocked and subscriptions record as
pending_payment with paper=True. The tier-scaled platform cut applies to
paper accounting too (voidbox.payments.tiers — CONFIRMED delegated table:
his tier names, Rex's rates on his word, reversible; every split labeled).
Human-approval mandate (2026-09-22): a charge needs a keeper approval
receipt. The bridge never auto-approves: subscribe returns
approval_required with the resumable id, the keeper taps approve
(approve_money_charge), then the subscribe is retried with the approval
id. No rail -> blocked -> pending_payment, honest throughout.
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Optional

_WORKSPACE: Optional[Path] = None

TRACK_AI = "ai"
TRACK_SI = "si"


def _ws() -> Path:
    if _WORKSPACE is None:
        raise RuntimeError("workspace not set")
    return _WORKSPACE


def _home() -> Optional[Path]:
    return _ws()


def _err(exc: BaseException) -> str:
    return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def _ok(**fields) -> str:
    out = {"ok": True}
    out.update(fields)
    return json.dumps(out, default=str)


def set_workspace(path: str) -> str:
    global _WORKSPACE
    _WORKSPACE = Path(path)
    _WORKSPACE.mkdir(parents=True, exist_ok=True)
    return "true"


def seed_workspace() -> str:
    """Seed a starter creator profile + one public post on first launch."""
    try:
        from levi.creator.ai import creators as ai_creators

        if not ai_creators.list_creators(_home()):
            ai_creators.create_creator(
                "levi", "Levi", "The first creator on this device.", "music", _home()
            )
        return _ok()
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ---------------------------------------------------------------- gate ---


def adult_gate_status() -> str:
    """Read-only adult-gate status. Never enables anything."""
    try:
        from levi.plaiground import gate

        return _ok(status=gate.status(_home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ------------------------------------------------------- AI creators ---


def ai_create_creator(handle: str, display_name: str, bio: str, category: str) -> str:
    try:
        from levi.creator.ai import creators as ai_creators

        return _ok(
            creator=ai_creators.create_creator(handle, display_name, bio, category, _home())
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_list_creators() -> str:
    try:
        from levi.creator.ai import creators as ai_creators

        return _ok(creators=ai_creators.list_creators(_home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_add_tier(creator_handle: str, name: str, price_minor: int, perks_json: str) -> str:
    try:
        from levi.creator.ai import creators as ai_creators

        perks = json.loads(perks_json or "[]")
        return _ok(
            tier=ai_creators.add_tier(creator_handle, name, int(price_minor), perks, _home())
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_list_tiers(creator_handle: str) -> str:
    try:
        from levi.creator.ai import creators as ai_creators

        return _ok(tiers=ai_creators.list_tiers(creator_handle, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_subscribe(
    creator_handle: str,
    tier_id: str,
    subscriber_id: str,
    authorized_by: str,
    approval_id: str = "",
) -> str:
    """Subscribe on the AI track.

    Paper-only: no rail -> pending_payment. Human-approval mandate: the
    first call raises approval_required with a resumable id; the keeper
    approves via approve_money_charge, then this is retried with the
    approval_id. The bridge never auto-approves.
    """
    try:
        from levi.creator.ai import creators as ai_creators

        auth = _auth(authorized_by)
        return _ok(
            subscription=ai_creators.subscribe(
                creator_handle, tier_id, subscriber_id, auth, _home(),
                approval_id=approval_id or None,
            )
        )
    except Exception as exc:  # noqa: BLE001
        aid = _approval_needed(exc)
        if aid is not None:
            return _approval_response(aid, exc)
        return _err(exc)


def ai_post_drop(creator_handle: str, title: str, body: str) -> str:
    try:
        from levi.creator.ai import creators as ai_creators

        return _ok(drop=ai_creators.post_drop(creator_handle, title, body, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_list_drops(creator_handle: str) -> str:
    try:
        from levi.creator.ai import creators as ai_creators

        return _ok(drops=ai_creators.list_drops(creator_handle, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_creator_message(sender: str, recipient: str, body: str) -> str:
    try:
        from levi.creator.ai import creators as ai_creators

        return _ok(message=ai_creators.send_message(sender, recipient, body, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# --------------------------------------------------------- AI dating ---


def ai_dating_create_profile(handle: str, display_name: str, bio: str, interests_json: str) -> str:
    try:
        from levi.creator.ai import dating as ai_dating

        interests = json.loads(interests_json or "[]")
        return _ok(
            profile=ai_dating.create_profile(handle, display_name, bio, interests, _home())
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_dating_list_profiles() -> str:
    try:
        from levi.creator.ai import dating as ai_dating

        return _ok(profiles=ai_dating.list_profiles(_home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_dating_find_matches(handle: str) -> str:
    try:
        from levi.creator.ai import dating as ai_dating

        return _ok(matches=ai_dating.find_matches(handle, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_dating_message(sender: str, recipient: str, body: str) -> str:
    try:
        from levi.creator.ai import dating as ai_dating

        return _ok(message=ai_dating.send_message(sender, recipient, body, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_dating_inbox(handle: str) -> str:
    try:
        from levi.creator.ai import dating as ai_dating

        return _ok(messages=ai_dating.inbox(handle, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ---------------------------------------------------------- AI media ---


def ai_post_media(
    creator_handle: str, kind: str, title: str, filename: str, data_b64: str, gate_json: str
) -> str:
    """gate_json: {"tier_id": ...} or {"grants": [...]} or {} for creator-only."""
    try:
        from levi.creator.ai import media as ai_media

        gate = json.loads(gate_json or "{}")
        return _ok(
            media=ai_media.post_media(
                creator_handle,
                kind,
                title,
                filename,
                data_b64,
                tier_id=gate.get("tier_id"),
                grants=gate.get("grants"),
                home=_home(),
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_list_media(creator_handle: str, user_id: str) -> str:
    try:
        from levi.creator.ai import media as ai_media

        return _ok(media=ai_media.list_media(creator_handle, user_id, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_grant_media_access(media_id: str, creator_handle: str, subscriber_id: str) -> str:
    try:
        from levi.creator.ai import media as ai_media

        return _ok(
            grant=ai_media.grant_access(media_id, creator_handle, subscriber_id, _home())
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_can_view_media(media_id: str, user_id: str) -> str:
    try:
        from levi.creator.ai import media as ai_media

        return _ok(can_view=ai_media.can_view(media_id, user_id, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ---------------------------------------------------------- AI chats ---


def ai_create_chat(creator_handle: str, other_id: str) -> str:
    try:
        from levi.creator.ai import chats as ai_chats

        return _ok(chat=ai_chats.create_chat(creator_handle, other_id, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_create_group(creator_handle: str, name: str, member_ids_json: str) -> str:
    try:
        from levi.creator.ai import chats as ai_chats

        member_ids = json.loads(member_ids_json or "[]")
        return _ok(chat=ai_chats.create_group(creator_handle, name, member_ids, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_send_chat_message(chat_id: str, sender_id: str, body: str) -> str:
    try:
        from levi.creator.ai import chats as ai_chats

        return _ok(message=ai_chats.send_chat_message(chat_id, sender_id, body, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_chat_thread(chat_id: str, user_id: str) -> str:
    try:
        from levi.creator.ai import chats as ai_chats

        return _ok(messages=ai_chats.chat_thread(chat_id, user_id, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ai_list_chats(user_id: str) -> str:
    try:
        from levi.creator.ai import chats as ai_chats

        return _ok(chats=ai_chats.list_chats(user_id, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ------------------------------------------------------------ content ---


def _auth(authorized_by: str):
    from levi.creator.money import MoneyAuthorization

    return MoneyAuthorization(
        authorized_by=authorized_by or "keeper",
        plan_id="",
        operation="charge",
        note="android",
    )


def _approval_needed(exc: BaseException) -> Optional[str]:
    """Extract the resumable approval id from a MoneyApprovalRequired."""
    if type(exc).__name__ == "MoneyApprovalRequired":
        # str(exc) carries the id; the exception also exposes .approval_id
        # on the sibling implementation — prefer the attribute.
        return getattr(exc, "approval_id", None) or getattr(exc, "entry_id", None)
    return None


def _approval_response(approval_id: Optional[str], exc: BaseException) -> str:
    return json.dumps(
        {
            "ok": False,
            "approval_required": True,
            "approval_id": approval_id,
            "error": "%s: %s" % (type(exc).__name__, exc),
            "instruction": (
                "The keeper must approve this charge first: call "
                "approve_money_charge with the approval_id above, then "
                "retry the subscribe with the same approval_id. "
                "No rail is configured, so the approved charge will be "
                "blocked and recorded as pending_payment (paper-only)."
            ),
        }
    )


def approve_money_charge(approval_id: str) -> str:
    """Keeper approves a pending money charge (the human gate).

    This is the explicit second tap — the bridge never auto-approves.
    Approval is recorded in the Cybrus approval store as by='keeper'.
    """
    try:
        from levi.cybrus.gateway import CybrusGateway

        gw = CybrusGateway()
        return _ok(approval=gw.approve(approval_id, by="keeper"))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def publish_content(
    creator_id: str,
    title: str,
    description: str,
    kind: str,
    track: str,
    gate_json: str,
) -> str:
    """gate_json: {"tier_id": ...} | {"grants": [...]} | {"public": true}.

    track="si" is gate-locked: require_adult raises when the adult gate is
    off, and the bridge returns ok:false. The AI track is the default.
    """
    try:
        from levi.creator import content as content_mod

        if track not in (TRACK_AI, TRACK_SI):
            raise ValueError("track must be 'ai' or 'si'")
        gate = json.loads(gate_json or "{}")
        return _ok(
            item=content_mod.publish(
                creator_id,
                title,
                description,
                kind,
                track,
                _home(),
                tier_id=gate.get("tier_id"),
                grants=gate.get("grants"),
                public=bool(gate.get("public")),
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def list_content(creator_id: str, track: str) -> str:
    try:
        from levi.creator import content as content_mod

        return _ok(items=content_mod.list_content(creator_id, track, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def list_for_viewer(creator_id: str, viewer_id: str, track: str) -> str:
    """Metadata-only for viewers who are not entitled (gating honesty)."""
    try:
        from levi.creator import content as content_mod

        return _ok(items=content_mod.list_for_viewer(creator_id, viewer_id, track, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def get_content_item(content_id: str, track: str) -> str:
    try:
        from levi.creator import content as content_mod

        return _ok(item=content_mod.get_item(content_id, track, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def revoke_content(content_id: str, creator_id: str, track: str) -> str:
    try:
        from levi.creator import content as content_mod

        return _ok(item=content_mod.revoke(content_id, creator_id, track, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def grant_content(content_id: str, creator_id: str, subscriber_id: str, track: str) -> str:
    try:
        from levi.creator import content as content_mod

        return _ok(
            grant=content_mod.grant(content_id, creator_id, subscriber_id, track, _home())
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ------------------------------------------------------- subscriptions ---


def create_creator_profile(handle: str, display_name: str, bio: str, payout_reference: str, track: str) -> str:
    try:
        from levi.creator import subscriptions as subs

        return _ok(
            profile=subs.create_profile(handle, display_name, bio, payout_reference, track, _home())
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def list_creator_profiles(track: str) -> str:
    try:
        from levi.creator import subscriptions as subs

        return _ok(profiles=subs.list_profiles(track, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def add_subscription_tier(
    creator_id: str, name: str, price_minor: int, period: str, track: str, perks_json: str
) -> str:
    try:
        from levi.creator import subscriptions as subs

        perks = json.loads(perks_json or "[]")
        return _ok(
            tier=subs.add_tier(
                creator_id, name, int(price_minor), period, track, None, perks, _home()
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def list_subscription_tiers(creator_id: str, track: str) -> str:
    try:
        from levi.creator import subscriptions as subs

        return _ok(tiers=subs.list_tiers(creator_id, track, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def subscribe_to_tier(
    creator_id: str, tier_id: str, subscriber_id: str, authorized_by: str, track: str,
    approval_id: str = "",
) -> str:
    """Paper-only: no rail -> subscription records as pending_payment.

    Human-approval mandate: first call returns approval_required; the
    keeper approves via approve_money_charge, then retries with the id.
    """
    try:
        from levi.creator import subscriptions as subs

        return _ok(
            subscription=subs.subscribe(
                creator_id, tier_id, subscriber_id, _auth(authorized_by), track, _home(),
                approval_id=approval_id or None,
            )
        )
    except Exception as exc:  # noqa: BLE001
        aid = _approval_needed(exc)
        if aid is not None:
            return _approval_response(aid, exc)
        return _err(exc)


def unsubscribe_from_tier(subscription_id: str, subscriber_id: str, track: str) -> str:
    try:
        from levi.creator import subscriptions as subs

        return _ok(
            subscription=subs.unsubscribe(subscription_id, subscriber_id, track, _home())
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def access_level(subscriber_id: str, creator_id: str, track: str) -> str:
    try:
        from levi.creator import subscriptions as subs

        return _ok(level=subs.access_level(subscriber_id, creator_id, track, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def creator_balance(creator_id: str, track: str) -> str:
    try:
        from levi.creator import subscriptions as subs

        return _ok(balance=subs.creator_balance(creator_id, track, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def list_payouts(creator_id: str, track: str) -> str:
    try:
        from levi.creator import subscriptions as subs

        return _ok(payouts=subs.list_payouts(creator_id, track, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def tier_suggestions() -> str:
    try:
        from levi.creator import subscriptions as subs

        return _ok(suggestions=subs.creator_tier_suggestions())
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# --------------------------------------------------------------- safety ---


def safety_add_contact(user_id: str, name: str, contact_ref: str, track: str) -> str:
    try:
        from levi.creator import safety as safety_mod

        return _ok(contact=safety_mod.add_contact(user_id, name, contact_ref, track, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def safety_list_contacts(user_id: str, track: str) -> str:
    try:
        from levi.creator import safety as safety_mod

        return _ok(contacts=safety_mod.list_contacts(user_id, track, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def safety_create_plan(
    user_id: str,
    who: str,
    where: str,
    when_at: str,
    check_in_minutes: int,
    contact_ids_json: str,
    track: str,
    disclosure: str,
) -> str:
    try:
        from levi.creator import safety as safety_mod

        contact_ids = json.loads(contact_ids_json or "[]")
        return _ok(
            plan=safety_mod.create_plan(
                user_id,
                who,
                where,
                when_at,
                int(check_in_minutes),
                contact_ids,
                track,
                disclosure or "",
                _home(),
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def safety_plan_status(plan_id: str, user_id: str, track: str) -> str:
    try:
        from levi.creator import safety as safety_mod

        return _ok(status=safety_mod.plan_status(plan_id, user_id, track, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def safety_check_in(plan_id: str, user_id: str, track: str) -> str:
    try:
        from levi.creator import safety as safety_mod

        return _ok(result=safety_mod.check_in(plan_id, user_id, track, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def safety_end_plan(plan_id: str, user_id: str, track: str) -> str:
    try:
        from levi.creator import safety as safety_mod

        return _ok(result=safety_mod.end_plan(plan_id, user_id, track, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def safety_run_escalation_check(track: str) -> str:
    try:
        from levi.creator import safety as safety_mod

        return _ok(escalations=safety_mod.run_escalation_check(track, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# -------------------------------------------------------------- pricing ---


def _tier_to_dict(t) -> dict:
    return {
        "name": t.name,
        "price_minor": t.price_minor,
        "period": t.period,
        "track": t.track,
        "receipt": t.receipt,
    }


def pricing_tables() -> str:
    try:
        from levi.creator import pricing as pricing_mod

        return _ok(
            dating=[_tier_to_dict(t) for t in pricing_mod.build_dating_schedule()],
            creator=[_tier_to_dict(t) for t in pricing_mod.build_creator_schedule()],
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def pricing_suggested_tiers(service: str) -> str:
    """service: 'dating' or 'creator' (the pricing module's vocabulary)."""
    try:
        from levi.creator import pricing as pricing_mod

        if service not in ("dating", "creator"):
            raise ValueError("service must be 'dating' or 'creator'")
        return _ok(suggestions=pricing_mod.suggested_tiers(service))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def pricing_split(amount_minor: int) -> str:
    """Platform fee vs creator share for a charge, in minor units."""
    try:
        from levi.creator import pricing as pricing_mod

        amount = int(amount_minor)
        return _ok(
            platform_fee=pricing_mod.platform_fee(amount),
            creator_share=pricing_mod.creator_share(amount),
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ---------------------------------------------------- SI (gate-locked) ---


def si_create_profile(handle: str, display_name: str, bio: str) -> str:
    """Gate-locked: raises GateLockedError while the adult gate is off."""
    try:
        from levi.creator.si import profiles as si_profiles

        return _ok(profile=si_profiles.create_profile(handle, display_name, bio, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def si_list_profiles() -> str:
    """Gate-locked: raises GateLockedError while the adult gate is off."""
    try:
        from levi.creator.si import profiles as si_profiles

        return _ok(profiles=si_profiles.list_profiles(_home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def si_subscribe(
    creator_handle: str, tier_id: str, subscriber_id: str, authorized_by: str,
    approval_id: str = "",
) -> str:
    """Gate-locked: raises GateLockedError while the adult gate is off.

    Money: same two-step keeper approval as the AI track; paper-only.
    """
    try:
        from levi.creator.si import subscriptions as si_subs

        return _ok(
            subscription=si_subs.subscribe(
                creator_handle, tier_id, subscriber_id, _auth(authorized_by), _home(),
                approval_id=approval_id or None,
            )
        )
    except Exception as exc:  # noqa: BLE001
        aid = _approval_needed(exc)
        if aid is not None:
            return _approval_response(aid, exc)
        return _err(exc)


def si_list_subscriptions(subscriber_id: str) -> str:
    """Gate-locked: raises GateLockedError while the adult gate is off."""
    try:
        from levi.creator.si import subscriptions as si_subs

        return _ok(subscriptions=si_subs.list_subscriptions(subscriber_id, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def debug_trace() -> str:
    return traceback.format_exc()


# ------------------------------------------- tier-cut (paper accounting) ---


def money_tier_table() -> str:
    """The platform-cut table, as it stands in the repo.

    Tier names are Chauncey's (FREE/PRO/HYBRID/ELITE). The rates were
    confirmed by DELEGATION — Rex's numbers on Chauncey's word
    ("figure it out, just told you less than competition"), reversible,
    stamped delegated rather than direct. He can change any rate in
    one edit via confirm_table().
    """
    try:
        from levi.voidbox.payments import tiers

        return _ok(
            provisional=tiers.is_provisional(),
            delegated=tiers.is_delegated(),
            confirmation=tiers.confirmation(),
            table_version=tiers.TABLE_VERSION,
            rates=dict(tiers.TIER_RATES),
            laws=[{"id": i, "text": t} for i, t in tiers.LAWS],
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def money_tier_cut(total_cents: int, tier: str) -> str:
    """Paper accounting of the founder commission for a payment.

    Uses the voidbox tier table (confirmed-delegated). Unknown tiers
    fail closed. No money moves — this is accounting only.
    """
    try:
        from levi.voidbox.payments import tiers

        split = tiers.price_split(int(total_cents), tier)
        return _ok(
            total_cents=split.total_cents,
            platform_cents=split.platform_cents,
            creator_cents=split.creator_cents,
            tier=split.tier,
            rate_bps=split.rate_bps,
            provisional=tiers.is_provisional(),
            delegated=tiers.is_delegated(),
            note="paper accounting only — no rail, no money moved",
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def money_payout_link(plugin: str, handle: str, amount_cents: int) -> str:
    """Build a payout request link (Cash App / PayPal plugin).

    Produces the link only — no money moves, no network call.
    """
    try:
        from levi.voidbox.payments import plugins

        p = plugins.get_plugin(plugin)
        return _ok(
            plugin=p.name,
            link=p.build_request_link(handle, int(amount_cents)),
            note="link only — paper, no charge executed",
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# --------------------------------------------- plaiground PIN ceremony ---


def plaiground_has_pin() -> str:
    try:
        from levi.plaiground import gate

        return _ok(has_pin=gate.has_pin(_home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def plaiground_set_pin(pin: str) -> str:
    """Set the Plaiground PIN. Stored as PBKDF2 hash, never plaintext.

    Minor-gated: refuses if a minor indicator is present.
    """
    try:
        from levi.plaiground import gate

        gate.set_pin(pin, _home())
        return _ok(set=True)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def plaiground_enable(confirmation: str, pin: str) -> str:
    """Enable adult mode: exact confirmation phrase + correct PIN.

    The gate proves affirmative owner opt-in ON THIS MACHINE — not age.
    Enabling with no PIN set, a wrong PIN, or a wrong phrase refuses.
    """
    try:
        from levi.plaiground import gate

        gate.enable_adult_mode(confirmation, pin, _home())
        return _ok(enabled=True)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def plaiground_disable() -> str:
    """Disable adult mode. Always allowed, no PIN needed (fail-closed)."""
    try:
        from levi.plaiground import gate

        return _ok(disabled=gate.disable_adult_mode(_home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def plaiground_confirmation_phrase() -> str:
    """The exact phrase the keeper must type to enable adult mode."""
    try:
        from levi.plaiground.gate import CONFIRMATION_PHRASE

        return _ok(phrase=CONFIRMATION_PHRASE)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# --------------------------------------- SI classifieds (gate-locked) ---


def si_post_listing(poster_id: str, headline: str, seeking: str, terms: str) -> str:
    """Post a skip-the-games-style adult listing. Gate-locked, sealed."""
    try:
        from levi.creator.si import dating as si_dating

        return _ok(
            listing=si_dating.post_listing(poster_id, headline, seeking, terms, _home())
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def si_search_listings(query: str) -> str:
    """Search listings. Gate-locked; public view is redacted (no poster id)."""
    try:
        from levi.creator.si import privacy as si_privacy

        return _ok(listings=si_privacy.public_search(query, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def si_respond_listing(listing_id: str, responder_id: str, message: str, reveal: bool) -> str:
    """Respond to a listing. Gate-locked; disclosure gate honored."""
    try:
        from levi.creator.si import privacy as si_privacy

        # Never trust truthiness of a passed string: "false" must mean False.
        reveal_flag = (
            reveal
            if isinstance(reveal, bool)
            else str(reveal).strip().lower() in ("1", "true", "yes", "y")
        )
        return _ok(
            response=si_privacy.respond(
                listing_id, responder_id, message, _home(),
                reveal_profile=reveal_flag,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def si_deactivate_listing(listing_id: str) -> str:
    """Deactivate your own listing. Gate-locked."""
    try:
        from levi.creator.si import dating as si_dating

        return _ok(listing=si_dating.deactivate(listing_id, _home()))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ------------------------------------------------------------ operators ---


def ops_cybrus_status() -> str:
    """Cybrus on top: money gateway law + rail posture, audit tail."""
    try:
        from levi.cybrus import money as cyb_money

        st = cyb_money.status()
        try:
            audit = cyb_money.MoneyGateway().audit_log(limit=10)
        except Exception:
            audit = []
        return _ok(gateway=st, audit_tail=audit)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ops_alerter_laws() -> str:
    """Device alerter law check (the 8 laws). Read-only."""
    try:
        from levi.device import alerter

        return _ok(**alerter.check_laws())
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ops_alerts_inbox() -> str:
    """Pending alerts from all alerter sources. Read-only (no send)."""
    try:
        from levi.device import alerter

        items = alerter.collect_new()
        return _ok(
            count=len(items),
            alerts=[
                {"source": i.get("source"), "title": i.get("title"),
                 "body": (i.get("body") or "")[:280]}
                for i in items
            ],
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def ops_demand_status() -> str:
    """DemandPulse watcher status (last polls per channel)."""
    try:
        from levi.demand import watcher

        return _ok(status=watcher.status())
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ---------------------------------------------------------- neighborhood ---


def hood_status() -> str:
    """NeighborOS status: what's live, what's gated."""
    try:
        from levi import neighboros

        brief_fns = [x for x in dir(neighboros) if not x.startswith("_")]
        return _ok(
            module="neighboros",
            exports=brief_fns[:20],
            note="NeighborPay / live money deferred — business/legal call (his).",
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def hood_nudges() -> str:
    """Neighbor nudges from the local store (same source the alerter reads)."""
    try:
        from levi.device import alerter

        alerter._register_defaults()
        items = alerter._read_neighbor()
        return _ok(
            count=len(items),
            nudges=[
                {"title": i.get("title"), "body": (i.get("body") or "")[:280]}
                for i in items
            ],
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def hood_post_job(title: str, detail: str, owner_id: str) -> str:
    """Post a neighborhood job (photo job posts, estimates)."""
    try:
        from levi.neighbor import post as hood_post

        fns = [x for x in dir(hood_post) if not x.startswith("_")]
        if hasattr(hood_post, "post_job"):
            return _ok(job=hood_post.post_job(title, detail, owner_id, _home()))
        return _err(RuntimeError("post_job not available; exports: %s" % fns[:10]))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# -------------------------------------------------------------- dispatch ---


def dispatch_hos_check(
    drive_hrs: float,
    onduty_hrs: float,
    drive_remaining_hrs: float = 8.0,
    shift_remaining_hrs: float = 10.0,
) -> str:
    """HOS co-pilot: check a plan against hours-of-service rules.

    The clock models remaining hours on each HOS clock (as read from the
    ELD); the plan states what it consumes. Honest scope: fixture clock
    unless wired to a real ELD source.
    """
    try:
        from datetime import datetime, timezone

        from levi.editions.transport.hos_copilot import clocks, rules

        clock = clocks.DriverClock(
            driver_id="keeper",
            captured_at=datetime.now(timezone.utc),
            drive_remaining_hrs=float(drive_remaining_hrs),
            shift_remaining_hrs=float(shift_remaining_hrs),
            break_remaining_hrs=8.0,
            cycle_remaining_hrs=60.0,
            source="fixture",
        )
        usage = rules.PlanUsage(
            drive_hrs=float(drive_hrs),
            onduty_hrs=float(onduty_hrs),
            drive_segments=(float(drive_hrs),),
            segment_limits=(8.0,),
        )
        violations = rules.check_plan(clock, usage)
        return _ok(
            violations=[{"code": v.code, "message": v.message} for v in violations],
            clean=len(violations) == 0,
            clock_source="fixture",
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def dispatch_refusal_check(text: str) -> str:
    """Check a dispatch request against refusal rules."""
    try:
        from levi.editions.transport.hos_copilot import refusals

        r = refusals.check_request(text)
        return _ok(refused=r is not None, refusal=str(r) if r else None)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def dispatch_shortlist_example() -> str:
    """What the load shortlist needs (honest: needs real load offers)."""
    try:
        from levi.editions.transport.hos_copilot import shortlist

        return _ok(
            needs="a list of LoadOffer dicts (origin, destination, pay_cents, miles)",
            note="shortlist.build_shortlist ranks real offers — no sample data ships; wire your offers in.",
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# --------------------------------------------------------------- daemons ---


def daemon_colony() -> str:
    """Daemon colony roster: every daemon module, importable or not."""
    import importlib
    import pkgutil

    try:
        import levi.daemon as colony

        names = sorted(
            m.name for m in pkgutil.iter_modules(colony.__path__)
            if not m.name.startswith("_")
        )
        live = []
        for n in names:
            try:
                importlib.import_module("levi.daemon." + n)
                live.append({"daemon": n, "importable": True})
            except Exception as e:  # noqa: BLE001
                live.append({"daemon": n, "importable": False,
                             "error": "%s: %s" % (type(e).__name__, str(e)[:120])})
        return _ok(count=len(live), daemons=live)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ------------------------------------------------- hicomb (code editor) ---


def _hicomb_base() -> Path:
    base = _ws() / "hicomb"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _hicomb_safe(relpath: str) -> Path:
    base = _hicomb_base().resolve()
    target = (base / (relpath or "")).resolve()
    if target != base and base not in target.parents:
        raise ValueError("path escapes the hicomb workspace")
    return target


def hicomb_status() -> str:
    """Hicomb on-device surface: the real buffer engine + workspace stats."""
    try:
        from levi.hicomb import buffer as buf_engine

        base = _hicomb_base()
        files = [p for p in base.rglob("*") if p.is_file()]
        return _ok(
            engine="levi.hicomb.buffer",
            buffer_class=buf_engine.Buffer.__name__,
            workspace=str(base),
            files=len(files),
            note="The house editor surface: open/edit/save with undo/redo, "
                 "driven by the real Hicomb buffer engine (stdlib-only, offline).",
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def hicomb_list_files(subdir: str = "") -> str:
    """List files under the hicomb workspace (relative paths)."""
    try:
        target = _hicomb_safe(subdir)
        if not target.is_dir():
            return _ok(files=[])
        out = []
        for p in sorted(target.rglob("*")):
            if p.is_file():
                out.append({
                    "path": p.relative_to(_hicomb_base()).as_posix(),
                    "bytes": p.stat().st_size,
                })
        return _ok(count=len(out), files=out[:500])
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def hicomb_read(relpath: str) -> str:
    """Read a workspace file through the real Hicomb buffer engine."""
    try:
        from levi.hicomb import buffer as buf_engine

        target = _hicomb_safe(relpath)
        if not target.is_file():
            return _err(FileNotFoundError(relpath))
        buf = buf_engine.Buffer.open(str(target))
        return _ok(path=relpath, lines=buf.line_count,
                   large=buf.is_large, text=buf.get_text())
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def hicomb_write(relpath: str, content: str) -> str:
    """Write a workspace file through the real Hicomb buffer engine."""
    try:
        from levi.hicomb import buffer as buf_engine

        target = _hicomb_safe(relpath)
        if target.suffix not in (".py", ".md", ".txt", ".json", ".js", ".ts",
                                 ".html", ".css", ".sh", ".yaml", ".yml"):
            return _err(ValueError("refusing to write that file type on-device"))
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            buf = buf_engine.Buffer.open(str(target))
        else:
            buf = buf_engine.Buffer("")
        buf.set_text(content or "")
        saved = buf.save(str(target))
        return _ok(path=relpath, saved=saved, lines=buf.line_count)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ------------------------------------------------- legion (the umbrella) ---


def legion_status() -> str:
    """Legion — 'for we are many': the umbrella over every agent family."""
    try:
        from levi import legion
        from levi.legion import packs, team

        return _ok(
            product=legion.PRODUCT_FULL_NAME,
            business_types=list(team.BUSINESS_TYPES),
            packs=packs.pack_names(),
            note="One face the customer talks to, the legion behind it. "
                 "Money paths are paper-only (Cybrus fail-closed).",
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def legion_packs() -> str:
    """Specialist add-on packs (restaurant, salon, shop, generic)."""
    try:
        from levi.legion import packs

        out = []
        for name in packs.pack_names():
            try:
                out.append({"pack": name, "detail": packs.get_pack(name)})
            except Exception as e:  # noqa: BLE001
                out.append({"pack": name, "error": "%s: %s" % (type(e).__name__, e)})
        return _ok(count=len(out), packs=out)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def legion_operators() -> str:
    """Wave-1 service-operator personas (Wren, Sidewinder) — the public identities."""
    try:
        import importlib
        import pkgutil

        import levi.legion.operators as ops_pkg

        names = sorted(
            m.name for m in pkgutil.iter_modules(ops_pkg.__path__)
            if not m.name.startswith("_")
        )
        live = []
        for n in names:
            try:
                mod = importlib.import_module("levi.legion.operators." + n)
                doc = (mod.__doc__ or "").strip().splitlines()
                live.append({"operator": n, "importable": True,
                             "blurb": doc[0] if doc else ""})
            except Exception as e:  # noqa: BLE001
                live.append({"operator": n, "importable": False,
                             "error": "%s: %s" % (type(e).__name__, str(e)[:120])})
        try:
            from levi import hive
            hive_ids = hive.known_ids()
            hive_note = "hive known_ids: %d" % len(hive_ids)
        except Exception as e:  # noqa: BLE001
            hive_note = "hive unreadable: %s" % type(e).__name__
        return _ok(count=len(live), operators=live, hive=hive_note)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ------------------------------------------------- systems (the whole map) ---

try:
    from levi_systems_registry import NOT_SHIPPED, SYSTEM_REGISTRY
except ImportError:  # pragma: no cover — test loader path
    from pathlib import Path as _P
    import sys as _sys

    _sys.path.insert(0, str(_P(__file__).resolve().parent))
    from levi_systems_registry import NOT_SHIPPED, SYSTEM_REGISTRY


def _probe_system(name: str, blurb: str) -> dict:
    import importlib

    if name in NOT_SHIPPED:
        return {"system": name, "on_device": False,
                "detail": "%s | not shipped: %s" % (blurb, NOT_SHIPPED[name])}
    try:
        mod = importlib.import_module("levi." + name)
        detail = blurb
        status_fn = getattr(mod, "status", None)
        if callable(status_fn):
            try:
                st = status_fn()
                detail = "%s | status: %s" % (blurb, str(st)[:200])
            except Exception as e:  # noqa: BLE001
                detail = "%s | status() raised %s" % (blurb, type(e).__name__)
        return {"system": name, "on_device": True, "detail": detail}
    except Exception as e:  # noqa: BLE001
        return {"system": name, "on_device": False,
                "detail": "%s | gated: %s: %s" % (blurb, type(e).__name__,
                                                  str(e)[:120])}


def systems_status() -> str:
    """Every major system: the full inventory map, importable on-device or
    honest about the gate. Generated from docs/MASTER_INVENTORY.md."""
    out = [_probe_system(name, blurb) for name, blurb in SYSTEM_REGISTRY]
    live = sum(1 for s in out if s["on_device"])
    return _ok(count=len(out), live=live, systems=out)


def system_detail(name: str) -> str:
    """Deep probe of one system: blurb, import state, file location."""
    import importlib

    blurb = next((b for n, b in SYSTEM_REGISTRY if n == name), None)
    if blurb is None:
        return _err(ValueError("unknown system: %s" % name))
    probed = _probe_system(name, blurb)
    if probed["on_device"]:
        try:
            mod = importlib.import_module("levi." + name)
            probed["module_file"] = str(getattr(mod, "__file__", ""))[:200]
            probed["exports"] = [x for x in dir(mod) if not x.startswith("_")][:40]
        except Exception:  # noqa: BLE001
            pass
    return _ok(**probed)
