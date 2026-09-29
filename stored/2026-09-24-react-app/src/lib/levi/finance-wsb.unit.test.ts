/**
 * Unit tests for the SIMULATED PREVIEW finance fixture generator.
 * The data here is synthetic by design — these tests assert shape and
 * internal consistency, never real-world correctness.
 */
import { describe, expect, it } from "vitest";
import { generateFixture } from "./finance-wsb";

describe("generateFixture", () => {
  it("is deterministic for the same seed", () => {
    const a = generateFixture(7);
    const b = generateFixture(7);
    expect(a.tape).toEqual(b.tape);
    // generated_at timestamps differ by construction; compare the rest.
    const strip = (s: (typeof a)["signals"]) => s.map(({ generated_at: _ga, ...rest }) => rest);
    expect(strip(a.signals)).toEqual(strip(b.signals));
    expect(a.portfolio).toEqual(b.portfolio);
    expect(a.bets).toEqual(b.bets);
  });

  it("produces signals with advisory flags and confidence in [0,1]", () => {
    const { signals } = generateFixture(42);
    expect(signals.length).toBeGreaterThan(0);
    for (const s of signals) {
      expect(s.advisory).toBe(true);
      expect(s.confidence).toBeGreaterThanOrEqual(0);
      expect(s.confidence).toBeLessThanOrEqual(1);
      expect(s.rationale.length).toBeGreaterThan(0);
      expect(["bullish", "bearish", "neutral"]).toContain(s.direction);
    }
  });

  it("keeps the portfolio arithmetic consistent", () => {
    const { portfolio } = generateFixture(42);
    const sum = Object.values(portfolio.positions).reduce(
      (acc, p) => acc + p.unrealized_pnl + p.realized_pnl,
      0,
    );
    expect(portfolio.total_pnl).toBeCloseTo(sum, 1);
    expect(portfolio.unrealized_pnl + portfolio.realized_pnl).toBeCloseTo(sum, 1);
  });

  it("settled bets carry a pnl, open bets do not", () => {
    const { bets } = generateFixture(42);
    for (const b of bets) {
      if (b.status === "settled") {
        expect(b.pnl).not.toBeNull();
        expect(b.exit_price).not.toBeNull();
      } else {
        expect(b.pnl).toBeNull();
        expect(b.exit_price).toBeNull();
      }
    }
  });

  it("sorts the leaderboard by total pnl descending", () => {
    const { leaderboard } = generateFixture(42);
    for (let i = 1; i < leaderboard.length; i++) {
      expect(leaderboard[i - 1].total_pnl).toBeGreaterThanOrEqual(leaderboard[i].total_pnl);
    }
  });
});
