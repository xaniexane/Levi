"""LEVI-native content machine — platform-aware social content helpers.

Content generation only; NEVER the network. Fits the King control plane:
King remains the orchestration layer (blueprint §4) and this module is one
of the content utilities it can call on. Sanitization of markdown into
captions lives in :mod:`levi.king.social`; this module adds platform
specs (limits, truncation, hashtag budgets), hook-formula rendering, and
structured content builders (posts, threads) plus validators.

Honest contract
---------------
* Everything here is local string assembly — no model, no API, no claims
  about reach or engagement.
* Platform limits are documented public limits (2026); they drift, so
  :func:`platform_spec` is data, not gospel. Validation *warns* rather
  than pretending certainty about feed rendering.
* Hook formulas are rhetorical patterns, not guarantees. The rationale
  notes say *why the pattern exists*, never that it will perform.

Origin note: the *concept* (platform specs + hook formulas + validators)
was surveyed from an external source repo during a source-sync port and
**rewritten from scratch** into LEVI-native code. No source text was
copied; see docs/SOURCE_SYNC_PROTOCOL.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Platform(Enum):
    """Supported publishing platforms."""

    LINKEDIN = "linkedin"
    X = "x"
    INSTAGRAM_FEED = "instagram_feed"
    INSTAGRAM_STORIES = "instagram_stories"
    TIKTOK = "tiktok"
    NEWSLETTER = "newsletter"


class HookFormula(Enum):
    """Rhetorical hook patterns. Patterns, not promises."""

    CONTRARIAN = "contrarian"
    CURIOSITY_GAP = "curiosity_gap"
    SPECIFICITY_SIGNAL = "specificity_signal"
    NEGATIVE_HOOK = "negative_hook"
    CALLOUT = "callout"
    SLIPPERY_SLOPE = "slippery_slope"
    PERMISSION = "permission"


class ContentFramework(Enum):
    """Long-form structural frameworks (body composition)."""

    PAS = "pas"  # Problem → Agitate → Solve
    BAB = "bab"  # Before → After → Bridge
    AIDA = "aida"  # Attention → Interest → Desire → Action
    SLAP = "slap"  # Stop, Look, Act, Purchase (interrupt → engage → act → convert)


@dataclass(frozen=True)
class PlatformSpec:
    """Documented platform constraints (public limits, 2026)."""

    name: str
    char_limit: Optional[int]
    truncation_point: Optional[int]
    optimal_length: Optional[int]
    hashtag_count: int
    hashtag_placement: str  # "start" | "end" | "none"
    structure: str


PLATFORM_SPECS: Dict[Platform, PlatformSpec] = {
    Platform.LINKEDIN: PlatformSpec(
        name="LinkedIn",
        char_limit=3000,
        truncation_point=210,  # "see more" fold on desktop/mobile
        optimal_length=900,
        hashtag_count=5,
        hashtag_placement="end",
        structure="Hook (above the fold) → story or insight → CTA",
    ),
    Platform.X: PlatformSpec(
        name="X",
        char_limit=280,  # free tier; premium tiers raise this
        truncation_point=280,
        optimal_length=280,
        hashtag_count=3,
        hashtag_placement="end",
        structure="Thread: each post stands alone, numbered",
    ),
    Platform.INSTAGRAM_FEED: PlatformSpec(
        name="Instagram Feed",
        char_limit=2200,
        truncation_point=125,
        optimal_length=800,
        hashtag_count=5,
        hashtag_placement="end",
        structure="Hook → scannable points → CTA",
    ),
    Platform.INSTAGRAM_STORIES: PlatformSpec(
        name="Instagram Stories",
        char_limit=None,  # visual-first; text is overlay
        truncation_point=None,
        optimal_length=None,
        hashtag_count=0,
        hashtag_placement="none",
        structure="Visual first; minimal overlay text per card",
    ),
    Platform.TIKTOK: PlatformSpec(
        name="TikTok",
        char_limit=4000,
        truncation_point=None,
        optimal_length=150,
        hashtag_count=5,
        hashtag_placement="end",
        structure="Keywords up front for search; caption supports the video",
    ),
    Platform.NEWSLETTER: PlatformSpec(
        name="Newsletter",
        char_limit=None,
        truncation_point=None,
        optimal_length=2500,
        hashtag_count=0,
        hashtag_placement="none",
        structure="Subject (30–50 chars) → hook → body → CTA",
    ),
}


def platform_spec(platform: Platform) -> PlatformSpec:
    """Return the documented spec for a platform."""
    if not isinstance(platform, Platform):
        raise ValueError(f"platform must be a Platform, got {platform!r}")
    return PLATFORM_SPECS[platform]


def parse_platform(value: str) -> Platform:
    """Parse a user-supplied platform name; raises ValueError if unknown."""
    if not isinstance(value, str):
        raise ValueError(f"platform name must be a string, got {type(value).__name__}")
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {"twitter": Platform.X, "ig": Platform.INSTAGRAM_FEED}
    if key in aliases:
        return aliases[key]
    for p in Platform:
        if p.value == key:
            return p
    raise ValueError(
        f"unknown platform {value!r}; expected one of "
        + ", ".join(sorted(p.value for p in Platform))
    )


def validate_length(content: str, platform: Platform) -> Dict[str, Any]:
    """Check content length against a platform spec. Pure function."""
    if not isinstance(content, str):
        raise ValueError(f"content must be a string, got {type(content).__name__}")
    spec = platform_spec(platform)
    count = len(content)
    warnings: List[str] = []
    valid = True
    if spec.char_limit is not None and count > spec.char_limit:
        valid = False
        warnings.append(f"exceeds {spec.name} limit by {count - spec.char_limit} chars")
    if spec.truncation_point is not None and count > spec.truncation_point:
        warnings.append(
            f"folds/truncates around {spec.truncation_point} chars on {spec.name}"
        )
    return {
        "platform": platform.value,
        "char_count": count,
        "limit": spec.char_limit,
        "truncation_point": spec.truncation_point,
        "valid": valid,
        "warnings": warnings,
    }


# -- hooks ---------------------------------------------------------------


@dataclass(frozen=True)
class HookPattern:
    """A hook formula: template with {slots}, plus an honest rationale."""

    template: str
    why: str
    slots: List[str] = field(default_factory=list)


HOOK_PATTERNS: Dict[HookFormula, HookPattern] = {
    HookFormula.CONTRARIAN: HookPattern(
        template="Conventional wisdom says {claim}. The data says otherwise.",
        why="Disagreement with a common belief creates a reason to keep reading.",
        slots=["claim"],
    ),
    HookFormula.CURIOSITY_GAP: HookPattern(
        template="I ran {experiment} for {duration}. The turning point came on day {day}.",
        why="An open loop — the reader wants the missing piece.",
        slots=["experiment", "duration", "day"],
    ),
    HookFormula.SPECIFICITY_SIGNAL: HookPattern(
        template="{number} {unit} in {timeframe}: the exact {method}, step by step.",
        why="Concrete numbers read as evidence; vagueness reads as marketing.",
        slots=["number", "unit", "timeframe", "method"],
    ),
    HookFormula.NEGATIVE_HOOK: HookPattern(
        template="{count} mistakes that cost me {outcome} (so you can skip them).",
        why="Loss aversion: people work harder to avoid a loss than gain a win.",
        slots=["count", "outcome"],
    ),
    HookFormula.CALLOUT: HookPattern(
        template="If you are a {role} still {habit}, this is for you.",
        why="Self-selection raises reader intent; the wrong readers opt out.",
        slots=["role", "habit"],
    ),
    HookFormula.SLIPPERY_SLOPE: HookPattern(
        template="It started with a single {trigger}. Then everything compounded.",
        why="Narrative momentum — a small start that escalates holds attention.",
        slots=["trigger"],
    ),
    HookFormula.PERMISSION: HookPattern(
        template="An unpopular take: {take}.",
        why="Preframing disagreement lowers the reader's defenses.",
        slots=["take"],
    ),
}

BANNED_OPENERS = (
    "i'm excited to share",
    "hey everyone",
    "as a ",
    "in today's fast-paced world",
    "in this post, i will",
)


def parse_hook_formula(value: str) -> HookFormula:
    """Parse a user-supplied hook formula name; raises ValueError if unknown."""
    if not isinstance(value, str):
        raise ValueError(f"formula name must be a string, got {type(value).__name__}")
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    for f in HookFormula:
        if f.value == key:
            return f
    raise ValueError(
        f"unknown hook formula {value!r}; expected one of "
        + ", ".join(sorted(f.value for f in HookFormula))
    )


def render_hook(formula: HookFormula, variables: Dict[str, str]) -> Dict[str, Any]:
    """Render a hook from a formula + slot values. Pure function.

    Returns the rendered hook and the pattern's rationale. Missing slots
    raise ValueError (no silent half-hooks).
    """
    if not isinstance(formula, HookFormula):
        raise ValueError(f"formula must be a HookFormula, got {formula!r}")
    if not isinstance(variables, dict):
        raise ValueError(f"variables must be a dict, got {type(variables).__name__}")
    pattern = HOOK_PATTERNS[formula]
    missing = [s for s in pattern.slots if s not in variables]
    if missing:
        raise ValueError(
            f"hook formula {formula.value!r} needs slots {missing}; "
            f"got {sorted(variables)}"
        )
    hook = pattern.template
    for slot in pattern.slots:
        hook = hook.replace("{" + slot + "}", str(variables[slot]))
    check = validate_hook(hook)
    return {
        "formula": formula.value,
        "hook": hook,
        "why": pattern.why,
        "hook_check": check,
    }


def validate_hook(hook: str) -> Dict[str, Any]:
    """Check a hook against hygiene rules. Pure function."""
    if not isinstance(hook, str):
        raise ValueError(f"hook must be a string, got {type(hook).__name__}")
    issues: List[str] = []
    lowered = hook.strip().lower()
    for banned in BANNED_OPENERS:
        if lowered.startswith(banned):
            issues.append(f"banned opener: {banned!r}")
            break
    if len(hook.strip()) < 20:
        issues.append("hook is very short (< 20 chars); may not carry a promise")
    if len(hook) > 280:
        issues.append("hook exceeds 280 chars; too long for most feed folds")
    return {"valid": not issues, "issues": issues, "length": len(hook)}


def validate_content(content: str, platform: Platform) -> Dict[str, Any]:
    """Full validation of content against a platform spec. Pure function."""
    spec = platform_spec(platform)
    length = validate_length(content, platform)
    hashtag_marks = content.count("#")
    checks: Dict[str, Any] = {"length": length, "hashtag_marks": hashtag_marks}
    valid = bool(length["valid"])
    if spec.hashtag_count > 0 and hashtag_marks > spec.hashtag_count + 2:
        valid = False
        checks["hashtags"] = (
            f"{hashtag_marks} '#' marks vs budget of ~{spec.hashtag_count} tags"
        )
    return {"platform": platform.value, "valid": valid, "checks": checks}


# -- builders ------------------------------------------------------------


def _tags_block(hashtags: Optional[List[str]], budget: int) -> str:
    if not hashtags or budget <= 0:
        return ""
    clean = [t.lstrip("#").strip().replace(" ", "") for t in hashtags if t.strip()]
    clean = [t for t in clean if t][:budget]
    if not clean:
        return ""
    return "\n\n" + " ".join("#" + t for t in clean)


def build_linkedin_post(
    hook: str,
    body: str,
    cta: str,
    hashtags: Optional[List[str]] = None,
) -> str:
    """Assemble a LinkedIn post: hook → body → CTA → tags."""
    spec = platform_spec(Platform.LINKEDIN)
    parts = [h for h in (hook.strip(), body.strip(), cta.strip()) if h]
    return "\n\n".join(parts) + _tags_block(hashtags, spec.hashtag_count)


def build_x_thread(posts: List[str]) -> str:
    """Assemble an X thread; each post must fit the 280-char post limit."""
    if not posts:
        raise ValueError("thread needs at least one post")
    spec = platform_spec(Platform.X)
    for i, post in enumerate(posts):
        if len(post) > (spec.char_limit or 280):
            raise ValueError(
                f"thread post {i + 1} is {len(post)} chars; "
                f"exceeds {spec.char_limit}-char post limit"
            )
    numbered = [f"{i + 1}/{len(posts)} {p}" for i, p in enumerate(posts)]
    return "\n\n".join(numbered)


def build_instagram_post(
    hook: str,
    points: List[str],
    cta: str,
    hashtags: Optional[List[str]] = None,
) -> str:
    """Assemble an Instagram feed post: hook → bullet points → CTA → tags."""
    spec = platform_spec(Platform.INSTAGRAM_FEED)
    bullets = "\n".join(f"• {p.strip()}" for p in points if p.strip())
    parts = [h for h in (hook.strip(), bullets, cta.strip()) if h]
    return "\n\n".join(parts) + _tags_block(hashtags, spec.hashtag_count)


def build_newsletter(
    subject: str,
    hook: str,
    body: str,
    cta: str,
) -> Dict[str, str]:
    """Assemble a newsletter: subject + body. Returns sections as a dict."""
    if not (20 <= len(subject) <= 78):
        raise ValueError(
            f"subject should be 20–78 chars for inbox display; got {len(subject)}"
        )
    return {
        "subject": subject.strip(),
        "body": "\n\n".join(h for h in (hook.strip(), body.strip(), cta.strip()) if h),
    }


def format_for_platform(
    platform: Platform,
    hook: str = "",
    body: str = "",
    cta: str = "",
    points: Optional[List[str]] = None,
    posts: Optional[List[str]] = None,
    hashtags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """One entry point: build content for a platform and validate it.

    Returns {"content": str, "validation": {...}}. Stories/tiktok take
    (hook, body, cta) as overlay/script text.
    """
    if platform is Platform.X:
        if not posts:
            raise ValueError("x platform needs 'posts' (thread list)")
        content = build_x_thread(posts)
    elif platform is Platform.INSTAGRAM_FEED:
        content = build_instagram_post(hook, points or [], cta, hashtags)
    elif platform is Platform.NEWSLETTER:
        built = build_newsletter(hook or "Untitled", body, body and cta or "")
        content = f"Subject: {built['subject']}\n\n{built['body']}"
    elif platform is Platform.LINKEDIN:
        content = build_linkedin_post(hook, body, cta, hashtags)
    else:  # instagram_stories, tiktok: freeform overlay/script text
        content = "\n\n".join(
            h for h in (hook.strip(), body.strip(), cta.strip()) if h
        ) + _tags_block(hashtags, platform_spec(platform).hashtag_count)
    return {"content": content, "validation": validate_content(content, platform)}


# -- skills --------------------------------------------------------------
# Registered into SkillRegistry (category="social", risk INFO). Lazy import
# of Skill/SkillRisk keeps this module importable without the registry.


def _skill_format(args: Dict[str, Any]) -> str:
    args = args or {}
    try:
        platform = parse_platform(str(args.get("platform", "")))
    except ValueError as exc:
        return f"content format failed: {exc}"
    try:
        result = format_for_platform(
            platform,
            hook=str(args.get("hook", "") or ""),
            body=str(args.get("body", "") or ""),
            cta=str(args.get("cta", "") or ""),
            points=args.get("points"),
            posts=args.get("posts"),
            hashtags=args.get("hashtags"),
        )
    except ValueError as exc:
        return f"content format failed: {exc}"
    content = result["content"]
    validation = result["validation"]
    status = "valid" if validation["valid"] else "INVALID"
    checks = validation["checks"]
    lines = [
        f"[{platform.value}] formatted content ({status}):",
        content,
        "",
        f"checks: {len(content)} chars; "
        + "; ".join(
            f"{k}={v}" if not isinstance(v, dict) else f"{k}.valid={v.get('valid')}"
            for k, v in checks.items()
        ),
    ]
    return "\n".join(lines)


def _skill_hook(args: Dict[str, Any]) -> str:
    args = args or {}
    try:
        formula = parse_hook_formula(str(args.get("formula", "")))
    except ValueError as exc:
        return f"hook render failed: {exc}"
    variables = args.get("variables") or {}
    if not isinstance(variables, dict):
        return "hook render failed: 'variables' must be a mapping"
    try:
        rendered = render_hook(formula, {k: str(v) for k, v in variables.items()})
    except ValueError as exc:
        return f"hook render failed: {exc}"
    out = [
        f"hook ({rendered['formula']}):",
        rendered["hook"],
        "",
        f"why: {rendered['why']}",
    ]
    check = rendered["hook_check"]
    if not check["valid"]:
        out.append("hygiene issues: " + "; ".join(check["issues"]))
    return "\n".join(out)


def _skill_validate(args: Dict[str, Any]) -> str:
    args = args or {}
    try:
        platform = parse_platform(str(args.get("platform", "")))
    except ValueError as exc:
        return f"content validate failed: {exc}"
    content = args.get("content", "")
    if not isinstance(content, str):
        return "content validate failed: 'content' must be a string"
    try:
        report = validate_content(content, platform)
    except ValueError as exc:
        return f"content validate failed: {exc}"
    status = "valid" if report["valid"] else "INVALID"
    return (
        f"[{platform.value}] content {status}: "
        f"{report['checks']['length']['char_count']} chars; "
        f"warnings: {report['checks']['length']['warnings'] or 'none'}"
    )


def _build_content_skills() -> List[Any]:
    from levi.skill.registry import Skill, SkillRisk

    return [
        Skill(
            id="social_content_format",
            name="Social Content Format",
            description=(
                "Build platform-structured social content (hook/body/CTA, "
                "threads, tag budgets) and validate it against platform specs. "
                "Content only — never posts or touches the network."
            ),
            category="social",
            risk_level=SkillRisk.INFO,
            handler=_skill_format,
            tags=["social", "content", "king"],
            version="1.0.0",
        ),
        Skill(
            id="social_hook_render",
            name="Social Hook Render",
            description=(
                "Render a hook from a rhetorical formula + slot values, "
                "with the pattern's rationale and hygiene check."
            ),
            category="social",
            risk_level=SkillRisk.INFO,
            handler=_skill_hook,
            tags=["social", "content", "hooks"],
            version="1.0.0",
        ),
        Skill(
            id="social_content_validate",
            name="Social Content Validate",
            description=(
                "Validate text against a platform's documented limits, "
                "fold points, and hashtag budget."
            ),
            category="social",
            risk_level=SkillRisk.INFO,
            handler=_skill_validate,
            tags=["social", "content", "validation"],
            version="1.0.0",
        ),
    ]


CONTENT_SKILLS: List[Any] = _build_content_skills()
