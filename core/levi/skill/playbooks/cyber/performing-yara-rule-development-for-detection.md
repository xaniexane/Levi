---
skill_id: cyber_performing_yara_rule_development_for_detection
name: YARA Rule Development for Detection
description: Author, test, and maintain YARA rules that detect malware families in EDR, sandboxes, and mail gateways.
risk: info
permissions: []
requires_confirmation: false
tags: [detection, yara, malware]
version: 1.0.0
---

## Purpose
YARA rules turn malware analysis into reusable detections. This playbook covers the full lifecycle from a defensive standpoint: selecting stable indicators from analyzed samples, writing precise rules, validating them against clean corpora to control false positives, and maintaining them in version control as families evolve.

## When to use
- A new malware family or variant is identified by the team or threat intel.
- Hunting across file shares, mail attachments, or EDR telemetry for known threats.
- Building detection content for sandboxes, gateways, or threat-hunting platforms.
- Replacing an overly broad or false-positive-prone existing rule.

## Prerequisites
- Analyzed malware samples in an isolated lab with hashes recorded.
- YARA installed (matching the version used by your detection platform).
- A clean corpus: representative benign files of similar types for false-positive testing.
- Version-controlled rule repository with metadata conventions.

## Procedure
1. Analyze the samples: extract strings, imports, section names, and behavioral notes; identify what is stable across variants.
2. Choose anchors resistant to trivial change: unique code sequences, distinctive strings, PE characteristics, not single common strings.
3. Write the rule with complete metadata (author, date, reference, malware family, confidence) and a descriptive identifier.
4. Structure conditions to require multiple anchors (e.g. 3 of 5 strings plus a file-size or header check) rather than one.
5. Test against the malware set to confirm detection, then against the clean corpus to measure false positives.
6. Iterate: tighten conditions until false positives are zero on the clean corpus while retaining variant coverage.
7. Commit to the repository with a changelog entry; deploy to detection platforms in monitor mode first.
8. Review rule performance quarterly; retire or split rules as families evolve or FPs appear.
9. Store the test corpora hashes alongside the rule so future maintainers can reproduce validation.
10. Test rules in the exact YARA version the detection platform runs; version differences break rules.
11. Add a rule retirement date or review trigger when the malware family is expected to evolve.

## Expected outputs
- Version-controlled YARA rule with metadata and test evidence.
- Validation report: detection rate on malware set, false-positive rate on clean corpus.
- Deployment notes and scheduled review date.
- Test corpus manifest with hashes for reproducible validation.
- Platform compatibility notes (YARA version, module availability).
- Rule lifecycle entry with review or retirement trigger.

## Pitfalls
- Single-string rules cause false positives and are trivially evaded; require combinations.
- Overfitting to one sample misses the family; underfitting flags benign software.
- Rules rot as malware evolves; unmaintained rules silently stop working.
- Performance matters; expensive regexes on every file scan can degrade endpoint performance.
- Wide-string modifiers double rule evaluation cost; use them deliberately.
- Private rules without metadata become unmaintainable; enforce metadata standards.
- Rules tested only on Windows samples may misfire on cross-platform deployments; test per platform.

## References
- YARA documentation (yara.readthedocs.io).
- MITRE ATT&CK for mapping rule coverage to techniques.
- NIST SP 800-94, Guide to Intrusion Detection and Prevention Systems.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
