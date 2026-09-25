# Demand Numbers — the scoring rubric

Every demand signal in the DemandPulse store carries a **number**: a
deterministic 0–100 score computed only from the signal's own properties.
No black box — this document is the whole algorithm. If the code and this
document disagree, the document wins and the code is a bug.

## The five factors (weights sum to 1.0)

| factor | weight | what it measures | how it's computed |
|---|---|---|---|
| expression_strength | 0.30 | how strongly the need is phrased | base 10 + demand-marker points + 5 for question form + up to 10 for length (1 per 10 chars); capped at 100 |
| frequency | 0.20 | how many DISTINCT source items the need was mined from | `min(100, 20 * log2(1 + distinct_items))` — legacy signals without item provenance fall back to seen_count and the basis says so |
| recency | 0.15 | how fresh the signal is | `100 * 2^(-days/30)` — 30-day half-life |
| source_diversity | 0.15 | corroboration across channels | 50 neutral for one channel, +25 per extra channel in the signal's near-dupe cluster, cap 100 |
| domain_match | 0.20 | fit to his known domains | 34 points per distinct matched domain term, cap 100 |

Composite = Σ (factor value × weight), rounded to 2 dp — then calibrated
by the source channel's **observed reliability**: × (0.75 + 0.5 ×
reliability). Reliability is the channel's measured extraction yield
(sentences surviving the quality gates ÷ sentences carrying a need
marker); 0.5 is the stated neutral prior when unmeasured. The multiplier
is printed on every number — never hidden.

## Expression markers

Matched case-insensitively on word boundaries. The full table lives in
`core/levi/demand/numbers.py` (`_EXPRESSION_MARKERS`); the shape is:

- purchase intent (25): "willing to pay", "would pay", "take my money", "shut up and take"
- price talk (8–20): "how much", "pricing", "price", "paid", "budget", "cost"
- active seeking (12–15): "looking for", "need/needs/needed", "seeking", "searching for", "in search of", "desperate", "require(s)", "want(s)"
- pain (8–12): "struggling", "frustrated/frustrating", "painful", "broken", "doesn't work", "problem(s)", "pain", "hate", "wish", "if only", "annoying"
- request (6–10): "help", "recommend(ation)", "suggest(ion)", "advice", "anyone know", "alternative(s)", "ideas", "tips"
- urgency (5–10): "urgent", "asap", "immediately", "deadline", "right now", "today", "now"

A signal's basis line lists exactly which markers matched — that's the audit trail.

## Domain terms (label-level only)

Domains: **levi**, **demandpulse**, **dynasty**, **content**. Terms are
matched against the signal text. The dynasty domain is matched on its
public label only — dynasty/IP material is eyes-only and is **never** read
for matching terms (standing orders).

A non-"general" segment counts as one domain hit (the segment already
encodes domain intent).

## Worked example

Signal: "I need help scheduling shifts", mined from 81 distinct feed
items, fresh, corroborated in 1 channel, segment "general", channel
reliability 0.5 (unmeasured).

- expression: base 10 + "need" 15 + "help" 10 + length 2 = **37.0**
- frequency: 20 × log2(82) = 127.1 → capped **100.0**
- recency: 0 days → **100.0**
- source_diversity: 1 channel → **50.0**
- domain_match: no domain terms → **0.0**

raw = 37.0×0.30 + 100.0×0.20 + 100.0×0.15 + 50.0×0.15 + 0.0×0.20
    = 11.1 + 20.0 + 15.0 + 7.5 + 0.0 = 53.60

reliability multiplier: 0.75 + 0.5×0.5 = **1.000**
number = 53.60 × 1.000 = **53.60**

## Opportunities

Signals cluster into opportunity rows by keyword Jaccard ≥ 0.35
(deterministic: processed in id order). Row score = mean of member signal
numbers. Rank: score desc, then row id asc. Tier = strongest member kind
(OBSERVED > INFERENCE > HYPOTHESIS) — the tier is never invented, only
inherited.

## Honesty notes

- A low number means "thin evidence", never "no opportunity".
- Repeats are occurrence metadata: distinct observed items feed the
  frequency factor but never raise confidence or change kind (N4).
  Re-polling the same source item adds nothing — it is already merged.
- Scores are sensed-demand advisories. They execute nothing and touch no money.
- Provenance: a feed signal carries its source item(s); without any,
  the number says so in the frequency basis.
