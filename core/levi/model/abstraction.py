"""
Model Abstraction Layer — Local-first
Discovery: local model-runner (reference: Ollama) → local OpenAI-compatible
→ deterministic offline fallback
Cloud is optional accelerator (disabled by default).

This is the canonical "try local model, else fall back" module — every other
caller routes through ModelRouter. For the persisted-config + diagnostics
wrapper used by the CLI and ops surfaces, see levi.model.relay.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import json
import time
import urllib.request
import urllib.error
import urllib.parse


def _validate_base_url(base_url: Any) -> str:
    """Validate a provider base URL before any request is built from it.

    Only http/https with a real host are accepted — a ``base_url`` becomes
    the request target, so ``file://``, empty hosts, and non-strings are
    rejected loudly instead of failing (or worse) at request time.
    """
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError(f"base_url must be a non-empty string, got {base_url!r}")
    parsed = urllib.parse.urlparse(base_url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(
            f"base_url must be an http(s) URL with a host, got {base_url!r}"
        )
    return base_url.strip().rstrip("/")


def _validate_model_id(model_id: Any) -> str:
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError(f"model_id must be a non-empty string, got {model_id!r}")
    return model_id.strip()


def _validate_request(request: Any) -> "GenerationRequest":
    """Validate a GenerationRequest's wire-relevant fields before sending."""
    if not isinstance(request, GenerationRequest):
        raise ValueError(
            f"request must be a GenerationRequest, got {type(request).__name__}"
        )
    if not isinstance(request.prompt, str) or not request.prompt.strip():
        raise ValueError("request.prompt must be a non-empty string")
    if request.system is not None and not isinstance(request.system, str):
        raise ValueError("request.system must be a string or None")
    if (
        isinstance(request.max_tokens, bool)
        or not isinstance(request.max_tokens, int)
        or not (1 <= request.max_tokens <= 131072)
    ):
        raise ValueError(
            f"request.max_tokens must be an int in 1..131072, got {request.max_tokens!r}"
        )
    if not isinstance(request.temperature, (int, float)) or not (
        0.0 <= request.temperature <= 2.0
    ):
        raise ValueError(
            f"request.temperature must be a number in 0.0..2.0, got {request.temperature!r}"
        )
    if request.stop is not None and (
        not isinstance(request.stop, list)
        or any(not isinstance(s, str) for s in request.stop)
    ):
        raise ValueError("request.stop must be a list of strings or None")
    return request


class ModelTier(str, Enum):
    LOCAL_FAST = "local_fast"
    LOCAL_REASONING = "local_reasoning"
    CLOUD_FAST = "cloud_fast"
    CLOUD_REASONING = "cloud_reasoning"
    EMBEDDING = "embedding"
    FALLBACK = "fallback"


@dataclass
class ModelInfo:
    id: str
    provider: str
    tier: ModelTier
    name: str
    is_local: bool
    context_window: int = 4096
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    capabilities: List[str] = field(default_factory=list)
    available: bool = False


@dataclass
class GenerationRequest:
    prompt: str
    system: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.7
    stop: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    text: str
    model_id: str
    provider: str
    is_local: bool
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    finish_reason: str = "stop"
    error: Optional[str] = None


class ModelProvider(ABC):
    @abstractmethod
    def list_models(self) -> List[ModelInfo]: ...

    @abstractmethod
    def generate(
        self, model_id: str, request: GenerationRequest
    ) -> GenerationResult: ...

    @abstractmethod
    def is_available(self) -> bool: ...


class DeterministicFallbackProvider(ModelProvider):
    """Always-available offline path. Companion-aware, honest about limits."""

    def list_models(self) -> List[ModelInfo]:
        return [
            ModelInfo(
                id="fallback-deterministic",
                provider="levi-local",
                tier=ModelTier.FALLBACK,
                name="Deterministic Fallback",
                is_local=True,
                available=True,
                capabilities=["status", "echo", "template", "companion_stub"],
            )
        ]

    def is_available(self) -> bool:
        return True

    def generate(self, model_id: str, request: GenerationRequest) -> GenerationResult:
        model_id = _validate_model_id(model_id)
        request = _validate_request(request)
        prompt = request.prompt.strip()
        # Full offline companion synthesizer (tone, continuity, alchemy, xyz, chess)
        try:
            from levi.ei.offline_companion import synthesize

            text = synthesize(prompt, system=request.system)
        except Exception:
            text = (
                f"Heard: “{prompt[:120]}”. Offline path hit an error; "
                "core commands still work: status, morning, nervous, mono, factory."
            )
        return GenerationResult(
            text=text,
            model_id=model_id,
            provider="levi-local",
            is_local=True,
            finish_reason="fallback",
        )


class OllamaProvider(ModelProvider):
    """Full chat via the local model-runner HTTP API when available.

    "Ollama" here names the local model-runner reference protocol
    (model ids ``ollama:<name>``); LEVI's identity is its own.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:11434"):
        self.base_url = _validate_base_url(base_url)
        self._available: Optional[bool] = None
        self._models: List[ModelInfo] = []

    def is_available(self) -> bool:
        try:
            with urllib.request.urlopen(
                f"{self.base_url}/api/tags", timeout=1.5
            ) as resp:
                if resp.status != 200:
                    self._available = False
                    return False
                data = json.loads(resp.read().decode("utf-8"))
                self._models = []
                models = data.get("models", []) if isinstance(data, dict) else []
                for m in models:
                    if not isinstance(m, dict):
                        continue
                    name = m.get("name") or m.get("model") or "unknown"
                    self._models.append(
                        ModelInfo(
                            id=f"ollama:{name}",
                            provider="ollama",
                            tier=ModelTier.LOCAL_REASONING,
                            name=name,
                            is_local=True,
                            available=True,
                            capabilities=["chat", "completion"],
                        )
                    )
                self._available = len(self._models) > 0
                if not self._models:
                    # Server up but no models pulled
                    self._models = [
                        ModelInfo(
                            id="ollama:default",
                            provider="ollama",
                            tier=ModelTier.LOCAL_REASONING,
                            name="(no model pulled)",
                            is_local=True,
                            available=False,
                            capabilities=[],
                        )
                    ]
                    self._available = False
                return self._available
        except Exception:
            self._available = False
            self._models = []
            return False

    def list_models(self) -> List[ModelInfo]:
        if self._available is None:
            self.is_available()
        return list(self._models)

    def generate(self, model_id: str, request: GenerationRequest) -> GenerationResult:
        model_id = _validate_model_id(model_id)
        request = _validate_request(request)
        t0 = time.time()
        # model_id like "ollama:llama3.2" or raw name
        name = (
            model_id.split(":", 1)[-1] if model_id.startswith("ollama:") else model_id
        )
        if name in ("default", "(no model pulled)"):
            # pick first available
            avail = [m for m in self.list_models() if m.available]
            if not avail:
                return GenerationResult(
                    text="Ollama is reachable but no model is pulled. Run: ollama pull llama3.2",
                    model_id=model_id,
                    provider="ollama",
                    is_local=True,
                    finish_reason="error",
                    error="no_model",
                )
            name = avail[0].name

        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})

        body = {
            "model": name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            msg = payload.get("message") or {}
            text = msg.get("content") or payload.get("response") or ""
            latency = (time.time() - t0) * 1000
            return GenerationResult(
                text=text.strip() or "(empty model response)",
                model_id=f"ollama:{name}",
                provider="ollama",
                is_local=True,
                tokens_in=int(payload.get("prompt_eval_count") or 0),
                tokens_out=int(payload.get("eval_count") or 0),
                latency_ms=latency,
                finish_reason="stop",
            )
        except Exception as e:
            return GenerationResult(
                text=f"Ollama generation failed: {e}",
                model_id=f"ollama:{name}",
                provider="ollama",
                is_local=True,
                finish_reason="error",
                error=str(e),
                latency_ms=(time.time() - t0) * 1000,
            )


class ModelRouter:
    def __init__(self):
        self.providers: List[ModelProvider] = [
            OllamaProvider(),
            DeterministicFallbackProvider(),
        ]
        self.preferred_local: Optional[str] = None
        self.cloud_enabled: bool = False

    def available_models(self) -> List[ModelInfo]:
        models: List[ModelInfo] = []
        for p in self.providers:
            if p.is_available():
                models.extend(
                    [
                        m
                        for m in p.list_models()
                        if m.available
                        or p.__class__.__name__ == "DeterministicFallbackProvider"
                    ]
                )
        # Always include fallback
        fb = DeterministicFallbackProvider().list_models()
        ids = {m.id for m in models}
        for m in fb:
            if m.id not in ids:
                models.append(m)
        return models

    def select(
        self, prefer_local: bool = True, tier: Optional[ModelTier] = None
    ) -> ModelInfo:
        models = self.available_models()
        local = [
            m
            for m in models
            if m.is_local and m.tier != ModelTier.FALLBACK and m.available
        ]
        if prefer_local and local:
            if self.preferred_local:
                for m in local:
                    if self.preferred_local in m.id or self.preferred_local in m.name:
                        return m
            return local[0]
        non_fb = [m for m in models if m.tier != ModelTier.FALLBACK and m.available]
        if non_fb:
            return non_fb[0]
        return (
            models[-1] if models else DeterministicFallbackProvider().list_models()[0]
        )

    def generate(
        self,
        request: GenerationRequest,
        prefer_local: bool = True,
        model_id: Optional[str] = None,
    ) -> GenerationResult:
        if model_id:
            for p in self.providers:
                for m in p.list_models():
                    if m.id == model_id or m.name == model_id:
                        return p.generate(
                            m.id if m.id.startswith("ollama") else model_id, request
                        )
            # try raw ollama name
            if any(
                isinstance(p, OllamaProvider) and p.is_available()
                for p in self.providers
            ):
                return OllamaProvider().generate(model_id, request)

        info = self.select(prefer_local=prefer_local)
        for p in self.providers:
            for m in p.list_models():
                if m.id == info.id:
                    return p.generate(info.id, request)
        return DeterministicFallbackProvider().generate(
            "fallback-deterministic", request
        )

    def status(self) -> Dict[str, Any]:
        # Force rediscovery
        for p in self.providers:
            if isinstance(p, OllamaProvider):
                p._available = None
        models = self.available_models()
        return {
            "local_available": any(
                m.is_local and m.tier != ModelTier.FALLBACK and m.available
                for m in models
            ),
            "cloud_enabled": self.cloud_enabled,
            "models": [
                {
                    "id": m.id,
                    "provider": m.provider,
                    "name": m.name,
                    "is_local": m.is_local,
                    "tier": m.tier.value,
                    "available": m.available,
                }
                for m in models
            ],
            "invariant": "Core remains fully functional with zero network",
        }
