import { useEffect, useState } from "react";
import { Onboarding } from "@/components/levi/Onboarding";
import { Shell } from "@/components/levi/Shell";
import { useLevi } from "@/lib/levi/store";

export function IndexPage() {
  const onboarded = useLevi((s) => s.onboarded);
  const [hydrated, setHydrated] = useState(() => useLevi.persist.hasHydrated());

  useEffect(() => {
    if (hydrated) return;
    return useLevi.persist.onFinishHydration(() => setHydrated(true));
  }, [hydrated]);

  if (!hydrated) {
    return (
      <main className="flex min-h-dvh items-center justify-center bg-bg text-muted">
        <p className="font-display text-2xl text-fg">LEVI</p>
      </main>
    );
  }
  return onboarded ? <Shell /> : <Onboarding />;
}
