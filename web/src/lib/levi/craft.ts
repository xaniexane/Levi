/** Premium story cascade — classical × modern × L.W.P. */

export const PREMIUM_CASCADE = [
  "In Medias Res Hook",
  "Plant (Chekhov)",
  "Try-Fail 1",
  "Sequel Reaction",
  "Midpoint Reversal",
  "B-Story Mirror",
  "Dark Night Cost",
  "Recognition",
  "Convergence Payoff",
  "Aftermath Image",
] as const;

export function nextCraftBeat(count: number) {
  return PREMIUM_CASCADE[count % PREMIUM_CASCADE.length]!;
}

export function craftParagraph(lead: string, beat: string, genre: string, wound: string) {
  const g = genre.replaceAll("_", " ");
  return [
    `### ${beat}`,
    `${lead} moves under ${g}. Scene goal is costly; the wound (${wound || "unnamed"}) still sets the interest rate.`,
    "Enter late. Leave before the air goes soft. Scar law: yesterday’s compromise is still collecting.",
  ].join("\n");
}
