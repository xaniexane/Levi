/** Product model — how LEVI makes money without becoming a pleaser SaaS. */

export type PlanId = "local" | "studio" | "sovereign";

export const PLANS: {
  id: PlanId;
  name: string;
  price: string;
  for: string;
  includes: string[];
  not: string;
}[] = [
  {
    id: "local",
    name: "Local",
    price: "Free",
    for: "One person, this device",
    includes: [
      "Talk, Write, Build on this device",
      "97 genres + personas",
      "HITL on consequences (never skipped)",
      "Offline path when the model is down",
    ],
    not: "No cloud sync. No team seats.",
  },
  {
    id: "studio",
    name: "Studio",
    price: "$29 / mo",
    for: "Writers and builders who ship weekly",
    includes: [
      "Everything in Local",
      "Premium craft cascade + character graph",
      "Builder templates and emergency E3–E6",
      "Genre / template packs",
      "Priority model path when available",
    ],
    not: "Still no auto-send to customers. HITL stays on.",
  },
  {
    id: "sovereign",
    name: "Sovereign",
    price: "$99 / mo",
    for: "Operators who need encrypted wings",
    includes: [
      "Everything in Studio",
      "Encrypted sync (Phase B) when you turn it on",
      "HITL fulfillment desk — human-gated offers",
      "Custom organ / charter workshop",
      "Exportable life-pack, no hostage data",
    ],
    not: "We never read your plaintext. Silence is not approval.",
  },
];

export const SERVICES = [
  {
    id: "hitl_desk",
    name: "HITL fulfillment desk",
    price: "From $400",
    note: "You approve. We prep. Nothing ships on silence.",
  },
  {
    id: "charter",
    name: "Charter workshop",
    price: "$1,200",
    note: "Bind LEVI to your non-negotiables in a day.",
  },
  {
    id: "story_pack",
    name: "Genre / world pack",
    price: "$79",
    note: "A locked bible + character graph for one series.",
  },
  {
    id: "builder_slice",
    name: "Emergency builder slice",
    price: "$250",
    note: "E5 MVP of one local tool under your HITL.",
  },
];

export function planRank(id: PlanId) {
  return { local: 0, studio: 1, sovereign: 2 }[id];
}

export function canUse(plan: PlanId, need: PlanId) {
  return planRank(plan) >= planRank(need);
}
