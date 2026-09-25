"""Bagatelle — mechanical pinball remix, honest edition.

Revives arch-games-bagatelle: pins in a board as skill-modulated chaos —
an analog probability space. The player chooses a launch angle and force;
gravity, wall bounces and elastic pin collisions decide the pocket.

Two LEVI-native additions the originals never had:
- every board encodes to a short shareable layout string, so two players
  can compete on the exact same board without a server;
- "prove the odds" mode: the game publishes the empirical pocket
  distribution for its own board, satisfying Charter rule 10 (odds public).
"""

from __future__ import annotations

import base64
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Physics constants
GRAVITY = 9.81  # px/s^2, board is small so this keeps trajectories lively
DT = 0.01  # fixed timestep keeps runs deterministic across machines
RESTITUTION_WALL = 0.8  # wall bounce retains 80% of normal velocity
RESTITUTION_PIN = 0.95  # pin collisions nearly elastic
MIN_SPEED = 0.05  # below this the ball is considered at rest


class StepBudgetExceeded(Exception):
    """Raised when a simulation does not settle within max_steps."""


@dataclass
class Pin:
    x: float
    y: float
    r: float = 2.0


@dataclass
class Pocket:
    x: float  # centre of the pocket along the bottom edge
    score: int


@dataclass
class BagatelleBoard:
    """A pin board. y grows downward; the ball launches from the bottom."""

    width: float = 100.0
    height: float = 140.0
    pins: List[Pin] = field(default_factory=list)
    pockets: List[Pocket] = field(default_factory=list)
    # The pocket width matters for rendering; gameplay only needs centres.
    pocket_half_width: float = 6.0

    # --- shareable layout string --------------------------------------
    # Encodes dims + rounded pins + pocket scores as a compact base64
    # token, e.g. "B1.64,9,3.2.12,4,2.2..." -> ASCII-safe for chat/QR.

    def layout_string(self) -> str:
        parts = ["B1", "%d" % round(self.width), "%d" % round(self.height)]
        for p in self.pins:
            parts.append(
                "P%d,%d,%d" % (round(p.x * 10), round(p.y * 10), round(p.r * 10))
            )
        for k in self.pockets:
            parts.append("K%d,%d" % (round(k.x * 10), k.score))
        raw = ";".join(parts).encode("ascii")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @classmethod
    def from_layout_string(cls, s: str) -> "BagatelleBoard":
        padded = s + "=" * (-len(s) % 4)
        try:
            raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii")
        except Exception as exc:
            raise ValueError("not a valid layout string: %r" % s) from exc
        pins: List[Pin] = []
        pockets: List[Pocket] = []
        tokens = raw.split(";")
        if not tokens or tokens[0] != "B1":
            raise ValueError("not a bagatelle layout string: %r" % s)
        bare = [t for t in tokens[1:] if t.isdigit()]
        if bare:
            width = float(bare[0])
        if len(bare) > 1:
            height = float(bare[1])
        for tok in tokens[1:]:
            if tok.isdigit():
                continue  # dimensions, already consumed
            tag = tok[0]
            vals = tok[1:].split(",")
            try:
                if tag == "P":
                    x, y, r = (int(v) for v in vals)
                    pins.append(Pin(x / 10.0, y / 10.0, r / 10.0))
                elif tag == "K":
                    x, score = int(vals[0]), int(vals[1])
                    pockets.append(Pocket(x / 10.0, score))
                else:
                    raise ValueError("unknown token: %r" % tok)
            except (ValueError, IndexError) as exc:
                raise ValueError("corrupt layout string: %r" % s) from exc
        return cls(width=width, height=height, pins=pins, pockets=pockets)


def classic_board() -> BagatelleBoard:
    """A small triangular pin field over five scoring pockets."""
    pins = []
    for row in range(5):
        y = 30.0 + row * 16.0
        n = row + 2
        for i in range(n):
            x = 50.0 + (i - (n - 1) / 2.0) * 14.0
            pins.append(Pin(x, y, 2.0))
    scores = [10, 50, 100, 50, 10]
    pockets = [Pocket(10.0 + i * 20.0, s) for i, s in enumerate(scores)]
    return BagatelleBoard(width=100.0, height=140.0, pins=pins, pockets=pockets)


@dataclass
class BallResult:
    path_sample: List[Tuple[float, float]]  # every ~10th position
    pocket_hit: Optional[Pocket]  # None if the ball stopped on the board
    steps: int


def _launch_velocity(angle_deg: float, force: float) -> Tuple[float, float]:
    theta = math.radians(angle_deg)
    return (force * math.cos(theta), -force * math.sin(theta))


def simulate(
    board: BagatelleBoard,
    angle_deg: float,
    force: float,
    seed: Optional[int] = None,
    max_steps: int = 2000,
) -> BallResult:
    """Launch a ball and integrate until it rests in a pocket or stops.

    Deterministic given seed. Raises StepBudgetExceeded if the ball is
    still moving after max_steps (prevents infinite bounce loops).
    """
    rng = random.Random(seed)
    vx, vy = _launch_velocity(angle_deg, force)
    x, y = board.width / 2.0, board.height - 5.0
    r = 1.5  # ball radius
    path: List[Tuple[float, float]] = []
    steps = 0
    jitter = 1e-9  # deterministic micro-nudge breaks perfect symmetries

    while steps < max_steps:
        steps += 1
        vy += GRAVITY * DT
        x += vx * DT
        y += vy * DT

        # Walls: left, right, top bounce; bottom is the pocket line.
        if x < r:
            x = r
            vx = -vx * RESTITUTION_WALL
        elif x > board.width - r:
            x = board.width - r
            vx = -vx * RESTITUTION_WALL
        if y < r:
            y = r
            vy = -vy * RESTITUTION_WALL

        # Pin collision: elastic reflect around the pin normal.
        for pin in board.pins:
            dx, dy = x - pin.x, y - pin.y
            dist = math.hypot(dx, dy)
            min_d = r + pin.r
            if dist < min_d and dist > 1e-12:
                nx, ny = dx / dist, dy / dist
                # Push out of the pin.
                x = pin.x + nx * min_d
                y = pin.y + ny * min_d
                # Reflect velocity, scaled by restitution.
                vn = vx * nx + vy * ny
                vx = (vx - 2 * vn * nx) * RESTITUTION_PIN
                vy = (vy - 2 * vn * ny) * RESTITUTION_PIN
                # Tiny deterministic jitter keeps mirrored launches from
                # locking into perfectly periodic orbits.
                vx += jitter * (rng.random() - 0.5)
                vy += jitter * (rng.random() - 0.5)

        if steps % 10 == 0:
            path.append((round(x, 2), round(y, 2)))

        speed = math.hypot(vx, vy)
        if y >= board.height - r:
            # Reached the bottom: find the pocket whose centre is nearest.
            best = min(board.pockets, key=lambda p: abs(p.x - x), default=None)
            path.append((round(x, 2), round(board.height - 1.0, 2)))
            return BallResult(path, best, steps)
        if speed < MIN_SPEED:
            # Ball came to rest on the board (e.g. perched on pins).
            return BallResult(path, None, steps)

    raise StepBudgetExceeded("ball still moving after %d steps" % max_steps)


def render_ascii(
    board: BagatelleBoard,
    path: Optional[List[Tuple[float, float]]] = None,
    width: int = 41,
    height: int = 21,
) -> str:
    """Rough ASCII view of the board, with an optional path overlay."""
    sx = width / board.width
    sy = height / board.height
    grid = [[" "] * width for _ in range(height)]
    for pin in board.pins:
        gx, gy = int(pin.x * sx), int(pin.y * sy)
        if 0 <= gx < width and 0 <= gy < height:
            grid[gy][gx] = "o"
    for k in board.pockets:
        gx = int(k.x * sx)
        label = "%d" % k.score
        for i, ch in enumerate(label):
            if 0 <= gx + i < width:
                grid[height - 1][gx + i] = ch
    if path:
        for x, y in path:
            gx, gy = int(x * sx), int(y * sy)
            if 0 <= gx < width and 0 <= gy < height and grid[gy][gx] == " ":
                grid[gy][gx] = "."
    lines = ["".join(row) for row in grid]
    return "\n".join(lines)


def empirical_distribution(
    board: BagatelleBoard,
    trials: int = 20000,
    seed: int = 7,
    angle_deg: float = 90.0,
    force: float = 260.0,
) -> Dict[int, float]:
    """Play the board N times and print the stated-vs-empirical odds.

    The ball has no "stated" odds — the honest declaration is the measured
    distribution itself. Returns pocket-score -> fraction.
    """
    rng = random.Random(seed)
    counts: Dict[int, int] = {}
    settled = 0
    for _ in range(trials):
        try:
            res = simulate(board, angle_deg, force, seed=rng.randrange(2**31))
        except StepBudgetExceeded:
            continue
        if res.pocket_hit is not None:
            settled += 1
            counts[res.pocket_hit.score] = counts.get(res.pocket_hit.score, 0) + 1
    dist = {s: c / trials for s, c in sorted(counts.items())}
    print(
        "Empirical odds — %d launches, angle=%g, force=%g" % (trials, angle_deg, force)
    )
    print("  pocket  empirical")
    for score in sorted(counts):
        print("  %5d   %8.3f" % (score, dist[score]))
    print("  unsettled balls: %.3f (not counted)" % (1.0 - settled / trials))
    return dist
