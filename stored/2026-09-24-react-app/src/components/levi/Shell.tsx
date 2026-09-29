import { useEffect } from "react";
import {
  Home,
  MessageSquare,
  PenLine,
  Hammer,
  Sparkles,
  TrendingUp,
  Hexagon,
  GitBranch,
  Scale,
  Recycle,
  ScrollText,
  Sun,
  Moon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useLevi, type View } from "@/lib/levi/store";
import { getPersona } from "@/lib/levi/personas";
import { HomeView } from "./Home";
import { TalkView } from "./Talk";
import { WriteView } from "./Write";
import { BuildView } from "./Build";
import { StudioView } from "./Studio";
import { FinanceView } from "./Finance";
import { HydraView } from "./Hydra";
import { EchoView } from "./Echo";
import { MandellaView } from "./Mandella";
import { CompostView } from "./Compost";
import { LedgerView } from "./Ledger";
import { Mark } from "./Mark";

const PRIMARY: { id: View; label: string; icon: typeof Home }[] = [
  { id: "home", label: "Home", icon: Home },
  { id: "talk", label: "Talk", icon: MessageSquare },
  { id: "write", label: "Write", icon: PenLine },
  { id: "build", label: "Build", icon: Hammer },
  { id: "studio", label: "Studio", icon: Sparkles },
  { id: "finance", label: "Finance", icon: TrendingUp },
];

const LATTICE: { id: View; label: string; icon: typeof Home }[] = [
  { id: "hydra", label: "Hydra", icon: Hexagon },
  { id: "echo", label: "Echo", icon: GitBranch },
  { id: "mandella", label: "Mandella", icon: Scale },
  { id: "compost", label: "Compost", icon: Recycle },
  { id: "ledger", label: "Ledger", icon: ScrollText },
];

const ALL_VIEWS = [...PRIMARY, ...LATTICE];
const LATTICE_IDS = new Set(LATTICE.map((i) => i.id));

function NavButton({
  item,
  current,
  onPick,
  compact,
}: {
  item: (typeof PRIMARY)[number];
  current: View;
  onPick: (v: View) => void;
  compact?: boolean;
}) {
  const active = current === item.id;
  return (
    <button
      onClick={() => onPick(item.id)}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-3 rounded-md text-sm transition-colors duration-150",
        compact
          ? "h-14 min-w-14 shrink-0 flex-col justify-center gap-1 px-2 text-micro"
          : "h-11 px-3",
        active ? "bg-elevated text-fg" : "text-muted hover:bg-surface hover:text-fg",
      )}
    >
      <item.icon className="size-4" strokeWidth={1.75} />
      {item.label}
    </button>
  );
}

/** Honest connection state: what the store actually believes, nothing more. */
function StatusLine() {
  const designMode = useLevi((s) => s.designMode);
  const hydraAwake = useLevi((s) => s.hydraAwake);
  const part2Locked = useLevi((s) => s.part2Locked);
  const halted = useLevi((s) => s.halted);
  return (
    <p className="flex items-center gap-1.5 text-micro leading-relaxed text-subtle">
      <span
        className={cn(
          "size-1.5 rounded-full",
          halted ? "bg-danger" : designMode === "hybrid" ? "bg-live" : "bg-subtle",
        )}
        aria-hidden
      />
      {halted ? "Halted" : designMode === "hybrid" ? "Hybrid" : "Sovereign"}
      {hydraAwake ? " · hydra" : ""}
      {part2Locked ? " · P2" : ""}
    </p>
  );
}

function ThemeToggle() {
  const theme = useLevi((s) => s.theme);
  const setTheme = useLevi((s) => s.setTheme);
  const next = theme === "void" ? "light" : "void";
  return (
    <button
      onClick={() => setTheme(next)}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      className="flex size-9 items-center justify-center rounded-full text-muted transition-colors hover:bg-elevated hover:text-fg"
    >
      {theme === "void" ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  );
}

/** Current register chip — taps through to Talk. */
function RegisterChip() {
  const persona = useLevi((s) => s.persona);
  const setView = useLevi((s) => s.setView);
  const p = getPersona(persona);
  return (
    <button
      onClick={() => setView("talk")}
      title={p.blurb}
      className="flex h-8 items-center gap-1.5 rounded-full bg-elevated px-3 text-xs text-muted transition-colors hover:text-fg"
    >
      <span className="size-1.5 rounded-full bg-accent" aria-hidden />
      {p.name}
    </button>
  );
}

export function Shell() {
  const view = useLevi((s) => s.view);
  const setView = useLevi((s) => s.setView);
  const name = useLevi((s) => s.name);
  const touchStreak = useLevi((s) => s.touchStreak);

  useEffect(() => {
    touchStreak();
  }, [touchStreak]);

  return (
    <div className="flex h-dvh overflow-hidden bg-bg">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-border px-4 py-6 md:flex">
        <div className="flex items-center gap-2 px-2">
          <Mark className="size-5 text-accent" />
          <div>
            <div className="font-display text-2xl leading-none tracking-tight">LEVI</div>
            <div className="mt-1 text-xs text-muted">{name || "companion"}</div>
          </div>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </div>
        <nav className="mt-8 flex flex-col gap-1">
          {PRIMARY.map((item) => (
            <NavButton key={item.id} item={item} current={view} onPick={setView} />
          ))}
        </nav>
        <p className="mt-6 px-2 text-micro tracking-kicker text-subtle uppercase">Lattice</p>
        <nav className="mt-2 flex flex-col gap-1">
          {LATTICE.map((item) => (
            <NavButton key={item.id} item={item} current={view} onPick={setView} />
          ))}
        </nav>
        <div className="mt-auto px-2">
          <StatusLine />
        </div>
      </aside>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* Mobile top bar: wordmark, register, theme. */}
        <div className="flex items-center gap-2 border-b border-border px-4 py-2.5 md:hidden">
          <Mark className="size-4 text-accent" />
          <span className="font-display text-lg leading-none tracking-tight">LEVI</span>
          <div className="ml-auto flex items-center gap-1.5">
            <RegisterChip />
            <ThemeToggle />
          </div>
        </div>

        <div
          className={cn(
            "flex min-h-0 min-w-0 flex-1 flex-col pb-16 md:pb-0",
            view !== "talk" && "overflow-y-auto",
          )}
        >
          {LATTICE_IDS.has(view) && (
            <div className="flex gap-1 overflow-x-auto border-b border-border px-3 py-2 md:hidden">
              {LATTICE.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setView(item.id)}
                  className={cn(
                    "h-8 shrink-0 rounded-full px-3 text-xs",
                    view === item.id ? "bg-accent text-accent-fg" : "bg-elevated text-muted",
                  )}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
          {view === "home" && <HomeView />}
          {view === "talk" && <TalkView />}
          {view === "write" && <WriteView />}
          {view === "build" && <BuildView />}
          {view === "studio" && <StudioView />}
          {view === "finance" && <FinanceView />}
          {view === "hydra" && <HydraView />}
          {view === "echo" && <EchoView />}
          {view === "mandella" && <MandellaView />}
          {view === "compost" && <CompostView />}
          {view === "ledger" && <LedgerView />}
        </div>
      </div>

      {/* Mobile: one scrollable row for all ten views. */}
      <nav className="safe-bottom fixed inset-x-0 bottom-0 z-20 border-t border-border bg-bg/95 backdrop-blur md:hidden">
        <div className="flex gap-0.5 overflow-x-auto px-2">
          {ALL_VIEWS.map((item) => (
            <NavButton key={item.id} item={item} current={view} onPick={setView} compact />
          ))}
        </div>
      </nav>
    </div>
  );
}
