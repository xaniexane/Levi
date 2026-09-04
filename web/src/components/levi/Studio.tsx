import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { PLANS, SERVICES, type PlanId } from "@/lib/levi/monetize";
import { runMirror } from "@/lib/levi/mirror";
import { mintCharacter, AXIS_TYPES } from "@/lib/levi/characters";
import { useLevi, type DemoId } from "@/lib/levi/store";
import { fabricStory } from "@/lib/levi/local";

const DEMOS: { id: DemoId; title: string; body: string }[] = [
  { id: "talk", title: "Talk", body: "A grounded reply. No hype. Goal held." },
  { id: "write", title: "Write", body: "A systems-horror opening on the shelf." },
  { id: "build", title: "Build", body: "A local checklist CLI scaffold." },
  { id: "mirror", title: "Mirror", body: "Three coils. Pressure language vetoed." },
];

export function StudioView() {
  const plan = useLevi((s) => s.plan);
  const setPlan = useLevi((s) => s.setPlan);
  const demos = useLevi((s) => s.demos);
  const markDemo = useLevi((s) => s.markDemo);
  const addMessage = useLevi((s) => s.addMessage);
  const addStory = useLevi((s) => s.addStory);
  const addProject = useLevi((s) => s.addProject);
  const addGraphChar = useLevi((s) => s.addGraphChar);
  const graph = useLevi((s) => s.graph);
  const setView = useLevi((s) => s.setView);
  const name = useLevi((s) => s.name);
  const [seed, setSeed] = useState("must buy today — limited time booking pages for clinics");
  const [mirror, setMirror] = useState<ReturnType<typeof runMirror> | null>(null);

  function runDemo(id: DemoId) {
    if (id === "talk") {
      addMessage("user", "I’m spinning. Hold me to the week.");
      addMessage(
        "levi",
        `${name || "Friend"}. Spinning is too many open loops. Write them for three minutes. Circle only what is due in 48 hours. One ten-minute action. Everything else parks.\n\nDemo complete — this is Talk.`,
      );
      markDemo("talk");
      setView("talk");
      return;
    }
    if (id === "write") {
      const spun = fabricStory("systems_horror", "The archive charges rent on forgotten names");
      addStory({
        title: spun.title,
        genre: "systems_horror",
        premise: "The archive charges rent on forgotten names",
        body: spun.body,
        characters: spun.characters,
      });
      markDemo("write");
      return;
    }
    if (id === "build") {
      addProject("Build me a local offline checklist CLI with SQLite called TaskLite");
      markDemo("build");
      return;
    }
    const r = runMirror(seed);
    setMirror(r);
    markDemo("mirror");
  }

  return (
    <main className="mx-auto w-full max-w-2xl px-5 py-8">
      <p className="text-xs tracking-kicker text-muted uppercase">Studio</p>
      <h1 className="mt-2 font-display text-4xl">Keep it honest. Make it last.</h1>
      <p className="mt-2 text-sm text-muted">
        Demos that actually run. A product model that does not skip HITL. Character graph on this device.
      </p>

      <section className="mt-8">
        <h2 className="text-sm font-medium text-muted">Solid demos</h2>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {DEMOS.map((d) => (
            <button
              key={d.id}
              onClick={() => runDemo(d.id)}
              className="rounded-xl border border-border bg-surface px-4 py-4 text-left hover:bg-elevated"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{d.title}</span>
                {demos.includes(d.id) && <span className="text-micro text-muted">done</span>}
              </div>
              <p className="mt-1 text-xs text-muted">{d.body}</p>
            </button>
          ))}
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-sm font-medium text-muted">Mirror cascade</h2>
        <p className="mt-1 text-xs text-muted">Forward · reverse · shadow. Local. No cloud.</p>
        <Textarea className="mt-3" rows={2} value={seed} onChange={(e) => setSeed(e.target.value)} />
        <Button className="mt-3" variant="outline" onClick={() => runDemo("mirror")}>
          Run coils
        </Button>
        {mirror && (
          <div className="mt-4 space-y-3 rounded-xl border border-border bg-surface p-4 text-sm">
            {mirror.coils.map((c) => (
              <div key={c.name}>
                <div className="text-xs tracking-kicker text-muted uppercase">{c.name}</div>
                <ul className="mt-1 list-disc pl-4 text-fg/90">
                  {c.lines.map((l) => (
                    <li key={l}>{l}</li>
                  ))}
                </ul>
              </div>
            ))}
            <div>
              <div className="text-xs tracking-kicker text-muted uppercase">Keep</div>
              <p className="mt-1 text-xs text-muted">{mirror.keep.join(" · ")}</p>
            </div>
            <div>
              <div className="text-xs tracking-kicker text-muted uppercase">Veto</div>
              <p className="mt-1 text-xs text-danger">{mirror.veto.join(" · ")}</p>
            </div>
          </div>
        )}
      </section>

      <section className="mt-10">
        <h2 className="text-sm font-medium text-muted">Character graph</h2>
        <p className="mt-1 text-xs text-muted">{AXIS_TYPES.toLocaleString()} voice×drive×wound×method types.</p>
        <Button
          className="mt-3"
          variant="outline"
          onClick={() => addGraphChar(mintCharacter(`${Date.now()}`))}
        >
          Mint character
        </Button>
        <ul className="mt-4 space-y-2">
          {graph.slice(0, 6).map((c) => (
            <li key={c.id} className="rounded-lg border border-border bg-surface px-4 py-3">
              <div className="text-sm font-medium">{c.name}</div>
              <p className="mt-1 text-xs text-muted">
                {c.voice} · {c.method} · want {c.drive} · wound {c.wound}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-10">
        <h2 className="text-sm font-medium text-muted">How LEVI is paid</h2>
        <p className="mt-1 text-xs text-muted">
          Free core stays free. Studio and Sovereign are the honest upgrade — not fake urgency.
        </p>
        <div className="mt-4 grid gap-3">
          {PLANS.map((p) => (
            <article
              key={p.id}
              className={`rounded-xl border p-4 ${
                plan === p.id ? "border-border-strong bg-elevated" : "border-border bg-surface"
              }`}
            >
              <div className="flex items-baseline justify-between gap-3">
                <h3 className="font-display text-2xl">{p.name}</h3>
                <span className="text-sm text-muted">{p.price}</span>
              </div>
              <p className="mt-1 text-xs text-muted">{p.for}</p>
              <ul className="mt-3 space-y-1 text-sm text-fg/90">
                {p.includes.map((i) => (
                  <li key={i}>{i}</li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-subtle">{p.not}</p>
              <Button
                className="mt-4 w-full"
                variant={plan === p.id ? "quiet" : "outline"}
                onClick={() => setPlan(p.id as PlanId)}
              >
                {plan === p.id ? "Current on this device" : `Use ${p.name} locally`}
              </Button>
            </article>
          ))}
        </div>
        <h3 className="mt-8 text-sm font-medium text-muted">HITL services</h3>
        <ul className="mt-3 space-y-2">
          {SERVICES.map((s) => (
            <li key={s.id} className="rounded-lg border border-border bg-surface px-4 py-3">
              <div className="flex justify-between gap-3 text-sm">
                <span className="font-medium">{s.name}</span>
                <span className="text-muted">{s.price}</span>
              </div>
              <p className="mt-1 text-xs text-muted">{s.note}</p>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-subtle">
          Preview uses local plan switching — no card charged. When you publish, these become real checkout.
        </p>
      </section>
    </main>
  );
}
