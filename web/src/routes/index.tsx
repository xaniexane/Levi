import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Onboarding } from "@/components/levi/Onboarding";
import { Shell } from "@/components/levi/Shell";
import { useLevi } from "@/lib/levi/store";

export const Route = createFileRoute("/")({ component: Home });

function Home() {
  const onboarded = useLevi((s) => s.onboarded);
  const [hydrated, setHydrated] = useState(() => useLevi.persist.hasHydrated());

  useEffect(() => {
    if (useLevi.persist.hasHydrated()) {
      setHydrated(true);
      return;
    }
    return useLevi.persist.onFinishHydration(() => setHydrated(true));
  }, []);

  if (!hydrated) {
    return (
      <main className="flex min-h-dvh items-center justify-center bg-bg text-muted">
        <p className="font-display text-2xl text-fg">LEVI</p>
      </main>
    );
  }
  return onboarded ? <Shell /> : <Onboarding />;
}
