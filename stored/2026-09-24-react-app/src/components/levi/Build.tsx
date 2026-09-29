import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { leviComplete } from "@/lib/levi/ai";
import { companionSystem } from "@/lib/levi/prompt";
import { scaffoldFromIR } from "@/lib/levi/local";
import { EMERGENCY, STAGES, stageNeedsHitl } from "@/lib/levi/nl-ir";
import { shelfSummary, useLevi, catalystAllowed } from "@/lib/levi/store";

const TEMPLATES = [
  { id: "checklist", nl: "Build me a local offline checklist CLI with SQLite called TaskLite" },
  { id: "notes", nl: "Build me a local offline notes CLI with JSON file storage" },
  { id: "timer", nl: "Build me a tiny local countdown CLI" },
  { id: "vault", nl: "Build me a local offline vault CLI with JSON storage called Seal" },
  { id: "pulse", nl: "Build me a local offline watch/pulse CLI called StandingWatch" },
];

export function BuildView() {
  const projects = useLevi((s) => s.projects);
  const activeId = useLevi((s) => s.activeProjectId);
  const addProject = useLevi((s) => s.addProject);
  const updateProject = useLevi((s) => s.updateProject);
  const advanceProject = useLevi((s) => s.advanceProject);
  const approveHitl = useLevi((s) => s.approveHitl);
  const persona = useLevi((s) => s.persona);
  const name = useLevi((s) => s.name);
  const goal = useLevi((s) => s.goal);
  const project = projects.find((p) => p.id === activeId) ?? projects[0];
  const [idea, setIdea] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  function start(nl: string) {
    addProject(nl);
    setIdea("");
  }

  async function refine() {
    if (!project || busy) return;
    setBusy(true);
    try {
      if (!catalystAllowed()) {
        updateProject(project.id, {
          code: scaffoldFromIR(project.ir),
          stage: "scaffold",
          notes: "Local scaffold written. Hybrid catalyst is off.",
        });
        return;
      }
      const result = await leviComplete({
        data: {
          maxTokens: 1400,
          messages: [
            {
              role: "system",
              content:
                companionSystem({ name, goal, persona, shelf: shelfSummary(), mode: "build" }) +
                "\nReturn a single Python CLI (main.py) only, no markdown fences if possible. Local-first, stdlib only.",
            },
            {
              role: "user",
              content: `Scaffold this project at ${project.ir.emergency}:\n${JSON.stringify(project.ir, null, 2)}`,
            },
          ],
        },
      });
      const code = result.ok && result.text ? stripFence(result.text) : scaffoldFromIR(project.ir);
      updateProject(project.id, { code, stage: "scaffold", notes: "Scaffold written." });
    } catch {
      updateProject(project.id, {
        code: scaffoldFromIR(project.ir),
        stage: "scaffold",
        notes: "Local scaffold written.",
      });
    } finally {
      setBusy(false);
    }
  }

  async function copyCode() {
    if (!project?.code) return;
    try {
      await navigator.clipboard.writeText(project.code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl px-5 py-8">
      <p className="text-xs tracking-kicker text-muted uppercase">Build</p>
      <h1 className="mt-2 font-display text-4xl">Emergency factory</h1>
      <p className="mt-2 text-sm text-muted">
        Natural language → IR → scaffold. HITL before implement. E3 skeleton through E6 product.
      </p>

      <div className="mt-6 rounded-xl border border-border bg-surface p-4">
        <Textarea
          rows={3}
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          placeholder="Build me a local offline checklist CLI with SQLite"
        />
        <Button className="mt-3 w-full" disabled={!idea.trim()} onClick={() => start(idea)}>
          Compile and start
        </Button>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {TEMPLATES.map((t) => (
            <Button key={t.id} size="sm" variant="quiet" onClick={() => start(t.nl)}>
              {t.id}
            </Button>
          ))}
        </div>
      </div>

      {project && (
        <section className="mt-8">
          <h2 className="font-display text-2xl">{project.name}</h2>
          <p className="mt-1 text-sm text-muted">{project.idea}</p>
          <p className="mt-2 text-xs text-muted">
            Emergency {project.ir.emergency ?? "E5"} ·{" "}
            {EMERGENCY.find((e) => e.id === (project.ir.emergency ?? "E5"))?.note}
          </p>
          <ol className="mt-4 flex flex-wrap gap-2">
            {STAGES.map((st) => (
              <li
                key={st}
                className={`rounded-full px-2.5 py-1 text-micro ${
                  st === project.stage ? "bg-accent text-accent-fg" : "bg-elevated text-muted"
                }`}
              >
                {st}
              </li>
            ))}
          </ol>
          <dl className="mt-4 grid grid-cols-2 gap-2 text-xs text-muted">
            <div>kind · {project.ir.artifact}</div>
            <div>lang · {project.ir.language}</div>
            <div>storage · {project.ir.storage ?? "none"}</div>
            <div>offline · {project.ir.offline ? "yes" : "no"}</div>
          </dl>
          {project.ir.constraints.includes("tiny-slice") && (
            <p className="mt-3 text-xs text-muted">
              Scoped to a tiny local slice so it can actually ship.
            </p>
          )}
          {project.notes && <p className="mt-3 text-sm text-fg/90">{project.notes}</p>}

          {stageNeedsHitl(project.stage) && !project.hitlApproved && (
            <div className="mt-4 rounded-lg border border-border bg-elevated px-4 py-3">
              <p className="text-sm">HITL gate. Silence is not approval.</p>
              <Button className="mt-3" size="sm" onClick={() => approveHitl(project.id)}>
                I approve this stage
              </Button>
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => advanceProject(project.id)}>
              Advance stage
            </Button>
            <Button size="sm" disabled={busy} onClick={() => void refine()}>
              {busy ? "Refining…" : "Refine scaffold"}
            </Button>
            {project.code && (
              <Button size="sm" variant="quiet" onClick={() => void copyCode()}>
                {copied ? "Copied" : "Copy code"}
              </Button>
            )}
          </div>
          {project.code && (
            <pre className="mt-4 overflow-x-auto rounded-lg border border-border bg-elevated p-3 font-mono text-xs leading-relaxed text-fg/90">
              {project.code}
            </pre>
          )}
        </section>
      )}

      {projects.length > 1 && (
        <ul className="mt-10 space-y-2">
          {projects.map((p) => (
            <li key={p.id}>
              <button
                onClick={() => useLevi.setState({ activeProjectId: p.id })}
                className={`w-full rounded-md border px-3 py-2 text-left text-sm hover:bg-elevated ${
                  p.id === project?.id ? "border-border-strong bg-elevated" : "border-border"
                }`}
              >
                {p.name} · {p.stage}
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

function stripFence(text: string) {
  return text
    .replace(/^```(?:python)?\n?/i, "")
    .replace(/\n?```$/i, "")
    .trim();
}
