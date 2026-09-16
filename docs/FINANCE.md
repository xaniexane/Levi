# LEVI Finance Domain — Paper-Only Simulator + Advisory Signals

**Status:** paper-only build. Live trading is **structurally impossible** in
this build (see [Paper vs. live](#paper-vs-live-what-live-would-require)).

**Safety gate:** the dependency/build sign-off for this domain was granted
in writing, and the **signal-logic safety sign-off was granted in writing
on 2026-09-15** ("Approved", against §6 as built: 8 rules, regime
detection, volatility-adjusted confidence, 15-question checklist). Signals
remain advisory-only and the build remains paper-only — live trading would
still need its own separate approvals and does not exist in this build.

---

## 1. What the finance domain is — and is not

**It is:**

- A **paper-only market simulator**: fetch real delayed daily bars, compute
  standard technical indicators, keep a paper portfolio ledger, and fill
  paper orders at real latest closes.
- An **advisory signal engine**: deterministic, rule-based scoring of
  indicators into a human-readable `Signal` (bullish / bearish / neutral
  with a confidence number). "AI" here means *deterministic heuristics
  plus optional local-model narration* — see the review brief.
- A **research notebook**: paper-trade ideas, watch the paper P&L, review
  what the indicators actually said — with zero real money involved.

**It is NOT:**

- **Not a trading system.** Nothing in this domain can place a real order,
  hold a real position, or move real money. There is no wired broker
  transport anywhere in the build.
- **Not financial advice.** Every signal is labeled advisory-only and
  carries a paper-only disclaimer by construction (see `Signal.advisory`,
  enforced in `__post_init__`).
- **Not a prediction engine.** Signals are fixed rules applied to past
  price data — they describe what the indicators say, not what the market
  will do.

---

## 2. Architecture

### 2.1 Package map (`core/levi/finance/`)

| Module | Job | May import |
|---|---|---|
| `market.py` | Market-data providers: `Bar`, `MarketDataProvider`, `StooqProvider` (keyless CSV over stdlib `urllib`), `MarketDataError` | stdlib only |
| `indicators.py` | Pure-stdlib indicators: `sma`, `ema`, `rsi`, `macd`, `bollinger`, `atr`, `stochastic`, `obv`, `adx` (+DI/−DI), `vwap` — plain lists, `None`-padded warmup — plus `classify_regime` (trending / ranging / volatile) | stdlib only (`math`) |
| `signals.py` | Deterministic signal scoring: `score_bars`, `generate_signal`, `narrate` | `indicators`, `market`, `model.abstraction` (narration only) |
| `portfolio.py` | Paper ledger: `Portfolio`, `Position`, JSON persistence, realized/unrealized P&L | stdlib only |
| `broker.py` | `PaperBroker` (default, simulated fills) and `AlpacaConnector` (declared, **transport not wired**) | stdlib + `plugins.registry` |
| CLI | `levi finance` in `core/levi/cli/main.py` (`cmd_finance`) | finance modules only — never a live broker |

### 2.2 Stdlib-only kernel (blueprint §1.1)

The finance kernel is stdlib-only: `urllib`, `csv`, `dataclasses`,
`math`, `json`, `pathlib`, `datetime`, `abc`, `re`. **No pandas, no
numpy, no requests, no broker SDK.** A real broker dependency would be a
deliberate, sign-off'd decision (blueprint §1.1) — it has not been made,
and nothing in the kernel assumes it.

### 2.3 Why `signals.py` cannot import broker code (advisory-only separation)

`signals.py` has **no import path to any trade-execution code** — not to
`broker.py`, not to the portfolio ledger, not to any connector. This is
deliberate architecture, not an accident:

- A `Signal` is *research output*, never an instruction to act. If the
  scoring code could reach an order router, a bug (or a future feature)
  could turn an advisory into an action. The separation makes that
  structurally impossible.
- The guarantee is enforced in code: `Signal.advisory` is always `True`
  (`__post_init__` raises otherwise), and the module docstring documents
  the no-import rule so future editors can't quietly add a broker import.

### 2.4 `PaperBroker` vs `AlpacaConnector`

- **`PaperBroker`** — the default and the *only* broker reachable from the
  CLI. A plain class (not a plugin `Connector`): it holds no credentials,
  touches no network, moves no money. Fills are computed deterministically
  from a caller-supplied reference price. Every `Fill` carries
  `simulated=True`, `broker="paper"`, and `str(fill)` always contains the
  word **SIMULATED** — a paper fill cannot be mistaken for a real one.
  `place_order` raises `OrderNotConfirmed` without explicit `confirm=True`
  (HITL, blueprint §1.5), `InvalidOrder` for bad input, and
  `NoReferencePrice` when no reference price is supplied — **a fill price
  is never invented**.
- **`AlpacaConnector`** — the honest connector contract for a real
  equities broker, reusing `levi.plugins.registry.Connector`. Its
  transport is **not wired**: no SDK, no `urllib` call, nothing. Any
  attempt to use it surfaces the registry's honest `transport_not_wired`
  status. Success is never simulated. It requires both `LEVI_ALPACA_KEY`
  and `LEVI_ALPACA_SECRET` (read from the environment, never logged,
  printed, or written to disk) and forces `requires_confirmation=True`
  with no per-feature override. It is deliberately **not registered** in
  the connector registry — the live path only exists behind
  `live_enabled()` / `get_broker("alpaca")`.

### 2.5 Honest-connector statuses

Providers and connectors never pretend. The vocabulary they use:

- `MarketDataError` — market data missing, invalid, or unusable. Providers
  raise it instead of returning empty results, so "no data" can never be
  mistaken for "zero data". The CLI maps it to an honest message + exit 1,
  never fabricated numbers.
- `transport_not_wired` — the Alpaca transport has no implementation;
  the connector says so plainly instead of faking a quote or an order.
- `missing_credential` — names exactly which env vars are absent and
  sends nothing.
- `LiveBrokerUnavailable` — `get_broker("alpaca")` raises this unless
  every live prerequisite holds, naming exactly what is missing.

---

## 3. Paper vs. live: what "live" would require

Live trading in this build is **structurally impossible**, not merely
switched off. Making it possible would require all five of the following,
**none of which is implemented**:

1. **A deliberate dependency decision with sign-off** (blueprint §1.1)
   to add a real broker transport — either stdlib `urllib` against the
   Alpaca REST API or an approved SDK — and a wired `_call_api`
   implementation in `AlpacaConnector`. Today there is no SDK import, no
   HTTP call, and no stub that pretends otherwise.
2. **A wired transport** in `AlpacaConnector` (the `_request` path
   currently falls through to the unwired base implementation).
3. **Credentials present**: `LEVI_ALPACA_KEY` **and**
   `LEVI_ALPACA_SECRET` both set and non-blank (read from the environment
   only; never logged, printed, or written to disk).
4. **The explicit opt-in flag**: `LEVI_BROKER_LIVE=1` in the environment.
5. **Per-order human confirmation, every time** — `PaperBroker.place_order`
   raises `OrderNotConfirmed` without `confirm=True`, and the registry
   forces `requires_confirmation=True` on `AlpacaConnector` with no
   per-feature override (blueprint §1.5).

`live_enabled()` returns `True` **only** when 3 + 4 hold, and
`get_broker("alpaca")` raises `LiveBrokerUnavailable` naming exactly what
is missing otherwise. The CLI (`levi finance order`) never reaches
`AlpacaConnector` at all: any `--live` flag or `LEVI_BROKER_LIVE`-shaped
usage is refused with exit code 2 and a message naming the five
requirements above.

> **Explicit statement:** none of the five items is wired. There is no
> code path — CLI, skill, plugin, or otherwise — that can place a real
> order in this build. Live trading is structurally impossible here, not
> just disabled by default.

---

## 4. Risk disclosures (plain language)

- **Signals are deterministic heuristics, not predictions.** The engine
  applies eight fixed rules to past price data (seven vote, one is
  context-only; §6.2). It does not know the
  future, does not model the economy, and does not "understand" the
  company. A bullish signal is a statement about indicator geometry —
  "price is above its 20-day average and momentum is positive" — not a
  forecast that the price will rise.
- **Paper fills ignore slippage, fees, and market impact.** A paper order
  fills at the latest daily close with zero commission, zero spread, and
  zero effect on the market. Real orders pay all three. Paper P&L is
  systematically flattering.
- **Past paper performance ≠ future results.** A strategy that "worked"
  on last year's bars, simulated, may fail on next month's market. This
  is true of every backtest ever run, including this one.
- **Never trade money you can't afford to lose.** If this domain ever
  grows a live path (see §3), that path will still be gated behind
  explicit human confirmation on every order — but the gate is the last
  line of defense, not the first. The first line is you.
- **This is not financial advice.** LEVI is a research companion, not a
  financial advisor. Nothing it prints — signals, narratives, indicator
  snapshots — is a recommendation to buy, sell, or hold anything.

---

## 5. CLI reference (`levi finance`)

All commands are paper-only. Market-data failures print an honest message
and exit 1; HITL/live refusals and invalid input exit 2.

| Command | What it does |
|---|---|
| `finance quote <SYM> [--json]` | Latest close + day range via Stooq. |
| `finance indicators <SYM>` | SMA20, EMA12/26, RSI14, MACD line/signal/histogram, Bollinger 20, ATR14, Stochastic %K/%D, OBV, ADX14 +DI/−DI, VWAP, and the regime label (trending / ranging / volatile) for the latest bar (`n/a` with warmup note when data is short). |
| `finance signal <SYM> [--json]` | Advisory signal: direction, confidence, rationale bullets, indicator snapshot, narrated text — with the "ADVISORY ONLY — paper only, not financial advice" banner. |
| `finance portfolio [--json]` | Paper ledger: cash, positions, realized / unrealized / total P&L, market value. Symbols whose prices can't be fetched are listed as **warnings** and valued at average cost — never zeroed. |
| `finance order <SYM> <QTY> --side buy\|sell [--yes] [--live]` | Paper order. Without `--yes`: refusal + exit 2 (HITL gate, nothing placed). With `--yes`: `PaperBroker` fills at the latest close, applies to the ledger, prints the **SIMULATED** fill, saves. `--live` (or `LEVI_BROKER_LIVE`): refused with the five live requirements, exit 2. Never reaches `AlpacaConnector`. |
| `finance deposit <AMOUNT>` | Funds the paper portfolio. Positive amounts only; cash starts at 0. |

The paper ledger lives at `~/.levi/finance/portfolio.json` (directory mode
`0o700`).

---

## 6. SIGNAL-LOGIC REVIEW BRIEF

*Written for the human safety sign-off (blueprint §5.5): the dependency
sign-off for this domain is done; the **signal-logic sign-off was granted
in writing on 2026-09-15** ("Approved"). The brief below remains the
standing reference for what was reviewed.
Read this section before deciding whether the signal engine is safe to
trust — even with paper money, and especially if a live path is ever
proposed. Every claim below is grounded in `core/levi/finance/signals.py`;
no rule is described that the code does not implement.*

### 6.1 The data source

`generate_signal(symbol)` fetches **daily OHLCV bars** from
`StooqProvider.daily_bars(symbol, days=120)` — a keyless CSV endpoint
fetched over stdlib `urllib`. Rows whose close is `N/D` are skipped (not
faked); an empty or unusable feed raises `MarketDataError`, which
propagates honestly — **a signal is never fabricated from a failed fetch**.
`score_bars(symbol, bars)` then runs the fixed rule set below. There is no
model, no randomness, no external state: **the same bars always produce
the same signal** (`generated_at` is the only field that varies).

### 6.2 The eight scoring rules

Seven of the eight rules can cast votes. Each rule either votes, notes
context, or abstains — abstention is always explicit and explained in the
rationale. Voting rules belong to a **rule class** (trend-following,
mean-reversion, value, flow); the class decides the per-regime weight
(§6.4).

**Rule 1 — Trend (trend-following): close vs SMA(20).**
Formula: `close > sma(closes, 20)[-1]` → **+1 bullish**; `close <`
→ **+1 bearish**; exactly equal → **abstain** (no vote). One comparison,
one vote at most.

**Rule 2 — Momentum (trend-following): MACD line vs signal line (epsilon-guarded).**
`macd(closes, fast=12, slow=26, signal=9)`; compares the final MACD line
value to the final signal-line value. Above → **+1 bullish**; below →
**+1 bearish**; within `MOMENTUM_EPS = 1e-9` → treated as equal,
**abstain**. The epsilon exists because converged EMA values can differ
by ~1e-15 of pure floating-point noise (verified on a perfect
straight-line price ramp) — such noise must never cast a vote. Warmup
edge: the signal line needs 34 bars (slow 26 + signal 9); with 30–33
bars the line value is `None` and the rule **abstains with a rationale
note** instead of guessing.

**Rule 3 — Strength (mean-reversion): RSI(14).**
`rsi(closes, 14)[-1] > 55` → **+1 bullish**; `< 45` → **+1 bearish**;
45–55 → **abstain**. Extremes (`> 70` overbought, `< 30` oversold) add a
**NOTE to the rationale only — never a point**. Zero-movement guard: if
`ATR(14) == 0.0` the series did not move at all and RSI collapses to the
Wilder formula artifact `100.0`; the strength vote is **withheld** and the
rationale says why.

**Rule 4 — Volatility context: Bollinger(20, 2) position.**
Position of the close inside the band: upper third (≥ 2/3) → mild bullish
note; lower third (≤ 1/3) → mild bearish note; middle third or zero band
width → neutral note. **Never a point.** `ATR(14)` as a percentage of the
close is reported in the snapshot as regime context, never as a vote.

**Rule 5 — Directional movement (trend-following): +DI(14) vs −DI(14).**
`adx(bars, 14)` returns Wilder-smoothed `+DI`/`−DI`; the final values are
compared. `+DI` above `−DI` (beyond `DI_EPS = 1e-9`) → **+1 bullish**
(buying pressure dominates); `−DI` above `+DI` → **+1 bearish**; within
epsilon → **abstain**. Rationale: ADX itself is directionless (high ADX
means a strong trend, up *or* down), so the +DI/−DI cross carries the
directional vote that ADX alone cannot.

**Rule 6 — Stochastic (mean-reversion): %K(14) vs %D(3).**
`stochastic(bars)`: `%K = 100 × (close − lowest low of 14) / (highest high
of 14 − lowest low of 14)`; `%D = SMA(%K, 3)`. Final `%K` above `%D`
(beyond `STOCH_EPS = 1e-9`) → **+1 bullish** (short-term momentum turning
up); below → **+1 bearish**; within epsilon → **abstain**. `%K > 80` or
`< 20` adds an overbought/oversold **NOTE (no point)**. Zero-range
windows (flat tape) define `%K = 50.0` — a documented midpoint choice,
never a division by zero.

**Rule 7 — Value (value class): close vs VWAP.**
`vwap(bars)` is the volume-weighted average price anchored at the first
bar: `Σ(typical × volume) / Σ(volume)` with `typical = (H+L+C)/3`. Final
close above VWAP → **+1 bullish** (the market is paying up versus the
average traded price over the window); below → **+1 bearish**; equal →
**abstain**. This is a value reference, not a timing signal.

**Rule 8 — Money flow (flow class): OBV slope over 5 bars.**
`obv(bars)` is Granville's On-Balance Volume (`obv[0] = 0`, then ± volume
by the sign of each close change). `OBV[-1] − OBV[-6] > 0` → **+1 bullish**
(accumulation); `< 0` → **+1 bearish** (distribution); `== 0` →
**abstain**. The OBV level is arbitrary; only the slope votes.

### 6.3 Regime detection (ADX + ATR%)

Before scoring, `indicators.classify_regime(bars)` labels the tape. Exact
thresholds, checked in this order:

| Check | Threshold | Label |
|---|---|---|
| `ATR(14) / close × 100 ≥ 4.0` | `REGIME_VOLATILE_ATR_PCT = 4.0` | **volatile** |
| else `ADX(14) ≥ 25.0` | `REGIME_TREND_ADX = 25.0` | **trending** |
| else | — | **ranging** |

Rationale, as documented in the code:

- **ADX ≥ 25** is Wilder's classic trend-presence threshold: ADX is
  directionless by construction (it measures trend *strength*), and 25
  is the conventional level at which a trend is considered worth
  following rather than noise.
- **The 20–25 "weak trend" band is deliberately folded into ranging.**
  This is a conservative choice: the engine does not assume a trend
  without clear evidence, so a borderline ADX keeps the
  mean-reversion-friendly weighting.
- **ATR% ≥ 4.0** flags tapes with unusually wide daily swings for
  large-cap daily bars (typical daily ATR% runs ~1–3%). It is a
  judgmental heuristic, not a researched universal constant — its job
  is to mark tapes where the confidence penalty (§6.5), not rule
  weighting, does the substantive work.
- **Volatility is checked first.** A tape can be both volatile and
  directional; on a high-ATR% tape the engine labels it `volatile`
  because the confidence penalty handles the risk and no rule class
  is privileged there.
- **Warmup:** ADX(14) needs 28 bars; with fewer than
  `max(2 × adx_period, atr_period)` bars the classifier returns
  `"unknown"` with `None` values — the regime is never guessed. (At the
  `MIN_BARS = 30` scoring floor the regime is always computable.)

### 6.4 Per-regime rule weights

Each voting rule's vote is multiplied by its class weight from
`REGIME_WEIGHTS` (pinned by test
`test_regime_weights_table_matches_documentation`):

| Rule class | Rules | trending (×) | ranging (×) | volatile (×) |
|---|---|---|---|---|
| trend-following | 1 trend, 2 momentum, 5 +DI/−DI | **1.5** | **0.5** | 1.0 |
| mean-reversion | 3 RSI strength, 6 stochastic | **0.5** | **1.5** | 1.0 |
| value | 7 VWAP position | 1.0 | 1.0 | 1.0 |
| flow | 8 OBV slope | 1.0 | 1.0 | 1.0 |

Documented rationale: trend-following indicators whipsaw in ranges
(false signals), and mean-reversion indicators fade strong trends
(painful) — so each class is up-weighted ×1.5 where it belongs and
down-weighted ×0.5 where it does not. VWAP position and OBV slope are
regime-neutral references (where the average price was paid; who is
accumulating), so they stay ×1.0 everywhere. In volatile tapes no class
is privileged (all ×1.0): the volatility penalty on confidence does the
substantive work there. **These multipliers are judgmental heuristics,
not backtest-fitted constants** — they encode a belief about indicator
behavior per regime, not measured optimal values.

### 6.5 Score: weighted net → volatility-adjusted confidence

`weighted_net = Σ (class_weight × vote)`, a float (e.g. +5.50, −1.50).
Direction: `weighted_net ≥ 2` → **bullish**; `≤ −2` → **bearish**;
otherwise **neutral** (this includes ties and single-vote pluralities).

Confidence, in exact order:

1. **Base:** `min(0.95, 0.5 + 0.12 × |net|)`. Mapping for integer |net|:
   0 → 0.50, 1 → 0.62, 2 → 0.74, 3 → 0.86, ≥ 4 → 0.95 (capped).
   Fractional nets interpolate: 1.5 → 0.68, 2.5 → 0.80, 3.5 → 0.92.
2. **Volatility penalty:** the base is divided by
   `1 + max(0, atr_pct − 2.0) / 4.0`, where `atr_pct` is ATR(14) as a
   percentage of the close. No penalty at or below 2% (a typical
   large-cap daily true range — judgmental baseline); each extra 4
   points of ATR% halves what remains: ATR% 6 → ×0.50, ATR% 10 → ×0.33.
   Identical votes on a wider-ranged tape therefore score strictly
   lower confidence (verified by
   `test_volatility_penalty_lowers_confidence_for_identical_votes`).
3. **Multi-timeframe confluence** (§6.6): +0.05 on agreement, −0.05 on
   divergence, 0.0 when unavailable.
4. **Final:** `clamp(base × vol_factor + mtf_delta, 0, 0.95)`, rounded to
   2 decimals — confidence never claims 1.00 from heuristics and never
   goes negative (bounds pinned by `test_confidence_stays_within_bounds`).

Worked example (the test-suite ramp fixture, 40 bars rising 1/day):
trend +1 × 1.5, momentum abstains, strength +1 × 0.5, +DI over −DI +1 ×
1.5, stochastic abstains (%K == %D on a perfect ramp), VWAP +1 × 1.0,
OBV +1 × 1.0 → net +5.50 → bullish; base = min(0.95, 0.5 + 0.66) = 0.95;
ATR% 1.08 ≤ 2 → factor 1.000; MTF unavailable (40 < 60 bars) → 0.00;
final **0.95**.

### 6.6 Multi-timeframe confluence (weekly resample)

Precise meaning in this engine: when at least `MTF_MIN_DAILY_BARS = 60`
daily bars exist, they are resampled into fixed **5-trading-day groups**
(`_weekly_bars`, oldest first — *not* calendar weeks; no calendar logic
is used, keeping the resample deterministic), and the weekly close is
compared to the weekly `SMA(10)` (`MTF_WEEKLY_SMA`). The trailing group
may cover fewer than 5 days (a partial week); it is kept as its own
week.

- Weekly close above the weekly SMA(10) while the daily signal is
  bullish (or below while bearish) → **confluence**: rationale note +
  **+0.05 confidence**.
- Weekly close on the opposite side → **divergence**: rationale note +
  **−0.05 confidence**.
- Weekly close equal to the SMA, neutral daily signal, or unwarm weekly
  SMA → note, **no adjustment**.
- Fewer than 60 daily bars → the rationale states confluence is
  **unavailable** ("no adjustment") — it is never estimated from what
  is missing.

Honest limits: 60 daily bars yield only 12 weekly bars, just enough to
warm a weekly SMA(10); the weekly view is coarse, and the ±0.05 nudge is
deliberately small — a tiebreaker, not a second vote. The nudge is
applied *after* the volatility penalty, so high-volatility tapes stay
penalized even when timeframes agree.

### 6.7 The minimum-data rule

Fewer than 30 bars (`MIN_BARS`) → direction **neutral**, confidence
**0.0**, and the rationale states exactly what is missing (SMA/Bollinger
need 20, RSI needs 15, ATR needs 14, +DI/−DI need 15, stochastic %D
needs 16, ADX(14) needs 28, MACD signal line needs 34). **Partial
data is never scored; a signal is never guessed.** Note the deliberate
consequence: with 30–33 bars the engine scores everything except the
momentum rule, which abstains — the signal is weaker by construction,
and the rationale says so.

### 6.8 Epsilon guards and edge cases (what the code defends against)

- **MACD float noise** (`MOMENTUM_EPS = 1e-9`): converged EMAs differ by
  ~1e-15; without the guard, noise would cast votes on flat/ramping
  series. The guard converts near-ties into abstentions. The same
  1e-9 guard protects the stochastic (`STOCH_EPS`) and +DI/−DI
  (`DI_EPS`) comparisons.
- **Zero-ATR / flat series**: RSI reads 100.0 on a series that never
  moved — the guard withholds the vote instead of reporting "maximum
  strength."
- **Zero-width Bollinger band**: flat series → band width 0 → neutral
  note, no division by zero, no vote.
- **Zero-range stochastic window**: flat tape → `%K` defined as 50.0
  (documented midpoint), never a division by zero.
- **Zero-volume VWAP prefix**: falls back to the bar's typical price,
  never a division by zero.
- **N/D rows in the feed**: skipped at parse time, never treated as zero.
- **Invalid symbols / bad input**: rejected at the provider boundary with
  `MarketDataError`, before any scoring.

### 6.9 The indicator snapshot

Every scored signal carries `indicator_snapshot` (values rounded to 4
decimals, except `regime`/`mtf_weekly_trend` strings): `bars_used`,
`close`, `sma20`, `macd_line`, `macd_signal`, `rsi14`, `bollinger_upper`,
`bollinger_middle`, `bollinger_lower`, `bollinger_position`, `atr14`,
`atr_pct_of_close`, `stochastic_k`, `stochastic_d`, `adx14`,
`plus_di14`, `minus_di14`, `vwap`, `obv`, `regime`, `mtf_weekly_bars`,
`mtf_weekly_trend`. Insufficient-data signals carry only `bars_used`.
The CLI prints the snapshot verbatim — what you see is exactly what was
scored.

### 6.10 How narration works (model-preferred, deterministic fallback)

`narrate(signal)` follows the model-preferred, offline-graceful pattern
(blueprint §1.4): it tries `ModelRouter` first with a prompt that
instructs the model to **keep every number unchanged, invent no new
facts, recommend no real trades**, and end with an explicit advisory-only
+ paper-only statement. On *any* failure — no model available, generation
error, empty text — it falls back to `fallback_narrative`, a pure
deterministic function that restates direction, confidence, and rationale
and always carries the advisory wording and paper-only disclaimer. When
no real local/cloud model is behind the router, `narrate()` skips the
router entirely and uses `fallback_narrative` directly — the router's
own generic offline template (which echoes prompts and carries
placeholder variables) is never used for signal commentary.
**Narration never raises**: it is commentary, not data, and a narration
failure can never corrupt or block a signal.

### 6.11 Questions for the reviewer (sign-off checklist)

Answer each in writing before signing off on the signal logic:

1. **Are the thresholds sensible?** RSI 55/45 with a 45–55 deadband;
   Bollinger thirds at 1/3 and 2/3; stochastic 80/20 zones; weighted net
   ±2 for a directional call. Is the deadband symmetric enough, or does
   it bias one side?
2. **Are the regime thresholds sensible?** ADX ≥ 25 for trending (with
   the 20–25 band folded into ranging — too conservative?); ATR% ≥ 4.0
   for volatile (a judgmental heuristic — too twitchy for small-caps,
   too lax for large-caps?). Should volatility be checked before trend
   strength?
3. **Are the per-regime weights sensible?** Trend-following ×1.5 when
   trending (×0.5 when ranging) and the mirror for mean-reversion;
   value/flow ×1.0 everywhere; everything ×1.0 when volatile. Too
   strong, too weak, or the wrong classes?
4. **Is the confidence calibration honest?** 0.50 at |net| 0 (a coin
   flip) rising 0.12 per weighted vote to a 0.95 cap — then divided by
   up to the volatility factor and nudged ±0.05 by multi-timeframe
   confluence. Does "confidence 0.95" read as more precise than a
   7-rule weighted vote count warrants?
5. **Is the volatility penalty honest?** Baseline 2% ATR with each extra
   4 points halving confidence. False precision, or a reasonable way to
   make wide tapes humble?
6. **Any lookahead bias?** Every rule uses only the final bar and
   trailing windows. Confirm no rule peeks at data beyond the bar being
   scored — including the weekly resample (5-bar groups, last group is
   the most recent bars).
7. **Warmup edges:** with 30–33 bars the momentum rule explicitly
   abstains. Is a signal with a documented abstention acceptable output,
   or should 34 bars be the hard floor?
8. **Bollinger position as notes, not votes:** the mild bullish/bearish
   *notes* appear in the rationale and therefore in the narrative. Could
   a reader mistake a "mild bullish note" for a vote? Is the wording
   ("no point") clear enough?
9. **RSI / stochastic extremes as notes:** overbought (> 70 / > 80) is
   reported as context alongside a bullish strength vote. Is that
   contradictory enough to confuse — "strength +1 but overbought"?
10. **VWAP anchoring:** VWAP is anchored at the first bar of the fetched
    window (120 daily bars by default), not reset intraday or monthly.
    Does "price vs 120-day anchored VWAP" mean what a reviewer would
    expect, or is the anchor arbitrary enough to mislead?
11. **OBV slope window:** 5 bars. Too twitchy? And OBV ignores the size
    of price moves (a 1¢ up-day counts the same as a $5 up-day) — is
    that acceptable for a flow vote?
12. **Multi-timeframe confluence:** ±0.05 nudge, 60-bar minimum, fixed
    5-bar groups instead of calendar weeks. Acceptable, or does the
    small nudge create a false sense of rigor?
13. **Narration fidelity:** the model prompt *instructs* number
    preservation, but a local model can still paraphrase loosely. Is the
    deterministic fallback the right default, with the model as
    enrichment only?
14. **Adversarial inputs:** gappy data (N/D rows skipped → fewer bars
    than requested), single-day spikes, splits/dividends in the raw feed
    (Stooq does not adjust). Should the engine detect or disclaim any of
    these?
15. **The big one:** even with every answer above satisfactory, are you
    comfortable with a human reading "bullish, confidence 0.95" and
    acting on it? If not, what would need to change — the numbers, the
    words, or the fact that a confidence number is shown at all?

**The signal-logic safety sign-off was granted in writing on 2026-09-15**
("Approved"). This checklist remains the standing review record: signals
are reviewed heuristics — useful for research and paper trading, not for
real-money decisions, and the build remains structurally paper-only.
