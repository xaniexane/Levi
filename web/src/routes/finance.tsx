import { createFileRoute } from "@tanstack/react-router";
import { FinancePage } from "./finance.page";

export const Route = createFileRoute("/finance")({ component: FinancePage });
