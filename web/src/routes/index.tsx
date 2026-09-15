import { createFileRoute } from "@tanstack/react-router";
import { IndexPage } from "./index.page";

export const Route = createFileRoute("/")({ component: IndexPage });
