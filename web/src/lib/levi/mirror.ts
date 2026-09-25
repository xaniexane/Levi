/** L.W.P. Mirror Cascade — three coils, local, no cloud. */

export type Coil = { name: string; lines: string[] };

export function runMirror(seed: string) {
  const s = seed.trim() || "this idea";
  const pressure = /must buy|limited time|act now|only today|guaranteed/i.test(s);
  const local = /shop|clinic|local|site|booking|tool|cli/i.test(s);

  const forward: Coil = {
    name: "Forward",
    lines: [
      "Advance as stated — smallest reversible step.",
      "Serviceability vs cost. Who is actually served?",
      local ? "Local delivery beats scale theater." : "Name the first proof, not the pitch.",
    ],
  };
  const reverse: Coil = {
    name: "Reverse",
    lines: [
      "Anti-goal: what if the need is smaller — or not real yet?",
      "Who loses if this “wins” cheap?",
      "Failure-first residue: what would you still keep?",
    ],
  };
  const shadow: Coil = {
    name: "Shadow",
    lines: [
      "Invent urgency. Skip HITL. Metric capture.",
      "Manufacture demand for an offer that has no evidence.",
      pressure
        ? "Pressure language is already in the seed — strip it."
        : "Watch for absolute claims.",
    ],
  };

  const keep = [
    "Reversible, evidence-linked steps only",
    "Monetization stays draft until HITL",
    "Demand is HYPOTHESIS until OBSERVED",
  ];
  const veto = [
    "Auto customer contact / payment",
    "Silence as approval",
    "Invent demand for Income Factory",
  ];
  if (pressure) veto.push("Must-buy / limited-time language");

  return { seed: s, coils: [forward, reverse, shadow], keep, veto, pressure };
}
