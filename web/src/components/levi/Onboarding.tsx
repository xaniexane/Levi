import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { useLevi, type Loop } from "@/lib/levi/store";
import { Mark } from "./Mark";

const LOOPS: { id: Loop; title: string; body: string }[] = [
  {
    id: "companion",
    title: "Talk",
    body: "Just talk. I'll listen, remember what matters, and be honest with you.",
  },
  {
    id: "writing",
    title: "Write",
    body: "Make something — stories in more genres than either of us can name.",
  },
  {
    id: "building",
    title: "Build",
    body: "Describe a tool. I'll scaffold it here, on your machine.",
  },
];

export function Onboarding() {
  const complete = useLevi((s) => s.completeOnboarding);
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [loop, setLoop] = useState<Loop>("companion");

  return (
    <main className="mx-auto flex min-h-dvh max-w-5xl flex-col justify-center overflow-y-auto px-5 py-8 md:flex-row md:items-center md:gap-16 md:px-10">
      <div className="animate-msg-in md:w-2/5">
        <Mark className="size-8 text-accent" />
        <p className="mt-5 text-xs font-medium tracking-kicker text-muted uppercase">
          Hey — I&rsquo;m LEVI
        </p>
        <h1 className="mt-2 font-display text-5xl text-fg md:text-6xl">
          Let&rsquo;s get you set up.
        </h1>
        <p className="mt-3 max-w-sm leading-relaxed text-muted">
          Part companion, part shipboard AI. I&rsquo;ll remember what matters, push back when
          you&rsquo;re coasting, and keep everything on this device unless you say otherwise. Three
          questions, then we&rsquo;re off.
        </p>
      </div>

      <form
        className="animate-msg-in mt-8 flex flex-col gap-4 md:mt-0 md:w-3/5 md:max-w-md"
        onSubmit={(e) => {
          e.preventDefault();
          complete({ name: name.trim() || "friend", goal: goal.trim(), loop });
        }}
      >
        <label className="flex flex-col gap-2">
          <span className="text-xs font-medium text-muted">What should I call you?</span>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="What do your friends call you?"
          />
        </label>
        <label className="flex flex-col gap-2">
          <span className="text-xs font-medium text-muted">
            What&rsquo;s one thing you want this week?
          </span>
          <Textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="Doesn't have to be big. Just yours."
            rows={2}
          />
        </label>
        <fieldset>
          <legend className="mb-2 text-xs font-medium text-muted">Where should we start?</legend>
          <div className="grid gap-2">
            {LOOPS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setLoop(item.id)}
                aria-pressed={loop === item.id}
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
          Let&rsquo;s go
        </Button>
        <p className="text-center text-xs text-subtle">
          Stays on this device. No account, no tracking. You can change all of this later.
        </p>
      </form>
    </main>
  );
}
