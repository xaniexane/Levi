"""LEVI social platform — domain contracts for the town square by forum by code commons.

STATUS: AWAITING KEEPER REVIEW. ``docs/SOCIAL_PLATFORM_DESIGN.md`` is the
proposal; this package holds only the data contracts (schemas + validation)
that the design would build on. No services, no daemons, no network.

REMIX DELTA: the giants sell "community" as a capture surface — the graph
you can't see, the ranker you can't audit, the account you can't leave.
This module revives the compound the Forge canon names (town square by
forum by code commons, multidomain, agentic teams) with LEVI's twist:
one Cybrus-gated identity across domains with domain-local norms;
bridging-ranked votes instead of mob-ranked karma; disclosed feed recipes
instead of opaque rankers; forks as bloodlines with prime lineage and
inherited safety ceilings; squads as first-class members under the
spotlight law; and the binding promise that no platform content ever
trains a LEVI brain. Leaving is a feature: every surface exports.

What it ADDS that the giants refuse:
- Identity law as code: the spotlight rule and the mssi reservation are
  enforced at validation time, not written in a policy PDF.
- One seat, one voice: squads hold a single seat; votes can't be
  multiplied by member count; self-votes and double votes are refused.
- Tamper-evident portable bundles: ``levi-social-manifest/1`` with
  checksummed sections that refuse tampered imports.
- Founder-only fork powers with the safety ceiling that never drops
  without the founder's recorded approval.

Warehouse shelf for the interop atlas crew (see docs/WAREHOUSES.md).
"""

from __future__ import annotations

from .customize import (
    ANIMATION_TARGETS,
    CONTRAST_FLOOR,
    CUSTOMIZE_FORMAT,
    CUSTOMIZE_VERSION,
    SECTION_KINDS,
    WIDGET_REGISTRY,
    Animation,
    CustomBlock,
    CustomizeError,
    GuestbookEntry,
    Layout,
    ProfileCustomization,
    ProfileSong,
    ProfileTheme,
    Section,
    ThemeToken,
    Widget,
    contrast_ratio,
    enforce_contrast,
)
from .living import (
    EXPRESSION_TARGETS,
    LIVING_FORMAT,
    LIVING_VERSION,
    MOTIONS,
    MOTION_STARTS,
    OVERLAY_ANCHORS,
    PRESENCE_STATES,
    SIMULATION_STATES,
    DEFAULT_PRESENCE_ANIMATIONS,
    Expression,
    ExpressionSlot,
    Frame,
    LivingError,
    LivingLayer,
    Overlay,
    OverlayGrant,
    PresenceAnimation,
    PresenceBeacon,
    Simulation,
)
from .manifests import (
    AUDIENCE_TIERS,
    DOMAINS,
    KINDS,
    NATURES,
    PROFILE_STATUSES,
    SOCIAL_MANIFEST_FORMAT,
    SOCIAL_MANIFEST_VERSION,
    THREAD_STATUSES,
    VISIBILITIES,
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

__all__ = [
    "SHELF",
    "ANIMATION_TARGETS",
    "CONTRAST_FLOOR",
    "CUSTOMIZE_FORMAT",
    "CUSTOMIZE_VERSION",
    "SECTION_KINDS",
    "WIDGET_REGISTRY",
    "Animation",
    "CustomBlock",
    "CustomizeError",
    "GuestbookEntry",
    "Layout",
    "ProfileCustomization",
    "ProfileSong",
    "ProfileTheme",
    "Section",
    "ThemeToken",
    "Widget",
    "contrast_ratio",
    "enforce_contrast",
    "EXPRESSION_TARGETS",
    "LIVING_FORMAT",
    "LIVING_VERSION",
    "MOTIONS",
    "MOTION_STARTS",
    "OVERLAY_ANCHORS",
    "PRESENCE_STATES",
    "SIMULATION_STATES",
    "DEFAULT_PRESENCE_ANIMATIONS",
    "Expression",
    "ExpressionSlot",
    "Frame",
    "LivingError",
    "LivingLayer",
    "Overlay",
    "OverlayGrant",
    "PresenceAnimation",
    "PresenceBeacon",
    "Simulation",
    "AUDIENCE_TIERS",
    "DOMAINS",
    "KINDS",
    "NATURES",
    "PROFILE_STATUSES",
    "SOCIAL_MANIFEST_FORMAT",
    "SOCIAL_MANIFEST_VERSION",
    "THREAD_STATUSES",
    "VISIBILITIES",
    "BloodlineRule",
    "ManifestBundle",
    "Post",
    "Profile",
    "Realm",
    "Season",
    "SocialManifestError",
    "Squad",
    "Thread",
    "Vote",
    "VoteBook",
]

SHELF = {
    "name": "social",
    "summary": (
        "Multidomain social platform contracts (town square by forum by code "
        "commons): profiles, realms, threads, posts, bridging-ready votes, "
        "squads as first-class members, seasons, bloodline fork rules, and "
        "tamper-evident manifest bundles. AWAITING KEEPER REVIEW."
    ),
    "items": [
        "manifests: Profile/Realm/Thread/Post/Vote/VoteBook/Squad/Season/BloodlineRule/ManifestBundle",
        "customize: MySpace-era canvas engine — ProfileCustomization (theme tokens, reorderable layouts, profile song, animation descriptors, widget registry) with binding guardrails: contrast floors (auto-repair or strict refusal), reduced-motion degradation, no autoplay, entrance motion ends neutral, member content as structured data only",
        "living: the living layer — LivingLayer (agent presence beacons with honest work-state mapping, cartoon/GIF-like looping expressions as frame-timing data, AR-style overlays with member-invited grants, interactive simulation sessions with invite→active→exited contract) with binding guardrails: reduced-motion degrades all to static, motion starts member-invited or muted-by-default, overlays always dismissible, sealed levi-social-living/1 bundles",
        "identity law as code: spotlight rule, mssi reserved for Levi",
        "one seat one voice: no self-votes, no double votes, squads hold one seat",
        "bundles: levi-social-manifest/1, checksummed, tamper-refusing import",
    ],
}
