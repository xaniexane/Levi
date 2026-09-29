import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { expandMandellaToEcho, generateMandella, MANDELLA_DOMAINS } from "@/lib/levi/organs";
import { useLevi } from "@/lib/levi/store";
import type { MandellaDomain } from "@/lib/levi/types";

export function MandellaView() {
  const addMandella = useLevi((s) => s.addMandella);
  const addEcho = useLevi((s) => s.addEcho);
  const setView = useLevi((s) => s.setView);
  const latest = useLevi((s) => s.mandellas[0]);
  const [premise, setPremise] = useState("");
  const [domain, setDomain] = useState<MandellaDomain | "">("");

  return (
    <main className="mx-auto w-full max-w-2xl px-5 py-8">
      <p className="text-xs tracking-kicker text-muted uppercase">Mandella · kept</p>
      <h1 className="mt-2 font-display text-4xl">Force a stake</h1>
      <p className="mt-2 text-sm text-muted">
        Incomplete information. A / B / C. Phantoms haunt the next draft. Compost is a different
        organ — failures, not roads not taken.
      </p>
      <form
        className="mt-6 space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          addMandella(generateMandella(domain || undefined, premise));
        }}
      >
        <div className="flex flex-wrap gap-1.5">
          {MANDELLA_DOMAINS.map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDomain(d === domain ? "" : d)}
              className={`h-9 rounded-full px-3 text-xs ${
                d === domain
                  ? "bg-accent text-accent-fg"
                  : "border border-border text-muted hover:text-fg"
              }`}
            >
              {d}
            </button>
          ))}
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            value={premise}
            onChange={(e) => setPremise(e.target.value)}
            placeholder="Premise: factory blocked at scaffold"
          />
          <Button type="submit">Generate</Button>
        </div>
      </form>
      {latest && (
        <div className="mt-6 space-y-3">
          <p className="font-mono text-micro text-muted">
            {latest.domain} · {latest.premise}
          </p>
          {latest.options.map((o) => (
            <article key={o.key} className="rounded-xl border border-border bg-surface p-4">
              <p className="text-micro tracking-kicker text-muted uppercase">
                {o.key === latest.recommended ? "Recommended" : "Option"} {o.key} · {o.risk} ·{" "}
                {o.optionality.toFixed(2)}
              </p>
              <h3 className="mt-1 text-sm font-medium">{o.label}</h3>
              <p className="mt-1 text-sm text-muted">
                {o.move} · verify: {o.verifiesWith}
              </p>
            </article>
          ))}
          <div className="rounded-lg border border-dashed border-border p-4">
            <p className="text-micro tracking-kicker text-muted uppercase">Phantoms</p>
            <ul className="mt-2 space-y-1 text-sm text-muted">
              {latest.phantoms.map((p) => (
                <li key={p.key}>
                  [{p.key}] {p.label} — still available to haunt the next draft
                </li>
              ))}
            </ul>
          </div>
          <Button
            variant="outline"
            onClick={() => {
              addEcho(expandMandellaToEcho(latest));
              setView("echo");
            }}
          >
            Expand stake into Echo
          </Button>
        </div>
      )}
    </main>
  );
}
