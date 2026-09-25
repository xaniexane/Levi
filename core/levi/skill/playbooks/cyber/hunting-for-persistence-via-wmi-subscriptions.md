---
skill_id: cyber_hunting_for_persistence_via_wmi_subscriptions
name: Hunting for Persistence via WMI Subscriptions
description: Detect malicious WMI event subscriptions: rogue EventFilter/EventConsumer/Binding instances and their payloads.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, persistence, windows]
version: 1.0.0
---
## Purpose

WMI event subscriptions — an EventFilter, an EventConsumer, and a
FilterToConsumerBinding — provide fileless, stealthy persistence that
survives reboots and hides from Autoruns-style tools that only check
common locations. This playbook covers enumerating, baselining, and
hunting malicious WMI subscriptions.

## When to use

- Post-compromise persistence sweeps: WMI subscriptions are a favorite
  APT persistence mechanism.
- Investigating EDR alerts for WMI event creation (Sysmon 19/20/21).
- Hunting for fileless persistence on servers and high-value hosts.
- Validating that persistence-hunting covers non-traditional
  mechanisms.

## Prerequisites

- Ability to enumerate WMI subscriptions fleet-wide (PowerShell
  `Get-WMIObject __EventFilter/__EventConsumer/__FilterToConsumerBinding`,
  Velociraptor artifacts, or EDR).
- Sysmon events 19 (WmiEventFilter), 20 (WmiEventConsumer), 21
  (WmiEventConsumerToFilter) collected centrally where available.
- Baseline of legitimate WMI subscriptions (SCCM, monitoring agents
  create them).
- Knowledge of consumer types: CommandLineEventConsumer (highest
  risk), ActiveScriptEventConsumer, and others.

## Procedure

1. **Enumerate all three classes.** List EventFilters, EventConsumers,
   and Bindings in the `root\subscription` namespace on each host.
   All three must exist for a working subscription — orphans of any
   class still merit review.
2. **Baseline legitimate subscriptions.** Document subscriptions created
   by management and monitoring tooling (names, queries, consumers).
   Legitimate filters typically watch for hardware/software events;
   attacker filters often use timer intervals or process-creation
   events as triggers.
3. **Inspect consumer payloads.** For each CommandLineEventConsumer,
   read the full command line; for ActiveScript consumers, extract the
   script text. Attacker payloads include encoded PowerShell,
   download cradles, and LOLBin invocations. Treat obfuscated payloads
   as malicious until proven otherwise.
4. **Check filter triggers.** Review the WQL queries in EventFilters:
   `__TimerInstruction` intervals (periodic execution), process-
   creation filters targeting security tools (defense evasion), or
   logon-event triggers. Compare against the legitimate baseline.
5. **Correlate creation events.** Use Sysmon 19/20/21 or
   WMI-Activity logs to date each subscription's creation and identify
   the creating process — attacker subscriptions cluster around
   intrusion timestamps and are created by script hosts or LOLBins,
   not installers.
6. **Hunt fleet-wide for the pattern.** Once a malicious subscription
   is characterized (naming pattern, payload shape), sweep the fleet
   for matches — attackers deploy the same persistence to multiple
   hosts.
7. **Remove completely.** Delete the binding, consumer, and filter (in
   that order), remove payload files, and verify via re-enumeration.
   Check for companion persistence — WMI subscriptions are often
   paired with other mechanisms.
8. **Deploy durable detections.** Alert on Sysmon 19/20/21 events
   outside change windows and on new CommandLineEventConsumer creation
   fleet-wide; add WMI-subscription enumeration to recurring
   persistence hunts.

## Expected outputs

- Per-host WMI subscription inventories with baseline comparison.
- Malicious subscriptions documented with payloads and creation
  context.
- Fleet-wide sweep results for matching patterns.
- Complete removal verification records.
- Detections for new WMI subscription creation.

## Pitfalls

- Enumeration requires the right namespace and permissions —
   `root\subscription` is not in the default namespace; incomplete
   queries miss everything.
- Legitimate management tools create subscriptions that look odd —
   baseline before alerting.
- Removing only the consumer leaves the filter (harmless alone but
   confusing); remove all three classes and verify.
- Sysmon 19/20/21 are not enabled by default in older configs —
   verify collection before relying on creation-event dating.
- WMI repository corruption can hide subscriptions from live queries —
   for high-assurance cases, examine the repository objects forensically.

## References

- MITRE ATT&CK: T1546.003 (Windows Management Instrumentation Event
  Subscription)
- Microsoft Learn: WMI event subscription classes documentation
- Sysmon documentation (events 19/20/21)
- Industry research on WMI persistence (defensive summaries)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
