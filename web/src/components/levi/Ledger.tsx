import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { PART2_CHECKS, verifyChain } from "@/lib/levi/hydra";
import { ORGAN_MAP } from "@/lib/levi/types";
import { useLevi } from "@/lib/levi/store";

export function LedgerView() {
  const ledger = useLevi((s) => s.ledger);
  const part2Locked = useLevi((s) => s.part2Locked);
  const part2EventId = useLevi((s) => s.part2EventId);
  const lockPart2 = useLevi((s) => s.lockPart2);
  const name = useLevi((s) => s.name);
  const designMode = useLevi((s) => s.designMode);
  const setDesignMode = useLevi((s) => s.setDesignMode);
  const halted = useLevi((s) => s.halted);
  const setHalted = useLevi((s) => s.setHalted);
  const journal = useLevi((s) => s.journal);
  const addJournal = useLevi((s) => s.addJournal);
  const exportBackup = useLevi((s) => s.exportBackup);
  const importBackup = useLevi((s) => s.importBackup);
  const ir = useLevi((s) => s.ir);
  const [note, setNote] = useState("");
  const [verse, setVerse] = useState("");
  const [restoreMsg, setRestoreMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const intact = verifyChain(ledger);

  function lock() {
    if (!/^levi,?\s+append part 2 and lock\.?$/i.test(verse.trim())) return;
    lockPart2(name || "owner");
    setVerse("");
  }

  async function download() {
    const blob = new Blob([exportBackup()], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "levi-ledger.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="mx-auto w-full max-w-2xl px-5 py-8">
      <p className="text-xs tracking-kicker text-muted uppercase">Ledger · journal merged</p>
      <h1 className="mt-2 font-display text-4xl">Provenance</h1>
      <p className="mt-2 text-sm text-muted">
        Hash-chained events. Seeds. Owner sign. Morning journal lives here now — not a separate
        organ.
      </p>
      <p className="mt-3 font-mono text-micro text-muted">
        chain {intact ? "intact" : "BROKEN"} · {ledger.length} events ·{" "}
        {part2Locked ? `Part 2 locked (${part2EventId})` : "Part 2 open"}
      </p>

      <section className="mt-6 rounded-xl border border-border bg-surface p-4">
        <div className="text-xs text-muted">Design mode</div>
        <div className="mt-2 flex flex-wrap gap-2">
          <Button
            size="sm"
            variant={designMode === "sovereignty" ? "primary" : "outline"}
            onClick={() => setDesignMode("sovereignty")}
          >
            Maximal sovereignty
          </Button>
          <Button
            size="sm"
            variant={designMode === "hybrid" ? "primary" : "outline"}
            onClick={() => setDesignMode("hybrid")}
          >
            Hybrid catalyst
          </Button>
        </div>
        <p className="mt-2 text-xs text-muted">
          {designMode === "sovereignty"
            ? "All compute local. Grok stays off."
            : "Local baseline. Grok is an opt-in catalyst on Talk / Write / Build."}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" variant="quiet" onClick={() => setHalted(!halted)}>
            {halted ? "Resume" : "Kill switch"}
          </Button>
          <Button size="sm" variant="outline" onClick={() => void download()}>
            Export backup
          </Button>
          <Button size="sm" variant="outline" onClick={() => fileRef.current?.click()}>
            Restore drill
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json"
            className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              const text = await file.text();
              setRestoreMsg(importBackup(text) ? "Restore verified." : "Restore blocked — bad JSON.");
            }}
          />
        </div>
        {restoreMsg && <p className="mt-2 text-xs text-muted">{restoreMsg}</p>}
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-medium text-muted">Part 2 lock</h2>
        <p className="mt-1 text-xs text-muted">
          Owner verse: “Levi, append Part 2 and lock.” Creates PART2-APPEND-uuid and signs.
        </p>
        {!part2Locked ? (
          <form
            className="mt-3 flex flex-col gap-2 sm:flex-row"
            onSubmit={(e) => {
              e.preventDefault();
              lock();
            }}
          >
            <Input
              value={verse}
              onChange={(e) => setVerse(e.target.value)}
              placeholder="Levi, append Part 2 and lock."
            />
            <Button type="submit">Lock</Button>
          </form>
        ) : (
          <p className="mt-2 text-sm">Locked. Hardening is canon on this device.</p>
        )}
        <ul className="mt-4 space-y-1.5 text-sm">
          {PART2_CHECKS.map((c) => (
            <li key={c.id} className="flex justify-between gap-3">
              <span>{c.label}</span>
              <span className="text-micro text-muted">{c.local ? "implemented" : "blocked"}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-medium text-muted">Organ map</h2>
        <p className="mt-1 text-xs text-muted">Old console organs vs this restore.</p>
        <ul className="mt-3 divide-y divide-border rounded-xl border border-border">
          {ORGAN_MAP.map((row) => (
            <li key={row.old + row.now} className="flex flex-col gap-0.5 px-4 py-3 sm:flex-row sm:items-baseline sm:justify-between">
              <div>
                <span className="text-sm">{row.old === "—" ? row.now : row.old}</span>
                <span className="text-micro text-muted"> → {row.now}</span>
              </div>
              <span className="text-micro text-muted">
                {row.status} · {row.note}
              </span>
            </li>
          ))}
        </ul>
      </section>

      {ir && (
        <section className="mt-8">
          <h2 className="text-sm font-medium text-muted">Lineage · current IR</h2>
          <p className="mt-2 font-mono text-xs text-muted">
            {ir.provenance.transforms.join(" → ")} · seed {ir.provenance.seed} · {ir.provenance.model}
          </p>
        </section>
      )}

      <section className="mt-8">
        <h2 className="text-sm font-medium text-muted">Journal</h2>
        <form
          className="mt-3 flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (!note.trim()) return;
            addJournal(note);
            setNote("");
          }}
        >
          <Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="One honest sentence." />
          <Button type="submit" size="sm" className="self-start">
            File note
          </Button>
        </form>
        <ul className="mt-4 space-y-2">
          {journal.slice(0, 8).map((j) => (
            <li key={j.id} className="rounded-lg border border-border bg-surface px-3 py-2 text-sm">
              {j.text}
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-medium text-muted">Events</h2>
        <ol className="mt-3 space-y-2">
          {ledger.slice(0, 24).map((e) => (
            <li key={e.id} className="rounded-lg border border-border bg-surface px-3 py-2">
              <div className="flex justify-between gap-3 font-mono text-micro text-muted">
                <span>
                  #{e.seq} {e.kind}
                </span>
                <span className="truncate">{e.hash.slice(0, 12)}</span>
              </div>
              <p className="mt-1 text-sm">{e.summary}</p>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
