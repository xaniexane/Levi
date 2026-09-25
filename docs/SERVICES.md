# SERVICES — the legion service-offering standard

**One pipeline for every provider.** Whether the provider is an organ
(UniForge, DemandPulse, ...) or Levi in general, cyber and
software-development services are offered through one standard:

    analyze -> quote -> deliver -> paid -> showcase

## Lineage

- **NeighborOS** (`core/levi/neighbor/pay.py`) — the settlement-ledger
  pattern: money is planned, previewed, and settled as a ledger, never
  as a casual charge. The services standard inherits that discipline.
- **The Site Lift** (Easy Touch Massage site uplift) — the reference
  implementation of the pattern: AI analysis of the target, a priced
  offer, delivered work, paid on delivery, and a public track record.
  `dev-lift` is that pattern, named.
- **The bounty hunter** (`core/levi/bounty/`) — the state machine the
  pipeline rides: `draft -> open -> quoted -> agreed -> hunting ->
  delivered -> paid` (forward-only, terminal states).
- **The price advisor** (`core/levi/advisor/`) — quoting is composed
  from the founder-level advisor: no free core, ~30-60% below giants,
  volume over margin, roster law. A quote is never a charge.
- **DemandPulse** — scouts the demand; opportunities can seed
  offerings (the analysis records the `sensed_from` link).

## Service taxonomy

| Type | Flavor | What it is |
|---|---|---|
| `cyber-audit` | UniForge | security audit of code or systems (defensive, blue-team) |
| `cyber-hardening` | UniForge | harden a system or codebase against attack |
| `cyber-forensics` | UniForge | forensic diagnosis of a breach, failure, or anomaly |
| `dev-build` | Site Lift | build new software to a specification |
| `dev-lift` | Site Lift | uplift an existing site/system (the Site Lift pattern) |
| `dev-automation` | Site Lift | automation, pipelines, and agent wiring |
| `job-search` | job organ | job search as a service: opportunity scan, scored matches, application packages |

## The five stages

1. **Analyze** — AI analysis of the problem. Structured findings with
   evidence, severity, and recommendations. No fabrication: every
   finding requires evidence; empty reports state honestly that
   nothing was recorded. Confidence is an honest self-grade.
2. **Quote** — priced via the founder price advisor. Doctrine in
   code; a quote, not a charge; moves nothing.
3. **Deliver** — the hunt runs; the solution ships with evidence and
   a verification note. The hunter wins on accuracy, not pressure —
   never violent, never manipulative.
4. **Paid** — settlement through the **Cybrus money gateway only**.
   The gateway is fail-closed (no rails registered), so settlement
   refuses honestly until Chauncey deliberately registers a rail.
5. **Showcase** — admission to the public track record. All three
   must hold: state PAID, a Cybrus gateway receipt, and the gateway's
   record showing the movement executed. The showcase starts empty
   and stays honest.

## Job search as a service

The job search lives and originates in the services system
(`core/levi/services/job_search.py`). It wraps the job organ's
real machinery — sourcing, triage scoring, prep — as a
first-class offering. It never rebuilds that logic, never
fabricates a profile (the profile loads from the jobs organ's
store or the scan fails honestly), and never submits an
application: the deliver stage produces the package; submission
stays behind the job organ's human apply gate.

Two paths, one pipeline:

- **Chauncey's own search** — provider `levi` (internal). Quote
  is the advisor's valuation, labeled "no charge, not a sale".
  Paid/showcase do not apply.
- **Client service** — any organ provider. Full pipeline:
  advisor quote, paid through the Cybrus gateway only, showcase
  on verified delivery + confirmed payment.

```bash
levi service offer levi job-search "Chauncey's search"   # internal
levi service offer demandpulse job-search "client search" # client service
```

## Money law

Cybrus alone handles money — binding. The services package quotes,
delivers, and tracks, but never touches funds directly. The guard
test (`tests/test_money_law.py`) fails the suite if any money verb
appears outside Cybrus.

## CLI

```bash
levi service offer uniforge cyber-audit "Q3 code audit" --problem "..." --scope "repo X"
levi service analyze svc_XXXXXXXX --subject "repo X" --summary "..." \
  --finding "SQL injection in login" --evidence_a "login.py:42" --severity high
levi service quote svc_XXXXXXXX --giant-price 500 --strategy volume
levi service deliver svc_XXXXXXXX --solution "..." --evidence "patch.diff" --verification "tests pass"
levi service showcase svc_XXXXXXXX   # refuses unless paid + gateway receipt
levi service list
```

## Honest limits

- Settlement and showcase admission are structurally unreachable
  today: no payment rails registered, so the gateway always refuses.
  `paid` exists as a state; it is reachable only when Chauncey
  registers a rail.
- The no-fabrication guards are structural (evidence required), but
  they cannot verify the *truth* of the evidence — the provider's
  honesty is enforced by the process, not proven by it.
- DemandPulse-sensed opportunities only see what's in the
  opportunity store; silent demand is invisible.
