---
skill_id: cyber_implementing_runtime_application_self_protection
name: Implementing Runtime Application Self-Protection
description: Deploy RASP for in-application attack detection and blocking — instrumentation strategy, protection modes, and tuning to avoid breaking legitimate traffic.
risk: low
permissions: []
requires_confirmation: false
tags: [application-security, rasp, defense-in-depth]
version: 1.0.0
---
## Purpose

Give applications the ability to defend themselves from inside the runtime. RASP instruments the running application (via agents, language-runtime hooks, or library integration) to observe actual execution context — the real SQL query built, the actual deserialization call, the true file path accessed — and blocks attacks (SQL injection, command injection, deserialization, SSRF, path traversal) with far fewer false positives than a WAF guessing from outside, because it sees what the code is really doing.

## When to use

- Protecting custom applications where WAF rules generate excessive false positives or can't see encrypted/internal traffic.
- Adding runtime protection for legacy applications that can't be easily recoded.
- Meeting in-application protection expectations for high-risk apps (banking, payment processing).
- Complementing SAST/DAST: RASP catches what static and dynamic testing missed, in production.
- Gaining attack telemetry with full application context (which user, which session, which code path).

## Prerequisites

- Application inventory with runtime stacks (Java, .NET, Node.js, Python — RASP support varies by language) and deployment models.
- RASP vendor/tool selection matched to your runtimes (commercial: Contrast, Hdiv; open-source options limited — evaluate honestly).
- Performance budget: RASP agents add latency and memory overhead; load-test before production.
- SIEM integration for RASP attack events with application context.
- Staged deployment plan: monitor-only before blocking, per application.

## Procedure

1. **Select RASP per runtime reality.** Match the tool to your actual stacks — Java and .NET have the most mature RASP options; Node.js and Python support varies. Evaluate: instrumentation method (agent vs. library), overhead under your load profile, and blocking accuracy on your vulnerability classes. Pilot on one representative application before committing fleet-wide.
2. **Deploy in monitor mode first.** Instrument the application with protection in detect-only. Run through full business cycles including peak load: measure performance overhead (latency percentiles, memory, CPU), and collect the attack-telemetry baseline. RASP in monitor mode is also a vulnerability discovery tool — it finds the injection points your testing missed.
3. **Tune protection rules per application.** Review every would-block event with developers: true attacks (keep blocking), legitimate-but-unusual patterns (tune the rule — e.g., the admin bulk-import that looks like mass assignment), and application bugs RASP exposed (fix the code; RASP found you a vulnerability). Tune until the block list is clean.
4. **Enable blocking progressively.** Switch protection modes per attack class, highest-confidence first (command injection, deserialization of untrusted data), then broader classes (SQLi, XSS, SSRF). Keep an emergency kill-switch: the ability to drop an application back to monitor mode in seconds without redeploying — a bad RASP rule in blocking mode is a self-inflicted DoS.
5. **Integrate attack telemetry with the SOC.** Ship RASP events with full context (user, session, stack trace location, payload) to the SIEM. Build playbooks: RASP block on SQLi from an authenticated user → investigate as potential account abuse; repeated blocks from one source → WAF/IP blocking and incident escalation. RASP telemetry's application context makes it high-fidelity.
6. **Use RASP findings to fix code.** Every blocked attack class maps to a code-level vulnerability. Feed RASP findings back to development as prioritized remediation: the deserialization sink RASP keeps blocking should be removed, not eternally shielded. RASP is a control and a sensor, not a substitute for secure code.
7. **Manage the agent lifecycle.** Include RASP agents in change management: test agent upgrades in staging (agent bugs crash applications), pin versions per application, and monitor agent health (a silently dead agent is silently absent protection). Coordinate with APM/monitoring agents to avoid instrumentation conflicts.
8. **Measure effectiveness.** Track: blocked attacks by class, false-positive rate, performance overhead, mean time from RASP finding to code fix, and coverage (% of critical applications instrumented). Report alongside WAF metrics to show the layered defense picture.

## Expected outputs

- RASP tooling matched to runtime stacks with pilot validation.
- Monitor-mode baselines with performance measurements and tuned rules.
- Progressive blocking enablement with emergency kill-switch tested.
- SOC integration with application-context alerting and playbooks.
- Feedback loop from RASP findings to code remediation; effectiveness metrics.

## Pitfalls

- **Blocking on day one.** Untested RASP rules in blocking mode break legitimate application flows — especially complex ones (bulk operations, admin functions, integrations). Monitor, tune, then block.
- **Performance surprises.** Agent overhead that looks fine in staging can degrade under production peak load. Load-test with the agent at realistic traffic before committing.
- **RASP as a code-fix replacement.** Shielding a known SQL injection with RASP forever instead of fixing the query accumulates risk (agent gaps, bypass techniques) and technical debt. Fix the code.
- **Agent conflicts.** Multiple instrumenting agents (APM + RASP + security) can conflict, causing crashes or blind spots. Test the full agent stack together.
- **Coverage theater.** Instrumenting the marketing site while the payment API runs unprotected misallocates the control. Prioritize by application risk, and be honest about runtime gaps the tooling can't cover.

## References

- OWASP guidance on runtime protection concepts — https://owasp.org/
- NIST SP 800-53 Rev. 5, SI-10 (Information Input Validation) and SI-16-adjacent runtime protections — https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final
- MITRE ATT&CK T1190 (Exploit Public-Facing Application) — the attack class RASP mitigates — https://attack.mitre.org/techniques/T1190/
- Vendor RASP documentation for the selected platform
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
