export type BuildIR = {
  kind: "build";
  name: string;
  goal: string;
  artifact: "cli" | "script" | "library" | "service";
  language: string;
  offline: boolean;
  storage: string | null;
  features: string[];
  constraints: string[];
  emergency: EmergencyTier;
};

export type EmergencyTier = "E3" | "E4" | "E5" | "E6";

export const EMERGENCY: { id: EmergencyTier; label: string; note: string }[] = [
  { id: "E3", label: "Skeleton", note: "Folders, README, one file that runs." },
  { id: "E4", label: "Wiring", note: "CLI flags, storage, one happy path." },
  { id: "E5", label: "MVP", note: "Usable for the named job. Tests for the core path." },
  { id: "E6", label: "Product", note: "Docs, error recovery, HITL on anything external." },
];

export function compileBuild(text: string): BuildIR {
  const t = text.toLowerCase();
  let artifact: BuildIR["artifact"] = "cli";
  if (/(library|package|sdk|module)/.test(t)) artifact = "library";
  else if (/(service|api|server|daemon)/.test(t)) artifact = "service";
  else if (/(script|one-off)/.test(t)) artifact = "script";

  let language = "python";
  if (/(javascript|typescript|node)/.test(t)) language = "javascript";
  else if (/\brust\b/.test(t)) language = "rust";
  else if (/\bgo\b|golang/.test(t)) language = "go";

  const storage = t.includes("sqlite") ? "sqlite" : t.includes("json") ? "json" : null;
  const features: string[] = [];
  if (/(checklist|todo|task)/.test(t)) features.push("checklist");
  if (/(note|memo)/.test(t)) features.push("notes");
  if (/(timer|countdown)/.test(t)) features.push("timer");
  if (/(vault|encrypt|secret)/.test(t)) features.push("vault");
  if (/(pulse|watch|cron)/.test(t)) features.push("watch");
  if (storage) features.push("persistence");

  const constraints = ["local-first"];
  if (t.includes("offline")) constraints.push("offline");
  if (/(social network|operating system|\bplatform\b|marketplace|everything app)/.test(t)) {
    constraints.push("tiny-slice");
    features.push("single-purpose");
  }

  let emergency: EmergencyTier = "E5";
  if (/\be3\b|skeleton/.test(t)) emergency = "E3";
  else if (/\be4\b|wiring/.test(t)) emergency = "E4";
  else if (/\be6\b|product grade|production/.test(t)) emergency = "E6";

  const quoted = text.match(/["']([^"']+)["']/);
  const called = t.match(/(?:called|named)\s+([a-z0-9_-]+)/);
  const name = (quoted?.[1] || called?.[1] || slugFrom(text)).slice(0, 40);

  return {
    kind: "build",
    name: name || "levi_app",
    goal: text.trim(),
    artifact,
    language,
    offline: !/(cloud|saas|hosted)/.test(t),
    storage,
    features: [...new Set(features)],
    constraints: [...new Set(constraints)],
    emergency,
  };
}

function slugFrom(text: string) {
  const m = text
    .toLowerCase()
    .match(/(?:build|make|create)\s+(?:me\s+)?(?:a|an)\s+(.+?)(?:\s+with\s+|$)/);
  const chunk = (m?.[1] ?? text)
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((w) => !["a", "an", "the", "local", "offline", "simple", "tiny"].includes(w))
    .slice(0, 3)
    .join("_");
  return chunk || "levi_app";
}

export const STAGES = [
  "idea",
  "requirements",
  "architecture",
  "scaffold",
  "hitl",
  "implement",
  "test",
  "ship",
] as const;

export type Stage = (typeof STAGES)[number];

export function nextStage(stage: Stage): Stage {
  const i = STAGES.indexOf(stage);
  return STAGES[Math.min(i + 1, STAGES.length - 1)]!;
}

export function stageNeedsHitl(stage: Stage) {
  return stage === "hitl" || stage === "ship";
}
