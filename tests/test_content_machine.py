"""Hermetic tests for the LEVI-native content machine.

No network, no HOME writes, no randomness: every assertion is
deterministic. All example data is synthetic.
"""

import pytest

from levi.king.content_machine import (
    BANNED_OPENERS,
    HOOK_PATTERNS,
    PLATFORM_SPECS,
    ContentFramework,
    HookFormula,
    Platform,
    build_instagram_post,
    build_linkedin_post,
    build_newsletter,
    build_x_thread,
    format_for_platform,
    parse_hook_formula,
    parse_platform,
    platform_spec,
    render_hook,
    validate_content,
    validate_hook,
    validate_length,
)


def test_platform_specs_cover_all_platforms():
    assert set(PLATFORM_SPECS) == set(Platform)
    for spec in PLATFORM_SPECS.values():
        assert spec.name
        assert spec.hashtag_placement in ("start", "end", "none")


def test_parse_platform_aliases():
    assert parse_platform("linkedin") is Platform.LINKEDIN
    assert parse_platform("Twitter") is Platform.X
    assert parse_platform("instagram-feed") is Platform.INSTAGRAM_FEED
    with pytest.raises(ValueError):
        parse_platform("myspace")


def test_parse_platform_rejects_non_string():
    with pytest.raises(ValueError):
        parse_platform(None)  # type: ignore[arg-type]


def test_platform_spec_rejects_non_platform():
    with pytest.raises(ValueError):
        platform_spec("linkedin")  # type: ignore[arg-type]


def test_validate_length_flags_over_limit():
    report = validate_length("x" * 300, Platform.X)
    assert report["valid"] is False
    assert report["char_count"] == 300
    assert any("exceeds" in w for w in report["warnings"])


def test_validate_length_warns_on_fold():
    report = validate_length("x" * 300, Platform.LINKEDIN)
    assert report["valid"] is True  # under 3000
    assert any("fold" in w or "truncat" in w for w in report["warnings"])


def test_validate_length_clean_for_short():
    report = validate_length("short post", Platform.X)
    assert report["valid"] is True
    assert report["warnings"] == []


def test_validate_length_rejects_non_string():
    with pytest.raises(ValueError):
        validate_length(123, Platform.X)  # type: ignore[arg-type]


def test_hook_patterns_have_slots_and_why():
    for formula, pattern in HOOK_PATTERNS.items():
        assert isinstance(formula, HookFormula)
        assert pattern.template and pattern.why
        for slot in pattern.slots:
            assert "{" + slot + "}" in pattern.template


def test_render_hook_contrarian():
    out = render_hook(HookFormula.CONTRARIAN, {"claim": "rest is laziness"})
    assert out["hook"] == (
        "Conventional wisdom says rest is laziness. The data says otherwise."
    )
    assert out["why"]
    assert out["hook_check"]["valid"] is True


def test_render_hook_missing_slot_raises():
    with pytest.raises(ValueError, match="needs slots"):
        render_hook(HookFormula.CONTRARIAN, {})


def test_render_hook_rejects_non_dict_variables():
    with pytest.raises(ValueError):
        render_hook(HookFormula.PERMISSION, "oops")  # type: ignore[arg-type]


def test_parse_hook_formula():
    assert parse_hook_formula("curiosity_gap") is HookFormula.CURIOSITY_GAP
    assert parse_hook_formula("Negative Hook") is HookFormula.NEGATIVE_HOOK
    with pytest.raises(ValueError):
        parse_hook_formula("mystery")


def test_validate_hook_banned_opener():
    report = validate_hook("I'm excited to share my morning routine")
    assert report["valid"] is False
    assert any("banned opener" in i for i in report["issues"])


def test_validate_hook_too_short():
    report = validate_hook("Hi.")
    assert report["valid"] is False


def test_validate_hook_clean():
    report = validate_hook("Seven quiet habits that compound into deep work.")
    assert report["valid"] is True
    assert report["issues"] == []


def test_banned_openers_are_lowercase_prefixes():
    for opener in BANNED_OPENERS:
        assert opener == opener.lower()


def test_build_linkedin_post_structure():
    post = build_linkedin_post(
        "A hook about focus.",
        "Body with the insight.",
        "Follow for more.",
        hashtags=["focus", "deepwork"],
    )
    assert post.startswith("A hook about focus.")
    assert "Body with the insight." in post
    assert post.rstrip().endswith("#deepwork")
    assert "#focus" in post


def test_build_x_thread_numbering_and_limit():
    thread = build_x_thread(["First point here.", "Second point here."])
    assert thread.startswith("1/2 First point here.")
    assert "2/2 Second point here." in thread
    with pytest.raises(ValueError, match="exceeds"):
        build_x_thread(["x" * 281])
    with pytest.raises(ValueError, match="at least one"):
        build_x_thread([])


def test_build_instagram_post_bullets():
    post = build_instagram_post(
        "Hook line.", ["point one", "point two"], "CTA here.", ["tag"]
    )
    assert "• point one" in post
    assert "• point two" in post
    assert post.rstrip().endswith("#tag")


def test_build_newsletter_subject_bounds():
    built = build_newsletter("A reasonable subject line here", "Hook.", "Body.", "CTA.")
    assert built["subject"] == "A reasonable subject line here"
    with pytest.raises(ValueError, match="subject"):
        build_newsletter("x", "Hook.", "Body.", "CTA.")
    with pytest.raises(ValueError, match="subject"):
        build_newsletter("x" * 79, "Hook.", "Body.", "CTA.")


def test_format_for_platform_x_and_validate():
    result = format_for_platform(Platform.X, posts=["a" * 100, "b" * 100])
    assert result["content"].startswith("1/2 ")
    assert result["validation"]["platform"] == "x"
    assert result["validation"]["valid"] is True


def test_format_for_platform_linkedin_validation():
    result = format_for_platform(
        Platform.LINKEDIN,
        hook="Hook.",
        body="Body.",
        cta="CTA.",
        hashtags=["a", "b", "c", "d", "e", "f", "g"],
    )
    # budget is 5; 7 tags supplied -> trimmed to budget, still valid
    assert result["content"].count("#") == 5
    assert result["validation"]["valid"] is True


def test_format_for_platform_x_needs_posts():
    with pytest.raises(ValueError, match="posts"):
        format_for_platform(Platform.X, hook="nope")


def test_validate_content_rejects_non_string():
    with pytest.raises(ValueError):
        validate_content(None, Platform.X)  # type: ignore[arg-type]


def test_content_frameworks_listed():
    assert {f.value for f in ContentFramework} == {"pas", "bab", "aida", "slap"}


def test_content_skills_registered():
    from levi.skill.registry import SkillRegistry, SkillRisk

    reg = SkillRegistry()
    for skill_id in (
        "social_content_format",
        "social_hook_render",
        "social_content_validate",
    ):
        skill = reg.get(skill_id)
        assert skill is not None, skill_id
        assert skill.category == "social"
        assert skill.risk_level == SkillRisk.INFO


def test_skill_format_handler_end_to_end():
    from levi.skill.registry import SkillRegistry

    reg = SkillRegistry()
    out = reg.invoke(
        "social_content_format",
        {
            "platform": "linkedin",
            "hook": "A hook about focus.",
            "body": "Body text.",
            "cta": "Follow along.",
            "hashtags": ["focus"],
        },
    )
    assert "[linkedin]" in out
    assert "A hook about focus." in out
    assert "#focus" in out


def test_skill_hook_handler_end_to_end():
    from levi.skill.registry import SkillRegistry

    reg = SkillRegistry()
    out = reg.invoke(
        "social_hook_render",
        {"formula": "permission", "variables": {"take": "meetings are optional"}},
    )
    assert "An unpopular take: meetings are optional." in out


def test_skill_validate_handler_bad_platform():
    from levi.skill.registry import SkillRegistry

    reg = SkillRegistry()
    out = reg.invoke("social_content_validate", {"platform": "nope", "content": "hi"})
    assert "failed" in out
