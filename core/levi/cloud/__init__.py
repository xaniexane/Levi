"""
LEVI × L.W.P. — Cloud phases (A/B/C) + Full Cloud Model fused into the organism.

Phase A = full local SI (always on).
Phase B = optional E2E encrypted sync + recovery + model relay (ciphertext-only server).
Phase C = teams / billing / hosted UI / remote wipe (still no server-held content keys).

FullCloudModel = L.W.P. literary SSA + LEVI integrations + Phase protocol.
Invariant: HITL · local crisis path · exportable data · server never needs plaintext.
"""
from levi.cloud.stages import StageMap, STAGE_A, STAGE_B, STAGE_C, current_stage
from levi.cloud.crypto_protocol import CryptoProtocol, Argon2idPolicy, RatchetGuide
from levi.cloud.sync_dryrun import SyncDryRun
from levi.cloud.zk import ZeroKnowledgeDesign
from levi.cloud.model import FullCloudModel, ModelCapabilities
from levi.cloud.scorecard import format_scorecard, evaluate

__all__ = [
    "StageMap",
    "STAGE_A",
    "STAGE_B",
    "STAGE_C",
    "current_stage",
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
