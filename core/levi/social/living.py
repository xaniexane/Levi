"""The living layer — descriptors for presence, cartoon motion, and immersion.

STATUS: AWAITING KEEPER REVIEW. This module implements the living-layer
canon from ``docs/SOCIAL_PLATFORM_DESIGN.md`` (§1a): agents shown working
(living presence — you watch your operators work, animated); mini-cartoon
and GIF-like implementations (looping animated expressions, cartoon-style
motion, the profile as a living thing); immersive overlays (AR-style
overlay layers and interactive simulations — the platform as a place you
step into, not a page you read).

What this is: shapes and rules, data + validation only. Presence
animations, cartoon expressions, overlays, and simulations are
*descriptors as data* — the engine validates them; it never executes
code. True VR/AR rendering is a client capability; this module defines
the descriptors and the contract, honestly.

Binding guardrails (the keeper's law, same as ``customize.py``):
- ``prefers-reduced-motion`` degrades everything to static — presence,
  expressions, overlays, simulations.
- No autoplay ambushes: motion starts member-invited or muted-by-default;
  "auto" start is refused at construction.
- Presence is honest: states that claim work (working, thinking,
  delivering) must name the work; rest states (idle, resting) must not
  fake it. Presence is never synthesized — it maps to real operator
  activity.
- Readability never breaks: motion never strands or obscures content.
- Immersion is never imposed: every overlay is dismissible and every
  overlay/simulation is member-invited, with a clean exit always
  available.

Stdlib only. No network, no storage backends — the caller persists the
sealed dicts however it persists anything else.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

LIVING_FORMAT = "levi-social-living"
LIVING_VERSION = 1


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LivingError(Exception):
    """Any living-layer refusal: bad descriptor, broken guardrail, faked
    presence, imposed immersion."""


_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")


def _check_id(value: str, what: str) -> str:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise LivingError("bad %s %r: simple id, max 64 chars" % (what, value))
    return value


def _check_name(value: str, what: str) -> str:
    if not isinstance(value, str) or not _NAME_RE.match(value):
        raise LivingError("bad %s %r: simple name, max 64 chars" % (what, value))
    return value


def _check_plain_text(value: str, what: str, max_len: int = 280) -> str:
    if not isinstance(value, str):
        raise LivingError("bad %s: must be text" % what)
    if len(value) > max_len:
        raise LivingError("bad %s: too long (max %d)" % (what, max_len))
    if "<" in value or ">" in value:
        raise LivingError("bad %s: markup refused — plain text only" % what)
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value):
        raise LivingError("bad %s: control chars refused" % what)
    return value


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# 1. Agent presence — living presence, honestly mapped
# ---------------------------------------------------------------------------

PRESENCE_STATES = ("idle", "working", "thinking", "delivering", "resting")
# States that claim real operator activity must name the work.
WORK_STATES = ("working", "thinking", "delivering")
# Rest states must not carry a fake activity claim.
REST_STATES = ("idle", "resting")

_MIN_ANIM_MS = 50
_MAX_ANIM_MS = 5000


@dataclass
class PresenceAnimation:
    """The animation descriptor for one presence state: a name, whether it
    loops, and its duration. Ambient and quiet — presence motion is
    muted-by-default, never an ambush."""

    name: str
    loop: bool = True
    duration_ms: int = 1200

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> "PresenceAnimation":
        _check_name(self.name, "presence animation name")
        if not isinstance(self.duration_ms, int) or not (
            _MIN_ANIM_MS <= self.duration_ms <= _MAX_ANIM_MS
        ):
            raise LivingError(
                "bad presence animation duration %r: %d–%d ms"
                % (self.duration_ms, _MIN_ANIM_MS, _MAX_ANIM_MS)
            )
        if not isinstance(self.loop, bool):
            raise LivingError("presence animation loop must be bool")
        return self

    def degraded(self) -> Dict[str, Any]:
        return {"name": self.name, "motion": "static"}

    def spec(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "loop": self.loop,
            "duration_ms": self.duration_ms,
        }


# Default animation per state — the house style for watching operators work.
DEFAULT_PRESENCE_ANIMATIONS: Dict[str, PresenceAnimation] = {
    "idle": PresenceAnimation(name="soft-breathe", loop=True, duration_ms=2400),
    "working": PresenceAnimation(name="hands-moving", loop=True, duration_ms=1200),
    "thinking": PresenceAnimation(name="slow-orbit", loop=True, duration_ms=3000),
    "delivering": PresenceAnimation(name="rise-and-settle", loop=False, duration_ms=900),
    "resting": PresenceAnimation(name="dim-ember", loop=True, duration_ms=4000),
}


@dataclass
class PresenceBeacon:
    """One operator's living presence: who, what state, and — for work
    states — *what work*, named. The honesty rule is code: a beacon that
    claims working/thinking/delivering without naming the activity is
    refused; a beacon in idle/resting that names an activity is refused
    too. Presence maps to real operator activity, never faked."""

    operator_id: str
    state: str
    activity: str = ""
    animation: PresenceAnimation = field(
        default_factory=lambda: PresenceAnimation(
            name="soft-breathe", loop=True, duration_ms=2400
        )
    )
    updated_at: str = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        _check_id(self.operator_id, "operator_id")
        if self.state not in PRESENCE_STATES:
            raise LivingError(
                "bad presence state %r: must be one of %s"
                % (self.state, ", ".join(PRESENCE_STATES))
            )
        if self.state in WORK_STATES:
            if not self.activity.strip():
                raise LivingError(
                    "dishonest presence: state %r must name the work "
                    "(activity required)" % (self.state,)
                )
            _check_plain_text(self.activity, "presence activity")
        else:  # REST_STATES
            if self.activity.strip():
                raise LivingError(
                    "dishonest presence: state %r must not claim an activity"
                    % (self.state,)
                )
        self.animation.validate()
        if not isinstance(self.updated_at, str) or not self.updated_at:
            raise LivingError("presence updated_at must be a timestamp string")

    def set_state(
        self, state: str, activity: str = ""
    ) -> "PresenceBeacon":
        """Move the beacon to a new honest state. Same honesty rule as
        construction — the caller supplies the real activity."""
        self.state = state
        self.activity = activity
        self.__post_init__()
        self.updated_at = _utcnow()
        return self

    def degraded(self) -> Dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "state": self.state,
            "activity": self.activity,
            "animation": self.animation.degraded(),
            "updated_at": self.updated_at,
        }

    def spec(self) -> Dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "state": self.state,
            "activity": self.activity,
            "animation": self.animation.spec(),
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# 2. Cartoon / GIF-like motion — looping animated expressions
# ---------------------------------------------------------------------------

MOTIONS = ("bounce", "pop", "wiggle", "morph", "parade")
# Motion start discipline: member-invited or muted-by-default. "auto" is
# refused — no autoplay ambushes.
MOTION_STARTS = ("member-invited", "muted")
_MIN_FRAME_MS = 50
_MAX_FRAME_MS = 2000
_MAX_LOOP_MS = 30000


@dataclass
class Frame:
    """One frame of a cartoon expression: a name and its timing. Names,
    not image bytes — the renderer owns the art; the engine owns the
    choreography."""

    name: str
    duration_ms: int

    def validate(self) -> "Frame":
        _check_name(self.name, "frame name")
        if not isinstance(self.duration_ms, int) or not (
            _MIN_FRAME_MS <= self.duration_ms <= _MAX_FRAME_MS
        ):
            raise LivingError(
                "bad frame duration %r: %d–%d ms"
                % (self.duration_ms, _MIN_FRAME_MS, _MAX_FRAME_MS)
            )
        return self


@dataclass
class Expression:
    """A looping animated expression in a cartoon style: a motion kind
    plus a frame sequence with timing. Profiles and posts can carry one
    (see ExpressionSlot)."""

    name: str
    motion: str
    frames: List[Frame] = field(default_factory=list)
    loop: bool = True
    starts: str = "muted"

    def __post_init__(self) -> None:
        _check_name(self.name, "expression name")
        if self.motion not in MOTIONS:
            raise LivingError(
                "bad motion %r: must be one of %s"
                % (self.motion, ", ".join(MOTIONS))
            )
        if self.starts not in MOTION_STARTS:
            raise LivingError(
                "bad motion start %r: must be one of %s (no autoplay ambushes)"
                % (self.starts, ", ".join(MOTION_STARTS))
            )
        if not self.frames:
            raise LivingError(
                "expression %r needs at least one frame" % (self.name,)
            )
        for f in self.frames:
            f.validate()
        names = [f.name for f in self.frames]
        if len(set(names)) != len(names):
            raise LivingError(
                "duplicate frame names in expression %r" % (self.name,)
            )
        if self.loop and self.total_ms() > _MAX_LOOP_MS:
            raise LivingError(
                "expression %r loops too long (%d ms > %d ms cap)"
                % (self.name, self.total_ms(), _MAX_LOOP_MS)
            )
        if not isinstance(self.loop, bool):
            raise LivingError("expression loop must be bool")

    def total_ms(self) -> int:
        return sum(f.duration_ms for f in self.frames)

    def degraded(self) -> Dict[str, Any]:
        """Reduced motion: the expression freezes on its first frame."""
        return {
            "name": self.name,
            "motion": "static",
            "frame": self.frames[0].name,
            "starts": self.starts,
        }

    def spec(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "motion": self.motion,
            "frames": [asdict(f) for f in self.frames],
            "loop": self.loop,
            "starts": self.starts,
            "total_ms": self.total_ms(),
        }


EXPRESSION_TARGETS = ("profile", "post")


@dataclass
class ExpressionSlot:
    """Where an expression lives: on a profile or a post."""

    target: str
    ref: str
    expression: Expression

    def __post_init__(self) -> None:
        if self.target not in EXPRESSION_TARGETS:
            raise LivingError(
                "bad expression target %r: must be one of %s"
                % (self.target, ", ".join(EXPRESSION_TARGETS))
            )
        _check_id(self.ref, "expression ref")
        # Expression validates itself in its own __post_init__.


# ---------------------------------------------------------------------------
# 3. Immersive overlays — AR-style layers and interactive simulations
# ---------------------------------------------------------------------------

OVERLAY_ANCHORS = ("profile-region", "viewport", "post")
_MAX_DEPTH = 99


@dataclass
class Overlay:
    """An AR-style overlay layer: anchored to a profile region, the
    viewport, or a post; depth-ordered; always dismissible. Anchoring to
    a profile region names the region; anchoring never covers content the
    member didn't invite it over — immersion is member-invited."""

    id: str
    anchor: str
    region: str = ""
    depth: int = 10
    dismissible: bool = True
    title: str = ""

    def __post_init__(self) -> None:
        _check_id(self.id, "overlay id")
        if self.anchor not in OVERLAY_ANCHORS:
            raise LivingError(
                "bad overlay anchor %r: must be one of %s"
                % (self.anchor, ", ".join(OVERLAY_ANCHORS))
            )
        if self.anchor == "profile-region":
            if not self.region:
                raise LivingError(
                    "overlay %r anchored to profile-region must name the region"
                    % (self.id,)
                )
            _check_id(self.region, "overlay region")
        elif self.region:
            raise LivingError(
                "overlay %r: region only valid with profile-region anchor"
                % (self.id,)
            )
        if not isinstance(self.depth, int) or not (0 <= self.depth <= _MAX_DEPTH):
            raise LivingError(
                "bad overlay depth %r: 0–%d" % (self.depth, _MAX_DEPTH)
            )
        if self.dismissible is not True:
            raise LivingError(
                "overlay %r must be dismissible: immersion is never imposed"
                % (self.id,)
            )
        if self.title:
            _check_plain_text(self.title, "overlay title", max_len=120)

    def degraded(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "anchor": self.anchor,
            "region": self.region,
            "depth": self.depth,
            "dismissible": True,
            "title": self.title,
            "motion": "static",
        }

    def spec(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "anchor": self.anchor,
            "region": self.region,
            "depth": self.depth,
            "dismissible": True,
            "title": self.title,
        }


@dataclass
class OverlayGrant:
    """The member's invitation for an overlay: an overlay renders only
    with a grant. No grant, no overlay — immersion is member-invited."""

    overlay_id: str
    member_id: str

    def __post_init__(self) -> None:
        _check_id(self.overlay_id, "grant overlay_id")
        _check_id(self.member_id, "grant member_id")


SIMULATION_STATES = ("invited", "active", "exited")


@dataclass
class Simulation:
    """An interactive simulation session: a scene, its actors, a
    member-invited entry, and a clean exit. True VR/AR rendering is a
    client capability — this is the descriptor and the contract.

    Lifecycle: invited -> active -> exited. Entry requires the member's
    invitation (``invited=True`` at construction); the exit is always
    available; re-entry needs a fresh session (a fresh invite)."""

    id: str
    scene: str
    actors: Tuple[str, ...] = ()
    invited: bool = True
    state: str = "invited"

    def __post_init__(self) -> None:
        _check_id(self.id, "simulation id")
        _check_plain_text(self.scene, "simulation scene", max_len=120)
        for actor in self.actors:
            _check_id(actor, "simulation actor")
        if len(set(self.actors)) != len(self.actors):
            raise LivingError(
                "duplicate actors in simulation %r" % (self.id,)
            )
        if self.invited is not True:
            raise LivingError(
                "simulation %r must be member-invited: immersion is never "
                "imposed" % (self.id,)
            )
        if self.state not in SIMULATION_STATES:
            raise LivingError(
                "bad simulation state %r: must be one of %s"
                % (self.state, ", ".join(SIMULATION_STATES))
            )

    def enter(self) -> "Simulation":
        """The member steps in. Only from invited — an exited session
        never reopens; a fresh invite starts a fresh session."""
        if self.state != "invited":
            raise LivingError(
                "simulation %r cannot enter from state %r"
                % (self.id, self.state)
            )
        self.state = "active"
        return self

    def exit(self) -> "Simulation":
        """The clean exit — always available from invited or active."""
        if self.state == "exited":
            raise LivingError(
                "simulation %r already exited" % (self.id,)
            )
        self.state = "exited"
        return self

    def degraded(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "scene": self.scene,
            "actors": list(self.actors),
            "state": self.state,
            "motion": "static",
        }

    def spec(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "scene": self.scene,
            "actors": list(self.actors),
            "invited": self.invited,
            "state": self.state,
        }


# ---------------------------------------------------------------------------
# The whole living layer — one owner's, sealed and portable
# ---------------------------------------------------------------------------


@dataclass
class LivingLayer:
    """Everything alive about one owner's presence on the platform:
    operator beacons, cartoon expressions, overlays (+ their grants),
    and simulation sessions."""

    owner_id: str
    beacons: List[PresenceBeacon] = field(default_factory=list)
    expressions: List[ExpressionSlot] = field(default_factory=list)
    overlays: List[Overlay] = field(default_factory=list)
    grants: List[OverlayGrant] = field(default_factory=list)
    simulations: List[Simulation] = field(default_factory=list)

    def __post_init__(self) -> None:
        _check_id(self.owner_id, "owner_id")
        # Members validate themselves; here we check cross-references.
        op_ids = [b.operator_id for b in self.beacons]
        if len(set(op_ids)) != len(op_ids):
            raise LivingError("duplicate operator beacons")
        expr_names = [s.expression.name for s in self.expressions]
        if len(set(expr_names)) != len(expr_names):
            raise LivingError("duplicate expression names")
        overlay_ids = [o.id for o in self.overlays]
        if len(set(overlay_ids)) != len(overlay_ids):
            raise LivingError("duplicate overlay ids")
        known_overlays = set(overlay_ids)
        for g in self.grants:
            if g.overlay_id not in known_overlays:
                raise LivingError(
                    "grant for unknown overlay %r" % (g.overlay_id,)
                )
        sim_ids = [s.id for s in self.simulations]
        if len(set(sim_ids)) != len(sim_ids):
            raise LivingError("duplicate simulation ids")

    def render(self, *, reduced_motion: bool = False) -> Dict[str, Any]:
        """The renderer-ready spec. With ``reduced_motion=True`` every
        beacon, expression, overlay, and simulation degrades to static —
        same identities, no movement."""
        if reduced_motion:
            beacons = [b.degraded() for b in self.beacons]
            expressions = [
                {"target": s.target, "ref": s.ref, **s.expression.degraded()}
                for s in self.expressions
            ]
            overlays = [o.degraded() for o in self.overlays]
            simulations = [s.degraded() for s in self.simulations]
        else:
            beacons = [b.spec() for b in self.beacons]
            expressions = [
                {"target": s.target, "ref": s.ref, **s.expression.spec()}
                for s in self.expressions
            ]
            overlays = [o.spec() for o in self.overlays]
            simulations = [s.spec() for s in self.simulations]
        return {
            "owner_id": self.owner_id,
            "beacons": beacons,
            "expressions": expressions,
            "overlays": overlays,
            "grants": [asdict(g) for g in self.grants],
            "simulations": simulations,
            "reduced_motion": reduced_motion,
        }

    # -- portable sealed form (mirrors the customize/manifests discipline) --

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "format": LIVING_FORMAT,
            "version": LIVING_VERSION,
            "owner_id": self.owner_id,
            "beacons": [
                {
                    "operator_id": b.operator_id,
                    "state": b.state,
                    "activity": b.activity,
                    "animation": b.animation.spec(),
                    "updated_at": b.updated_at,
                }
                for b in self.beacons
            ],
            "expressions": [
                {
                    "target": s.target,
                    "ref": s.ref,
                    "expression": s.expression.spec(),
                }
                for s in self.expressions
            ],
            "overlays": [o.spec() for o in self.overlays],
            "grants": [asdict(g) for g in self.grants],
            "simulations": [s.spec() for s in self.simulations],
        }
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        data["checksum"] = hashlib.sha256(canonical.encode()).hexdigest()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LivingLayer":
        if data.get("format") != LIVING_FORMAT:
            raise LivingError("bad bundle format %r" % (data.get("format"),))
        if data.get("version") != LIVING_VERSION:
            raise LivingError("bad bundle version %r" % (data.get("version"),))
        expect = data.get("checksum", "")
        body = {k: v for k, v in data.items() if k != "checksum"}
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        if hashlib.sha256(canonical.encode()).hexdigest() != expect:
            raise LivingError("checksum mismatch: tampered bundle refused")

        def _beacon(b: Dict[str, Any]) -> PresenceBeacon:
            a = b.get("animation", {})
            return PresenceBeacon(
                operator_id=b["operator_id"],
                state=b["state"],
                activity=b.get("activity", ""),
                animation=PresenceAnimation(
                    name=a.get("name", "soft-breathe"),
                    loop=a.get("loop", True),
                    duration_ms=a.get("duration_ms", 1200),
                ),
                updated_at=b.get("updated_at", _utcnow()),
            )

        def _slot(s: Dict[str, Any]) -> ExpressionSlot:
            e = s["expression"]
            return ExpressionSlot(
                target=s["target"],
                ref=s["ref"],
                expression=Expression(
                    name=e["name"],
                    motion=e["motion"],
                    frames=[
                        Frame(name=f["name"], duration_ms=f["duration_ms"])
                        for f in e.get("frames", [])
                    ],
                    loop=e.get("loop", True),
                    starts=e.get("starts", "muted"),
                ),
            )

        return cls(
            owner_id=body["owner_id"],
            beacons=[_beacon(b) for b in body.get("beacons", [])],
            expressions=[_slot(s) for s in body.get("expressions", [])],
            overlays=[Overlay(**o) for o in body.get("overlays", [])],
            grants=[OverlayGrant(**g) for g in body.get("grants", [])],
            simulations=[Simulation(**s) for s in body.get("simulations", [])],
        )
