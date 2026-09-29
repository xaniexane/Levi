import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { compostFailure, refineCompost } from "@/lib/levi/organs";
import { useLevi } from "@/lib/levi/store";

export function CompostView() {
  const compost = useLevi((s) => s.compost);
  const addCompost = useLevi((s) => s.addCompost);
  const updateCompost = useLevi((s) => s.updateCompost);
  const [manual, setManual] = useState("");

  return (
    <main className="mx-auto w-full max-w-2xl px-5 py-8">
      <p className="text-xs tracking-kicker text-muted uppercase">Compost · Part 2 §16</p>
      <h1 className="mt-2 font-display text-4xl">Failed experiments</h1>
      <p className="mt-2 text-sm leading-relaxed text-muted">
        Old organ: REIM / RIEM. New law: quarantined, non-canonical, kept for learning. Residue
        stays; the failed surface does not enter bible.
      </p>
      <form
        className="mt-6 space-y-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (!manual.trim()) return;
          addCompost(compostFailure({ source: "manual", failure: manual }));
          setManual("");
        }}
      >
        <Textarea
          value={manual}
          onChange={(e) => setManual(e.target.value)}
          placeholder="Paste a bad reply, a failed scaffold, a wrong fact…"
        />
        <div className="flex flex-wrap gap-2">
          <Button type="submit">REIM — compost</Button>
          <Button
            type="button"
            variant="outline"
            onClick={() =>
              compost.filter((c) => !c.refined).forEach((c) => updateCompost(refineCompost(c)))
            }
          >
            RIEM — refine all
          </Button>
        </div>
      </form>
      <ul className="mt-6 space-y-3">
        {compost.length === 0 && (
          <li className="rounded-xl border border-dashed border-border p-4 text-sm text-muted">
            Empty. Mark a Talk reply, or paste a failure here.
          </li>
        )}
        {compost.map((c) => (
          <li key={c.id} className="rounded-xl border border-border bg-surface p-4">
            <p className="text-micro tracking-kicker text-muted uppercase">
              {c.source} · {c.quarantined ? "quarantined" : "loose"} ·{" "}
              {c.refined ? "RIEM refined" : "REIM residue"}
            </p>
            <p className="mt-2 text-xs text-muted">Failure: {c.failure}</p>
            <p className="mt-2 text-sm">Residue: {c.residue}</p>
            <p className="mt-1 text-sm">Lesson: {c.lesson}</p>
            {c.compressed && <p className="mt-2 font-mono text-xs text-muted">{c.compressed}</p>}
            {!c.refined && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="mt-3"
                onClick={() => updateCompost(refineCompost(c))}
              >
                Refine this
              </Button>
            )}
          </li>
        ))}
      </ul>
    </main>
  );
}
