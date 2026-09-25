# Shield Service — authorized assessment + hardening

Penetration testing and hardening — strengthening weak points — as a
providable service for other platforms and businesses. **Defensive
blue-team only.**

## What it is

Shield takes a client's system through:

```
intake -> authorize -> assess (plan + findings) -> harden -> verify -> sealed report
```

offered through the legion service standard:

```
analyze -> quote -> deliver -> paid -> showcase
```

## The law (hard gates, in code)

1. **Written authorization or nothing.** No authorization record, no
   assessment, no findings, no hardening — every entry point calls
   `require_authorization()` first. The gate opens only on the exact
   confirmation phrase, a named signatory, a non-empty asset scope,
   testing windows, and a future expiry date.
2. **Rules of engagement are enforced.** The authorization names the
   permitted assessment categories; any other category is refused.
   Targets outside the authorized scope raise `ScopeViolation` —
   rejected, not warned.
3. **No offensive capability exists.** The service plans assessments
   from the defensive playbook knowledge base and records findings
   with evidence. It performs no automated intrusion and ships no
   offensive tooling — asserted by test (`test_no_offensive_capability`).
4. **Findings require evidence.** A finding without evidence cannot be
   recorded. A hardening action without a verification note cannot be
   verified. A finding closes only after every linked action is
   re-verified: assess → report → harden → verify.
5. **Money through Cybrus only, fail-closed.** Quotes ride the founder
   price advisor (a quote is never a charge). Settlement attempts the
   Cybrus gateway and refuses without a registered rail.
6. **Showcase needs consent.** Only paid, receipted work is showcased,
   and only with the client's explicit consent.

## Method base

Assessment plans resolve method references live from the 823
defensive cyber playbooks (`levi.skill.cyber_skills`), so new
playbooks register automatically:

| Category | Playbook tags consulted |
|---|---|
| wireless | wireless, assessment |
| web-application | web, appsec, assessment |
| network | network, assessment |
| configuration | hardening, configuration |
| cloud | cloud, assessment |
| email-security | phishing, email, defense |
| incident-readiness | incident-response, tabletop, readiness |

## Quickstart

```bash
# 1. Authorize (the exact confirmation phrase is required)
python -m levi.services.shield authorize \
  --client "Acme Corp" --contact "J. Rivera" --role "CISO" \
  --assets "acme.example.com,mail.acme.example.com" \
  --windows "2026-10-01..2026-10-07 02:00-05:00 UTC" \
  --categories "network,configuration" --by "J. Rivera" \
  --expires "2026-10-08" \
  --confirm "I AUTHORIZE THIS SECURITY ASSESSMENT"

# 2. Plan the assessment (writes plan JSON to stdout)
python -m levi.services.shield plan <auth-id> \
  --type network --targets "acme.example.com" > plan.json

# 3. Record a finding (evidence is mandatory)
python -m levi.services.shield finding <auth-id> \
  --plan <plan-id> --target "acme.example.com" --severity high \
  --title "Management interface exposed" \
  --evidence "TCP/443 responds on WAN with default certificate" \
  --playbook cyber_<skill_id>

# 4. Build the hardening plan, then verify each action
python -m levi.services.shield harden <auth-id>
python -m levi.services.shield verify <auth-id> <action-id> \
  --note "re-checked: interface no longer reachable from WAN"

# 5. Seal the report
python -m levi.services.shield report <auth-id> --plan-json plan.json
```

## Honest limits

- The service plans and records; evidence capture against the
  client's scope is operator-driven. There is no automated scanning
  or intrusion capability in this module — by design.
- The authorization gate proves a recorded, affirmative, in-scope
  act on this machine. It is not a substitute for the client's own
  legal counsel on testing agreements.
- Playbook references are method guidance, not guarantees: a plan
  is only as good as the operator executing it.
- Money is paper-only until Chauncey registers a payment rail;
  settlement fails closed until then.
