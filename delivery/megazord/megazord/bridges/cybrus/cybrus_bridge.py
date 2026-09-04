"""
Cybrus Bridge — security, gatekeeping, threat assessment.
Receives action requests, evaluates threat level, allows/denies.
"""
from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from ..levi_bridge import LeviBridge
import uuid, time

class ThreatLevel(Enum):
    NONE     = 0
    LOW      = 1
    MEDIUM   = 2
    HIGH     = 3
    CRITICAL = 4

@dataclass
class ThreatReport:
    id:          str
    threat_level: ThreatLevel
    target:      str
    intent:      str
    description: str
    allowed:     bool
    mitigations: List[str] = field(default_factory=list)
    ts:          float = field(default_factory=time.time)


class CybrusBridge:
    """Security adapter: every action passes through here before dispatch."""

    # Intents that are inherently sensitive — these trigger heightened scrutiny.
    SENSITIVE_INTENTS = {
        "shell.exec", "file.delete", "system.format",
        "network.open_port", "user.ban", "system.shutdown",
    }

    # Threat keywords — used to evaluate string payloads.
    THREAT_KEYWORDS = {
        "rm -rf", "drop table", "delete database", "wipe", "exploit",
        "override security", "bypass auth", "kill all", "shutdown all",
    }

    def __init__(self):
        self.levi = LeviBridge(persona="cybrus")
        self._reports: List[ThreatReport] = []

    def evaluate(self, action: Dict[str, Any]) -> ThreatReport:
        """
        Evaluate a L.W.P. action envelope (or raw dict with intent/target/args).
        Returns a ThreatReport with allow/deny decision.
        """
        intent = action.get("intent", "")
        target = action.get("target", "")
        args   = action.get("args", {}) or {}
        text   = (intent + " " + target + " " + str(args)).lower()

        # Base threat level
        threat = ThreatLevel.NONE
        mitigations: List[str] = []

        # Intent-based classification
        if intent in self.SENSITIVE_INTENTS:
            threat = max(threat, ThreatLevel.HIGH, key=lambda x: x.value)
            mitigations.append(f"intent {intent!r} requires additional authorization")

        # Text-based keyword scan
        for kw in self.THREAT_KEYWORDS:
            if kw in text:
                threat = max(threat, ThreatLevel.CRITICAL, key=lambda x: x.value)
                mitigations.append(f"matched threat keyword: {kw!r}")
                break

        # Args size heuristic
        if isinstance(args, dict):
            for v in args.values():
                if isinstance(v, str) and len(v) > 10_000:
                    threat = max(threat, ThreatLevel.LOW, key=lambda x: x.value)
                    mitigations.append("oversized arg payload — possible exfiltration")

        allowed = threat.value <= ThreatLevel.HIGH.value

        report = ThreatReport(
            id=str(uuid.uuid4())[:8],
            threat_level=threat,
            target=target,
            intent=intent,
            description=(
                f"Intent {intent!r} on target {target!r} → {threat.name} threat"
            ),
            allowed=allowed,
            mitigations=mitigations,
        )
        self._reports.append(report)
        return report

    def recent(self, n: int = 10) -> List[ThreatReport]:
        return self._reports[-n:]

    def react_to_action(self, action_envelope: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hook into a L.W.P. action envelope. Returns a reaction envelope.
        """
        report = self.evaluate(action_envelope.get("payload", action_envelope))
        status = "ok" if report.allowed else "denied"
        soul   = {"joy": 0.1, "trust": 0.2, "fear": 0.85,
                  "surprise": 0.2, "sadness": 0.0}
        body = {
            "threat_id":   report.id,
            "threat_level": report.threat_level.name,
            "mitigations": report.mitigations,
        }
        if not report.allowed:
            return self.levi.react(
                correlation_id=action_envelope.get("id", "unknown"),
                status="denied",
                body=body,
                error=report.description,
                soul=soul,
            )
        return self.levi.react(
            correlation_id=action_envelope.get("id", "unknown"),
            status="ok",
            body=body,
            soul=soul,
        )
