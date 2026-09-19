"""Hermetic tests for levi.social manifest contracts — pure data, no I/O.

These tests lock the domain-model contract in docs/SOCIAL_PLATFORM_DESIGN.md
(AWAITING KEEPER REVIEW). If a test breaks, the contract changed: that needs
the keeper's sign-off, not a quiet fix.
"""

from __future__ import annotations

import pytest

from levi.social import SHELF
from levi.social.manifests import (
    BloodlineRule,
    ManifestBundle,
    Post,
    Profile,
    Realm,
    Season,
    SocialManifestError,
    Squad,
    Thread,
    Vote,
    VoteBook,
)


def _profile(**kw):
    fields = dict(id="ada", handle="ada", display_name="Ada")
    fields.update(kw)
    return Profile(**fields)


# ---- shelf registration -------------------------------------------------


def test_shelf_names_social():
    assert SHELF["name"] == "social"


# ---- Profile ------------------------------------------------------------


def test_profile_valid():
    p = _profile(domains=["personal", "legion"], nature="si")
    assert p.to_dict()["handle"] == "ada"
    assert Profile.from_dict(p.to_dict()).id == "ada"


def test_profile_bad_id():
    with pytest.raises(SocialManifestError):
        _profile(id="not an id!")


def test_profile_handle_must_be_lowercase():
    with pytest.raises(SocialManifestError):
        _profile(handle="Ada")


def test_profile_bad_kind():
    with pytest.raises(SocialManifestError):
        _profile(kind="brand")


def test_profile_mssi_reserved_for_levi():
    with pytest.raises(SocialManifestError):
        _profile(nature="mssi")


def test_profile_levi_may_be_mssi():
    p = Profile(
        id="levi", handle="levi", display_name="Levi", kind="founder", nature="mssi"
    )
    assert p.nature == "mssi"


def test_profile_spotlight_handle():
    with pytest.raises(SocialManifestError):
        _profile(handle="levi")


def test_profile_spotlight_display_name():
    with pytest.raises(SocialManifestError):
        _profile(display_name="I am Levi")


def test_profile_leviathan_word_is_not_levi():
    # "leviathan" is the dynasty brand, not LEVI's face.
    p = _profile(bio="leviathan rising", display_name="Leviathan Watcher")
    assert p.bio == "leviathan rising"


def test_profile_bio_too_long():
    with pytest.raises(SocialManifestError):
        _profile(bio="x" * 501)


def test_profile_needs_a_domain():
    with pytest.raises(SocialManifestError):
        _profile(domains=[])


def test_profile_unknown_domain():
    with pytest.raises(SocialManifestError):
        _profile(domains=["atlantis"])


def test_profile_from_dict_ignores_unknown_keys():
    p = Profile.from_dict({"id": "ada", "handle": "ada", "zzz": 1})
    assert p.id == "ada"


# ---- Realm --------------------------------------------------------------


def test_realm_valid():
    r = Realm(
        id="r1",
        name="Town Hall",
        domain="public",
        visibility="open",
        charter_ref="charter://town-hall/3",
        norms=["no-ads"],
    )
    assert Realm.from_dict(r.to_dict()).domain == "public"


def test_realm_unknown_domain():
    with pytest.raises(SocialManifestError):
        Realm(id="r1", name="X", domain="atlantis")


def test_realm_bad_visibility():
    with pytest.raises(SocialManifestError):
        Realm(id="r1", name="X", domain="public", visibility="everyone")


def test_realm_empty_name():
    with pytest.raises(SocialManifestError):
        Realm(id="r1", name="", domain="public")


# ---- Thread / Post ------------------------------------------------------


def test_thread_valid():
    t = Thread(id="t1", realm_id="r1", title="Hello", author_id="ada")
    assert Thread.from_dict(t.to_dict()).status == "open"


def test_thread_empty_title():
    with pytest.raises(SocialManifestError):
        Thread(id="t1", realm_id="r1", title="", author_id="ada")


def test_thread_bad_status():
    with pytest.raises(SocialManifestError):
        Thread(id="t1", realm_id="r1", title="Hi", author_id="ada", status="pinned")


def test_post_valid_and_tree_ok():
    root = Post(id="p1", thread_id="t1", author_id="ada", body="root")
    reply = Post(id="p2", thread_id="t1", author_id="bob", body="reply", parent_id="p1")
    reply.check_tree({"p1": root, "p2": reply})  # no raise
    assert Post.from_dict(reply.to_dict()).parent_id == "p1"


def test_post_empty_body():
    with pytest.raises(SocialManifestError):
        Post(id="p1", thread_id="t1", author_id="ada", body="")


def test_post_body_too_long():
    with pytest.raises(SocialManifestError):
        Post(id="p1", thread_id="t1", author_id="ada", body="x" * 10001)


def test_post_bad_audience():
    with pytest.raises(SocialManifestError):
        Post(id="p1", thread_id="t1", author_id="ada", body="hi", audience="everyone")


def test_post_missing_parent():
    orphan = Post(id="p9", thread_id="t1", author_id="ada", body="x", parent_id="ghost")
    with pytest.raises(SocialManifestError):
        orphan.check_tree({})


def test_post_parent_wrong_thread():
    other = Post(id="p1", thread_id="t2", author_id="ada", body="root")
    cross = Post(id="p2", thread_id="t1", author_id="bob", body="x", parent_id="p1")
    with pytest.raises(SocialManifestError):
        cross.check_tree({"p1": other})


# ---- Vote / VoteBook ----------------------------------------------------


def test_vote_value_must_be_plus_or_minus_one():
    with pytest.raises(SocialManifestError):
        Vote(post_id="p1", voter_id="ada", value=0)


def test_votebook_add_and_tally():
    book = VoteBook()
    book.add(Vote(post_id="p1", voter_id="ada", value=1), author_id="bob")
    book.add(Vote(post_id="p1", voter_id="cat", value=-1), author_id="bob")
    assert book.tally("p1") == {"up": 1, "down": 1, "net": 0}


def test_votebook_double_vote_refused():
    book = VoteBook()
    book.add(Vote(post_id="p1", voter_id="ada", value=1))
    with pytest.raises(SocialManifestError):
        book.add(Vote(post_id="p1", voter_id="ada", value=-1))


def test_votebook_self_vote_refused():
    book = VoteBook()
    with pytest.raises(SocialManifestError):
        book.add(Vote(post_id="p1", voter_id="ada", value=1), author_id="ada")


def test_votebook_retract_then_revote_ok():
    book = VoteBook()
    book.add(Vote(post_id="p1", voter_id="ada", value=1))
    book.retract("ada", "p1")
    book.add(Vote(post_id="p1", voter_id="ada", value=-1))
    assert book.tally("p1")["net"] == -1
    assert len(book.retractions()) == 1


def test_votebook_retract_missing():
    with pytest.raises(SocialManifestError):
        VoteBook().retract("ada", "p1")


# ---- Squad --------------------------------------------------------------


def test_squad_valid():
    s = Squad(
        id="sq1",
        name="Night Watch",
        purpose="keep the lamps lit",
        seat_profile_id="sq1-seat",
        members=["ada", "bob"],
        mentor="sq0",
    )
    assert Squad.from_dict(s.to_dict()).members == ["ada", "bob"]


def test_squad_empty_members_refused():
    with pytest.raises(SocialManifestError):
        Squad(
            id="sq1", name="Ghosts", purpose="haunt", seat_profile_id="s1", members=[]
        )


def test_squad_spotlight_refused():
    with pytest.raises(SocialManifestError):
        Squad(
            id="sq1",
            name="Levi",
            purpose="be the voice",
            seat_profile_id="s1",
            members=["ada"],
        )


# ---- Season -------------------------------------------------------------


def test_season_valid():
    s = Season(
        id="s202610",
        label="October 2026",
        tier="2",
        roster_slots=3,
        starts_at="2026-10-01T00:00:00+00:00",
        ends_at="2026-11-01T00:00:00+00:00",
    )
    assert Season.from_dict(s.to_dict()).roster_slots == 3


def test_season_must_end_after_start():
    with pytest.raises(SocialManifestError):
        Season(
            id="s1",
            label="X",
            tier="2",
            roster_slots=1,
            starts_at="2026-11-01T00:00:00+00:00",
            ends_at="2026-10-01T00:00:00+00:00",
        )


def test_season_slots_positive():
    with pytest.raises(SocialManifestError):
        Season(
            id="s1",
            label="X",
            tier="2",
            roster_slots=0,
            starts_at="2026-10-01T00:00:00+00:00",
            ends_at="2026-11-01T00:00:00+00:00",
        )


# ---- BloodlineRule ------------------------------------------------------


def test_bloodline_valid():
    b = BloodlineRule(repo_id="commons", prime_id="commons", safety_ceiling="standard")
    assert BloodlineRule.from_dict(b.to_dict()).prime_id == "commons"


def test_bloodline_fork_inherits_ceiling():
    b = BloodlineRule(
        repo_id="commons-fork",
        prime_id="commons",
        parent_id="commons",
        safety_ceiling="standard",
    )
    assert b.parent_id == "commons"


def test_bloodline_override_without_approval_refused():
    with pytest.raises(SocialManifestError):
        BloodlineRule(
            repo_id="r", prime_id="p", safety_ceiling="standard", founder_override=True
        )


def test_bloodline_override_with_approval_ok():
    b = BloodlineRule(
        repo_id="r",
        prime_id="p",
        safety_ceiling="standard",
        founder_override=True,
        founder_approval="cybrus://approval/77",
    )
    assert b.founder_override is True


# ---- ManifestBundle -----------------------------------------------------


def _bundle():
    return ManifestBundle(
        sections={
            "profiles": [_profile().to_dict()],
            "realms": [Realm(id="r1", name="Town Hall", domain="public").to_dict()],
        }
    ).seal()


def test_bundle_seal_verify_roundtrip():
    b = _bundle()
    b.verify()  # no raise
    again = ManifestBundle.from_json(b.to_json())
    again.verify()


def test_bundle_tampered_section_refused():
    b = _bundle()
    b.sections["profiles"][0]["handle"] = "mallory"
    with pytest.raises(SocialManifestError):
        b.verify()


def test_bundle_tampered_manifest_refused():
    b = _bundle()
    b.manifest = "0" * 64
    with pytest.raises(SocialManifestError):
        b.verify()


def test_bundle_wrong_format_refused():
    b = _bundle()
    b.format = "evil-bundle"
    with pytest.raises(SocialManifestError):
        b.verify()
