import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/react";
import { DynamicUI, type DynamicUIAction, type DynamicUIEnvelope } from "./DynamicUI";

afterEach(cleanup);

const envelope = (elements: DynamicUIEnvelope["elements"]): DynamicUIEnvelope => ({
  kind: "dynamic-ui",
  version: 1,
  elements,
});

describe("DynamicUI", () => {
  it("renders text, card, and progress elements", () => {
    const { container, getByText } = render(
      <DynamicUI
        onAction={() => {}}
        payload={envelope([
          { type: "text", text: "Hello there", tone: "accent" },
          { type: "card", title: "Card title", body: "Card body" },
          { type: "progress", label: "Syncing", value: 0.5 },
        ])}
      />,
    );
    expect(getByText("Hello there")).toBeTruthy();
    expect(getByText("Card title")).toBeTruthy();
    expect(getByText("Card body")).toBeTruthy();
    expect(getByText("Syncing")).toBeTruthy();
    const bar = container.querySelector('[role="progressbar"]');
    expect(bar?.getAttribute("aria-valuenow")).toBe("50");
  });

  it("fires an intent action when a button is tapped", () => {
    const seen: DynamicUIAction[] = [];
    const { getByText } = render(
      <DynamicUI
        onAction={(a) => seen.push(a)}
        payload={envelope([
          {
            type: "buttons",
            buttons: [{ label: "Run", action: { kind: "intent", intent: "demo.run" } }],
          },
        ])}
      />,
    );
    fireEvent.click(getByText("Run"));
    expect(seen).toEqual([{ kind: "intent", intent: "demo.run" }]);
  });

  it("requires two taps for confirm/danger actions", () => {
    const seen: DynamicUIAction[] = [];
    const { getByText } = render(
      <DynamicUI
        onAction={(a) => seen.push(a)}
        payload={envelope([
          {
            type: "buttons",
            buttons: [
              {
                label: "Delete",
                style: "danger",
                action: { kind: "intent", intent: "memory.delete", confirm: true },
              },
            ],
          },
        ])}
      />,
    );
    fireEvent.click(getByText("Delete"));
    expect(seen).toEqual([]); // first tap only arms
    fireEvent.click(getByText("Tap again to confirm"));
    expect(seen).toHaveLength(1);
    expect(seen[0]).toMatchObject({ kind: "intent", intent: "memory.delete" });
  });

  it("renders http(s) url actions with the domain, blocks other schemes", () => {
    const seen: DynamicUIAction[] = [];
    const { getByText, getAllByText } = render(
      <DynamicUI
        onAction={(a) => seen.push(a)}
        payload={envelope([
          {
            type: "buttons",
            buttons: [
              { label: "Docs", action: { kind: "url", url: "https://docs.levi.dev/guide" } },
              { label: "Evil", action: { kind: "url", url: "javascript:alert(1)" } },
            ],
          },
        ])}
      />,
    );
    expect(getByText("docs.levi.dev")).toBeTruthy(); // domain shown next to label
    fireEvent.click(getByText("Docs"));
    expect(seen).toHaveLength(1);
    expect(seen[0]).toMatchObject({ kind: "url", url: "https://docs.levi.dev/guide" });
    // The javascript: button never renders as a link — it degrades to a warning.
    expect(getAllByText(/Blocked non-http\(s\) link/).length).toBe(1);
  });

  it("submits form values merged into the intent args", () => {
    const seen: DynamicUIAction[] = [];
    const { getByLabelText, getByRole, getByText } = render(
      <DynamicUI
        onAction={(a) => seen.push(a)}
        payload={envelope([
          {
            type: "form",
            title: "Weekly goal",
            fields: [
              { name: "goal", label: "Goal", field: "text", required: true },
              { name: "level", label: "Level", field: "select", options: ["low", "high"] },
              { name: "notify", label: "Notify me", field: "toggle", default: true },
            ],
            submit: { label: "Save", action: { kind: "intent", intent: "goal.set" } },
          },
        ])}
      />,
    );
    fireEvent.change(getByLabelText(/Goal/), { target: { value: "Ship the page" } });
    fireEvent.change(getByLabelText(/Level/), { target: { value: "high" } });
    expect(getByRole("switch", { name: "Notify me" }).getAttribute("aria-checked")).toBe("true");
    fireEvent.click(getByText("Save"));
    expect(seen).toHaveLength(1);
    expect(seen[0]).toMatchObject({
      kind: "intent",
      intent: "goal.set",
      args: { goal: "Ship the page", level: "high", notify: true },
    });
  });

  it("renders an unknown element type as plain text with a warning, never crashing", () => {
    const { getByText, container } = render(
      <DynamicUI
        onAction={() => {}}
        payload={envelope([
          { type: "text", text: "before" },
          // Unknown types come through as untyped payloads from the wire.
          { type: "carousel", items: [] } as unknown as DynamicUIEnvelope["elements"][number],
        ])}
      />,
    );
    expect(getByText("before")).toBeTruthy();
    expect(getByText(/Unsupported element type/).textContent).toContain("carousel");
    expect(container.textContent).toContain("carousel");
  });

  it("renders a malformed envelope as a plain-text fallback instead of throwing", () => {
    const { getByText } = render(
      <DynamicUI onAction={() => {}} payload={{ kind: "dynamic-ui", version: 2, elements: [] }} />,
    );
    expect(getByText(/Unrecognized dynamic-UI payload/)).toBeTruthy();
  });

  it("renders null / garbage payloads without throwing", () => {
    const { getByText } = render(<DynamicUI onAction={() => {}} payload={null} />);
    expect(getByText(/Unrecognized dynamic-UI payload/)).toBeTruthy();
  });

  it("supports indeterminate progress", () => {
    const { container } = render(
      <DynamicUI
        onAction={() => {}}
        payload={envelope([{ type: "progress", label: "Working", indeterminate: true }])}
      />,
    );
    const bar = container.querySelector('[role="progressbar"]');
    expect(bar?.getAttribute("aria-valuenow")).toBeNull();
  });

  it("does not inject raw html — strings render as text", () => {
    const { container } = render(
      <DynamicUI
        onAction={() => {}}
        payload={envelope([{ type: "text", text: "<img src=x onerror=alert(1)>" }])}
      />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<img src=x onerror=alert(1)>");
  });

  it("calls onAction for plain card action buttons", () => {
    const onAction = vi.fn();
    const { getByText } = render(
      <DynamicUI
        onAction={onAction}
        payload={envelope([
          {
            type: "card",
            title: "Pick one",
            actions: [{ label: "Yes", action: { kind: "intent", intent: "confirm.yes" } }],
          },
        ])}
      />,
    );
    fireEvent.click(getByText("Yes"));
    expect(onAction).toHaveBeenCalledWith({ kind: "intent", intent: "confirm.yes" });
  });
});
