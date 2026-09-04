import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { useLevi, type Loop } from "@/lib/levi/store";
import { Mark } from "./Mark";

const LOOPS: { id: Loop; title: string; body: string }[] = [
  { id: "companion", title: "Talk", body: "A companion who remembers, challenges, and protects." },
  { id: "writing", title: "Write", body: "Stories in 97 genres. Expand. Modify. Spiral." },
  { id: "building", title: "Build", body: "Natural language becomes a local project." },
];

export function Onboarding() {
  const complete = useLevi((s) => s.completeOnboarding);
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [loop, setLoop] = useState<Loop>("companion");

  return (
    <main className="mx-auto flex min-h-dvh max-w-5xl flex-col justify-center overflow-y-auto px-5 py-8 md:flex-row md:items-center md:gap-16 md:px-10">
      <div className="md:w-2/5">
        <Mark className="size-8 text-accent" />
        <p className="mt-5 text-xs font-medium tracking-kicker text-muted uppercase">
          Local-first companion
        </p>
        <h1 className="mt-2 font-display text-5xl text-fg md:text-6xl">LEVI</h1>
        <p className="mt-3 max-w-sm text-muted">
          Friend. Mentor. Challenger. Protector. Talk, write, build — plus Hydra, Echo, Mandella,
          Compost, and a signed ledger. Default: sovereign. Grok is a catalyst you turn on.
        </p>
      </div>

      <form
        className="mt-8 flex flex-col gap-4 md:mt-0 md:w-3/5 md:max-w-md"
        onSubmit={(e) => {
          e.preventDefault();
          complete({ name: name.trim() || "friend", goal: goal.trim(), loop });
        }}
      >
        <label className="flex flex-col gap-2">
          <span className="text-xs font-medium text-muted">What should I call you?</span>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" />
        </label>
        <label className="flex flex-col gap-2">
          <span className="text-xs font-medium text-muted">One goal this week</span>
          <Textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="Optional — I’ll hold it with you"
            rows={2}
          />
        </label>
        <fieldset>
          <legend className="mb-2 text-xs font-medium text-muted">Start in</legend>
          <div className="grid gap-2">
            {LOOPS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setLoop(item.id)}
                className={`rounded-md border px-4 py-2.5 text-left transition-colors duration-150 ${
                  loop === item.id
                    ? "border-border-strong bg-elevated"
                    : "border-border bg-surface hover:bg-elevated"
                }`}
              >
                <div className="text-sm font-medium">{item.title}</div>
                <div className="mt-0.5 text-xs text-muted">{item.body}</div>
              </button>
            ))}
          </div>
        </fieldset>
        <Button type="submit" size="lg" className="w-full">
          Begin
        </Button>
        <p className="text-center text-xs text-subtle">
          Stays on this device. Free core. Lattice in the second row. No account.
        </p>
      </form>
    </main>
  );
}
