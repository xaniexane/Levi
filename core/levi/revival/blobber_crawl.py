"""Grid-based dungeon crawling: discrete steps, turns, line of sight, attrition.

Studied from: dead-game-genres-2026-09-16/report.md [Entries - Grid-Based
Dungeon Crawlers] (the genre's mechanical shape: discrete grid movement with
step/turn, tile-based line of sight, mapping as a player skill via an
automap that only records what the party has seen, and resource attrition -
hit points, light, rations - draining across a delve).

This is an original, from-scratch implementation for LEVI. A ``Delve`` runs
on a rectangular tile grid (``#`` wall, ``.`` floor, ``D`` door, ``T``
treasure, ``^`` trap, ``E`` exit, ``M`` monster). The party moves one tile at
a time and turns in place (N/E/S/W); movement is bump-blocked by walls and
locked doors until opened with a key. Line of sight is computed per party
facing with a simple raycast over the grid, and only tiles in sight are
marked on the automap (mapping is earned by looking, not granted). Each move
and turn ticks attrition: torches burn down, rations are eaten every N steps,
monsters deal damage when adjacent. The delve is won by reaching the exit
alive, lost when the party is wiped or the light dies with no torches left.

Honest limits: monsters are stationary and strike only when orthogonally
adjacent (a deliberate simplification - no pathfinding); traps are single-use
and visible only with a "search" action; combat is a single opposed roll.

Public surface:
- ``Delve(map_text)``: parse an ASCII map; ``party`` is a 4-member roster.
- ``step()`` / ``turn_left()`` / ``turn_right()`` / ``search()`` / ``open_door()``
- ``visible()`` -> set of (x, y): tiles currently in line of sight.
- ``automap()`` -> str: the player-earned map so far.
- ``status()`` -> dict snapshot.

stdlib-only. No network. Deterministic except combat rolls (seedable).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

ORIGIN = "levi-revival/blobber-crawl"

WALL, FLOOR, DOOR, TREASURE, TRAP, EXIT, MONSTER = "#", ".", "D", "T", "^", "E", "M"

DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]  # N, E, S, W
DIR_NAMES = ("north", "east", "south", "west")


@dataclass
class Member:
    name: str
    hp: int = 10
    max_hp: int = 10

    @property
    def alive(self) -> bool:
        return self.hp > 0


@dataclass
class Delve:
    map_text: str
    seed: Optional[int] = None

    def __post_init__(self) -> None:
        rows = [
            list(line.rstrip("\n")) for line in self.map_text.strip("\n").splitlines()
        ]
        width = max(len(r) for r in rows)
        self.grid: List[List[str]] = [r + ["#"] * (width - len(r)) for r in rows]
        self.h = len(self.grid)
        self.w = width
        self.rng = random.Random(self.seed)
        # party starts on the first floor tile scanning top-left
        self.x = self.y = 0
        for yy in range(self.h):
            for xx in range(self.w):
                if self.grid[yy][xx] == FLOOR:
                    self.x, self.y = xx, yy
                    break
            else:
                continue
            break
        self.facing = 1  # east
        self.party: List[Member] = [
            Member("Ash"),
            Member("Bramble"),
            Member("Cinder"),
            Member("Dusk"),
        ]
        self.steps = 0
        self.torches = 3
        self.torch_burn = 100  # percent of current torch
        self.rations = 4
        self.keys = 1
        self.gold = 0
        self.seen: Set[Tuple[int, int]] = set()
        self.sprung_traps: Set[Tuple[int, int]] = set()
        self.won = False
        self.lost = False
        self._update_sight()

    # -- sensing -----------------------------------------------------------------
    def _blocked_sight(self, x: int, y: int) -> bool:
        return self.grid[y][x] in (WALL, DOOR)

    def _los_ray(self, dx: int, dy: int, max_range: int) -> Set[Tuple[int, int]]:
        seen: Set[Tuple[int, int]] = set()
        x, y = self.x, self.y
        for _ in range(max_range):
            x, y = x + dx, y + dy
            if not (0 <= x < self.w and 0 <= y < self.h):
                break
            seen.add((x, y))
            if self._blocked_sight(x, y):
                break
        return seen

    def visible(self) -> Set[Tuple[int, int]]:
        """Tiles in line of sight: forward cone of 5 plus the party's own tile."""
        out = {(self.x, self.y)}
        fx, fy = DIRS[self.facing]
        # forward, forward-left, forward-right rays
        left = DIRS[(self.facing - 1) % 4]
        right = DIRS[(self.facing + 1) % 4]
        rng = 5 if self.torch_burn > 0 else 1
        for dx, dy in (
            (fx, fy),
            (fx + left[0], fy + left[1]),
            (fx + right[0], fy + right[1]),
        ):
            out |= self._los_ray(dx, dy, rng)
        return out

    def _update_sight(self) -> None:
        self.seen |= self.visible()

    def automap(self) -> str:
        """The player-earned map: only tiles the party has ever seen."""
        lines = []
        for y in range(self.h):
            row = ""
            for x in range(self.w):
                if (x, y) == (self.x, self.y):
                    row += "@"
                elif (x, y) in self.seen:
                    t = self.grid[y][x]
                    row += t if t != MONSTER else "M"
                else:
                    row += " "
            lines.append(row)
        return "\n".join(lines)

    # -- movement ------------------------------------------------------------------
    def _tick_attrition(self) -> List[str]:
        events: List[str] = []
        self.steps += 1
        self.torch_burn -= 2
        if self.torch_burn <= 0:
            if self.torches > 0:
                self.torches -= 1
                self.torch_burn = 100
                events.append(f"You light a new torch ({self.torches} left).")
            else:
                self.torch_burn = 0
                self.lost = True
                events.append("The last torch gutters out. Darkness takes the party.")
        if self.steps % 25 == 0:
            if self.rations > 0:
                self.rations -= 1
                for m in self.party:
                    m.hp = min(m.max_hp, m.hp + 2)
                events.append("The party eats. (+2 HP each)")
            else:
                for m in self.party:
                    m.hp -= 1
                events.append("No rations left - hunger gnaws. (-1 HP each)")
        if all(not m.alive for m in self.party):
            self.lost = True
            events.append("The party has fallen.")
        return events

    def _enter_tile(self) -> List[str]:
        events: List[str] = []
        t = self.grid[self.y][self.x]
        if t == TREASURE:
            loot = self.rng.randint(10, 40)
            self.gold += loot
            self.grid[self.y][self.x] = FLOOR
            events.append(f"Treasure! +{loot} gold.")
        elif t == TRAP and (self.x, self.y) not in self.sprung_traps:
            self.sprung_traps.add((self.x, self.y))
            dmg = self.rng.randint(2, 5)
            for m in self.party:
                m.hp -= dmg
            events.append(f"A trap springs! {dmg} damage to everyone.")
        elif t == EXIT:
            self.won = True
            events.append("You stagger out into daylight. The delve is complete!")
        # adjacent monsters strike
        for dx, dy in DIRS:
            nx, ny = self.x + dx, self.y + dy
            if 0 <= nx < self.w and 0 <= ny < self.h and self.grid[ny][nx] == MONSTER:
                dmg = self.rng.randint(1, 4)
                victim = self.rng.choice(
                    [m for m in self.party if m.alive] or self.party
                )
                victim.hp -= dmg
                events.append(f"A lurker claws {victim.name} for {dmg}!")
        return events

    def step(self) -> List[str]:
        """Move one tile forward. Returns event lines."""
        if self.won or self.lost:
            return ["The delve is over."]
        dx, dy = DIRS[self.facing]
        nx, ny = self.x + dx, self.y + dy
        if not (0 <= nx < self.w and 0 <= ny < self.h):
            return ["A wall of solid rock. (bump)"]
        t = self.grid[ny][nx]
        if t == WALL:
            return ["A wall. (bump)"]
        if t == DOOR:
            return ["A locked door bars the way. (use open_door with a key)"]
        if t == MONSTER:
            return ["A lurker blocks the corridor - you cannot step through it."]
        self.x, self.y = nx, ny
        events = [f"You step {DIR_NAMES[self.facing]}."]
        events += self._enter_tile()
        events += self._tick_attrition()
        self._update_sight()
        return events

    def turn_left(self) -> List[str]:
        if self.won or self.lost:
            return ["The delve is over."]
        self.facing = (self.facing - 1) % 4
        events = [f"You turn to face {DIR_NAMES[self.facing]}."]
        events += self._tick_attrition()
        self._update_sight()
        return events

    def turn_right(self) -> List[str]:
        if self.won or self.lost:
            return ["The delve is over."]
        self.facing = (self.facing + 1) % 4
        events = [f"You turn to face {DIR_NAMES[self.facing]}."]
        events += self._tick_attrition()
        self._update_sight()
        return events

    def open_door(self) -> List[str]:
        dx, dy = DIRS[self.facing]
        nx, ny = self.x + dx, self.y + dy
        if not (0 <= nx < self.w and 0 <= ny < self.h) or self.grid[ny][nx] != DOOR:
            return ["No door ahead."]
        if self.keys <= 0:
            return ["No keys left."]
        self.keys -= 1
        self.grid[ny][nx] = FLOOR
        self._update_sight()
        return ["The key turns. The door swings open."]

    def search(self) -> List[str]:
        """Reveal traps in the 8 neighboring tiles (a player skill action)."""
        if self.won or self.lost:
            return ["The delve is over."]
        found = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = self.x + dx, self.y + dy
                if (
                    0 <= nx < self.w
                    and 0 <= ny < self.h
                    and self.grid[ny][nx] == TRAP
                    and (nx, ny) not in self.sprung_traps
                ):
                    found.append((nx, ny))
                    self.seen.add((nx, ny))
        events = self._tick_attrition()
        self._update_sight()
        if found:
            return [
                f"You spot {len(found)} trap(s) nearby - marked on your map."
            ] + events
        return ["You find nothing suspicious."] + events

    def attack(self) -> List[str]:
        """Strike an orthogonally adjacent monster. Single opposed roll."""
        if self.won or self.lost:
            return ["The delve is over."]
        for dx, dy in DIRS:
            nx, ny = self.x + dx, self.y + dy
            if 0 <= nx < self.w and 0 <= ny < self.h and self.grid[ny][nx] == MONSTER:
                alive = [m for m in self.party if m.alive]
                if not alive:
                    return ["No one left standing to fight."]
                atk = self.rng.randint(1, 6) + len(alive)
                if atk >= 5:
                    self.grid[ny][nx] = FLOOR
                    loot = self.rng.randint(5, 20)
                    self.gold += loot
                    events = [f"The party slays the lurker! +{loot} gold."]
                else:
                    dmg = self.rng.randint(1, 3)
                    victim = self.rng.choice(alive)
                    victim.hp -= dmg
                    events = [
                        f"The blow misses - the lurker rakes {victim.name} for {dmg}!"
                    ]
                events += self._tick_attrition()
                self._update_sight()
                return events
        return ["No monster in reach."]

    def status(self) -> Dict[str, object]:
        return {
            "pos": (self.x, self.y),
            "facing": DIR_NAMES[self.facing],
            "steps": self.steps,
            "torches": self.torches,
            "torch_burn": self.torch_burn,
            "rations": self.rations,
            "keys": self.keys,
            "gold": self.gold,
            "party": [(m.name, m.hp, m.max_hp) for m in self.party],
            "won": self.won,
            "lost": self.lost,
        }


DEMO_MAP = """\
##########
#..T...#.#
#.##.#.#.#
#D...#.#E#
#.####.#.#
#..^..M#.#
##########\
"""
