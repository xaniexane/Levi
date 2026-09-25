import { useMemo } from "react";
import { Link } from "@tanstack/react-router";
import { FinanceWsb } from "@/components/levi/FinanceWsb";
import { generateFixture } from "@/lib/levi/finance-wsb";

export function FinancePage() {
  // SIMULATED PREVIEW fixture — synthetic data only. A future iteration
  // swaps this for the real finance engine output without re-shaping.
  const snapshot = useMemo(() => generateFixture(42), []);
  return (
    <div className="min-h-dvh bg-bg">
      <div className="mx-auto max-w-6xl px-4 pt-4 md:px-8">
        <Link
          to="/"
          className="text-xs text-muted underline-offset-2 hover:text-fg hover:underline"
        >
          ← Back to LEVI
        </Link>
      </div>
      <FinanceWsb snapshot={snapshot} />
    </div>
  );
}
