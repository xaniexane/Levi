import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, Check, Copy, RotateCcw, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  FEATURED_PERSONAS,
  PERSONAS,
  REGISTERS,
  getPersona,
  isRegister,
  type Persona,
  type PersonaId,
} from "@/lib/levi/personas";
import type { ChatMessage } from "@/lib/levi/ai";
import { streamChat } from "@/lib/levi/stream";
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
  const updateMessage = useLevi((s) => s.updateMessage);
  const truncateAfter = useLevi((s) => s.truncateAfter);
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
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const busyRef = useRef(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const nearBottomRef = useRef(true);

  // Auto-scroll only while the user is near the bottom — never yank them
  // back up after they've scrolled away to re-read.
  useEffect(() => {
    if (!nearBottomRef.current) return;
    endRef.current?.scrollIntoView({ behavior: streamingId ? "auto" : "smooth" });
  }, [messages, busy, pending, streamingId]);

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

  /** The cloud reply path — streams tokens live, falls back locally and honestly. */
  async function respond(input: string) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);

    const fallback = () => localReply({ input, name, goal, persona, shelf: shelfSummary() });

    if (!catalystAllowed()) {
      addMessage("levi", fallback());
      busyRef.current = false;
      setBusy(false);
      return;
    }

    const p = getPersona(persona);
    const history = useLevi.getState().messages.slice(-12);
    const draft = addMessage("levi", "");
    setStreamingId(draft.id);
    const aborter = new AbortController();
    abortRef.current = aborter;

    let acc = "";
    try {
      const { error } = await streamChat({
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
          ...history.map((m): ChatMessage => ({
            role: m.role === "levi" ? "assistant" : "user",
            content: m.text,
          })),
        ],
        maxTokens: p.noHero ? 180 : p.interrogation ? 220 : 700,
        signal: aborter.signal,
        onToken: (t) => {
          acc += t;
          updateMessage(draft.id, acc);
        },
      });
      if (error || !acc.trim()) {
        updateMessage(draft.id, fallback());
      }
    } catch {
      updateMessage(draft.id, fallback());
    } finally {
      abortRef.current = null;
      setStreamingId(null);
      busyRef.current = false;
      setBusy(false);
    }
  }

  async function send(raw?: string) {
    const input = (raw ?? text).trim();
    if (!input || busyRef.current) return;
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
    await respond(input);
  }

  /** Retry: drop the trailing reply and run the same user turn again. */
  function retry(userId: string, input: string) {
    if (busyRef.current) return;
    truncateAfter(userId);
    void respond(input);
  }

  async function copy(id: string, value: string) {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = value;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    setCopiedId(id);
    window.setTimeout(() => setCopiedId((c) => (c === id ? null : c)), 1400);
  }

  function stop() {
    abortRef.current?.abort();
  }

  const featured: Persona[] = PERSONAS.filter((p) => FEATURED_PERSONAS.includes(p.id));
  const classics = PERSONAS.filter((p) => !p.register);

  const personaChip = (p: Persona) => (
    <button
      key={p.id}
      title={p.blurb}
      onClick={() => setPersona(p.id as PersonaId)}
      className={`flex h-8 shrink-0 items-center gap-1.5 rounded-full px-3 text-xs transition-colors duration-150 ${
        persona === p.id ? "bg-accent text-accent-fg" : "bg-elevated text-muted hover:text-fg"
      }`}
    >
      {p.register && persona !== p.id && (
        <span className="size-1.5 rounded-full bg-accent" aria-hidden />
      )}
      {p.name}
    </button>
  );

  const current = getPersona(persona);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="border-b border-border px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-sm font-medium">
              Talk
              {isRegister(persona) && (
                <span className="rounded-full bg-elevated px-2 py-0.5 text-micro text-muted">
                  register
                </span>
              )}
            </div>
            <div className="text-xs text-muted">
              {current.blurb}
              {designMode === "sovereignty" ? " · local" : " · hybrid"}
            </div>
          </div>
        </div>
        <div className="mt-3 flex gap-1.5 overflow-x-auto pb-1">
          {!more ? (
            <>
              {featured.map(personaChip)}
              <button
                onClick={() => setMore(true)}
                className="h-8 shrink-0 rounded-full px-3 text-xs text-muted hover:text-fg"
              >
                All
              </button>
            </>
          ) : (
            <button
              onClick={() => setMore(false)}
              className="h-8 shrink-0 rounded-full px-3 text-xs text-muted hover:text-fg"
            >
              Less
            </button>
          )}
        </div>
        {more && (
          <div className="flex flex-col gap-2 pb-1">
            <div className="text-micro uppercase tracking-[0.18em] text-subtle">
              LEVI registers
            </div>
            <div className="flex flex-wrap gap-1.5">{REGISTERS.map(personaChip)}</div>
            <div className="text-micro uppercase tracking-[0.18em] text-subtle">
              Classic personas
            </div>
            <div className="flex flex-wrap gap-1.5">{classics.map(personaChip)}</div>
          </div>
        )}
      </header>

      <div
        ref={scrollRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          nearBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 140;
        }}
        className="flex-1 overflow-y-auto px-4 py-5"
      >
        <div className="mx-auto flex max-w-2xl flex-col gap-4">
          {messages.map((m) => {
            const isStreaming = streamingId === m.id;
            const showBubble = m.text.length > 0 || isStreaming;
            return (
              <div
                key={m.id}
                className={`animate-msg-in ${m.role === "user" ? "ml-8 text-right" : "mr-8"}`}
              >
                {showBubble && (
                  <div
                    className={`inline-block rounded-lg px-3.5 py-2.5 text-left text-sm leading-relaxed whitespace-pre-wrap ${
                      m.role === "user" ? "bg-elevated text-fg" : "bg-surface text-fg"
                    } ${isStreaming ? "streaming-glow" : ""}`}
                  >
                    {m.text}
                    {isStreaming && m.text.length === 0 && (
                      <span
                        className="flex items-center gap-1 py-1"
                        role="status"
                        aria-label="LEVI is thinking"
                      >
                        {[0, 1, 2].map((i) => (
                          <span key={i} className="typing-dot size-1.5 rounded-full bg-muted" />
                        ))}
                      </span>
                    )}
                  </div>
                )}
                {m.role === "levi" && !isStreaming && m.text && (
                  <div className="mt-1 flex items-center gap-3">
                    <button
                      className="flex items-center gap-1 text-micro text-subtle underline-offset-2 hover:text-muted hover:underline"
                      onClick={() => void copy(m.id, m.text)}
                      aria-label="Copy reply"
                    >
                      {copiedId === m.id ? (
                        <Check className="size-3" />
                      ) : (
                        <Copy className="size-3" />
                      )}
                      {copiedId === m.id ? "Copied" : "Copy"}
                    </button>
                    <button
                      className="flex items-center gap-1 text-micro text-subtle underline-offset-2 hover:text-muted hover:underline disabled:opacity-40"
                      disabled={busy}
                      onClick={() => {
                        const idx = messages.findIndex((x) => x.id === m.id);
                        const prev = [...messages.slice(0, idx)]
                          .reverse()
                          .find((x) => x.role === "user");
                        if (prev) retry(prev.id, prev.text);
                      }}
                      aria-label="Retry reply"
                    >
                      <RotateCcw className="size-3" />
                      Retry
                    </button>
                    {!m.composted && (
                      <button
                        className="text-micro text-subtle underline-offset-2 hover:text-muted hover:underline"
                        onClick={() => {
                          addCompost(compostFailure({ source: "chat", failure: m.text }));
                          markComposted(m.id);
                        }}
                      >
                        Compost this
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
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
            placeholder={`Talk with ${current.name}`}
            className="h-12 flex-1 rounded-md border border-border bg-elevated px-3 text-sm text-fg placeholder:text-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
          />
          {busy ? (
            <Button
              type="button"
              size="icon"
              variant="ghost"
              onClick={stop}
              aria-label="Stop generating"
            >
              <Square className="size-4" />
            </Button>
          ) : (
            <Button type="submit" size="icon" disabled={!text.trim()} aria-label="Send">
              <ArrowUp className="size-4" />
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}
