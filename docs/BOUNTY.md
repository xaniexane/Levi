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
