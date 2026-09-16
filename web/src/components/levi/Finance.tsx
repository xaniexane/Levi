import { useMemo } from "react";
import { FinanceWsb } from "./FinanceWsb";
import { generateFixture } from "@/lib/levi/finance-wsb";

/**
 * Finance view — the WSB dashboard the finance crew built, surfaced in the
 * app shell. Same SIMULATED PREVIEW fixture as the /finance route: one
 * dashboard, two ways in. All numbers are synthetic paper-trading data.
 */
export function FinanceView() {
  const snapshot = useMemo(() => generateFixture(42), []);
  return <FinanceWsb snapshot={snapshot} />;
}
