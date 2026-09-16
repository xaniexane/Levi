/**
 * FinanceWsb — WSB-flavored paper-trading dashboard for /finance.
 *
 * ═══════════════════════════════════════════════════════════════════
 *  PAPER ONLY — SIMULATED. Every number is synthetic fixture data from
 *  generateFixture() in @/lib/levi/finance-wsb. Nothing is a real price,
 *  a real portfolio, or a real trade. Advisory content is NOT financial
 *  advice. Confidence values are HEURISTIC AGREEMENT, never probability.
 * ═══════════════════════════════════════════════════════════════════
 *
 * WSB energy with CLEAN slang only — no slurs, ever. The fun ("positions
 * or ban", "diamond hands vs paper hands", "to the moon") stays; hateful
 * language is hard-blocked: it never appears here or in fixtures.
 */

import { useMemo } from "react";
import {
  type Bet,
  type FinanceWsbSnapshot,
  type LeaderboardRow,
  type Signal,
} from "@/lib/levi/finance-wsb";

function fmtMoney(n: number): string {
  const sign = n < 0 ? "−" : "";
  const abs = Math.abs(n);
  return `${sign}$${abs.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(n: number): string {
  const sign = n < 0 ? "−" : "+";
  return `${sign}${Math.abs(n).toFixed(2)}%`;
}

function pnlClass(n: number): string {
  return n >= 0 ? "text-ok" : "text-danger";
}

/** Honesty banner — every finance panel ships with this visible. */
function HonestyBadge() {
  return (
    <div className="flex flex-wrap items-center gap-2" role="note" aria-label="Honesty notice">
      <span className="rounded-full border border-accent/60 bg-accent/10 px-3 py-1 font-mono text-[11px] font-bold tracking-[0.18em] text-accent uppercase">
        Paper only — simulated
      </span>
      <span className="rounded-full border border-border-strong bg-elevated px-3 py-1 font-mono text-[11px] tracking-[0.18em] text-muted uppercase">
        Not financial advice
      </span>
      <span className="rounded-full border border-border-strong bg-elevated px-3 py-1 font-mono text-[11px] tracking-[0.18em] text-muted uppercase">
        Confidence = heuristic agreement, not probability
      </span>
    </div>
  );
}

function SectionTitle({ kicker, title }: { kicker: string; title: string }) {
  return (
    <div className="mb-4">
      <p className="font-mono text-[11px] font-bold tracking-[0.24em] text-accent uppercase">
        {kicker}
      </p>
      <h2 className="font-display text-2xl font-bold text-fg">{title}</h2>
    </div>
  );
}

function Tape({ tape }: { tape: FinanceWsbSnapshot["tape"] }) {
  const items = [...tape, ...tape]; // loop the marquee seamlessly
  return (
    <div
      className="overflow-hidden border-y border-border bg-surface"
      aria-label="Simulated ticker tape"
    >
      <div className="flex w-max animate-wsb-tape gap-8 py-2.5 whitespace-nowrap">
        {items.map((t, i) => (
          <span key={i} className="font-mono text-sm">
            <span className="font-bold text-fg">${t.symbol}</span>{" "}
            <span className="text-muted">{fmtMoney(t.price)}</span>{" "}
            <span className={t.change_pct >= 0 ? "text-ok" : "text-danger"}>
              {fmtPct(t.change_pct)} {t.change_pct >= 0 ? "🚀" : "📉"}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

function GainLossBanner({ portfolio }: { portfolio: FinanceWsbSnapshot["portfolio"] }) {
  const total = portfolio.total_pnl;
  const gain = total >= 0;
  return (
    <section
      className={`relative overflow-hidden rounded-xl border p-6 md:p-8 ${
        gain ? "border-ok/50 bg-ok/10" : "border-danger/50 bg-danger/10"
      }`}
      aria-label="Gain or loss summary"
    >
      <p className="font-mono text-[11px] font-bold tracking-[0.24em] text-muted uppercase">
        {gain ? "📈 Gain porn — portfolio update" : "📉 Loss porn — portfolio update"}
      </p>
      <p className={`font-display mt-2 text-4xl font-black md:text-5xl ${pnlClass(total)}`}>
        {fmtMoney(total)}
      </p>
      <p className="mt-2 max-w-xl text-sm text-muted">
        {gain
          ? "Diamonds are being formed under pressure. But remember: this is paper — nobody got rich today."
          : "The market giveth and the market rug-pull-eth. But remember: this is paper — nobody went broke today."}{" "}
        Diamond hands 💎🙌 vs paper hands 🧻 — where do you land?
      </p>
      <HonestyBadge />
    </section>
  );
}

const DIRECTION_STYLE: Record<Signal["direction"], string> = {
  bullish: "border-ok/50 bg-ok/10 text-ok",
  bearish: "border-danger/50 bg-danger/10 text-danger",
  neutral: "border-border-strong bg-elevated text-muted",
};

const DIRECTION_EMOJI: Record<Signal["direction"], string> = {
  bullish: "🚀",
  bearish: "🐻",
  neutral: "🦀",
};

function SignalCards({ signals }: { signals: Signal[] }) {
  return (
    <section aria-label="Due diligence signals">
      <SectionTitle kicker="The DD desk" title="Due diligence, ape-approved" />
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {signals.map((s) => (
          <article key={s.symbol} className="rounded-xl border border-border bg-surface p-5">
            <div className="flex items-center justify-between">
              <h3 className="font-mono text-lg font-black text-fg">${s.symbol}</h3>
              <span
                className={`rounded-full border px-3 py-1 font-mono text-[11px] font-bold tracking-[0.18em] uppercase ${DIRECTION_STYLE[s.direction]}`}
              >
                {DIRECTION_EMOJI[s.direction]} {s.direction}
              </span>
            </div>
            <p className="mt-3 text-sm text-muted">
              Heuristic agreement:{" "}
              <span className="font-mono font-bold text-fg">{Math.round(s.confidence * 100)}%</span>{" "}
              <span className="text-subtle">(heuristic, not probability)</span>
            </p>
            <ul className="mt-3 space-y-1.5">
              {s.rationale.map((r, i) => (
                <li key={i} className="text-sm text-fg/90">
                  <span className="text-accent">▸</span> {r}
                </li>
              ))}
            </ul>
            <dl className="mt-4 grid grid-cols-2 gap-2 border-t border-border pt-3">
              {Object.entries(s.indicator_snapshot).map(([k, v]) => (
                <div key={k} className="font-mono text-xs">
                  <dt className="text-subtle">{k}</dt>
                  <dd className="text-fg">{v}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 font-mono text-[11px] tracking-[0.18em] text-subtle uppercase">
              Advisory only — not financial advice
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}

function PositionsOrBan({ portfolio }: { portfolio: FinanceWsbSnapshot["portfolio"] }) {
  const entries = Object.entries(portfolio.positions);
  return (
    <section aria-label="Paper portfolio positions">
      <SectionTitle kicker="Post 'em" title="Positions or ban" />
      <div className="overflow-hidden rounded-xl border border-border bg-surface">
        <div className="border-b border-border bg-elevated/60 px-5 py-3">
          <p className="font-mono text-xs text-muted">
            Cash: <span className="font-bold text-fg">{fmtMoney(portfolio.cash)}</span> · Market
            value: <span className="font-bold text-fg">{fmtMoney(portfolio.market_value)}</span> ·
            Unrealized:{" "}
            <span className={pnlClass(portfolio.unrealized_pnl)}>
              {fmtMoney(portfolio.unrealized_pnl)}
            </span>{" "}
            · Realized:{" "}
            <span className={pnlClass(portfolio.realized_pnl)}>
              {fmtMoney(portfolio.realized_pnl)}
            </span>
          </p>
        </div>
        {entries.length === 0 ? (
          <p className="px-5 py-8 text-center text-muted">
            No positions. The ban hammer is trembling… ⚒️
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {entries.map(([symbol, p]) => (
              <li
                key={symbol}
                className="flex flex-wrap items-center justify-between gap-2 px-5 py-4"
              >
                <div>
                  <p className="font-mono text-base font-black text-fg">${symbol}</p>
                  <p className="font-mono text-xs text-muted">
                    {p.qty} sh @ {fmtMoney(p.avg_cost)}
                  </p>
                </div>
                <div className="text-right font-mono text-sm">
                  <p className={pnlClass(p.unrealized_pnl)}>
                    {p.unrealized_pnl >= 0 ? "💎" : "🧻"} {fmtMoney(p.unrealized_pnl)}
                  </p>
                  <p className="text-xs text-subtle">realized {fmtMoney(p.realized_pnl)}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
        <p className="border-t border-border px-5 py-3 font-mono text-[11px] tracking-[0.18em] text-subtle uppercase">
          Paper only — simulated · not financial advice
        </p>
      </div>
    </section>
  );
}

function BetTickets({ bets }: { bets: Bet[] }) {
  return (
    <section aria-label="Paper bet tickets">
      <SectionTitle kicker="YOLO responsibly (it's fake money)" title="Paper-bet tickets" />
      <div className="grid gap-4 md:grid-cols-2">
        {bets.map((b: Bet) => (
          <article
            key={b.id}
            className="relative rounded-xl border border-dashed border-border-strong bg-surface p-5"
          >
            <div className="flex items-center justify-between">
              <p className="font-mono text-sm font-bold text-fg">
                🎟️ {b.trader} <span className="text-subtle">·</span>{" "}
                <span className={b.side === "buy" ? "text-ok" : "text-danger"}>
                  {b.side.toUpperCase()}
                </span>{" "}
                ${b.symbol} ×{b.qty}
              </p>
              <span
                className={`rounded-full px-2.5 py-0.5 font-mono text-[11px] font-bold uppercase ${
                  b.status === "open" ? "bg-accent/15 text-accent" : "bg-elevated text-muted"
                }`}
              >
                {b.status}
              </span>
            </div>
            <p className="mt-2 font-mono text-xs text-muted">
              in {fmtMoney(b.entry_price)}
              {b.exit_price != null ? ` → out ${fmtMoney(b.exit_price)}` : " → riding…"}
            </p>
            {b.pnl != null && (
              <p className={`mt-1 font-display text-2xl font-black ${pnlClass(b.pnl)}`}>
                {fmtMoney(b.pnl)}
                {b.early_exit && (
                  <span className="ml-2 align-middle font-mono text-xs font-normal text-subtle">
                    🧻 paper hands (early exit)
                  </span>
                )}
                {b.pnl >= 0 && (
                  <span className="ml-2 align-middle font-mono text-xs font-normal text-subtle">
                    💎 diamond hands
                  </span>
                )}
              </p>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

function Leaderboard({ rows }: { rows: LeaderboardRow[] }) {
  return (
    <section aria-label="Paper trading leaderboard">
      <SectionTitle kicker="The hall of gain" title="Leaderboard" />
      <div className="overflow-x-auto rounded-xl border border-border bg-surface">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead>
            <tr className="border-b border-border bg-elevated/60 font-mono text-[11px] tracking-[0.18em] text-muted uppercase">
              <th className="px-5 py-3">#</th>
              <th className="px-5 py-3">Trader</th>
              <th className="px-5 py-3">Bets</th>
              <th className="px-5 py-3">Win rate</th>
              <th className="px-5 py-3">Diamond rate 💎</th>
              <th className="px-5 py-3 text-right">Total P&amp;L</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r: LeaderboardRow, i: number) => (
              <tr key={r.trader} className="border-b border-border last:border-0">
                <td className="px-5 py-3 font-mono text-muted">
                  {i === 0 ? "👑" : i === 1 ? "🥈" : i === 2 ? "🥉" : i + 1}
                </td>
                <td className="px-5 py-3 font-bold text-fg">{r.trader}</td>
                <td className="px-5 py-3 font-mono text-muted">{r.bets}</td>
                <td className="px-5 py-3 font-mono text-fg">{Math.round(r.win_rate * 100)}%</td>
                <td className="px-5 py-3 font-mono text-fg">
                  💎 {Math.round(r.diamond_rate * 100)}%
                </td>
                <td className={`px-5 py-3 text-right font-mono font-bold ${pnlClass(r.total_pnl)}`}>
                  {fmtMoney(r.total_pnl)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 font-mono text-[11px] tracking-[0.18em] text-subtle uppercase">
        Paper only — simulated
      </p>
    </section>
  );
}

function CopyTrading({
  copyReport,
  topTrader,
}: {
  copyReport: FinanceWsbSnapshot["copy_report"];
  topTrader: string;
}) {
  const cr = copyReport;
  return (
    <section aria-label="Copy trading forecast">
      <SectionTitle kicker="Ape together" title="Copy-trading forecast" />
      <div className="rounded-xl border border-accent/40 bg-accent/5 p-6">
        <p className="text-sm text-fg">
          {cr.follow ? "🐵 Following" : "🙈 Skipping"}{" "}
          <span className="font-bold">{topTrader}</span> — mirroring{" "}
          <span className="font-mono font-bold">{cr.n_mirrored}</span> paper signals.
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <div className="rounded-lg border border-border bg-surface p-4">
            <p className="font-mono text-[11px] tracking-[0.18em] text-subtle uppercase">
              Forecast copier P&amp;L
            </p>
            <p className={`font-display text-2xl font-black ${pnlClass(cr.copier_pnl)}`}>
              {fmtMoney(cr.copier_pnl)}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-surface p-4">
            <p className="font-mono text-[11px] tracking-[0.18em] text-subtle uppercase">
              Leader P&amp;L
            </p>
            <p className={`font-display text-2xl font-black ${pnlClass(cr.trader_pnl)}`}>
              {fmtMoney(cr.trader_pnl)}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-surface p-4">
            <p className="font-mono text-[11px] tracking-[0.18em] text-subtle uppercase">
              Heuristic win agreement
            </p>
            <p className="font-display text-2xl font-black text-fg">
              {Math.round(cr.win_rate * 100)}%
            </p>
          </div>
        </div>
        <p className="mt-4 text-sm text-muted">{cr.note}</p>
        <p className="mt-2 font-mono text-[11px] tracking-[0.18em] text-subtle uppercase">
          Forecast is simulated — not a promise, not financial advice
        </p>
      </div>
    </section>
  );
}

export function FinanceWsb({ snapshot }: { snapshot: FinanceWsbSnapshot }) {
  const topTrader = useMemo(
    () => (snapshot.leaderboard.length > 0 ? snapshot.leaderboard[0].trader : "—"),
    [snapshot],
  );
  return (
    <div className="min-h-full bg-bg text-fg">
      <style>{`@keyframes wsb-tape { from { transform: translateX(0); } to { transform: translateX(-50%); } }
.animate-wsb-tape { animation: wsb-tape 30s linear infinite; }
@media (prefers-reduced-motion: reduce) { .animate-wsb-tape { animation: none; } }`}</style>
      <Tape tape={snapshot.tape} />
      <main className="mx-auto max-w-6xl space-y-10 px-4 py-8 md:px-8">
        <header className="space-y-4">
          <p className="font-mono text-[11px] font-bold tracking-[0.24em] text-accent uppercase">
            Levi finance · WSB mode
          </p>
          <h1 className="font-display text-4xl font-black md:text-5xl">
            Stonks go up <span className="text-accent">🚀</span>
          </h1>
          <p className="max-w-2xl text-muted">
            Due-diligence signals, paper positions, and glorious simulated bets. LEVI crunches the
            heuristics; the apes bring the energy. All numbers are synthetic — treat them like a
            sketch, not a bank statement.
          </p>
          <HonestyBadge />
        </header>
        <GainLossBanner portfolio={snapshot.portfolio} />
        <SignalCards signals={snapshot.signals} />
        <PositionsOrBan portfolio={snapshot.portfolio} />
        <BetTickets bets={snapshot.bets} />
        <Leaderboard rows={snapshot.leaderboard} />
        <CopyTrading copyReport={snapshot.copy_report} topTrader={topTrader} />
        <footer className="border-t border-border pt-6 pb-4">
          <p className="font-mono text-[11px] leading-relaxed tracking-[0.14em] text-subtle uppercase">
            Snapshot generated {snapshot.generated_at} · Paper only — simulated · Not financial
            advice · Confidence = heuristic agreement, never probability
          </p>
        </footer>
      </main>
    </div>
  );
}
