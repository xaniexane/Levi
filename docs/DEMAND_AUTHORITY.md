# DemandPulse Autonomous Upgrade Authority

DemandPulse may **automatically** execute upgrades and changes when it senses
time-sensitivity — under a strict, binding tier framework (Chauncey, 2026-09-17).

## Tiers

| Tier  | Meaning | Behavior |
|-------|---------|----------|
| MINOR | reversible, low-risk: config tweaks, small patches | **Full auto.** Executes on a live signal; audit entry + receipt. |
| MID   | bounded: dependency upgrades, module improvements | **Auto, but** every action carries a full audit trail + receipt (six gates recorded). |
| MAJOR | architecture changes, irreversible acts, security, founder-level | **NEVER auto.** Escalates to Chauncey; the framework executes nothing. |

## Trigger

Nothing runs without a **live time-sensitive sensed signal** (confidence ≥ 0.5,
not expired). No signal → refusal. Expired or low-confidence signal → refusal.
Time-sensitivity is the trigger; without it there is no authority.

## Fail closed

- **Ambiguous classification = MAJOR = escalate.** Unknown kinds, irreversible
  flags, security-sensitive flags, founder-level flags, or non-local scope all
  land at major. There is deliberately no way to auto-run them.
- **Major actions are structurally unexecutable**: the framework contains no
  code path that invokes an executor for a major action — even if one is
  passed. `register_executor` refuses major kinds outright.
- Executor exceptions never take down the framework; the failure is recorded.

## Six-gate chain

Every autonomous execution records Plan → Preview → Permission → Execute →
Verify → Receipt in its audit entry. Permission for autonomous minor/mid acts
is the **standing grant** (Chauncey, 2026-09-17) — labeled honestly in the
record as standing authority, not per-action human approval.

## Posture

Global posture is recorded on every receipt: **high deterministic ambition**
— aggressive, ambitious methods; never violent, never manipulative.

## Executors

The framework ships with safe built-in executors (`config-tweak` writes to a
sandboxed file under `~/.levi/demand/`; patch-like kinds record an advisory
note). Real executors for production changes (e.g. actual dependency upgrades)
are registered by the caller via `register_executor` — registration of a
major kind is refused.

## CLI

```
levi demand --authority status
levi demand --authority audit [-n 20]
levi demand --authority escalations
levi demand --authority resolve <id> --note "..."
levi demand --authority sense --source X --evidence "..." --confidence 0.8 --ttl 3600
levi demand --authority propose --kind dependency-upgrade --target levi.scores [--execute --signal <id> --param k=v]
```

## Records

- Audit: `~/.levi/demand/authority-audit.jsonl` (what, why, tier, signal, result)
- Escalations: `~/.levi/demand/escalations.jsonl` (open until Chauncey resolves)

## Honest limits

- Classification is kind-based heuristics + flags, not understanding of intent.
- The built-in mid-tier executors record advisories; actual system changes need
  real registered executors, each still tier-gated.
- A MID receipt is a record of what ran, not a guarantee the change was wise.
- Major-tier escalations execute nothing — they wait on Chauncey by design.
