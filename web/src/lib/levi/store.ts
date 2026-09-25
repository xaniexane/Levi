import { create } from "zustand";
import { persist } from "zustand/middleware";
import { uid } from "@/lib/utils";
import type { PersonaId } from "./personas";
import { DEFAULT_THEME, applyTheme, type Theme } from "./theme";
import { compileBuild, nextStage, type BuildIR, type Stage } from "./nl-ir";
import { greeting, scaffoldFromIR } from "./local";
import { nextStreak } from "./retention";
import type { PlanId } from "./monetize";
import type { GraphChar } from "./characters";
import type {
  CompostEntry,
  DesignMode,
  EchoRun,
  HydraIR,
  JournalNote,
  Kpis,
  LedgerEvent,
  MandellaScenario,
  StressResult,
  View,
} from "./types";
import { appendEvent, genesisEvent } from "./hydra";

export type { View } from "./types";
export type Loop = "companion" | "writing" | "building";

export type ChatMsg = {
  id: string;
  role: "user" | "levi";
  text: string;
  at: number;
  composted?: boolean;
};

export type Character = {
  name: string;
  archetype: string;
  want: string;
  need: string;
};

export type Story = {
  id: string;
  title: string;
  genre: string;
  premise: string;
  body: string;
  characters: Character[];
  modes: string[];
  updatedAt: number;
};

export type Project = {
  id: string;
  name: string;
  idea: string;
  ir: BuildIR;
  stage: Stage;
  code: string;
  notes: string;
  hitlApproved: boolean;
  updatedAt: number;
};

export type DemoId = "talk" | "write" | "build" | "mirror";

type LeviState = {
  onboarded: boolean;
  name: string;
  goal: string;
  loop: Loop;
  view: View;
  persona: PersonaId;
  messages: ChatMsg[];
  stories: Story[];
  activeStoryId: string | null;
  projects: Project[];
  activeProjectId: string | null;
  pending: { kind: "story" | "build"; text: string } | null;
  streak: number;
  lastVisit: string | null;
  ritualDone: string | null;
  demos: DemoId[];
  plan: PlanId;
  graph: GraphChar[];
  designMode: DesignMode;
  hydraAwake: boolean;
  part2Locked: boolean;
  part2EventId: string | null;
  halted: boolean;
  ir: HydraIR | null;
  ledger: LedgerEvent[];
  echoes: EchoRun[];
  mandellas: MandellaScenario[];
  compost: CompostEntry[];
  journal: JournalNote[];
  stress: StressResult[];
  kpis: Kpis;
  completeOnboarding: (p: { name: string; goal: string; loop: Loop }) => void;
  updateProfile: (p: { name?: string; goal?: string }) => void;
  setView: (v: View) => void;
  setPersona: (p: PersonaId) => void;
  addMessage: (role: ChatMsg["role"], text: string) => ChatMsg;
  updateMessage: (id: string, text: string) => void;
  truncateAfter: (id: string) => void;
  markComposted: (id: string) => void;
  theme: Theme;
  setTheme: (t: Theme) => void;
  setPending: (p: LeviState["pending"]) => void;
  addStory: (s: Omit<Story, "id" | "updatedAt" | "modes">) => Story;
  updateStory: (id: string, patch: Partial<Story>) => void;
  addProject: (idea: string) => Project;
  updateProject: (id: string, patch: Partial<Project>) => void;
  advanceProject: (id: string) => void;
  approveHitl: (id: string) => void;
  touchStreak: () => void;
  completeRitual: () => void;
  markDemo: (id: DemoId) => void;
  setPlan: (p: PlanId) => void;
  addGraphChar: (c: GraphChar) => void;
  setDesignMode: (m: DesignMode) => void;
  setHydraAwake: (v: boolean) => void;
  setIR: (ir: HydraIR | null) => void;
  ledgerPush: (kind: string, summary: string, seed: string, signature?: string) => LedgerEvent;
  lockPart2: (owner: string) => LedgerEvent;
  setHalted: (v: boolean) => void;
  addEcho: (r: EchoRun) => void;
  addMandella: (s: MandellaScenario) => void;
  addCompost: (e: CompostEntry) => void;
  updateCompost: (e: CompostEntry) => void;
  addJournal: (text: string) => JournalNote;
  setStress: (results: StressResult[], kpis: Kpis) => void;
  importBackup: (raw: string) => boolean;
  exportBackup: () => string;
  resetLocal: () => void;
};

const kpis0: Kpis = { cis: 1, hr: 0, ccr: 0, rt: 0, di: 0, rs: 1 };

const empty = {
  onboarded: false,
  name: "",
  goal: "",
  loop: "companion" as Loop,
  view: "home" as View,
  persona: "normal" as PersonaId,
  theme: DEFAULT_THEME as Theme,
  messages: [] as ChatMsg[],
  stories: [] as Story[],
  activeStoryId: null as string | null,
  projects: [] as Project[],
  activeProjectId: null as string | null,
  pending: null as LeviState["pending"],
  streak: 0,
  lastVisit: null as string | null,
  ritualDone: null as string | null,
  demos: [] as DemoId[],
  plan: "local" as PlanId,
  graph: [] as GraphChar[],
  designMode: "sovereignty" as DesignMode,
  hydraAwake: false,
  part2Locked: false,
  part2EventId: null as string | null,
  halted: false,
  ir: null as HydraIR | null,
  ledger: [] as LedgerEvent[],
  echoes: [] as EchoRun[],
  mandellas: [] as MandellaScenario[],
  compost: [] as CompostEntry[],
  journal: [] as JournalNote[],
  stress: [] as StressResult[],
  kpis: kpis0,
};

export const useLevi = create<LeviState>()(
  persist(
    (set, get) => ({
      ...empty,
      completeOnboarding: ({ name, goal, loop }) => {
        const s = nextStreak(null, 0);
        const genesis = genesisEvent(name);
        set({
          onboarded: true,
          name,
          goal,
          loop,
          view: loop === "writing" ? "write" : loop === "building" ? "build" : "talk",
          streak: s.streak,
          lastVisit: s.lastVisit,
          ledger: [genesis],
          messages: [
            {
              id: uid("m"),
              role: "levi",
              text: greeting({ name, goal, loop }),
              at: Date.now(),
            },
          ],
        });
      },
      updateProfile: (p) => set(p),
      setView: (view) => set({ view }),
      setPersona: (persona) => set({ persona }),
      setTheme: (theme) => {
        set({ theme });
        if (typeof document !== "undefined") applyTheme(theme);
      },
      addMessage: (role, text) => {
        const msg: ChatMsg = { id: uid("m"), role, text, at: Date.now() };
        set({ messages: [...get().messages, msg].slice(-80) });
        return msg;
      },
      updateMessage: (id, text) =>
        set({
          messages: get().messages.map((m) => (m.id === id ? { ...m, text } : m)),
        }),
      truncateAfter: (id) => {
        const msgs = get().messages;
        const idx = msgs.findIndex((m) => m.id === id);
        if (idx >= 0) set({ messages: msgs.slice(0, idx + 1) });
      },
      markComposted: (id) =>
        set({
          messages: get().messages.map((m) => (m.id === id ? { ...m, composted: true } : m)),
        }),
      setPending: (pending) => set({ pending }),
      addStory: (s) => {
        const story: Story = {
          ...s,
          id: uid("story"),
          modes: ["create"],
          updatedAt: Date.now(),
        };
        set({ stories: [story, ...get().stories], activeStoryId: story.id, view: "write" });
        get().ledgerPush("STORY", `Story “${story.title}” (${story.genre})`, story.id);
        return story;
      },
      updateStory: (id, patch) =>
        set({
          stories: get().stories.map((s) =>
            s.id === id ? { ...s, ...patch, updatedAt: Date.now() } : s,
          ),
        }),
      addProject: (idea) => {
        const ir = compileBuild(idea);
        const project: Project = {
          id: uid("proj"),
          name: ir.name,
          idea,
          ir,
          stage: "scaffold",
          code: scaffoldFromIR(ir),
          notes: ir.constraints.includes("tiny-slice")
            ? "Scoped to a tiny local slice. Scaffold is on the shelf."
            : "Local scaffold written. HITL before anything leaves this device.",
          hitlApproved: false,
          updatedAt: Date.now(),
        };
        set({
          projects: [project, ...get().projects],
          activeProjectId: project.id,
          view: "build",
        });
        get().ledgerPush("BUILD", `Project ${project.name} compiled`, project.id);
        return project;
      },
      updateProject: (id, patch) =>
        set({
          projects: get().projects.map((p) =>
            p.id === id ? { ...p, ...patch, updatedAt: Date.now() } : p,
          ),
        }),
      advanceProject: (id) =>
        set({
          projects: get().projects.map((p) => {
            if (p.id !== id) return p;
            const next = nextStage(p.stage);
            if (next === "implement" && !p.hitlApproved) {
              return {
                ...p,
                stage: "hitl",
                notes: "HITL required before implement. Silence is not approval.",
                updatedAt: Date.now(),
              };
            }
            return { ...p, stage: next, updatedAt: Date.now() };
          }),
        }),
      approveHitl: (id) => {
        set({
          projects: get().projects.map((p) =>
            p.id === id
              ? {
                  ...p,
                  hitlApproved: true,
                  stage: nextStage("hitl"),
                  notes: "HITL approved. Implement is open.",
                  updatedAt: Date.now(),
                }
              : p,
          ),
        });
        get().ledgerPush("HITL", `HITL approved for ${id}`, id, get().name);
      },
      touchStreak: () => {
        const cur = get();
        const n = nextStreak(cur.lastVisit, cur.streak);
        if (n.touched) set({ streak: n.streak, lastVisit: n.lastVisit });
      },
      completeRitual: () => {
        const cur = get();
        const n = nextStreak(cur.lastVisit, cur.streak);
        set({ ritualDone: n.lastVisit, streak: n.streak, lastVisit: n.lastVisit });
        get().ledgerPush("RITUAL", "Daily ritual marked", n.lastVisit);
      },
      markDemo: (id) => {
        const demos = get().demos;
        if (demos.includes(id)) return;
        set({ demos: [...demos, id] });
      },
      setPlan: (plan) => set({ plan }),
      addGraphChar: (c) => set({ graph: [c, ...get().graph].slice(0, 40) }),
      setDesignMode: (designMode) => {
        set({ designMode });
        get().ledgerPush("MODE", `Design mode → ${designMode}`, designMode, get().name);
      },
      setHydraAwake: (hydraAwake) => set({ hydraAwake }),
      setIR: (ir) => set({ ir }),
      ledgerPush: (kind, summary, seed, signature) => {
        const ev = appendEvent(get().ledger, kind, summary, seed, signature);
        set({ ledger: [ev, ...get().ledger].slice(0, 400) });
        return ev;
      },
      lockPart2: (owner) => {
        const id = `PART2-APPEND-${uid("p2").slice(3)}`;
        const ev = appendEvent(
          get().ledger,
          id,
          "Part 2 appended and locked. Operational hardening is canon.",
          id,
          owner,
        );
        set({
          ledger: [ev, ...get().ledger].slice(0, 400),
          part2Locked: true,
          part2EventId: ev.id,
        });
        return ev;
      },
      setHalted: (halted) => {
        set({ halted, ir: get().ir ? { ...get().ir!, halted } : get().ir });
        get().ledgerPush(halted ? "KILL" : "RESUME", halted ? "Kill switch" : "Resumed", "halt");
      },
      addEcho: (r) => {
        set({ echoes: [r, ...get().echoes].slice(0, 40) });
        get().ledgerPush("ECHO", `Echo seed “${r.seed.slice(0, 48)}”`, r.id);
      },
      addMandella: (s) => {
        set({ mandellas: [s, ...get().mandellas].slice(0, 40) });
        get().ledgerPush("MANDELLA", `${s.domain} · ${s.recommended}`, s.id);
      },
      addCompost: (e) => {
        set({ compost: [e, ...get().compost].slice(0, 80) });
        get().ledgerPush("COMPOST", e.lesson.slice(0, 80), e.id);
      },
      updateCompost: (e) =>
        set({
          compost: get().compost.map((c) => (c.id === e.id ? e : c)),
        }),
      addJournal: (text) => {
        const note: JournalNote = {
          id: uid("jou"),
          text: text.trim(),
          createdAt: new Date().toISOString(),
        };
        set({ journal: [note, ...get().journal].slice(0, 80) });
        get().ledgerPush("JOURNAL", note.text.slice(0, 80), note.id);
        return note;
      },
      setStress: (stress, kpis) => {
        set({ stress, kpis });
        get().ledgerPush(
          "STRESS",
          `${stress.filter((r) => r.pass).length}/${stress.length} passed`,
          "stress",
        );
      },
      exportBackup: () => {
        const s = get();
        return JSON.stringify(
          {
            v: 1,
            name: s.name,
            goal: s.goal,
            stories: s.stories,
            projects: s.projects,
            ledger: s.ledger,
            echoes: s.echoes,
            mandellas: s.mandellas,
            compost: s.compost,
            journal: s.journal,
            ir: s.ir,
            part2Locked: s.part2Locked,
            designMode: s.designMode,
            kpis: s.kpis,
          },
          null,
          2,
        );
      },
      importBackup: (raw) => {
        try {
          const data = JSON.parse(raw) as Partial<LeviState> & { v?: number };
          if (!data || typeof data !== "object") return false;
          set({
            name: data.name ?? get().name,
            goal: data.goal ?? get().goal,
            stories: data.stories ?? get().stories,
            projects: data.projects ?? get().projects,
            ledger: data.ledger ?? get().ledger,
            echoes: data.echoes ?? get().echoes,
            mandellas: data.mandellas ?? get().mandellas,
            compost: data.compost ?? get().compost,
            journal: data.journal ?? get().journal,
            ir: data.ir ?? get().ir,
            part2Locked: data.part2Locked ?? get().part2Locked,
            designMode: data.designMode ?? get().designMode,
            kpis: data.kpis ?? get().kpis,
          });
          get().ledgerPush("RESTORE", "Backup restored", "restore", get().name);
          return true;
        } catch {
          return false;
        }
      },
      resetLocal: () => set({ ...empty }),
    }),
    {
      name: "levi-life",
      merge: (persisted, current) => ({
        ...current,
        ...(persisted as object),
      }),
    },
  ),
);

export function shelfSummary() {
  const s = useLevi.getState();
  const bits: string[] = [];
  if (s.stories[0]) bits.push(`story “${s.stories[0].title}” (${s.stories[0].genre})`);
  if (s.projects[0]) bits.push(`project ${s.projects[0].name} @ ${s.projects[0].stage}`);
  if (s.part2Locked) bits.push("Part 2 locked");
  return bits.join("; ");
}

export function catalystAllowed() {
  const s = useLevi.getState();
  return s.designMode === "hybrid" && !s.halted;
}
