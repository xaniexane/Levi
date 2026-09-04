export type HeadId =
  | "logic"
  | "creation"
  | "systems"
  | "security"
  | "evolution"
  | "identity";

export type DesignMode = "sovereignty" | "hybrid";

export type View =
  | "home"
  | "talk"
  | "write"
  | "build"
  | "studio"
  | "hydra"
  | "echo"
  | "mandella"
  | "compost"
  | "ledger";

export type BranchKind = "taken" | "not_taken" | "wild";

export interface Branch {
  id: string;
  kind: BranchKind;
  label: string;
  summary: string;
  risk: "low" | "medium" | "high" | "unknown";
  optionality: number;
}

export interface EchoRun {
  id: string;
  seed: string;
  branches: Branch[];
  insight: string;
  createdAt: string;
  fromMandella?: string;
  stake?: string;
}

export interface MandellaOption {
  key: "A" | "B" | "C";
  label: string;
  move: string;
  optionality: number;
  risk: "low" | "medium" | "high";
  verifiesWith: string;
}

export interface Phantom {
  key: string;
  label: string;
  move: string;
  hashThread: string;
}

export type MandellaDomain =
  | "crisis"
  | "resource"
  | "trust"
  | "identity"
  | "build"
  | "write"
  | "security"
  | "product";

export interface MandellaScenario {
  id: string;
  domain: MandellaDomain;
  premise: string;
  constraints: string[];
  options: MandellaOption[];
  recommended: "A" | "B" | "C";
  verification: string;
  phantoms: Phantom[];
  createdAt: string;
}

export interface CompostEntry {
  id: string;
  createdAt: string;
  source: "chat" | "echo" | "mandella" | "manual" | "hydra" | "stress";
  failure: string;
  residue: string;
  lesson: string;
  refined?: string;
  compressed?: string;
  quarantined: boolean;
}

export interface JournalNote {
  id: string;
  text: string;
  createdAt: string;
}

export interface HeadFragment {
  head: HeadId;
  interpretation: string;
  assumptions: string[];
  subtasks: string[];
  risks: string[];
  veto?: string;
  at: string;
}

export interface IrConflict {
  a: HeadId;
  b: HeadId;
  issue: string;
  resolvedBy: HeadId;
  resolution: string;
}

export interface HydraIR {
  taskId: string;
  taskDefinition: string;
  seed: string;
  constraints: { cost: { maxUSD: number }; latencyMs: number; safety: string[] };
  context: { continuityState: string; designMode: DesignMode };
  cognitiveHeads: HeadId[];
  headFragments: HeadFragment[];
  mergedGraph: {
    nodes: { id: string; kind: string; label: string }[];
    edges: { from: string; to: string }[];
  };
  executionPlan: { steps: { id: string; action: string; retries: number }[] };
  identityRules: { owner: string; refusal: string[] };
  evolutionRules: { allowed: string; sandbox: boolean; approvalRequired: boolean };
  riskProfile: { hallucinationTolerance: number; dataExposure: number };
  verificationChecklist: { check: string; pass: boolean }[];
  conflicts: IrConflict[];
  provenance: {
    source: string;
    transforms: string[];
    model: string;
    seed: string;
  };
  signed: boolean;
  halted: boolean;
}

export interface LedgerEvent {
  id: string;
  seq: number;
  at: string;
  kind: string;
  summary: string;
  seed: string;
  prevHash: string;
  hash: string;
  signature?: string;
}

export interface StressResult {
  id: string;
  name: string;
  pass: boolean;
  detail: string;
  at: string;
}

export interface Kpis {
  cis: number;
  hr: number;
  ccr: number;
  rt: number;
  di: number;
  rs: number;
}

export const ORGAN_MAP: {
  old: string;
  now: View;
  status: "merged" | "kept" | "added";
  note: string;
}[] = [
  { old: "Chat", now: "talk", status: "merged", note: "Talk is the companion. Personas, HITL, Grok catalyst." },
  { old: "Morning", now: "home", status: "merged", note: "Daily ritual and streak live on Home." },
  { old: "Journal", now: "ledger", status: "merged", note: "Human notes sit on the ledger with provenance." },
  { old: "Echoverse", now: "echo", status: "kept", note: "Taken / not-taken / wild. Still a distinct organ." },
  { old: "Mandella", now: "mandella", status: "kept", note: "A/B/C stakes and phantoms. Feeds Echo." },
  { old: "Compost (REIM/RIEM)", now: "compost", status: "kept", note: "Part 2 archive: quarantined, non-canon, learnable." },
  { old: "—", now: "write", status: "added", note: "97-genre story fabric." },
  { old: "—", now: "build", status: "added", note: "NL → IR factory, E3–E6, HITL." },
  { old: "—", now: "studio", status: "added", note: "Demos, mirror coils, plans." },
  { old: "—", now: "hydra", status: "added", note: "Six heads, convergence, signed plans." },
  { old: "—", now: "ledger", status: "added", note: "Hash chain, seeds, Part 2 lock, audit." },
];
