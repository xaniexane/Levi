/** L.W.P. character graph — combinatorial, local. */

const DRIVES = ["belonging", "mastery", "justice", "freedom", "legacy", "curiosity", "safety", "truth"] as const;
const WOUNDS = ["abandonment", "humiliation", "betrayal", "powerlessness", "erasure", "exile"] as const;
const METHODS = ["strategy", "charm", "service", "analysis", "humor", "craft", "endurance"] as const;
const VOICES = ["spare", "lyrical", "clinical", "ironic", "tender", "blunt"] as const;
const ROOTS = ["Ash", "Nyx", "Quill", "Vesper", "Reed", "Sable", "Wren", "Cass", "Orin", "Lumen"];

export type GraphChar = {
  id: string;
  name: string;
  drive: string;
  wound: string;
  method: string;
  voice: string;
  want: string;
  need: string;
};

function pick<T>(arr: readonly T[], n: number) {
  return arr[n % arr.length]!;
}

export function mintCharacter(seed: string): GraphChar {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 33 + seed.charCodeAt(i)) >>> 0;
  const drive = pick(DRIVES, h);
  const wound = pick(WOUNDS, h >> 3);
  const method = pick(METHODS, h >> 6);
  const voice = pick(VOICES, h >> 9);
  const name = `${pick(ROOTS, h >> 12)}-${drive.slice(0, 3)}`;
  return {
    id: `char.${h.toString(16).slice(0, 8)}`,
    name,
    drive,
    wound,
    method,
    voice,
    want: `to secure ${drive} without admitting the ${wound}`,
    need: `to face ${wound} using ${method} without losing ${drive}`,
  };
}

export const AXIS_TYPES = DRIVES.length * WOUNDS.length * METHODS.length * VOICES.length;
