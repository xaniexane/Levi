---
skill_id: cyber_implementing_ics_firewall_with_tofino
name: Implementing an ICS Firewall with Tofino
description: Deploy an Intel Tofino programmable switch as a P4-based industrial firewall that allowlists OT protocols and blocks unauthorized traffic at the zone boundary.
risk: low
permissions: []
requires_confirmation: false
tags: [network, ics, ot, firewall]
version: 1.0.0
---
## Purpose

Place a deterministic, line-rate industrial firewall at OT zone boundaries using an Intel Tofino programmable switch. The P4 data plane parses industrial protocols (Modbus/TCP, DNP3, EtherNet/IP, OPC UA) and enforces an explicit allowlist of source/destination/function-code tuples, dropping everything else before it reaches controllers and safety systems.

## When to use

- Segmenting Purdue levels 2/3 (supervisory) from level 1 (control) where a traditional stateful firewall cannot keep up with scan-cycle traffic.
- Enforcing read-only access from a historian or data diode adjacency into the control network.
- Replacing aging serial/transparent firewalls with a programmable device that can be updated without forklift hardware changes.
- Building a DMZ conduit between IT and OT that must inspect industrial protocol semantics, not just TCP ports.
- Lab-validating OT protocol allowlists before pushing them to production enforcement points.

## Prerequisites

- An asset and data-flow inventory for the zone: every controller, HMI, historian, and the exact protocols and function codes each legitimately uses.
- Tofino-based switch hardware (or the P4 behavioral model `bmv2` for lab work) with the P4 compiler toolchain (`p4c`) available.
- A maintenance window and a tested rollback plan; misconfigured OT firewalls halt processes.
- Network captures (pcaps) of normal traffic per conduit, taken over at least one full production cycle.
- Change-control approval from operations; OT changes require process-engineer sign-off, not just IT approval.

## Procedure

1. **Baseline the protocol inventory.** Capture traffic on each conduit for a full cycle and enumerate the protocols in use. For each flow record the 5-tuple plus OT-specific fields — e.g., Modbus function codes (1, 2, 3, 4 = read; 5, 6, 15, 16 = write), DNP3 function codes, EtherNet/IP CIP services, OPC UA message types.
2. **Define the allowlist policy as code.** Express every permitted flow explicitly: source zone, destination zone, protocol, port, and allowed function codes. Default-deny everything else. Keep the policy in version control and review it with process engineers — a denied write to a PLC during a batch is a safety event, not a security win.
3. **Write the P4 program.** Implement parsers for Ethernet/IPv4/TCP plus the OT application headers you need (Modbus MBAP header and function code byte is the classic starting point). Build match-action tables keyed on (src/dst IP, TCP port, function code) with actions `allow`, `drop`, and `mirror_to_ids`. Keep tables small enough for the pipeline stages you have.
4. **Compile and lab-test.** Compile with `p4c` targeting the Tofino architecture, load the program in the lab, and replay the production pcaps through it. Verify that every legitimate flow passes and that crafted violations (e.g., Modbus function code 16 write from the historian network) are dropped and mirrored.
5. **Deploy in monitor mode first.** Insert the switch with the policy in alert/mirror-only mode on the production conduit. Compare alerts against the baseline for one full cycle and tune the allowlist; OT networks always contain undocumented flows.
6. **Cut over to enforcement.** Switch the default action to drop during the maintenance window with operations staff present. Verify HMIs, historians, and controllers behave normally, then monitor drop counters closely for the first 48 hours.
7. **Wire drops to the SIEM.** Export drop/mirror metadata (syslog or streaming telemetry) to the SOC with context: zone, protocol, function code, endpoints. A dropped Modbus write from IT is an incident, not noise.
8. **Manage the lifecycle.** Treat P4 programs like firewall firmware: version them, sign the artifacts, test changes in the lab, and re-baseline after every process change. Review the allowlist quarterly against the asset inventory.

## Expected outputs

- A version-controlled P4 program implementing the conduit allowlist, with compiled artifacts and checksums.
- A documented allowlist matrix (zones × protocols × function codes × direction) signed off by operations.
- Lab replay test results showing pass/drop behavior on production pcaps.
- SIEM ingestion of firewall drop/mirror events with an OT-specific detection use case.
- A change-management record and rollback procedure for the enforcement point.

## Pitfalls

- **Denying legitimate writes during production.** OT protocols like Modbus have no authentication; the firewall cannot distinguish an operator's legitimate write from an attacker's. Overly broad write-blocking breaks the process. Scope write rules to known-good source/destination pairs.
- **Skipping the monitor phase.** Undocumented engineering-laptop connections and vendor remote-access sessions are the norm in OT; enforcing on day one causes outages.
- **Forgetting failover behavior.** Decide explicitly what the switch does on program crash or power loss — fail-closed protects the process but stops it; fail-open keeps production running but removes protection. Document the choice with operations.
- **Table exhaustion.** Tofino pipeline stages are finite; a policy with tens of thousands of entries may not fit. Aggregate aggressively (subnets, port ranges) and keep per-flow state out of the data plane.
- **Ignoring encrypted OT traffic.** OPC UA with security enabled is opaque to header parsing; plan enforcement at the endpoint or via TLS-terminating proxies for those flows instead of pretending the P4 parser sees inside.

## References

- NIST SP 800-82 Rev. 3, "Guide to Operational Technology (OT) Security" — https://csrc.nist.gov/publications/detail/sp/800-82/rev-3/final
- IEC 62443-3-3, "System security requirements and security levels" (defines zone/conduit and SR requirements; standard available via IEC/ISA)
- MITRE ATT&CK for ICS — https://attack.mitre.org/techniques/ics/
- P4 language documentation and p4c compiler — https://p4.org/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
