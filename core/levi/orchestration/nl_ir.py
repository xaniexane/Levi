"""
NL → IR (Natural Language to Intermediate Representation)

When the user builds or automates, natural language is compiled into a
structured IR before Factory / Automation DNA executes.

Local-first: deterministic compiler + optional model refinement later.
IR is first-class and interpenetrable with L.W.P. graph nodes.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from enum import Enum
import re
import uuid


class IRKind(str, Enum):
    BUILD = "build"
    AUTOMATE = "automate"
    UNKNOWN = "unknown"


class ArtifactType(str, Enum):
    CLI = "cli"
    LIBRARY = "library"
    SCRIPT = "script"
    SERVICE = "service"
    AUTOMATION = "automation"
    OTHER = "other"


@dataclass
class BuildIR:
    """Intermediate representation for constructive (Factory) intents."""

    id: str
    kind: IRKind
    raw: str
    name: str
    goal: str
    artifact_type: ArtifactType = ArtifactType.CLI
    language: str = "python"
    offline: bool = True
    storage: Optional[str] = None  # sqlite | json | none
    features: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    stack: List[str] = field(default_factory=list)
    risk_ceiling: int = 2
    confidence: float = 0.6
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["artifact_type"] = self.artifact_type.value
        return d

    def to_factory_idea(self) -> str:
        parts = [
            f"GOAL: {self.goal}",
            f"NAME: {self.name}",
            f"ARTIFACT: {self.artifact_type.value}",
            f"LANG: {self.language}",
            f"OFFLINE: {self.offline}",
        ]
        if self.storage:
            parts.append(f"STORAGE: {self.storage}")
        if self.features:
            parts.append(f"FEATURES: {', '.join(self.features)}")
        if self.constraints:
            parts.append(f"CONSTRAINTS: {', '.join(self.constraints)}")
        if self.stack:
            parts.append(f"STACK: {', '.join(self.stack)}")
        return " | ".join(parts)


@dataclass
class AutomateIR:
    """Intermediate representation for automation intents."""

    id: str
    kind: IRKind
    raw: str
    name: str
    goal: str
    trigger: str = "manual"  # manual | schedule | event
    schedule: Optional[str] = None
    actions: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    risk_ceiling: int = 1
    confidence: float = 0.6
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d


def _slug_name(text: str, fallback: str = "project") -> str:
    t = text.lower().strip()
    # Try quoted name
    m = re.search(r"[\"']([^\"']+)[\"']", text)
    if m:
        return (
            re.sub(r"[^a-z0-9_]+", "_", m.group(1).lower())[:40].strip("_") or fallback
        )
    # "called X" / "named X"
    m = re.search(r"(?:called|named)\s+([a-zA-Z0-9_-]+)", t)
    if m:
        return m.group(1)[:40]
    # first meaningful chunk after build/make
    m = re.search(
        r"(?:build|make|create|scaffold)\s+(?:me\s+)?(?:a\s+|an\s+)?(.+?)(?:\s+with\s+|\s+using\s+|$)",
        t,
    )
    if m:
        chunk = re.sub(r"[^a-z0-9\s]", "", m.group(1)).strip()
        words = [
            w
            for w in chunk.split()
            if w
            not in {
                "a",
                "an",
                "the",
                "local",
                "offline",
                "simple",
                "tiny",
                "small",
                "new",
            }
        ][:4]
        if words:
            return "_".join(words)[:40]
    return fallback


class NLIRCompiler:
    """
    Compile natural language → BuildIR or AutomateIR.
    Deterministic rules first; model can refine later when available.
    """

    BUILD_HINTS = (
        "build",
        "make me",
        "make a",
        "create a",
        "create an",
        "scaffold",
        "factory",
        "new project",
        "write a",
        "generate a",
        "implement a",
    )
    AUTO_HINTS = (
        "automate",
        "every day",
        "every morning",
        "schedule",
        "whenever",
        "when i",
        "cron",
        "remind me to run",
        "on startup",
    )

    def _require_text(self, text: str, what: str) -> str:
        """Natural-language input must be a non-empty string."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                f"NLIRCompiler.{what}: 'text' must be a non-empty string, got {text!r}"
            )
        return text

    def classify(self, text: str) -> IRKind:
        text = self._require_text(text, "classify")
        t = text.lower().strip()
        auto_score = sum(1 for h in self.AUTO_HINTS if h in t)
        build_score = sum(1 for h in self.BUILD_HINTS if h in t)
        if auto_score > build_score and auto_score > 0:
            return IRKind.AUTOMATE
        if build_score > 0:
            return IRKind.BUILD
        if any(w in t for w in ("app", "cli", "tool", "script", "service")):
            return IRKind.BUILD
        return IRKind.UNKNOWN

    def compile(self, text: str) -> BuildIR | AutomateIR:
        text = self._require_text(text, "compile")
        kind = self.classify(text)
        if kind == IRKind.AUTOMATE:
            return self.compile_automate(text)
        if kind == IRKind.BUILD:
            return self.compile_build(text)
        # Default constructive lean if ambiguous but action-like
        return self.compile_build(text)

    def compile_build(self, text: str) -> BuildIR:
        text = self._require_text(text, "compile_build")
        t = text.lower()
        notes: List[str] = []
        features: List[str] = []
        constraints: List[str] = []
        stack: List[str] = []

        artifact = ArtifactType.CLI
        if any(w in t for w in ("library", "package", "module", "sdk")):
            artifact = ArtifactType.LIBRARY
        elif any(w in t for w in ("service", "api", "server", "daemon")):
            artifact = ArtifactType.SERVICE
        elif any(w in t for w in ("script", "one-off", "oneshot")):
            artifact = ArtifactType.SCRIPT
        elif "cli" in t or "command line" in t or "terminal" in t:
            artifact = ArtifactType.CLI
        elif "app" in t or "tool" in t:
            artifact = ArtifactType.CLI
            notes.append("defaulted app/tool → cli artifact")

        language = "python"
        if "javascript" in t or "node" in t or "typescript" in t:
            language = "javascript"
            stack.append("node")
        elif "rust" in t:
            language = "rust"
        elif "go " in t or t.endswith(" go") or " golang" in t:
            language = "go"
        elif "python" in t or "sqlite" in t:
            language = "python"

        offline = True
        if any(w in t for w in ("cloud", "saas", "hosted", "online only")):
            offline = False
            constraints.append("cloud_ok")
        else:
            constraints.append("local-first")

        storage = None
        if "sqlite" in t:
            storage = "sqlite"
            stack.append("sqlite")
            features.append("persistence")
        elif "json" in t and "file" in t:
            storage = "json"
            features.append("file_persistence")

        for feat, keys in [
            ("checklist", ("checklist", "todo", "tasks")),
            ("notes", ("notes", "memo")),
            ("timer", ("timer", "countdown")),
            ("status", ("status", "health")),
            ("auth", ("login", "auth", "password")),
        ]:
            if any(k in t for k in keys):
                features.append(feat)

        if "offline" in t or "local" in t:
            constraints.append("offline")
        if "no network" in t or "airgap" in t:
            constraints.append("airgap")

        name = _slug_name(text, fallback="levi_app")
        goal = text.strip()
        conf = 0.55
        if artifact != ArtifactType.OTHER:
            conf += 0.1
        if storage:
            conf += 0.1
        if features:
            conf += 0.05
        conf = min(conf, 0.95)

        return BuildIR(
            id=f"ir.build.{uuid.uuid4().hex[:10]}",
            kind=IRKind.BUILD,
            raw=text,
            name=name,
            goal=goal,
            artifact_type=artifact,
            language=language,
            offline=offline,
            storage=storage,
            features=sorted(set(features)),
            constraints=sorted(set(constraints)),
            stack=sorted(set(stack)),
            risk_ceiling=2 if artifact != ArtifactType.SERVICE else 3,
            confidence=conf,
            notes=notes,
        )

    def compile_automate(self, text: str) -> AutomateIR:
        text = self._require_text(text, "compile_automate")
        t = text.lower()
        trigger = "manual"
        schedule = None
        if "every morning" in t or "daily" in t or "every day" in t:
            trigger = "schedule"
            schedule = "daily"
        elif "every hour" in t:
            trigger = "schedule"
            schedule = "hourly"
        elif "when" in t or "whenever" in t:
            trigger = "event"

        actions: List[str] = []
        if "status" in t:
            actions.append("status")
        if "backup" in t:
            actions.append("backup")
        if "remember" in t:
            actions.append("remember")
        if "factory" in t or "build" in t:
            actions.append("factory_status")
        if not actions:
            actions.append("status")

        name = _slug_name(text, fallback="automation")
        return AutomateIR(
            id=f"ir.auto.{uuid.uuid4().hex[:10]}",
            kind=IRKind.AUTOMATE,
            raw=text,
            name=name,
            goal=text.strip(),
            trigger=trigger,
            schedule=schedule,
            actions=actions,
            conditions=[],
            risk_ceiling=1,
            confidence=0.6,
        )


def compile_nl(text: str) -> Dict[str, Any]:
    """Public helper: always returns dict IR."""
    ir = NLIRCompiler().compile(text)
    return ir.to_dict()
