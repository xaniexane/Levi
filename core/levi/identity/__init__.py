"""Identity variant engine — Echo/Mandella variant loop with REIM/RIEM.

Reflect an identity (Echo), reconstruct it into controlled variants
(Mandella), compost outcomes (REIM), compress lessons into heritable genome
(RIEM, controlled compression). Whole-organism scope reflects every
manifest-declared module.
"""

from levi.identity.cycle import IdentityCycle
from levi.identity.echo import EchoEngine, Reflection, reflection_to_dict
from levi.identity.genome import GenomeStore
from levi.identity.mandella import MandellaEngine
from levi.identity.reim import REIM
from levi.identity.riem import RIEM
from levi.identity.scope import iter_module_identities, module_identity

__all__ = [
    "EchoEngine",
    "MandellaEngine",
    "REIM",
    "RIEM",
    "GenomeStore",
    "IdentityCycle",
    "Reflection",
    "reflection_to_dict",
    "iter_module_identities",
    "module_identity",
]
