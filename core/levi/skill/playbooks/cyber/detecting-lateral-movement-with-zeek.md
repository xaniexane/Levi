---
skill_id: cyber_detecting_lateral_movement_with_zeek
name: Detecting Lateral Movement with Zeek
description: Use Zeek network security monitoring to detect lateral movement from connection and protocol logs.
risk: low
permissions: []
requires_confirmation: false
tags: [zeek, network, lateral-movement]
version: 1.0.0
---
## Purpose

When endpoints are unmanaged, uninstrumented, or compromised below the EDR, the network is the remaining witness. This playbook shows defenders how to use Zeek (formerly Bro) connection, protocol, and notice logs to detect lateral movement: internal SMB/RDP/SSH fan-out, unusual internal services, and data staging — from span-port or tap deployments.

## When to use

- EDR coverage is incomplete (OT, lab networks, BYOD segments) and you need network-based movement detection.
- You have Zeek deployed and want lateral-movement use cases beyond the default notices.
- Investigating a suspected compromise and need historical internal-connection data.
- Validating EDR lateral-movement alerts against independent network evidence.

## Prerequisites

- Zeek sensors with visibility into east-west traffic — span ports, taps, or virtual taps on inter-VLAN/server-segment links (not just the internet edge).
- Zeek logs (conn, smb, rdp, ssh,dce_rpc, dns, notice) shipped to a SIEM or queryable store with stable UID correlation.
- Asset context: which subnets are servers, workstations, OT, DMZ; and known-good internal services per segment.
- Time synchronization (NTP) across sensors — Zeek timestamps must align with endpoint logs for correlation.

## Procedure

1. Confirm east-west visibility. Check conn.log for internal-to-internal connections across your server and workstation subnets. If Zeek only sees north-south (internet) traffic, lateral-movement detection is impossible — fix sensor placement before writing a single query.
2. Detect SMB fan-out. Query for internal hosts with high distinct destination counts on TCP 445 in short windows, excluding backup servers, scanners, and domain controllers replicating. SMB fan-out from a workstation is one of the highest-fidelity movement indicators in Windows networks.
3. Detect RDP/SSH/WinRM anomalies. Alert on: RDP (TCP 3389) to servers from non-admin workstations; SSH between hosts that have no administrative relationship; and WinRM (5985/5986) from unexpected sources. Use Zeek's rdp.log and ssh.log auth-success fields to weight successful sessions.
4. Watch DCE-RPC and named pipes. Lateral tools abuse DCE-RPC endpoints (atsvc, scmr) and SMB named pipes for execution. Unusual DCE-RPC endpoint usage from workstations, or named-pipe names associated with tooling, merit investigation — baseline normal pipe names per server role first.
5. Correlate with DNS and connection timing. Movement often follows internal reconnaissance: DNS queries for many hostnames, then connections. Chain conn.log UIDs with dns.log to show the recon-then-connect sequence, and check for long-duration, low-byte sessions (interactive shells) versus bulk transfers (staging).
6. Feed findings back into scoping. Every confirmed movement edge (src → dst) becomes a new pivot: query Zeek for the destination's own outbound connections in the window. Iterate until the movement graph stops growing, then hand the full graph to incident response.

## Expected outputs

- Zeek-based lateral-movement queries: SMB fan-out, RDP/SSH/WinRM anomaly, DCE-RPC/pipe anomaly, recon-then-connect chaining.
- Sensor placement map proving east-west coverage, with gaps documented and remediated.
- Movement-graph scoping procedure using UID-correlated Zeek logs.
- Baseline of normal internal service usage per segment for tuning.

## Pitfalls

- Zeek on only the internet edge sees none of this — east-west sensor placement is the whole game.
- SMB fan-out alerts without scanner/backup exclusions are unusable; maintain the exclusion list.
- Encrypted RDP/SSH hides commands but Zeek still logs endpoints, duration, and bytes — use the metadata.
- DHCP churn breaks IP-based attribution over long windows — join with DHCP logs or EDR hostnames.
- High-volume conn.log needs aggregation before alerting; alert on statistics, not raw connections.

## References

- Zeek documentation (docs.zeek.org) — conn, smb, rdp, ssh, dce_rpc logs; MITRE ATT&CK TA0008 (Lateral Movement) — https://attack.mitre.org/tactics/TA0008/; NIST SP 800-94 (intrusion detection and prevention systems)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
