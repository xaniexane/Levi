/**
 * finance-wsb.ts — data types + SIMULATED PREVIEW fixtures for the
 * WSB-flavored paper-trading dashboard.
 *
 * ═══════════════════════════════════════════════════════════════════
 *  EVERYTHING IN THIS MODULE IS SIMULATED PAPER-TRADING DATA.
 *  Nothing here is a real price, a real portfolio, or a real trade.
 *  Advisory content is NOT financial advice.
 * ═══════════════════════════════════════════════════════════════════
 *
 * The shapes below mirror the Python finance domain (core/levi/finance/)
 * so the UI can later be wired to the real engine without a re-shape.
 */

export type SignalDirection = "bullish" | "bearish" | "neutral";

export interface Signal {
  symbol: string;
  direction: SignalDirection;
  /** Heuristic agreement score, 0–1. NOT a probability — see dashboard copy. */
  confidence: number;
  rationale: string[];
  indicator_snapshot: Record<string, string | number>;
  generated_at: string;
  advisory: true;
}

export interface Position {
  qty: number;
  avg_cost: number;
  realized_pnl: number;
  unrealized_pnl: number;
}

export interface PortfolioSummary {
  cash: number;
  positions: Record<string, Position>;
  realized_pnl: number;
  unrealized_pnl: number;
  market_value: number;
  total_pnl: number;
}

export type BetStatus = "open" | "settled";

export interface Bet {
  id: string;
  trader: string;
  symbol: string;
  side: "buy" | "sell";
  qty: number;
  entry_price: number;
  exit_price: number | null;
  status: BetStatus;
  pnl: number | null;
  early_exit: boolean;
}

export interface LeaderboardRow {
  trader: string;
  bets: number;
  wins: number;
  win_rate: number;
  total_pnl: number;
  /** Fraction of held bets never early-exited, 0–1. */
  diamond_rate: number;
}

export interface CopyReport {
  follow: boolean;
  n_mirrored: number;
  copier_pnl: number;
  trader_pnl: number;
  win_rate: number;
  note: string;
}

/** Ticker-tape entry shown in the meme tape marquee. */
export interface TapeEntry {
  symbol: string;
  price: number;
  change_pct: number;
}

export interface FinanceWsbSnapshot {
  generated_at: string;
  tape: TapeEntry[];
  signals: Signal[];
  portfolio: PortfolioSummary;
  bets: Bet[];
  leaderboard: LeaderboardRow[];
  copy_report: CopyReport;
}

const TRADERS = [
  "DiamondDee",
  "PaperHandsPete",
  "MoonshotMara",
  "YoloYusuf",
  "ThetaGangTheo",
  "ApeTogetherAmy",
] as const;

const SYMBOLS = ["MOON", "DIP", "HODL", "APES", "YOLO", "GAIN"] as const;

const RATIONALES: Record<SignalDirection, string[]> = {
  bullish: [
    "Regime filter says trend is green across the heuristic stack.",
    "Volatility band tightened — coiled-spring setup per the rules.",
    "Momentum heuristics agree 7 of 8; volume proxy confirms.",
  ],
  bearish: [
    "Trend heuristics flipped negative on the last three candles.",
    "Volatility expansion without follow-through — distribution smell.",
    "Mean-reversion score deep in the red zone.",
  ],
  neutral: [
    "Indicators are fighting each other — no edge, sit out.",
    "Chop detector pinging: chop, chop, chop.",
    "Confidence too low to ape in; preservation mode.",
  ],
};

function pick<T>(arr: readonly T[], r: () => number): T {
  return arr[Math.floor(r() * arr.length)];
}

/** Tiny seeded PRNG so the fixture reads as stable per session render. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * generateFixture — SIMULATED PREVIEW data generator.
 *
 * Builds a fully synthetic snapshot for UI development. Every number is
 * invented at render time; pass a `seed` for deterministic output.
 */
export function generateFixture(seed = 42): FinanceWsbSnapshot {
  const rnd = mulberry32(seed);
  const now = new Date().toISOString();

  const tape: TapeEntry[] = SYMBOLS.map((symbol) => {
    const price = 20 + rnd() * 480;
    const change_pct = (rnd() - 0.48) * 24;
    return {
      symbol,
      price: Math.round(price * 100) / 100,
      change_pct: Math.round(change_pct * 100) / 100,
    };
  });

  const signals: Signal[] = SYMBOLS.slice(0, 5).map((symbol) => {
    const direction = pick(["bullish", "bearish", "neutral"] as const, rnd);
    return {
      symbol,
      direction,
      confidence: Math.round((0.45 + rnd() * 0.5) * 100) / 100,
      rationale: RATIONALES[direction].slice(0, 2 + Math.floor(rnd() * 2)),
      indicator_snapshot: {
        rsi_14: Math.round(20 + rnd() * 60),
        macd_hist: Math.round((rnd() - 0.5) * 4 * 100) / 100,
        atr_pct: `${Math.round(rnd() * 8 * 10) / 10}%`,
        trend_score: Math.round((rnd() * 2 - 1) * 100) / 100,
      },
      generated_at: now,
      advisory: true as const,
    };
  });

  const positions: Record<string, Position> = {};
  let unrealized_pnl = 0;
  let realized_pnl = 0;
  for (const s of SYMBOLS.slice(0, 4)) {
    const qty = 10 + Math.floor(rnd() * 90);
    const avg_cost = Math.round((20 + rnd() * 300) * 100) / 100;
    const tapePrice = tape.find((t) => t.symbol === s)?.price ?? avg_cost;
    const unreal = Math.round((tapePrice - avg_cost) * qty * 100) / 100;
    const realized = Math.round((rnd() - 0.5) * 2000 * 100) / 100;
    positions[s] = { qty, avg_cost, realized_pnl: realized, unrealized_pnl: unreal };
    unrealized_pnl += unreal;
    realized_pnl += realized;
  }
  unrealized_pnl = Math.round(unrealized_pnl * 100) / 100;
  realized_pnl = Math.round(realized_pnl * 100) / 100;
  const market_value =
    Math.round(
      Object.entries(positions).reduce((sum, [sym, p]) => {
        const px = tape.find((t) => t.symbol === sym)?.price ?? p.avg_cost;
        return sum + px * p.qty;
      }, 0) * 100,
    ) / 100;
  const cash = Math.round((25000 + rnd() * 25000) * 100) / 100;

  const bets: Bet[] = TRADERS.map((trader, i) => {
    const symbol = SYMBOLS[i % SYMBOLS.length];
    const entry = tape.find((t) => t.symbol === symbol)?.price ?? 100;
    const settled = rnd() > 0.45;
    const exit_price = settled ? Math.round(entry * (0.85 + rnd() * 0.35) * 100) / 100 : null;
    const side = rnd() > 0.5 ? "buy" : "sell";
    const qty = 5 + Math.floor(rnd() * 45);
    const pnl = settled
      ? Math.round(((exit_price ?? 0) - entry) * qty * (side === "buy" ? 1 : -1) * 100) / 100
      : null;
    return {
      id: `bet-${seed}-${i}`,
      trader,
      symbol,
      side,
      qty,
      entry_price: entry,
      exit_price,
      status: settled ? "settled" : "open",
      pnl,
      early_exit: settled && rnd() > 0.7,
    };
  });

  const leaderboard: LeaderboardRow[] = bets
    .map((b) => {
      const wins = b.status === "settled" && (b.pnl ?? 0) > 0 ? 1 : 0;
      return {
        trader: b.trader,
        bets: 1 + Math.floor(rnd() * 24),
        wins,
        win_rate: Math.round((0.3 + rnd() * 0.5) * 100) / 100,
        total_pnl: Math.round((b.pnl ?? (rnd() - 0.4) * 3000) * 100) / 100,
        diamond_rate: Math.round(rnd() * 100) / 100,
      };
    })
    .sort((a, b2) => b2.total_pnl - a.total_pnl);

  const top = leaderboard[0];
  const copy_report: CopyReport = {
    follow: true,
    n_mirrored: 3 + Math.floor(rnd() * 8),
    copier_pnl: Math.round(top.total_pnl * (0.4 + rnd() * 0.3) * 100) / 100,
    trader_pnl: top.total_pnl,
    win_rate: top.win_rate,
    note: `Mirroring ${top.trader}'s paper signals. Copier fills land slightly worse than the leader — that's slippage, not magic.`,
  };

  return {
    generated_at: now,
    tape,
    signals,
    portfolio: {
      cash,
      positions,
      realized_pnl,
      unrealized_pnl,
      market_value,
      total_pnl: Math.round((realized_pnl + unrealized_pnl) * 100) / 100,
    },
    bets,
    leaderboard,
    copy_report,
  };
}
