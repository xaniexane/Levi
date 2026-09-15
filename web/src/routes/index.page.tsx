import { useEffect, useState } from "react";
import { Onboarding } from "@/components/levi/Onboarding";
import { Shell } from "@/components/levi/Shell";
import { useLevi } from "@/lib/levi/store";

export function IndexPage() {
  const onboarded = useLevi((s) => s.onboarded);
  // Always render the splash on the first pass — server and client agree, so
  // hydration matches. zustand/persist hydrates synchronously from
  // localStorage on the client, so the effect below flips to the real UI
  // immediately after first paint (no visible flash for returning users).
  // (useLevi.persist is undefined during SSR: no window.localStorage there.)
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const persist = useLevi.persist;
    if (!persist || persist.hasHydrated()) {
      setHydrated(true);
      return;
    }
    return persist.onFinishHydration(() => setHydrated(true));
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
