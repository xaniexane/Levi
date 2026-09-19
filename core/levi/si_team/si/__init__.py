"""Native SI cores — pure LEVI-native synthetic reasoning per role.

Rules-engine based today; stdlib only; local-first. Each core owns its
own weights-path convention and corpus note, and honestly reports which
substrate actually answered. The SI core never imports from ai/.
"""

from __future__ import annotations

from typing import Dict, List

from levi.si_team.si import alpha as _alpha
from levi.si_team.si import core as _core
from levi.si_team.si import dweller as _dweller
from levi.si_team.si import levi as _levi
from levi.si_team.si import omega as _omega

SiCore = _core.SiCore


CORES: Dict[str, SiCore] = {
    "levi": _levi.LeviCore(),
    "alpha": _alpha.AlphaCore(),
    "omega": _omega.OmegaCore(),
    "dweller": _dweller.DwellerCore(),
}


def get_core(role: str) -> SiCore | None:
    return CORES.get((role or "").strip().lower())


def list_cores() -> List[str]:
    return list(CORES)
