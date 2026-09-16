import { useMemo } from "react";
import { FinanceWsb } from "@/components/levi/FinanceWsb";
import { generateFixture } from "@/lib/levi/finance-wsb";

export function FinancePage() {
  // SIMULATED PREVIEW fixture — synthetic data only. A future iteration
  // swaps this for the real finance engine output without re-shaping.
  const snapshot = useMemo(() => generateFixture(42), []);
  return <FinanceWsb snapshot={snapshot} />;
}
