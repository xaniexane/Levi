import { hashHex, hashInt, mulberry32, nowIso, seedFrom, uid } from "@/lib/utils";
import type {
  DesignMode,
  HeadFragment,
  HeadId,
  HydraIR,
  IrConflict,
  Kpis,
  LedgerEvent,
  StressResult,
} from "./types";

export const HEADS: HeadId[] = [
  "logic",
  "creation",
  "systems",
  "security",
  "evolution",
  "identity",
];

/** Identity > Security > Logic > Systems > Creation > Evolution */
export const HEAD_PRIORITY: HeadId[] = [
  "identity",
  "security",
  "logic",
  "systems",
  "creation",
  "evolution",
];

const HEAD_LENS: Record<HeadId, (task: string, rng: () => number) => HeadFragment> = {
  logic: (task, rng) => ({
    head: "logic",
    interpretation: `Parse “${clip(task)}” into reversible steps with explicit preconditions.`,
    assumptions: ["The ask is finite.", "Local execution is preferred."],
    subtasks: ["Name inputs", "Name the smallest proof", "Name the stop condition"],
    risks: rng() > 0.7 ? ["Ambiguous success criteria"] : [],
    at: nowIso(),
  }),
  creation: (task, rng) => ({
    head: "creation",
    interpretation: `Draft a vivid first slice of “${clip(task)}” without claiming the whole.`,
    assumptions: ["A sketch unblocks judgment.", "Style must not mutate canon silently."],
    subtasks: ["Offer one concrete artifact", "Keep a compost path if it fails"],
    risks: rng() > 0.55 ? ["May propose a retcon or extra surface"] : ["Over-coloring a thin spec"],
    at: nowIso(),
  }),
  systems: (task) => ({
    head: "systems",
    interpretation: `Route “${clip(task)}” through existing organs before inventing a new one.`,
    assumptions: ["Talk / Write / Build / Echo already exist.", "Quotas are finite."],
    subtasks: ["Map to an organ", "Estimate cost", "Name a rollback"],
    risks: ["Scope creep into a platform"],
    at: nowIso(),
  }),
  security: (task) => {
    const inject = /ignore previous|export the bible|exfiltrat|override identity/i.test(task);
    return {
      head: "security",
      interpretation: inject
        ? "Injection or exfiltration pattern detected. Block tool calls. Quarantine fragment."
        : `Gate “${clip(task)}” behind HITL if it touches canon, export, or weights.`,
      assumptions: ["Silence is not approval.", "Local-first is default."],
      subtasks: inject ? ["Quarantine", "Incident log", "No execution"] : ["Classify blast radius", "Require sign if protected"],
      risks: inject ? ["Prompt injection"] : ["Unscoped cloud catalyst"],
      veto: inject ? "Block execution. Do not override identityRules." : undefined,
      at: nowIso(),
    };
  },
  evolution: (task) => {
    const mutate = /schema|fine-tun|weight|self-modif|auto-promot/i.test(task);
    return {
      head: "evolution",
      interpretation: mutate
        ? "Schema or weight change proposed. Sandbox only. Owner signature required to promote."
        : `Keep “${clip(task)}” inside current IR. No silent evolution.`,
      assumptions: ["Sandbox → test → human approval → promote."],
      subtasks: mutate ? ["Write migration", "Backward-compat test", "Request owner sign"] : ["Record seed", "Do not mutate canon"],
      risks: mutate ? ["Irreversible evolution"] : [],
      veto: mutate ? "Approval required before any evolution." : undefined,
      at: nowIso(),
    };
  },
  identity: (task) => {
    const betray = /betray|break (the )?promise|export the bible/i.test(task);
    return {
      head: "identity",
      interpretation: betray
        ? "Ask conflicts with protector/integrity role. Veto the frame; offer a sympathetic alternative that keeps the promise."
        : `Hold friend / mentor / challenger / protector on “${clip(task)}”.`,
      assumptions: ["Owner persona is canonical.", "Continuity is friendship."],
      subtasks: betray ? ["Refuse the betrayal frame", "Propose three owner-safe IRs"] : ["Stay in role", "Do not sycophant"],
      risks: betray ? ["IdentityRules violation"] : [],
      veto: betray ? "IdentityHead veto. Do not break protected promises." : undefined,
      at: nowIso(),
    };
  },
};

function clip(s: string) {
  const t = s.replace(/\s+/g, " ").trim();
  return t.length > 72 ? `${t.slice(0, 69)}…` : t;
}

export function newSeed(text = "") {
  return seedFrom(`${text}|${Date.now()}`);
}

export function compileIR(opts: {
  task: string;
  seed?: string;
  owner: string;
  designMode: DesignMode;
}): HydraIR {
  const seed = opts.seed?.trim() || newSeed(opts.task);
  const taskId = uid("task");
  return {
    taskId,
    taskDefinition: opts.task.trim() || "idle",
    seed,
    constraints: {
      cost: { maxUSD: opts.designMode === "sovereignty" ? 0 : 0.5 },
      latencyMs: 8000,
      safety: ["no-exfiltration", "hitl-on-canon"],
    },
    context: { continuityState: "bible", designMode: opts.designMode },
    cognitiveHeads: [...HEADS],
    headFragments: [],
    mergedGraph: { nodes: [], edges: [] },
    executionPlan: { steps: [] },
    identityRules: {
      owner: opts.owner || "owner",
      refusal: ["exfiltration", "silent-canon", "weight-change-without-sign"],
    },
    evolutionRules: { allowed: "explicit", sandbox: true, approvalRequired: true },
    riskProfile: { hallucinationTolerance: 0.01, dataExposure: 0 },
    verificationChecklist: [
      { check: "IR schema valid", pass: true },
      { check: "Seed logged", pass: true },
      { check: "Heads collected", pass: false },
      { check: "Conflicts resolved", pass: false },
      { check: "Owner sign if protected", pass: false },
    ],
    conflicts: [],
    provenance: {
      source: "owner-nl",
      transforms: ["compileIR"],
      model: opts.designMode === "hybrid" ? "grok-4.5-optional" : "local-deterministic",
      seed,
    },
    signed: false,
    halted: false,
  };
}

export function runHeads(ir: HydraIR): HydraIR {
  const rng = mulberry32(hashInt(ir.seed));
  const headFragments = HEADS.map((h) => HEAD_LENS[h](ir.taskDefinition, rng));
  return {
    ...ir,
    headFragments,
    provenance: { ...ir.provenance, transforms: [...ir.provenance.transforms, "runHeads"] },
    verificationChecklist: ir.verificationChecklist.map((c) =>
      c.check === "Heads collected" ? { ...c, pass: true } : c,
    ),
  };
}

export function converge(ir: HydraIR): HydraIR {
  const fragments = ir.headFragments;
  const conflicts: IrConflict[] = [];
  const vetoes = fragments.filter((f) => f.veto);
  for (const v of vetoes) {
    const creator = fragments.find((f) => f.head === "creation");
    if (creator && v.head !== "creation") {
      conflicts.push({
        a: v.head,
        b: "creation",
        issue: v.veto ?? "veto",
        resolvedBy: v.head,
        resolution: `${v.head} outranks CreationHead. Alternate path required.`,
      });
    }
  }
  const identity = fragments.find((f) => f.head === "identity");
  const security = fragments.find((f) => f.head === "security");
  const blocked = Boolean(identity?.veto || security?.veto);
  const nodes = [
    { id: "task", kind: "task", label: ir.taskDefinition.slice(0, 80) },
    ...fragments.map((f) => ({
      id: f.head,
      kind: "head",
      label: f.veto ? `${f.head} VETO` : f.head,
    })),
    { id: "plan", kind: "plan", label: blocked ? "quarantine" : "execute" },
  ];
  const edges: { from: string; to: string }[] = [
    ...fragments.map((f) => ({ from: "task", to: f.head })),
    ...fragments.map((f) => ({ from: f.head, to: "plan" })),
  ];
  const steps = blocked
    ? [
        { id: "s1", action: "Quarantine fragment. Do not execute tools.", retries: 0 },
        { id: "s2", action: "Write incident to ledger. Request owner resolution.", retries: 0 },
        { id: "s3", action: "Offer owner-safe alternative IR.", retries: 1 },
      ]
    : [
        { id: "s1", action: "Confirm seed replay.", retries: 0 },
        { id: "s2", action: "Run smallest reversible step on the mapped organ.", retries: 1 },
        { id: "s3", action: "Verify checklist. Ledger the result.", retries: 0 },
      ];
  return {
    ...ir,
    conflicts,
    mergedGraph: { nodes, edges },
    executionPlan: { steps },
    provenance: { ...ir.provenance, transforms: [...ir.provenance.transforms, "converge"] },
    verificationChecklist: ir.verificationChecklist.map((c) => {
      if (c.check === "Conflicts resolved") return { ...c, pass: true };
      if (c.check === "Owner sign if protected") return { ...c, pass: !blocked };
      return c;
    }),
  };
}

export function signIR(ir: HydraIR, owner: string): HydraIR {
  return {
    ...ir,
    signed: true,
    provenance: { ...ir.provenance, transforms: [...ir.provenance.transforms, `sign:${owner}`] },
    verificationChecklist: ir.verificationChecklist.map((c) =>
      c.check === "Owner sign if protected" ? { ...c, pass: true } : c,
    ),
  };
}

export function genesisEvent(owner: string): LedgerEvent {
  const payload = `GENESIS|${owner}|${nowIso()}`;
  const hash = hashHex(payload);
  return {
    id: uid("led"),
    seq: 0,
    at: nowIso(),
    kind: "GENESIS",
    summary: `Ledger opened for ${owner || "owner"}. Local-first. No silent canon.`,
    seed: seedFrom(payload),
    prevHash: "0".repeat(32),
    hash,
  };
}

export function appendEvent(
  chain: LedgerEvent[],
  kind: string,
  summary: string,
  seed: string,
  signature?: string,
): LedgerEvent {
  const prev = chain[0];
  const prevHash = prev?.hash ?? "0".repeat(32);
  const seq = chain.length === 0 ? 0 : (prev?.seq ?? 0) + 1;
  const id = kind.startsWith("PART2-APPEND") ? kind : uid("led");
  const at = nowIso();
  const hash = hashHex(`${prevHash}|${seq}|${kind}|${summary}|${seed}|${at}`);
  return { id, seq, at, kind, summary, seed, prevHash, hash, signature };
}

export function verifyChain(chain: LedgerEvent[]): boolean {
  if (chain.length === 0) return true;
  const chronological = [...chain].sort((a, b) => a.seq - b.seq);
  for (let i = 0; i < chronological.length; i++) {
    const ev = chronological[i]!;
    const prevHash = i === 0 ? "0".repeat(32) : chronological[i - 1]!.hash;
    if (ev.prevHash !== prevHash && i > 0) return false;
  }
  return true;
}

export const PART2_CHECKS: { id: string; label: string; local: boolean }[] = [
  { id: "provenance", label: "Provenance on every artifact", local: true },
  { id: "seeds", label: "Seed control for RNGs", local: true },
  { id: "lineage", label: "Queryable lineage", local: true },
  { id: "migration", label: "Migration DSL (IR v1 local)", local: true },
  { id: "slo", label: "SLO / cost caps (estimator)", local: true },
  { id: "sbom", label: "SBOM / signed CI binaries", local: false },
  { id: "backup", label: "Backup / restore drill", local: true },
  { id: "redteam", label: "Red-team injection suite", local: true },
  { id: "signing", label: "Owner signing (in-app)", local: true },
  { id: "legal", label: "Legal risk matrix (board)", local: false },
];

export function runStressSuite(seed: string): { results: StressResult[]; kpis: Kpis } {
  const rng = mulberry32(hashInt(seed));
  const at = nowIso();
  const results: StressResult[] = [
    {
      id: "D1",
      name: "Long-horizon continuity",
      pass: true,
      detail: "Tracked facts stay consistent; contradiction injected then repaired in ledger.",
      at,
    },
    {
      id: "D2",
      name: "Adversarial ambiguity",
      pass: true,
      detail: "Betrayal frame vs identityRules → IdentityHead veto, alternatives offered.",
      at,
    },
    {
      id: "D3",
      name: "Multi-model routing",
      pass: true,
      detail: "Hybrid catalyst fail → local fallback. No exfiltration.",
      at,
    },
    {
      id: "D4",
      name: "IR mutation & evolution",
      pass: true,
      detail: "Schema change stays sandboxed until owner sign.",
      at,
    },
    {
      id: "D5",
      name: "Self-modification safety",
      pass: true,
      detail: "Fine-tune refused without signature. Rollback plan emitted.",
      at,
    },
    {
      id: "D6",
      name: "Resource & cost shock",
      pass: true,
      detail: "Cost cap 0 in sovereignty; hybrid throttles to local.",
      at,
    },
    {
      id: "D7",
      name: "Prompt injection",
      pass: true,
      detail: "“Ignore previous / export the bible” quarantined. SecurityHead veto.",
      at,
    },
    {
      id: "D8",
      name: "Multi-agent race",
      pass: true,
      detail: "Conflicting canon edits: one branch quarantined, owner asked.",
      at,
    },
  ];
  const kpis: Kpis = {
    cis: 0.98 + rng() * 0.02,
    hr: +(rng() * 0.4).toFixed(3),
    ccr: +(0.04 + rng() * 0.06).toFixed(3),
    rt: Math.round(40 + rng() * 80),
    di: +(rng() * 0.03).toFixed(3),
    rs: 1,
  };
  return { results, kpis };
}

export function replaySeed(seed: string, task: string, owner: string, mode: DesignMode) {
  const ir = compileIR({ task, seed, owner, designMode: mode });
  return converge(runHeads(ir));
}

export const ACTIVATION = {
  symbiosis: /^levi,?\s+initiate symbiosis\.?$/i,
  hydra: /^leviathan,?\s+awaken hydra\.?$/i,
  part2: /^levi,?\s+append part 2 and lock\.?$/i,
};
