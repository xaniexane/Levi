# BOUNTY.md — Bug-Bounty Recon Pipeline

LEVI's bug-bounty recon automates the **machine half** of bounty hunting:
attack-surface inventory. It enumerates subdomains, probes liveness and
ports, fingerprints web services from ordinary responses, collects
archived URLs, harvests JavaScript for endpoints, and flags
secret-shaped strings for the hunter to verify. Findings persist with
change detection, so a scheduled monitor tells you when *new* attack
surface appears.

What it does **not** do: exploit anything. No vulnerability-exploit
execution, no credential brute-forcing, no payload delivery beyond
ordinary GET requests. Findings are inventory, never exploit results.

## The scope rule (structural, not advisory)

Every network touch passes a scope gate against enrolled program scopes
(`~/.levi/bounty/scope.json`):

- `levi bounty scope add example.com` — enrolls `example.com` **and its
  subdomains**. Nothing is ever auto-enrolled.
- `levi bounty scope remove example.com` / `levi bounty scope list`
- Any target outside every enrolled scope → **hard refusal**. There is no
  `--force`, no environment override, no bypass. Every finding records the
  scope entry that authorized it.

Only ever enroll scopes for programs you are authorized to test. Scanning
outside your authorized scope is not bounty hunting — the pipeline
refuses to do it.

## Politeness defaults

- Honest User-Agent: `LEVI-bounty-recon/1.0 (authorized bug-bounty recon; in-scope targets only)`
- Timeouts on everything (8–10s); 0.5s delay between requests; sequential
  requests (no concurrency); a dead host or dead source never crashes a run.
- crt.sh and the Wayback CDX API are passive (no packets to the target);
  DNS resolution and TCP connect-scans are the lightest active touches.

## CLI usage

```bash
levi bounty scope add example.com
levi bounty scope list
levi bounty recon example.com
levi bounty recon example.com --ports 80,443,8080
levi bounty findings            # everything stored
levi bounty findings --new      # new since last run
levi bounty monitor             # recon every enrolled scope, print only new
```

Findings live at `~/.levi/bounty/findings.json` as
`{id, target, scope, kind, detail, evidence, first_seen, last_seen}`.
Repeat sightings refresh `last_seen`; `first_seen` never moves — that is
what powers `--new` and the monitor.

Finding kinds: `subdomain`, `open_port`, `http_service`, `tls_cert`,
`archived_url`, `js_endpoint`, `possible_exposure`. A
`possible_exposure` is a regex pattern match in JavaScript (e.g. an
AWS-shaped key) — reported for manual verification, never used or tested.

## Scheduling the monitor

**Via the LEVI agent** (preferred — stays inside the organism):

```
# in levi agent chat / tools:
schedule_add(name="bounty-monitor", cron="0 7 * * *",
             task="run: levi bounty monitor")
```

**Via system cron** (if LEVI is on PATH):

```cron
0 7 * * * /usr/local/bin/levi bounty monitor >> ~/.levi/bounty/monitor.log 2>&1
```

The monitor prints only new findings, so a quiet run means no new attack
surface — the ideal daily signal for a hunter.

## Limits (honest)

- crt.sh only sees hosts with certificates; the built-in wordlist is
  modest by design. Coverage is "good first pass", not exhaustive.
- Template vulnerability scanning (nuclei-style) is deliberately **not**
  included: active vulnerability probing crosses from inventory into
  testing, and belongs under explicit per-program judgment, not an
  unattended pipeline.
- The judgment half — novel vulns, business logic, chaining, report
  writing — stays human. The machine finds; the hunter decides.

---

# The Service-Bounty Hunter

Chauncey's order: bounty hunter abilities — find the problem, deliver a
detailed accurate solution, secure payment for the services — plus the
hunt showcase: the public track record.

## The hunt

A **bounty** = a problem statement + terms (scope, deadline, payment
terms). Bounties are registered manually (`levi bounty register ...`) or
sensed as drafts from DemandPulse opportunities
(`levi bounty sense --register`) — the hunter composes DemandPulse's
scouting, never duplicates it.

The state machine is forward-only and fail-closed:

```
draft -> open -> quoted -> agreed -> hunting -> delivered -> paid
```

Side exits to `cancelled` exist from every pre-paid state; `disputed`
can return to `hunting` or cancel. `paid` and `cancelled` are terminal.

**The no-fabrication guard.** Nothing reaches `delivered` without all
four: a real solution, real evidence, an honest confidence number
(0–1), and verification notes. The hunter wins on accuracy, not
pressure — never manipulative. A delivery that cannot be verified is
refused, not faked.

**Quotes are quotes, not charges.** `levi bounty quote` prices the hunt
through the founder-level price advisor (doctrine: no free core,
~30–60% below giants, volume over margin). Quoting moves nothing.

## Payment — Cybrus only

Binding law: **Cybrus is the only one ever allowed to handle money.**
The bounty module plans and tracks payment but never moves funds
itself. Every movement goes through `levi.cybrus.money.MoneyGateway`:

- `pay --plan` — builds the gateway PLAN (preview, not permission).
- `pay --execute --authorized-by <keeper>` — attempts settlement.
  Authorization must be Chauncey's keeper identity; the module never
  forges it.

Payment states: `none → quoted → agreed → delivered → paid`. `paid`
requires a gateway receipt showing an executed movement.

**Honest boundary:** no payment rails are registered and no rail
plug-ins are wired, so `MoneyGateway.execute()` always refuses
(fail-closed). Settlement therefore refuses truthfully today, and
`paid` — and with it showcase admission — is structurally unreachable
until Chauncey deliberately registers a rail. The module records the
refusal instead of pretending payment happened.

## The hunt showcase

`levi bounty showcase` renders the public track record. Admission is
structural, not editorial — all three must hold:

1. the bounty is in state `paid`,
2. it carries a Cybrus gateway receipt,
3. the gateway's own record shows the movement **executed**.

`--admit <bounty-id>` enforces this and refuses anything less, with the
reason stated. `--verify-client <entry-id>` adds the client's
attestation — a mark of confirmation, never a substitute for payment
proof. No fake entries, ever; the record starts empty and stays honest.

## Posture

High deterministic ambition, never violent, never manipulative. The
six-gate chain (Plan → Preview → Permission → Execute → Verify →
Receipt) governs the consequential acts: quoting (plan/preview),
agreement (permission), delivery (execute/verify), settlement
(receipt). Every step is logged on the bounty's append-only history.

## CLI quick reference

```
levi bounty register "Hunt title" --problem "..." --scope "..." --client "..."
levi bounty list [--state hunting]
levi bounty quote <id> [--giant-price 99] [--strategy volume|margin]
levi bounty agree <id> --note "client accepted terms on <date>"
levi bounty start <id>
levi bounty deliver <id> --solution "..." --evidence "a;;b" --confidence 0.9 --verification "..."
levi bounty pay <id> --plan
levi bounty pay <id> --execute --authorized-by chauncey
levi bounty pay <id> --status
levi bounty sense [--min-worth 0.5] [--register]
levi bounty showcase [--admit <id>] [--verify-client <entry-id> --note "..."]
```
