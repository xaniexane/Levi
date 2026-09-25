"""LEVI model layer — local-first generation owned by LEVI.

Third-party providers (local model-runners, OpenAI-compatible endpoints)
appear only as labeled references/connectors; LEVI identity is its own.
"""

from levi.model.abstraction import (
    DeterministicFallbackProvider,
    GenerationRequest,
    GenerationResult,
    ModelInfo,
    ModelProvider,
    ModelRouter,
    ModelTier,
    OllamaProvider,
)
from levi.model.relay import ModelRelay, RelayConfig

__all__ = [
    "DeterministicFallbackProvider",
    "GenerationRequest",
    "GenerationResult",
    "ModelInfo",
    "ModelProvider",
    "ModelRouter",
    "ModelTier",
    "ModelRelay",
    "OllamaProvider",
    "RelayConfig",
]
