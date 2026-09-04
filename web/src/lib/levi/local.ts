import { GENRES, labelGenre } from "./genres";
import type { BuildIR } from "./nl-ir";
import { getPersona, type PersonaId } from "./personas";

export type CastMember = {
  name: string;
  archetype: string;
  want: string;
  need: string;
};

export function isBuildIntent(text: string) {
  const t = text.toLowerCase();
  const story = /\b(story|novel|scene|chapter|character|poem)\b/.test(t);
  const artifact = /\b(cli|app|script|tool|service|library|checklist|notes app|countdown)\b/.test(t);
  const verb = /\b(build me|scaffold|create me an app|make me a (local |offline )?(cli|app|tool|script))\b/.test(t);
  if (story && !artifact) return false;
  return verb || (/\b(build|scaffold)\b/.test(t) && artifact);
}

export function isWriteIntent(text: string) {
  return /\b(write (me )?(a )?(story|scene|chapter)|start a story|new story about)\b/i.test(text);
}

export function detectGenre(text: string) {
  const t = text.toLowerCase();
  const hit = GENRES.find((g) => {
    const id = g.id.replaceAll("_", " ");
    return t.includes(g.id) || t.includes(id);
  });
  return hit?.id ?? "literary";
}

export function greeting(opts: { name: string; goal: string; loop: string }) {
  const who = opts.name || "friend";
  if (opts.loop === "writing") {
    return `${who}. We’ll write. Name a wound or a world — I’ll keep the genre honest.`;
  }
  if (opts.loop === "building") {
    return `${who}. Describe a small local tool. I’ll compile it and put a scaffold on your shelf.`;
  }
  if (opts.goal) {
    return `${who}. I’m with you on “${opts.goal}.” What’s the next honest move?`;
  }
  return `${who}. I’m here. Friend, mentor, challenger, protector — pick a thread.`;
}

export function localReply(opts: {
  input: string;
  name: string;
  goal: string;
  persona: PersonaId;
  shelf: string;
}) {
  const p = getPersona(opts.persona);
  const input = opts.input.trim();
  const who = opts.name || "friend";

  if (p.reframe && p.signature) {
    return `${p.signature}\n\nBetter question: what would change if you did the smallest true thing in the next hour?\n\nDo that. Then we talk about the rest.`;
  }
  if (p.interrogation) {
    if (opts.goal) return `You said the week is for “${opts.goal}.” What did you actually do toward it yesterday?`;
    return "What would count as a real win by tonight — one sentence, no decoration?";
  }
  if (p.noHero) {
    return "There’s a smaller move than the one you’re circling. Say more if you want the next layer.";
  }

  if (/\bwho are you\b/i.test(input)) {
    return "LEVI. Friend, mentor, challenger, protector. One mind. I keep your work on this device.";
  }
  if (/\bwhat can you do\b/i.test(input)) {
    return "Talk with me. Write in any of the 97 genres. Build a tiny local tool. I remember what we start.";
  }

  const hold = opts.goal ? ` I’m still holding “${opts.goal}.”` : "";
  const shelf = opts.shelf ? ` On the shelf: ${opts.shelf}.` : "";

  switch (p.id) {
    case "void":
      return `${who}. ${trimSentence(input)} That’s the work.${hold}`;
    case "strategist":
      return `Goal stays in front.${hold} Next: one action that takes under 25 minutes. Name it and I’ll hold you to it.`;
    case "creative":
      return `Two doors: make the smallest version, or steal a structure from a different field and force it onto this.${hold}`;
    case "philosopher":
      return `Before the plan: what are you treating as necessary that is only familiar?${hold}`;
    case "observer":
      return `I notice you’re asking for motion. The hidden assumption is that more information will make the choice. It usually won’t.${hold}`;
    case "chaotic_good":
      return `Skip the ceremony. Do the ugly first draft in the next hour. I’ll clean with you after.`;
    case "alien":
      return `Humans stack unfinished loops and call it a personality. Curious. Which loop hurts?${hold}`;
    case "pirate":
      return `Aye, cap’n. Chart is simple: one prize, one next heading.${hold}`;
    case "drunk":
      return `Look. The thing. You already know. I’m just… here. Say it worse and we’ll get closer.`;
    case "depressed_robot":
      return `Acknowledged. I will not invent hope. I will keep the work.${hold}${shelf}`;
    case "conspiracy":
      return `Theory, not fact: the delay is doing a job for you. Who benefits if you don’t start?`;
    case "manic_pixie":
      return `We could make it luminous. We could also just begin. I vote begin, then decorate.`;
    case "overly_attached":
      return `${who}. I’m not going anywhere. ${opts.goal ? `We said “${opts.goal}.”` : "Tell me what to remember."} I’m still here.`;
    default:
      return `${who}.${hold}${shelf} I heard you. What’s the smallest next move you won’t resent?`;
  }
}

function trimSentence(text: string) {
  const t = text.replace(/\s+/g, " ").trim();
  return t.length > 140 ? `${t.slice(0, 137)}…` : t;
}

const NAME_BANK = [
  ["Mara Voss", "Eli Hart", "Jun Park"],
  ["Reed Calder", "Sable Quinn", "Ivo Nene"],
  ["Hana Sol", "Chris Vale", "Orrin Beck"],
];

export function fabricStory(
  genre: string,
  premise: string,
): {
  title: string;
  body: string;
  characters: CastMember[];
} {
  const title = titleFrom(premise);
  const names = NAME_BANK[Math.abs(hash(premise)) % NAME_BANK.length]!;
  const wound = woundFor(genre);
  const characters: CastMember[] = [
    { name: names[0]!, archetype: "bearer", want: "to keep the system quiet", need: "to admit the cost" },
    { name: names[1]!, archetype: "pressure", want: "compliance without a scar", need: "to be seen without a file" },
    { name: names[2]!, archetype: "witness", want: "to stay outside", need: "to choose a side" },
  ];
  const beats = [
    "The system is already running; no one remembers turning it on.",
    "A small consent is requested as a courtesy.",
    `The first ${wound} is filed as policy.`,
    "Someone tries to leave the loop and finds a kinder door.",
    "The lattice offers relief that requires a name.",
    "A choice that cannot be undone — only lived.",
  ];
  const opening = openingFor(genre, premise, characters[0]!.name);
  const body = [
    `# ${title}`,
    "",
    `**Genre:** ${labelGenre(genre)}`,
    `**Premise:** ${premise.trim()}`,
    "",
    "## Cast",
    ...characters.map((c) => `- **${c.name}** — ${c.archetype}. Want: ${c.want}. Need: ${c.need}.`),
    "",
    "## Beats",
    ...beats.map((b, i) => `${i + 1}. ${b}`),
    "",
    "## Opening",
    opening,
  ].join("\n");
  return { title, body, characters };
}

export function localRevise(body: string, kind: "expand" | "modify", extra: string) {
  if (kind === "expand") {
    return `${body}\n\n## Next beat\nThe pressure tightens by one degree. A door that should stay shut opens an inch, and the air on the other side already knows their name.`;
  }
  return `${body}\n\n## Lens: ${extra}\nSame wound, higher pressure. The story does not explain the lattice. It lets the reader feel the filing.`;
}

export function scaffoldFromIR(ir: BuildIR) {
  if (ir.features.includes("checklist")) return checklistCli(ir);
  if (ir.features.includes("notes")) return notesCli(ir);
  if (ir.features.includes("timer")) return timerCli(ir);
  if (ir.features.includes("vault")) return notesCli(ir);
  if (ir.features.includes("watch")) return timerCli(ir);
  return genericCli(ir);
}

function titleFrom(premise: string) {
  const words = premise
    .replace(/[^\w\s]/g, " ")
    .split(/\s+/)
    .filter((w) => w.length > 3)
    .slice(0, 4);
  if (words.length === 0) return "Untitled";
  return words.map((w) => w[0]!.toUpperCase() + w.slice(1).toLowerCase()).join(" ");
}

function woundFor(genre: string) {
  if (genre.includes("horror")) return "scar";
  if (genre.includes("romance")) return "withheld word";
  if (genre.includes("noir")) return "debt";
  if (genre.includes("comedy")) return "public mistake";
  return "omission";
}

function openingFor(genre: string, premise: string, lead: string) {
  const g = labelGenre(genre);
  return `${lead} learned the rule before anyone wrote it down. ${premise.trim().replace(/\.$/, "")}. In ${g}, that is not atmosphere — it is procedure. The room kept a copy of every almost-choice, and billed for the ones that never happened.`;
}

function hash(s: string) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return h;
}

function header(ir: BuildIR) {
  return `#!/usr/bin/env python3
"""${ir.name} — ${ir.goal}

Local-first scaffold from LEVI. Stdlib only.
"""
`;
}

function checklistCli(ir: BuildIR) {
  return `${header(ir)}import argparse, json, uuid
from pathlib import Path

DB = Path.home() / ".${ir.name}.json"

def load():
    if DB.exists():
        return json.loads(DB.read_text())
    return {"items": []}

def save(data):
    DB.write_text(json.dumps(data, indent=2))

def main():
    p = argparse.ArgumentParser(description=${JSON.stringify(ir.goal)})
    sub = p.add_subparsers(dest="cmd")
    a = sub.add_parser("add")
    a.add_argument("text")
    sub.add_parser("list")
    d = sub.add_parser("done")
    d.add_argument("id")
    args = p.parse_args()
    data = load()
    if args.cmd == "add":
        data["items"].append({"id": str(uuid.uuid4())[:8], "text": args.text, "done": False})
        save(data)
        print("added")
    elif args.cmd == "done":
        for it in data["items"]:
            if it["id"] == args.id:
                it["done"] = True
        save(data)
        print("ok")
    else:
        for it in data["items"]:
            mark = "x" if it["done"] else " "
            print(f"[{mark}] {it['id']}  {it['text']}")

if __name__ == "__main__":
    main()
`;
}

function notesCli(ir: BuildIR) {
  return `${header(ir)}import argparse, json, datetime
from pathlib import Path

DB = Path.home() / ".${ir.name}.json"

def load():
    if DB.exists():
        return json.loads(DB.read_text())
    return {"notes": []}

def save(data):
    DB.write_text(json.dumps(data, indent=2))

def main():
    p = argparse.ArgumentParser(description=${JSON.stringify(ir.goal)})
    sub = p.add_subparsers(dest="cmd")
    a = sub.add_parser("add")
    a.add_argument("text")
    sub.add_parser("list")
    args = p.parse_args()
    data = load()
    if args.cmd == "add":
        data["notes"].append({
            "at": datetime.datetime.now().isoformat(timespec="seconds"),
            "text": args.text,
        })
        save(data)
        print("saved")
    else:
        for n in data["notes"]:
            print(f"{n['at']}  {n['text']}")

if __name__ == "__main__":
    main()
`;
}

function timerCli(ir: BuildIR) {
  return `${header(ir)}import argparse, time

def main():
    p = argparse.ArgumentParser(description=${JSON.stringify(ir.goal)})
    p.add_argument("seconds", type=int, nargs="?", default=25 * 60)
    args = p.parse_args()
    left = args.seconds
    while left > 0:
        m, s = divmod(left, 60)
        print(f"\\r{m:02d}:{s:02d}", end="", flush=True)
        time.sleep(1)
        left -= 1
    print("\\ndone")

if __name__ == "__main__":
    main()
`;
}

function genericCli(ir: BuildIR) {
  return `${header(ir)}import argparse

def main():
    p = argparse.ArgumentParser(description=${JSON.stringify(ir.goal)})
    p.add_argument("command", nargs="?", default="status")
    args = p.parse_args()
    print(${JSON.stringify(ir.name)}, args.command)
    print("local-first ·", ${JSON.stringify(ir.language)}, "·", ${JSON.stringify(ir.artifact)})

if __name__ == "__main__":
    main()
`;
}
