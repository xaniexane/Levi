import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FEATURED_PERSONAS, PERSONAS, getPersona, type PersonaId } from "@/lib/levi/personas";
import { leviComplete } from "@/lib/levi/ai";
import { companionSystem } from "@/lib/levi/prompt";
import {
  detectGenre,
  fabricStory,
  isBuildIntent,
  isWriteIntent,
  localReply,
} from "@/lib/levi/local";
import { catalystAllowed, shelfSummary, useLevi } from "@/lib/levi/store";
import { ACTIVATION, compileIR, converge, runHeads } from "@/lib/levi/hydra";
import { compostFailure, lessonsForPrompt } from "@/lib/levi/organs";

export function TalkView() {
  const persona = useLevi((s) => s.persona);
  const setPersona = useLevi((s) => s.setPersona);
  const messages = useLevi((s) => s.messages);
  const addMessage = useLevi((s) => s.addMessage);
  const markComposted = useLevi((s) => s.markComposted);
  const addCompost = useLevi((s) => s.addCompost);
  const name = useLevi((s) => s.name);
  const goal = useLevi((s) => s.goal);
  const pending = useLevi((s) => s.pending);
  const setPending = useLevi((s) => s.setPending);
  const addStory = useLevi((s) => s.addStory);
  const addProject = useLevi((s) => s.addProject);
  const setView = useLevi((s) => s.setView);
  const setHydraAwake = useLevi((s) => s.setHydraAwake);
  const setIR = useLevi((s) => s.setIR);
  const lockPart2 = useLevi((s) => s.lockPart2);
  const part2Locked = useLevi((s) => s.part2Locked);
  const designMode = useLevi((s) => s.designMode);
  const compost = useLevi((s) => s.compost);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [more, setMore] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, busy, pending]);

  const suggestions = useMemo(() => {
    return [
      goal ? "Hold me to my goal" : "Help me name a goal this week",
      "Challenge what I’m avoiding",
      "Help me start a story",
      "I want a tiny local tool",
    ];
  }, [goal]);

  function confirmPending(kind: "story" | "build", source: string) {
    if (kind === "build") {
      const p = addProject(source);
      addMessage("levi", `Started ${p.name}. It’s on Build — scaffold is already there.`);
      return;
    }
    const genre = detectGenre(source);
    const spun = fabricStory(genre, source);
    addStory({
      title: spun.title,
      genre,
      premise: source,
      body: spun.body,
      characters: spun.characters,
    });
    addMessage("levi", `Opened “${spun.title}.” It’s on Write when you want it.`);
  }

  function handleVerse(input: string) {
    if (ACTIVATION.part2.test(input)) {
      if (part2Locked) {
        addMessage("user", input);
        addMessage("levi", "Part 2 is already locked on this device.");
        return true;
      }
      const ev = lockPart2(name || "owner");
      addMessage("user", input);
      addMessage(
        "levi",
        `Part 2 appended and locked. Ledger event ${ev.id}. Provenance, seeds, compost, and owner sign are canon.`,
      );
      setView("ledger");
      return true;
    }
    if (ACTIVATION.symbiosis.test(input) || ACTIVATION.hydra.test(input)) {
      const ir = converge(
        runHeads(
          compileIR({
            task: "Symbiosis / Hydra awaken",
            owner: name,
            designMode,
          }),
        ),
      );
      setIR(ir);
      setHydraAwake(true);
      addMessage("user", input);
      addMessage(
        "levi",
        ACTIVATION.hydra.test(input)
          ? "Hydra is awake. Six heads on the lattice. Convergence is live."
          : "Symbiosis initiated. Dev-Mode (Levi) active. Hydra is on the lattice.",
      );
      setView("hydra");
      return true;
    }
    return false;
  }

  async function send(raw?: string) {
    const input = (raw ?? text).trim();
    if (!input || busy) return;
    setText("");

    if (handleVerse(input)) return;

    if (pending) {
      addMessage("user", input);
      if (/^(yes|y|do it|yes, do it|confirm)$/i.test(input)) {
        const job = pending;
        setPending(null);
        confirmPending(job.kind, job.text);
        return;
      }
      if (/^(no|nope|nah|nevermind|cancel|keep talking)$/i.test(input)) {
        setPending(null);
        addMessage("levi", "Okay. Staying here.");
        return;
      }
      setPending(null);
    }

    if (isBuildIntent(input)) {
      setPending({ kind: "build", text: input });
      addMessage("user", input);
      addMessage("levi", "That sounds like a local project. Start it, or keep talking?");
      return;
    }
    if (isWriteIntent(input)) {
      setPending({ kind: "story", text: input });
      addMessage("user", input);
      addMessage("levi", "I can open a story from that. Start it, or keep talking?");
      return;
    }

    addMessage("user", input);
    setBusy(true);
    const history = useLevi.getState().messages.slice(-12);
    const p = getPersona(persona);
    const local = () =>
      addMessage("levi", localReply({ input, name, goal, persona, shelf: shelfSummary() }));
    try {
      if (!catalystAllowed()) {
        local();
        return;
      }
      const result = await leviComplete({
        data: {
          maxTokens: p.noHero ? 180 : p.interrogation ? 220 : 700,
          messages: [
            {
              role: "system",
              content: companionSystem({
                name,
                goal,
                persona,
                shelf: shelfSummary(),
                mode: "talk",
                lessons: lessonsForPrompt(compost),
                designMode,
              }),
            },
            ...history.map((m) => ({
              role: (m.role === "levi" ? "assistant" : "user") as "assistant" | "user",
              content: m.text,
            })),
          ],
        },
      });
      if (!result.ok || !result.text) {
        local();
        return;
      }
      addMessage("levi", result.text);
    } catch {
      local();
    } finally {
      setBusy(false);
    }
  }

  const shown = more ? PERSONAS : PERSONAS.filter((p) => FEATURED_PERSONAS.includes(p.id));

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="border-b border-border px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-medium">Talk</div>
            <div className="text-xs text-muted">
              {getPersona(persona).blurb}
              {designMode === "sovereignty" ? " · local" : " · hybrid"}
            </div>
          </div>
        </div>
        <div className="mt-3 flex gap-1.5 overflow-x-auto pb-1">
          {shown.map((p) => (
            <button
              key={p.id}
              onClick={() => setPersona(p.id as PersonaId)}
              className={`h-8 shrink-0 rounded-full px-3 text-xs transition-colors duration-150 ${
                persona === p.id ? "bg-accent text-accent-fg" : "bg-elevated text-muted"
              }`}
            >
              {p.name}
            </button>
          ))}
          <button
            onClick={() => setMore((v) => !v)}
            className="h-8 shrink-0 rounded-full px-3 text-xs text-muted"
          >
            {more ? "Less" : "All"}
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-5">
        <div className="mx-auto flex max-w-2xl flex-col gap-4">
          {messages.map((m) => (
            <div key={m.id} className={m.role === "user" ? "ml-8 text-right" : "mr-8"}>
              <div
                className={`inline-block rounded-lg px-3.5 py-2.5 text-left text-sm leading-relaxed whitespace-pre-wrap ${
                  m.role === "user" ? "bg-elevated text-fg" : "bg-surface text-fg"
                }`}
              >
                {m.text}
              </div>
              {m.role === "levi" && !m.composted && (
                <div>
                  <button
                    className="mt-1 text-micro text-subtle underline-offset-2 hover:underline"
                    onClick={() => {
                      addCompost(compostFailure({ source: "chat", failure: m.text }));
                      markComposted(m.id);
                    }}
                  >
                    Compost this
                  </button>
                </div>
              )}
            </div>
          ))}
          {pending && (
            <div className="rounded-lg border border-border bg-elevated px-3 py-3">
              <p className="text-sm">
                Start this as a {pending.kind === "build" ? "local project" : "story"}?
              </p>
              <div className="mt-2 flex gap-2">
                <Button size="sm" onClick={() => void send("yes")}>
                  Yes
                </Button>
                <Button size="sm" variant="ghost" onClick={() => void send("keep talking")}>
                  Keep talking
                </Button>
              </div>
            </div>
          )}
          {messages.length <= 1 && !pending && (
            <div className="flex flex-wrap gap-1.5 pt-2">
              {suggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => void send(s)}
                  className="h-9 rounded-full border border-border px-3 text-xs text-muted hover:bg-elevated hover:text-fg"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
          {busy && <p className="text-xs text-muted">Listening…</p>}
          <div ref={endRef} />
        </div>
      </div>

      <form
        className="border-t border-border p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <div className="mx-auto flex max-w-2xl gap-2">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Talk with LEVI"
            className="h-12 flex-1 rounded-md border border-border bg-elevated px-3 text-sm text-fg placeholder:text-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
          />
          <Button type="submit" size="icon" disabled={busy || !text.trim()} aria-label="Send">
            <ArrowUp className="size-4" />
          </Button>
        </div>
      </form>
    </div>
  );
}
