---
skill_id: cyber_detecting_azure_lateral_movement
name: Detecting Azure Lateral Movement
description: Detect lateral movement across Azure with sign-in, activity-log, and network-flow correlation.
risk: info
permissions: []
requires_confirmation: false
tags: [azure, detection, lateral-movement]
version: 1.0.0
---
## Purpose

Catch attackers moving through your Azure estate — between VMs, subscriptions, and into on-prem via hybrid paths — by correlating identity, activity, and network signals. Lateral movement in Azure looks like legitimate administration; the difference is in the patterns.

## When to use

- Hunting for intruders who have a foothold in Azure (compromised VM, stolen credential).
- Building detections for hybrid environments where movement crosses cloud/on-prem boundaries.
- Investigating an alert where the initial compromise vector is known but the blast radius isn't.
- Validating network segmentation between Azure subnets and subscriptions.

## Prerequisites

- Centralized logs: Entra ID sign-in/audit logs, Azure Activity Log, NSG flow logs, Defender for Cloud alerts, VM-level EDR.
- Asset inventory: VMs, VNets, peerings, VPN/ExpressRoute connections, and hybrid identity sync topology.
- Baseline of normal administrative patterns: jump hosts, admin workstations, automation service principals.
- Alerting path with runbooks for containment (NSG isolation, account disable).

## Procedure

1. **Map the legitimate movement paths.** Document how admins actually move: which jump hosts, which service principals run automation, which VNets peer, and where ExpressRoute/VPN lands. Every detection is a deviation from this map — without it, you're guessing.
2. **Detect anomalous remote access.** Alert on: RDP/SSH to VMs from unexpected sources (NSG flow logs + host logs), WinRM/PowerShell remoting from non-admin hosts, Azure Bastion sessions from unusual users, and `Run Command` invocations (attackers love Run Command — it's agent-based execution that bypasses network controls). Baseline the automation that legitimately uses these.
3. **Detect identity-based movement.** Alert on: sign-ins to Azure portal/CLI from a compromised-associated identity followed by new resource access, service principals authenticating from new IPs, and managed-identity token use from unexpected hosts. In hybrid environments, correlate Entra sign-ins with on-prem AD logons — movement often crosses the boundary.
4. **Detect subscription and tenant traversal.** Alert on: new role assignments (especially Owner/Contributor) by non-IaC identities, access to subscriptions the identity never touched, and cross-tenant activity. Attackers escalate by collecting subscriptions; each new subscription access is a scope-expansion event.
5. **Monitor the hybrid bridge.** Alert on: new devices registered in hybrid join, AD Connect sync anomalies, Pass-Through Authentication agent changes, and lateral movement between Azure VMs and on-prem via ExpressRoute/VPN. The hybrid identity path is the most common route from cloud foothold to domain dominance — watch it hardest.
6. **Correlate host and network signals.** Join EDR process data (PsExec, WMI, PowerShell remoting, credential dumping) with NSG flow anomalies (new east-west flows, RDP bursts). A single EDR alert is a data point; EDR + flow + identity anomaly on the same host within an hour is lateral movement.
7. **Contain by breaking the path.** On confirmation: isolate the VM via NSG (not just EDR — defense in depth), disable the compromised identities and revoke sessions, rotate credentials the attacker touched (especially local admin and service principal secrets), and check every host the attacker touched for persistence before reconnecting anything.

## Expected outputs

- A documented legitimate-movement map with detections for anomalous remote access, identity movement, and subscription traversal.
- Hybrid-bridge monitoring with correlated host/network/identity signals.
- Path-breaking containment runbooks (NSG isolation, identity revocation, credential rotation).

## Pitfalls

- No NSG flow logs — you're blind to the network half of lateral movement.
- Alerting on Run Command without baselining automation — legitimate DevOps use drowns the signal.
- Treating cloud and on-prem as separate investigations — the attacker doesn't.
- Missing managed-identity abuse — it looks like the application, not the attacker.
- Containing the host but not the identity — the attacker just moves to the next VM.

## References

- Microsoft Learn — NSG flow logs, Azure Activity Log, Defender for Cloud
- MITRE ATT&CK T1021 (Remote Services) and T1550 (Use Alternate Authentication Material)
- Microsoft threat-hunting guidance for Azure lateral movement
- NIST SP 800-207 (Zero Trust) — micro-segmentation principles
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
