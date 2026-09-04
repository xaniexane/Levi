"""
LEVI × L.W.P. — Cloud phases (A/B/C) + Full Cloud Model fused into the organism.

Phase A = full local SI (always on).
Phase B = optional E2E encrypted sync + recovery + model relay (ciphertext-only server).
Phase C = teams / billing / hosted UI / remote wipe (still no server-held content keys).

FullCloudModel = L.W.P. literary SSA + LEVI integrations + Phase protocol.
Invariant: HITL · local crisis path · exportable data · server never needs plaintext.
"""
from levi.cloud.phases import PhaseMap, PHASE_A, PHASE_B, PHASE_C, current_phase
from levi.cloud.crypto_protocol import CryptoProtocol, Argon2idPolicy, RatchetGuide
from levi.cloud.sync_dryrun import SyncDryRun
from levi.cloud.zk import ZeroKnowledgeDesign
from levi.cloud.model import FullCloudModel, ModelCapabilities
from levi.cloud.scorecard import format_scorecard, evaluate

__all__ = [
    "PhaseMap",
    "PHASE_A",
    "PHASE_B",
    "PHASE_C",
    "current_phase",
    "CryptoProtocol",
    "Argon2idPolicy",
    "RatchetGuide",
    "SyncDryRun",
    "ZeroKnowledgeDesign",
    "FullCloudModel",
    "ModelCapabilities",
    "format_scorecard",
    "evaluate",
]
