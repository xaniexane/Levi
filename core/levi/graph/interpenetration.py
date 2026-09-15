"""
Interpenetration / Composition Engine

Everything interpenetrates:
  personas × skills × specialists × automations × companion roles × L.W.P. primitives

Composites inherit the strictest risk ceiling, remain policy-gated,
and can be registered back into the Capability Graph.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set
from enum import Enum
from datetime import datetime, timezone
import uuid
import json
from pathlib import Path


class NodeKind(str, Enum):
    PERSONA = "persona"
    SKILL = "skill"
    SPECIALIST = "specialist"
    AUTOMATION = "automation"
    COMPANION_ROLE = "companion_role"
    EI_DIMENSION = "ei_dimension"
    LWP_PRIMITIVE = "lwp_primitive"
    COMPOSITE = "composite"
    MEMORY_TYPE = "memory_type"
    GENRE = "genre"


@dataclass
class GraphNode:
    id: str
    kind: NodeKind
    name: str
    description: str = ""
    risk_ceiling: int = 1
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    relation: str  # composes_with | requires | enhances | transfers_to | constrains
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Composite:
    """A verified composition of interpenetrating parts."""

    id: str
    name: str
    description: str
    parts: List[str]  # node ids
    risk_ceiling: int
    created_at: str
    verified: bool = False
    behavior_summary: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DEFAULT_GRAPH_DIR = Path.home() / ".levi" / "graph"

# Circuit Breaker / Governor bounds — combinatorial space is open but not unbounded
MAX_COMPOSITION_DEPTH = 8  # max ancestry depth for a composite
MAX_PARTS_PER_COMPOSITE = 12  # max direct parts
MAX_COMPOSITES = 500  # soft cap on stored composites
MAX_GRAPH_NODES = 2000  # soft cap on total nodes


class InterpenetrationEngine:
    """
    Lightweight Capability Graph + composition.
    Phase 1: in-memory + file persistence. No unbound self-modification.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_GRAPH_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self.composites: Dict[str, Composite] = {}
        self._seed_core_nodes()
        self._load()

    def _seed_core_nodes(self) -> None:
        """Seed with known first-class entities so interpenetration has material."""
        seeds = [
            # Companion roles
            GraphNode(
                "role.friend",
                NodeKind.COMPANION_ROLE,
                "Best Friend",
                "Reliable presence and continuity",
                1,
                ["companion"],
            ),
            GraphNode(
                "role.mentor",
                NodeKind.COMPANION_ROLE,
                "Mentor",
                "Teaches and grows capability",
                1,
                ["companion"],
            ),
            GraphNode(
                "role.challenger",
                NodeKind.COMPANION_ROLE,
                "Challenger",
                "Surfaces weak assumptions",
                2,
                ["companion"],
            ),
            GraphNode(
                "role.protector",
                NodeKind.COMPANION_ROLE,
                "Protector",
                "Guards against irreversible harm",
                4,
                ["companion"],
            ),
            # Key personas
            GraphNode(
                "persona.interrogation",
                NodeKind.PERSONA,
                "Interrogation",
                "Questions the user; withholds answer until demanded",
                1,
                ["persona"],
            ),
            GraphNode(
                "persona.no_hero",
                NodeKind.PERSONA,
                "No Hero",
                "Short/vague; expands on request",
                1,
                ["persona"],
            ),
            GraphNode(
                "persona.reframe",
                NodeKind.PERSONA,
                "Reframe",
                "Better question then answers that",
                1,
                ["persona"],
            ),
            GraphNode(
                "persona.void",
                NodeKind.PERSONA,
                "Void",
                "Dry, precise, anti-hype",
                1,
                ["persona"],
            ),
            GraphNode(
                "persona.strategist",
                NodeKind.PERSONA,
                "Strategist",
                "Goals, sequence, tradeoffs",
                1,
                ["persona"],
            ),
            # Specialists
            GraphNode(
                "spec.supervisor",
                NodeKind.SPECIALIST,
                "Supervisor",
                "Coordinates decomposition and synthesis",
                3,
                ["agent"],
            ),
            GraphNode(
                "spec.companion",
                NodeKind.SPECIALIST,
                "Companion Specialist",
                "Ensures companion framing",
                2,
                ["agent"],
            ),
            GraphNode(
                "spec.research",
                NodeKind.SPECIALIST,
                "Research",
                "Search, retrieve, synthesize",
                1,
                ["agent"],
            ),
            GraphNode(
                "spec.memory",
                NodeKind.SPECIALIST,
                "Memory",
                "Recall/remember/summarize",
                1,
                ["agent"],
            ),
            GraphNode(
                "spec.coding",
                NodeKind.SPECIALIST,
                "Coding",
                "Code within sandbox",
                3,
                ["agent"],
            ),
            GraphNode(
                "spec.security",
                NodeKind.SPECIALIST,
                "Security",
                "Risk and policy review",
                4,
                ["agent"],
            ),
            GraphNode(
                "spec.automation",
                NodeKind.SPECIALIST,
                "Automation",
                "Workflow design and run",
                3,
                ["agent"],
            ),
            # Skills
            GraphNode(
                "skill.remember",
                NodeKind.SKILL,
                "Remember",
                "Store semantic memory",
                1,
                ["skill"],
            ),
            GraphNode(
                "skill.recall",
                NodeKind.SKILL,
                "Recall",
                "Search memories",
                0,
                ["skill"],
            ),
            GraphNode(
                "skill.phase1_checklist",
                NodeKind.SKILL,
                "Phase1 Checklist",
                "Progress checklist",
                0,
                ["skill"],
            ),
            GraphNode(
                "skill.status", NodeKind.SKILL, "Status", "System health", 0, ["skill"]
            ),
            GraphNode(
                "skill.factory_create",
                NodeKind.SKILL,
                "Factory Create",
                "Software Factory project from idea",
                1,
                ["skill", "factory"],
            ),
            GraphNode(
                "skill.factory_advance",
                NodeKind.SKILL,
                "Factory Advance",
                "Advance factory pipeline stage",
                2,
                ["skill", "factory"],
            ),
            GraphNode(
                "cap.software_factory",
                NodeKind.SPECIALIST,
                "Software Factory",
                "LEVI-native software factory capability",
                3,
                ["factory", "capability"],
            ),
            GraphNode(
                "cap.automation_runtime",
                NodeKind.SPECIALIST,
                "Automation Runtime",
                "LEVI automation execution",
                3,
                ["automation", "capability"],
            ),
            # L.W.P. primitives (conceptual seeds)
            GraphNode(
                "lwp.cascade",
                NodeKind.LWP_PRIMITIVE,
                "Cascade Chain",
                "Typed deterministic sequence",
                2,
                ["lwp"],
            ),
            GraphNode(
                "lwp.spiral",
                NodeKind.LWP_PRIMITIVE,
                "Spiral Coil",
                "Iterative feedback workflow",
                2,
                ["lwp"],
            ),
            GraphNode(
                "lwp.governor",
                NodeKind.LWP_PRIMITIVE,
                "Governor",
                "Dynamic budget/complexity control",
                3,
                ["lwp"],
            ),
            GraphNode(
                "lwp.circuit_breaker",
                NodeKind.LWP_PRIMITIVE,
                "Circuit Breaker",
                "Resource/risk limiter",
                4,
                ["lwp"],
            ),
            GraphNode(
                "lwp.bible",
                NodeKind.LWP_PRIMITIVE,
                "Bible",
                "Immutable verified canon",
                1,
                ["lwp"],
            ),
            GraphNode(
                "lwp.banks",
                NodeKind.LWP_PRIMITIVE,
                "Banks",
                "Versioned approved stores",
                1,
                ["lwp"],
            ),
        ]
        for n in seeds:
            self.nodes[n.id] = n

        # Seed ALL L.W.P. formal genres (97) — never truncate
        try:
            from levi.graph.genres import GenreRegistry

            greg = GenreRegistry()
            for g in greg.list():
                nid = f"genre.{g.id}"
                self.nodes[nid] = GraphNode(
                    id=nid,
                    kind=NodeKind.GENRE,
                    name=g.id,
                    description=f"L.W.P. genre: {g.id} ({g.category.value})",
                    risk_ceiling=1,
                    tags=["genre", "lwp", g.category.value],
                )
        except Exception:
            pass  # genres module optional at import time

        # Software Factory DNA — stages and capabilities as first-class interpenetrable nodes
        factory_seeds = [
            ("factory.stage.idea", "Idea", "Factory cascade stage: idea capture"),
            (
                "factory.stage.requirements",
                "Requirements",
                "Factory cascade stage: requirements",
            ),
            (
                "factory.stage.architecture",
                "Architecture",
                "Factory cascade stage: architecture",
            ),
            ("factory.stage.scaffold", "Scaffold", "Factory cascade stage: scaffold"),
            (
                "factory.stage.implement",
                "Implement",
                "Factory cascade stage: implement",
            ),
            ("factory.stage.build", "Build", "Factory cascade stage: build"),
            ("factory.stage.test", "Test", "Factory cascade stage: test"),
            ("factory.stage.package", "Package", "Factory cascade stage: package"),
            (
                "factory.ability.codegen",
                "Codegen Ability",
                "Generate code under sandbox",
            ),
            ("factory.ability.verify", "Verify Ability", "Verify factory outputs"),
            (
                "factory.ability.rollback",
                "Rollback Ability",
                "Roll back factory artifacts",
            ),
        ]
        for fid, fname, fdesc in factory_seeds:
            self.nodes[fid] = GraphNode(
                id=fid,
                kind=NodeKind.SKILL if "ability" in fid else NodeKind.LWP_PRIMITIVE,
                name=fname,
                description=fdesc,
                risk_ceiling=3 if "implement" in fid or "codegen" in fid else 2,
                tags=["factory", "dna", "interpenetrable"],
            )

        # Seed useful edges (interpenetration hints)
        seed_edges = [
            ("persona.interrogation", "spec.research", "composes_with"),
            ("persona.interrogation", "skill.recall", "composes_with"),
            ("persona.no_hero", "role.mentor", "enhances"),
            ("persona.reframe", "role.challenger", "enhances"),
            ("role.protector", "spec.security", "requires"),
            ("role.protector", "lwp.circuit_breaker", "enhances"),
            ("spec.automation", "lwp.cascade", "composes_with"),
            ("spec.automation", "lwp.spiral", "composes_with"),
            ("spec.coding", "lwp.governor", "constrained_by"),
            ("skill.remember", "spec.memory", "requires"),
            ("skill.recall", "spec.memory", "requires"),
            ("role.friend", "role.mentor", "composes_with"),
            ("role.mentor", "role.challenger", "composes_with"),
            ("role.challenger", "role.protector", "composes_with"),
            # Genre interpenetration (examples — all 97 are nodes and fully composable)
            ("genre.systems_horror", "persona.void", "composes_with"),
            ("genre.memory_thriller", "spec.memory", "composes_with"),
            ("genre.interpenetration_romance", "role.friend", "composes_with"),
            ("genre.cascade_realism", "lwp.cascade", "enhances"),
            ("genre.daemon_comedy", "persona.drunk", "composes_with"),
            ("genre.platform_gothic", "genre.data_haunting", "composes_with"),
            ("genre.algorithmic_fate", "lwp.governor", "constrained_by"),
            ("genre.continuity_horror", "lwp.bible", "enhances"),
            ("genre.noir", "genre.post_privacy_noir", "composes_with"),
            ("genre.sci_fi", "genre.cyberpunk", "composes_with"),
            # Factory DNA interpenetration — same formula as everything in LEVI
            ("cap.software_factory", "lwp.cascade", "requires"),
            ("cap.software_factory", "lwp.spiral", "composes_with"),
            ("cap.software_factory", "lwp.governor", "constrained_by"),
            ("cap.software_factory", "lwp.circuit_breaker", "constrained_by"),
            ("cap.software_factory", "role.protector", "requires"),
            ("cap.software_factory", "spec.coding", "composes_with"),
            ("cap.software_factory", "spec.verification", "composes_with"),
            ("cap.software_factory", "persona.strategist", "enhances"),
            ("cap.software_factory", "persona.interrogation", "composes_with"),
            ("factory.stage.implement", "spec.coding", "requires"),
            ("factory.stage.test", "spec.verification", "requires"),
            ("factory.ability.codegen", "lwp.governor", "constrained_by"),
            ("factory.ability.rollback", "role.protector", "enhances"),
            ("skill.factory_create", "cap.software_factory", "requires"),
            ("skill.factory_advance", "lwp.cascade", "enhances"),
            ("cap.automation_runtime", "cap.software_factory", "composes_with"),
            ("genre.cascade_realism", "cap.software_factory", "enhances"),
            ("genre.daemon_comedy", "cap.software_factory", "composes_with"),
        ]
        for src, tgt, rel in seed_edges:
            if src in self.nodes and tgt in self.nodes:
                self.edges.append(GraphEdge(src, tgt, rel))

    def _load(self) -> None:
        path = self.data_dir / "composites.json"
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                for c in raw.get("composites", []):
                    comp = Composite(**c)
                    self.composites[comp.id] = comp
                    # Also surface composite as a node
                    self.nodes[comp.id] = GraphNode(
                        id=comp.id,
                        kind=NodeKind.COMPOSITE,
                        name=comp.name,
                        description=comp.description,
                        risk_ceiling=comp.risk_ceiling,
                        tags=comp.tags + ["composite"],
                    )
            except Exception:
                pass

    def _persist(self) -> None:
        path = self.data_dir / "composites.json"
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "composites": [c.to_dict() for c in self.composites.values()],
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _ancestry_depth(self, node_id: str, seen: Optional[Set[str]] = None) -> int:
        """Depth of composite ancestry (0 = leaf)."""
        if node_id not in self.nodes:
            return 0
        node = self.nodes[node_id]
        if node.kind != NodeKind.COMPOSITE:
            return 0
        seen = seen or set()
        if node_id in seen:
            return 0  # cycle guard
        seen.add(node_id)
        comp = self.composites.get(node_id)
        if not comp or not comp.parts:
            return 1
        return 1 + max(self._ancestry_depth(p, seen) for p in comp.parts)

    def propose_composite(
        self,
        name: str,
        part_ids: List[str],
        description: str = "",
        behavior_summary: str = "",
        tags: Optional[List[str]] = None,
    ) -> Composite:
        """
        Propose a new composite from existing nodes (including other composites).
        Recursive interpenetration: composites of composites are legal.
        Risk ceiling = max of parts. Bounded by Circuit Breaker.
        Not auto-promoted; verified=False until approved.
        """
        if len(self.composites) >= MAX_COMPOSITES:
            raise RuntimeError(
                f"Circuit breaker: max composites ({MAX_COMPOSITES}) reached"
            )
        if len(self.nodes) >= MAX_GRAPH_NODES:
            raise RuntimeError(
                f"Circuit breaker: max graph nodes ({MAX_GRAPH_NODES}) reached"
            )
        if len(part_ids) > MAX_PARTS_PER_COMPOSITE:
            raise ValueError(
                f"Circuit breaker: max {MAX_PARTS_PER_COMPOSITE} parts per composite"
            )
        if len(part_ids) < 2:
            raise ValueError("A composite needs at least 2 parts")

        missing = [p for p in part_ids if p not in self.nodes]
        if missing:
            raise KeyError(f"Unknown parts: {missing}")

        # Depth check: new composite depth = 1 + max part depth
        part_depths = [self._ancestry_depth(p) for p in part_ids]
        new_depth = 1 + max(part_depths)
        if new_depth > MAX_COMPOSITION_DEPTH:
            raise RuntimeError(
                f"Circuit breaker: composition depth {new_depth} exceeds max {MAX_COMPOSITION_DEPTH}"
            )

        risk = max(self.nodes[p].risk_ceiling for p in part_ids)
        comp = Composite(
            id=f"composite.{uuid.uuid4().hex[:10]}",
            name=name,
            description=description or f"Composition of: {', '.join(part_ids)}",
            parts=list(part_ids),
            risk_ceiling=risk,
            created_at=datetime.now(timezone.utc).isoformat(),
            verified=False,
            behavior_summary=behavior_summary,
            tags=(tags or ["composite"])
            + ([f"depth-{new_depth}"] if new_depth > 1 else []),
        )
        self.composites[comp.id] = comp
        self.nodes[comp.id] = GraphNode(
            id=comp.id,
            kind=NodeKind.COMPOSITE,
            name=comp.name,
            description=comp.description,
            risk_ceiling=comp.risk_ceiling,
            tags=comp.tags,
            metadata={"depth": new_depth, "part_count": len(part_ids)},
        )
        for p in part_ids:
            self.edges.append(GraphEdge(comp.id, p, "composes_with"))
        self._persist()
        return comp

    def verify_composite(self, composite_id: str) -> Composite:
        """Mark a composite as verified (promotion step). Still subject to policy at runtime."""
        comp = self.composites[composite_id]
        comp.verified = True
        self._persist()
        return comp

    def neighbors(
        self, node_id: str, relation: Optional[str] = None
    ) -> List[GraphNode]:
        out = []
        for e in self.edges:
            if e.source_id == node_id and (relation is None or e.relation == relation):
                if e.target_id in self.nodes:
                    out.append(self.nodes[e.target_id])
            elif e.target_id == node_id and (
                relation is None or e.relation == relation
            ):
                if e.source_id in self.nodes:
                    out.append(self.nodes[e.source_id])
        return out

    def suggest_compositions(
        self, seed_id: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Suggest interpenetration partners for a node.
        Genres, personas, skills, specialists, composites, LWP primitives —
        all are valid partners. Same-kind pairs (e.g. genre × genre) are allowed
        for combinatorial depth; different-kind pairs are preferred but not exclusive.
        """
        # Resolve bare names
        if seed_id not in self.nodes:
            for prefix in (
                "genre.",
                "persona.",
                "skill.",
                "spec.",
                "role.",
                "lwp.",
                "composite.",
            ):
                if prefix + seed_id in self.nodes:
                    seed_id = prefix + seed_id
                    break
        if seed_id not in self.nodes:
            return []
        seed = self.nodes[seed_id]
        suggestions = []
        for nid, node in self.nodes.items():
            if nid == seed_id:
                continue
            # Everything interpenetrates — including genre × genre and composite × genre
            same_kind = node.kind == seed.kind
            suggestions.append(
                {
                    "with": nid,
                    "name": node.name,
                    "kind": node.kind.value,
                    "combined_risk": max(seed.risk_ceiling, node.risk_ceiling),
                    "reason": f"{seed.kind.value} × {node.kind.value}"
                    + (" (same-kind)" if same_kind else ""),
                    "same_kind": same_kind,
                }
            )
        # Prefer cross-kind, then lower risk, then name
        suggestions.sort(key=lambda s: (s["same_kind"], s["combined_risk"], s["name"]))
        return suggestions[:limit]

    def stats(self) -> Dict[str, Any]:
        by_kind: Dict[str, int] = {}
        for n in self.nodes.values():
            by_kind[n.kind.value] = by_kind.get(n.kind.value, 0) + 1
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "composites": len(self.composites),
            "verified_composites": sum(
                1 for c in self.composites.values() if c.verified
            ),
            "by_kind": by_kind,
            "data_dir": str(self.data_dir),
            "principle": "Everything interpenetrates under policy and integrity",
        }
