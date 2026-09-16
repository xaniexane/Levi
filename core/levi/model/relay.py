"""
Model Relay — config + diagnostics wrapper over the canonical router.

Deliberate division of labor (not a competing implementation — see
blueprint §3 and the King precedent):

  * levi.model.abstraction.ModelRouter is the ONE place "try local model,
    else fall back" logic lives. It owns the provider chain:
    Ollama (if up) → deterministic offline companion synthesizer.
  * This module adds: a persisted RelayConfig (~/.levi/model_relay.json),
    a probe for the local model-runner reference (Ollama protocol), and a
    self-test/status surface used by the CLI (`levi relay`) and ops/health
    callers. generate() delegates to the router — it does not reimplement
    the chain.

Note: RelayConfig.cloud_endpoints is a declared-but-unwired contract
(config-ready slots; keys via env, never hardcoded). The chain today is
Ollama → offline synthesizer; nothing sends cloud traffic yet. When a
cloud provider is wired into abstraction.ModelRouter, these slots become
live.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
import json

from levi.model.abstraction import (
    GenerationRequest,
    GenerationResult,
    ModelRouter,
)


DEFAULT = Path.home() / ".levi" / "model_relay.json"


@dataclass
class RelayConfig:
    prefer_local: bool = True
    cloud_endpoints: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def _clean_endpoints(cls, raw: Any) -> List[Dict[str, str]]:
        """Filter a persisted endpoint list down to well-formed entries.

        Config files are user-editable, so malformed entries degrade to
        "dropped" rather than raising — the relay still starts.
        """
        if not isinstance(raw, list):
            return []
        cleaned: List[Dict[str, str]] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            url = entry.get("url", "")
            if not isinstance(url, str) or not url.strip():
                continue
            cleaned.append(
                {
                    k: str(v)
                    for k, v in entry.items()
                    if isinstance(k, str) and isinstance(v, (str, int, float, bool))
                }
            )
        return cleaned

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "RelayConfig":
        p = Path(path).expanduser() if path else DEFAULT
        if not p.exists():
            return cls()
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(d, dict):
                return cls()
            return cls(
                prefer_local=bool(d.get("prefer_local", True)),
                cloud_endpoints=cls._clean_endpoints(d.get("cloud_endpoints")),
            )
        except (OSError, ValueError):
            return cls()

    def save(self, path: Optional[Path] = None) -> None:
        p = Path(path).expanduser() if path else DEFAULT
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
        tmp.replace(p)


class ModelRelay:
    """Ordered generation: local → cloud config → offline."""

    def __init__(self, config: Optional[RelayConfig] = None):
        self.config = config or RelayConfig.load()
        self.router = ModelRouter()

    def generate(self, prompt: str, system: Optional[str] = None) -> GenerationResult:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("relay prompt must be a non-empty string")
        if system is not None and not isinstance(system, str):
            raise ValueError("relay system must be a string or None")
        req = GenerationRequest(prompt=prompt, system=system)
        return self.router.generate(req)

    def probe_ollama(self) -> Dict[str, Any]:
        import urllib.request

        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:11434/api/tags", timeout=2
            ) as r:
                data = json.loads(r.read().decode())
                entries = (data.get("models") if isinstance(data, dict) else None) or []
                models = [m.get("name", "") for m in entries if isinstance(m, dict)]
                return {"up": True, "models": [m for m in models if m][:12]}
        except Exception as e:
            return {"up": False, "error": str(e)[:120], "models": []}

    def test(self) -> str:
        lines = ["=== Model Relay TEST ===", ""]
        ol = self.probe_ollama()
        if ol.get("up"):
            lines.append(
                "Local model-runner (Ollama reference): UP  models=%s"
                % (ol.get("models") or ["(none)"])
            )
        else:
            lines.append(
                "Local model-runner (Ollama reference): down (%s) — OK; offline path required"
                % ol.get("error", "n/a")
            )
        try:
            res = self.generate("relay test ping", system="Reply with one short line.")
            ok = bool(res.text)
            lines.append("Offline/chain generate: %s" % ("PASS" if ok else "FAIL"))
            lines.append(
                "  provider=%s model=%s local=%s"
                % (res.provider, res.model_id, res.is_local)
            )
            lines.append("  text_head=%r" % ((res.text or "")[:120],))
        except Exception as e:
            lines.append("Offline/chain generate: FAIL %s" % e)
        lines.append("")
        lines.append("Policy: crisis/regulation must never require paid cloud.")
        lines.append(self.status())
        return "\n".join(lines)

    def status(self) -> str:
        lines = [
            "=== LEVI Model Relay ===",
            f"prefer_local: {self.config.prefer_local}",
            f"cloud_endpoints configured: {len(self.config.cloud_endpoints)}",
            "Chain: Ollama (if available) → offline companion synthesizer",
            "Cloud slots are config-ready; keys via env — never hardcode secrets.",
        ]
        return "\n".join(lines)
