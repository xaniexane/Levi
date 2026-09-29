import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLevi } from "@/lib/levi/store";
import { GENRES } from "@/lib/levi/genres";
import { PERSONAS } from "@/lib/levi/personas";
import { todayKey } from "@/lib/levi/retention";
import { PLANS } from "@/lib/levi/monetize";
import { ORGAN_MAP } from "@/lib/levi/types";
import { Mark } from "./Mark";

const LATTICE_CARDS: {
  view: "hydra" | "echo" | "mandella" | "compost" | "ledger";
  title: string;
  body: string;
}[] = [
  { view: "hydra", title: "Hydra", body: "Six heads. Converge. Sign." },
  { view: "echo", title: "Echo", body: "Taken / not-taken / wild." },
  { view: "mandella", title: "Mandella", body: "A/B/C. Phantoms remain." },
  { view: "compost", title: "Compost", body: "Quarantine. Learn. Non-canon." },
  { view: "ledger", title: "Ledger", body: "Seeds, Part 2 lock, journal." },
];

export function HomeView() {
  const name = useLevi((s) => s.name);
  const goal = useLevi((s) => s.goal);
  const stories = useLevi((s) => s.stories);
  const projects = useLevi((s) => s.projects);
  const messages = useLevi((s) => s.messages);
  const streak = useLevi((s) => s.streak);
  const ritualDone = useLevi((s) => s.ritualDone);
  const demos = useLevi((s) => s.demos);
  const plan = useLevi((s) => s.plan);
  const kpis = useLevi((s) => s.kpis);
  const designMode = useLevi((s) => s.designMode);
  const part2Locked = useLevi((s) => s.part2Locked);
  const hydraAwake = useLevi((s) => s.hydraAwake);
  const setView = useLevi((s) => s.setView);
  const updateProfile = useLevi((s) => s.updateProfile);
  const completeRitual = useLevi((s) => s.completeRitual);
  const touchStreak = useLevi((s) => s.touchStreak);
  const resetLocal = useLevi((s) => s.resetLocal);
  const [editing, setEditing] = useState(false);
  const [draftGoal, setDraftGoal] = useState(goal);

  useEffect(() => {
    touchStreak();
  }, [touchStreak]);

  const setStoryId = (id: string) => {
    useLevi.setState({ activeStoryId: id, view: "write" });
  };
  const setProjectId = (id: string) => {
    useLevi.setState({ activeProjectId: id, view: "build" });
  };

  const latest = [...stories, ...projects].sort((a, b) => b.updatedAt - a.updatedAt)[0];
  const lastLevi = [...messages].reverse().find((m) => m.role === "levi");
  const ritualToday = ritualDone === todayKey();
  const planName = PLANS.find((p) => p.id === plan)?.name ?? "Local";

  return (
    <main className="mx-auto w-full max-w-2xl px-5 py-8 md:py-12">
      <Mark className="size-7 text-accent" />
      <p className="mt-4 text-xs tracking-kicker text-muted uppercase">Home · morning merged</p>
      <h1 className="mt-2 font-display text-4xl">{name ? `${name}.` : "You’re here."}</h1>
      <p className="mt-2 text-sm text-muted">
        {streak > 0 ? `${streak}-day return` : "First day"} · {planName} · {designMode} ·{" "}
        {demos.length}/4 demos
        {part2Locked ? " · Part 2 locked" : ""}
        {hydraAwake ? " · hydra" : ""}
      </p>

      {editing ? (
        <form
          className="mt-4 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            updateProfile({ goal: draftGoal.trim() });
            setEditing(false);
          }}
        >
          <Input
            value={draftGoal}
            onChange={(e) => setDraftGoal(e.target.value)}
            placeholder="One goal this week"
            autoFocus
          />
          <Button type="submit">Hold</Button>
        </form>
      ) : goal ? (
        <p className="mt-3 text-muted">
          This week: {goal}{" "}
          <button
            className="text-xs text-subtle underline-offset-2 hover:underline"
            onClick={() => {
              setDraftGoal(goal);
              setEditing(true);
            }}
          >
            edit
          </button>
        </p>
      ) : (
        <p className="mt-3 text-muted">
          No weekly goal.{" "}
          <button
            className="text-subtle underline-offset-2 hover:underline"
            onClick={() => setEditing(true)}
          >
            Set one
          </button>
        </p>
      )}

      <dl className="mt-6 grid grid-cols-3 gap-2 text-xs sm:grid-cols-6">
        {(
          [
            ["CIS", kpis.cis.toFixed(2)],
            ["HR", String(kpis.hr)],
            ["CCR", String(kpis.ccr)],
            ["RT", kpis.rt ? `${kpis.rt}ms` : "—"],
            ["DI", String(kpis.di)],
            ["RS", String(kpis.rs)],
          ] as const
        ).map(([k, v]) => (
          <div key={k} className="rounded-md border border-border bg-surface px-2 py-2">
            <div className="text-micro text-muted">{k}</div>
            <div className="font-mono tabular-nums">{v}</div>
          </div>
        ))}
      </dl>

      <div className="mt-6 rounded-xl border border-border bg-surface px-4 py-4">
        <div className="text-xs text-muted">Daily ritual</div>
        <p className="mt-1 text-sm">
          Name the constraint. One reversible step. Come back tomorrow.
        </p>
        <Button
          className="mt-3"
          size="sm"
          variant={ritualToday ? "quiet" : "primary"}
          onClick={() => {
            completeRitual();
            setView("talk");
          }}
        >
          {ritualToday ? "Ritual marked · talk" : "Mark today · talk"}
        </Button>
      </div>

      {lastLevi && (
        <button
          onClick={() => setView("talk")}
          className="mt-4 w-full rounded-xl border border-border bg-surface px-4 py-4 text-left hover:bg-elevated"
        >
          <div className="text-xs text-muted">Continue talking</div>
          <p className="mt-1 line-clamp-2 text-sm text-fg">{lastLevi.text}</p>
        </button>
      )}

      <section className="mt-8">
        <h2 className="text-sm font-medium text-muted">Lattice</h2>
        <p className="mt-1 text-xs text-muted">Old organs kept. Hydra and ledger added.</p>
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
          {LATTICE_CARDS.map((c) => (
            <button
              key={c.view}
              onClick={() => setView(c.view)}
              className="rounded-xl border border-border bg-surface px-3 py-3 text-left hover:bg-elevated"
            >
              <div className="text-sm font-medium">{c.title}</div>
              <p className="mt-1 text-xs text-muted">{c.body}</p>
            </button>
          ))}
        </div>
      </section>

      <div className="mt-8 flex flex-wrap gap-2">
        <Button onClick={() => setView("talk")}>Talk</Button>
        <Button variant="outline" onClick={() => setView("write")}>
          Write
        </Button>
        <Button variant="outline" onClick={() => setView("build")}>
          Build
        </Button>
        <Button variant="quiet" onClick={() => setView("studio")}>
          Demos & studio
        </Button>
        {latest && (
          <Button
            variant="quiet"
            onClick={() => {
              if ("genre" in latest) setStoryId(latest.id);
              else setProjectId(latest.id);
            }}
          >
            Continue work
          </Button>
        )}
      </div>

      <section className="mt-10">
        <h2 className="text-sm font-medium text-muted">Shelf</h2>
        {stories.length === 0 && projects.length === 0 ? (
          <p className="mt-3 text-sm text-subtle">
            Empty. Run a demo in Studio, or start Talk / Write / Build.
          </p>
        ) : (
          <ul className="mt-4 space-y-2">
            {stories.slice(0, 6).map((s) => (
              <li key={s.id}>
                <button
                  onClick={() => setStoryId(s.id)}
                  className="w-full rounded-lg border border-border bg-surface px-4 py-3 text-left hover:bg-elevated"
                >
                  <div className="text-sm font-medium">{s.title}</div>
                  <div className="mt-0.5 text-xs text-muted">
                    story · {s.genre.replaceAll("_", " ")}
                  </div>
                </button>
              </li>
            ))}
            {projects.slice(0, 6).map((p) => (
              <li key={p.id}>
                <button
                  onClick={() => setProjectId(p.id)}
                  className="w-full rounded-lg border border-border bg-surface px-4 py-3 text-left hover:bg-elevated"
                >
                  <div className="text-sm font-medium">{p.name}</div>
                  <div className="mt-0.5 text-xs text-muted">
                    project · {p.stage}
                    {p.hitlApproved ? " · HITL ok" : ""}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="mt-10 text-xs text-subtle">
        {ORGAN_MAP.filter((r) => r.status === "merged").length} organs merged ·{" "}
        {ORGAN_MAP.filter((r) => r.status === "kept").length} kept ·{" "}
        {ORGAN_MAP.filter((r) => r.status === "added").length} added · {GENRES.length} genres ·{" "}
        {PERSONAS.length} personas
      </p>
      <button
        className="mt-4 text-micro text-subtle underline-offset-2 hover:underline"
        onClick={() => {
          if (window.confirm("Clear this device’s LEVI shelf and start over?")) resetLocal();
        }}
      >
        Start over
      </button>
    </main>
  );
}
