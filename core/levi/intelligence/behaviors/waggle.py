"""Waggle dance — honeybee symbolic vector communication (class BEE, echo).

Real mechanism (von Frisch, Nobel 1973): on the vertical comb, the angle
of the waggle run relative to gravity encodes the flight angle relative
to the sun's azimuth; the waggle-run duration encodes distance; tempo
encodes profitability. Followers average several runs. Translated: a
lossless symbolic vector codec — direction + distance + quality in one
dance, decodable by any agent holding the same sun reference.
"""

from __future__ import annotations

import math
from typing import Dict


def encode(bearing_deg: float, distance_m: float, quality: float) -> Dict[str, float]:
    """Encode a resource vector as a waggle dance.

    bearing_deg: compass bearing from hive to resource (0-360).
    distance_m: meters to resource. quality: 0.0-1.0 profitability.
    Returns the dance parameters a follower would observe.
    """
    assert 0.0 <= quality <= 1.0
    assert distance_m >= 0.0
    waggle_angle = bearing_deg % 360.0  # vs. gravity == vs. sun azimuth
    waggle_duration = distance_m / 300.0  # ~1s per 300m (von Frisch scale)
    tempo = 1.0 + 9.0 * quality  # circuits per bout scale with profit
    return {
        "waggle_angle": waggle_angle,
        "waggle_duration": waggle_duration,
        "tempo": tempo,
    }


def decode(dance: Dict[str, float], sun_azimuth_deg: float) -> Dict[str, float]:
    """Decode a dance back to a resource vector.

    Followers average runs; here one averaged dance decodes exactly.
    """
    bearing = (dance["waggle_angle"] + sun_azimuth_deg) % 360.0
    distance = dance["waggle_duration"] * 300.0
    quality = max(0.0, min(1.0, (dance["tempo"] - 1.0) / 9.0))
    return {
        "bearing_deg": bearing,
        "distance_m": distance,
        "quality": quality,
    }


def angular_error(a: float, b: float) -> float:
    """Smallest angular distance between two bearings in degrees."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


assert math.isclose(angular_error(10.0, 350.0), 20.0)
