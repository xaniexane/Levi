import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Mark } from "./Mark";

describe("Mark", () => {
  it("renders an svg marked aria-hidden", () => {
    const { container } = render(<Mark />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("aria-hidden")).toBe("true");
  });

  it("passes className through to the svg", () => {
    const { container } = render(<Mark className="h-8 w-8" />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("class")).toContain("h-8");
    expect(svg?.getAttribute("class")).toContain("w-8");
  });

  it("renders without className", () => {
    const { container } = render(<Mark />);
    expect(container.querySelector("svg")).not.toBeNull();
  });
});
