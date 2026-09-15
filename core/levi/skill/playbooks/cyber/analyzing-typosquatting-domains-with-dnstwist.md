# Analyzing Typosquatting Domains with dnstwist

See also: analyzing-certificate-transparency-for-phishing.md

## Purpose

Proactively discover typosquatting and lookalike domains targeting your brand — the registrations
attackers use for phishing, credential harvesting, and business-email-compromise infrastructure —
using dnstwist's permutation engine. Findings feed takedown workflows, defensive registrations, and
phishing-detection rules before the domains are weaponized.

The strategic value is time: a lookalike domain found at registration gives you days or weeks of
lead time before it appears in a phishing email. This playbook operationalizes that lead time.

## When to use

- Brand-protection monitoring: scheduled sweeps for new lookalike registrations of your domains.
- During a phishing incident: checking whether the attacker registered sibling domains you haven't
  seen yet.
- Before a product launch or rebrand: identifying the lookalike surface of the new name so marketing
  and security can act.
- Threat-intel enrichment: assessing whether a suspicious domain from an alert is part of a broader
  typosquat cluster.
- Executive-protection: monitoring lookalikes of executive names used in BEC pretexting.

## Prerequisites

- Written authorization from brand/security leadership for the monitoring scope: the exact seed
  domains, the sweep frequency, and who receives findings. Include approval for passive DNS and
  WHOIS lookups.
- The seed domain list (your owned domains and key product names) in a versioned file.
- A defined disposition workflow: who evaluates hits, who requests takedowns, and who approves
  defensive registrations (with budget owner identified).
- Note: dnstwist's checks are passive (DNS queries, WHOIS lookups, HTTP banner grabs). Do not log
  into, submit credentials to, or otherwise interact with suspicious domains — observation only.
- A safe page-capture method (isolated browser or sandboxed fetch) approved for the triage step, so
  analysts don't improvise one mid-investigation.

## Procedure

1. Prepare the seed list. Write one domain per line in `seeds.txt`. Include your primary domains,
   product names as domains where relevant, and known-good variants. Exclude domains you do not own
   or have no mandate to monitor.
2. Run the baseline permutation scan. Execute dnstwist with registration checking and a TLD
   dictionary: `dnstwist --registered --tld dictionaries/common_tlds.dict --format json --output
   baseline.json example.com`. The `--registered` flag filters to domains that actually resolve or
   have NS records; the TLD dictionary expands coverage beyond the seed's own TLD.
3. Add phishing-signal checks. Re-run (or run initially) with content checks enabled: `dnstwist
   --registered --mxcheck --ssdeep --tld dictionaries/common_tlds.dict --format json --output
   detailed.json example.com`. `--mxcheck` flags domains with mail exchangers (phishing-ready), and
   `--ssdeep` fuzzy-hashes page content against the legitimate site to catch visual clones.
4. Triage the registered hits. For each registered permutation, classify: defensive registration
   candidate (you should own it), benign third party (document and move on), suspicious-but-dormant
   (parked, no content — watch), or active threat (phishing kit, credential form, brand
   impersonation). Record the evidence for each classification: screenshots via a safe rendering
   method, DNS records, WHOIS data.
5. Investigate active threats. For phishing-active domains: capture the page safely (isolated
   browser or `curl` of HTML only — never submit credentials), extract kit indicators (form actions,
   exfil URLs, favicon hashes), check CT logs for certificates issued to the domain, and pivot on
   WHOIS/registrar and name server patterns for sibling registrations.
6. Pivot on infrastructure. For confirmed-malicious domains, pivot on shared name servers,
   registrar, creation-date clustering, and TLS certificate overlaps to find sibling domains the
   permutation scan missed. Attackers often register in batches — one found domain implies more.
7. Act on the findings. File takedown/abuse reports with the registrar and hosting provider (include
   the evidence bundle); submit the domain and its indicators to your threat-intel platform and
   phishing-detection feeds; and route defensive-registration candidates to the domain team with a
   priority order.
8. Prioritize defensive registrations. Rank candidates by risk: exact-match typos of the primary
   domain and homoglyph variants first, then high-traffic product names. Present the ranked list
   with per-domain cost so the budget owner can approve in one decision.
9. Schedule recurring sweeps. Run the scan on a cadence (weekly for high-value brands, monthly
   otherwise) and diff against the previous run: `jq` the JSON outputs and alert only on newly
   registered permutations. New registrations are the signal; the steady-state list is background.
10. Report. Produce a per-sweep summary: new registrations found, classifications, actions taken
    (takedowns filed, defensive regs requested), and open watch items. Track takedown turnaround
    times as a program metric.

## Key tools & commands

- dnstwist: `dnstwist --registered --tld dictionaries/common_tlds.dict --format json --output
  out.json <domain>`; add `--mxcheck` for mail-server detection and `--ssdeep` for page-content
  similarity against the legitimate site. `--nameservers` lets you specify resolvers; `--threads`
  controls scan parallelism.
- `jq` for diffing runs: compare the current and previous JSON outputs and extract newly appearing
  domains.
- `whois <domain>` and RDAP lookups for registration detail on hits; `dig <domain> +short` variants
  for DNS detail.
- crt.sh for checking whether the lookalike domain has been issued a TLS certificate.
- A sandboxed browser or `curl -sL --max-time 20` for safe page capture — never interactive login.

## Expected outputs

- The versioned seed-domain list.
- Per-sweep JSON outputs with registered permutations, DNS records, MX findings, and ssdeep scores.
- A triage table: domain → classification → evidence → disposition.
- Infrastructure-pivot results: sibling domains found via shared NS/registrar/cert patterns.
- Evidence bundles for active threats (page capture, DNS, WHOIS, certificate data).
- Takedown/abuse tickets filed with references; threat-intel submissions.
- A ranked defensive-registration list with costs.
- A new-registration diff alert per sweep and a program metrics summary.

## Pitfalls

- Treating every registered permutation as hostile: most typosquats are parked, defensive, or
  unrelated businesses. Classify on evidence, not on registration alone.
- Running dnstwist without `--registered` and triaging thousands of unregistered permutations —
  noise that buries the real hits.
- Interacting with a live phishing page (submitting test credentials, clicking through) — this can
  tip off the attacker and, in some jurisdictions, create liability. Observe passively.
- Forgetting IDN homographs: dnstwist covers many permutations, but verify punycode/IDN variants of
  your brand separately.
- Letting sweeps go stale: a quarterly scan misses the median phishing domain lifespan. Match
  cadence to your threat level.
- Defensive registration without a renewal process: a lapsed defensive domain is worse than never
  owning it, because it can be re-registered by an attacker with built-in trust.
- Pivoting on shared infrastructure too aggressively: shared hosting and privacy-protected WHOIS
  create false sibling links. Require multiple independent pivots.

## References

- dnstwist documentation (GitHub: elceef/dnstwist) — permutation algorithms and flag reference.
- ssdeep documentation — fuzzy hashing for page-similarity comparison.
- MITRE ATT&CK T1583.001 (Acquire Infrastructure: Domains) and T1566 (Phishing) for the attacker-use
  context.
- ICANN RDAP documentation for registration-data lookups.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
