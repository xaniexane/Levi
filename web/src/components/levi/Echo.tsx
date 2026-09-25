import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { simulateEcho } from "@/lib/levi/organs";
import { useLevi } from "@/lib/levi/store";

export function EchoView() {
  const echoes = useLevi((s) => s.echoes);
  const addEcho = useLevi((s) => s.addEcho);
  const [seed, setSeed] = useState("");
  const latest = echoes[0];

  return (
    <main className="mx-auto w-full max-w-2xl px-5 py-8">
      <p className="text-xs tracking-kicker text-muted uppercase">Echo · old Echoverse</p>
      <h1 className="mt-2 font-display text-4xl">Explore space</h1>
      <p className="mt-2 text-sm text-muted">
        Bounded simulation — taken, not-taken, wild. Not a claim of literal timelines. Kept as its
        own organ; Talk does not replace it.
      </p>
      <form
        className="mt-6 flex flex-col gap-2 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          addEcho(simulateEcho(seed || "silence", 3));
        }}
      >
        <Input
          value={seed}
          onChange={(e) => setSeed(e.target.value)}
          placeholder="Seed: deepen retention or add surface"
        />
        <Button type="submit">Simulate</Button>
      </form>
      {latest && (
        <div className="mt-6 space-y-3">
          <p className="font-mono text-micro text-muted">Seed: {latest.seed}</p>
          {latest.branches.map((b) => (
            <article key={b.id} className="rounded-xl border border-border bg-surface p-4">
              <p className="text-micro tracking-kicker text-muted uppercase">
                {b.kind.replaceAll("_", " ")} · risk {b.risk} · optionality{" "}
                {b.optionality.toFixed(2)}
              </p>
              <h3 className="mt-1 text-sm font-medium">{b.label}</h3>
              <p className="mt-1 text-sm text-muted">{b.summary}</p>
            </article>
          ))}
          <p className="text-sm">Insight: {latest.insight}</p>
        </div>
      )}
    </main>
  );
}
