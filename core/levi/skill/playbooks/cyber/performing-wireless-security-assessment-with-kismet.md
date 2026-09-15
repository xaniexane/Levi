---
skill_id: cyber_performing_wireless_security_assessment_with_kismet
name: Wireless Security Assessment with Kismet
description: Use Kismet for passive wireless surveys, device inventory, and rogue access point detection.
risk: low
permissions: []
requires_confirmation: false
tags: [wireless, kismet, assessment]
version: 1.0.0
---

## Purpose
Kismet is a passive wireless detector that catalogs access points, clients, and Bluetooth devices without transmitting. This playbook uses it for defensive purposes: building an authoritative wireless device inventory, spotting rogue or misconfigured access points, and documenting the RF environment around sensitive facilities. Passive collection keeps the assessment non-disruptive.

## When to use
- Baseline wireless inventory for a new or changed office.
- Rogue AP hunts and periodic compliance sweeps.
- Pre-assessment reconnaissance before an authorized wireless test.
- Investigating reports of suspicious wireless activity near a facility.

## Prerequisites
- Kismet installed with a monitor-mode capable adapter (and GPS receiver if mapping).
- Authorization for the survey area and a list of expected corporate SSIDs/BSSIDs.
- Storage for capture logs (pcapng) and Kismet log databases.
- Floor plans or facility maps for correlating signal observations to locations.

## Procedure
1. Configure kismet.conf with the capture source in monitor mode; disable any transmission features.
2. Walk or drive the survey area systematically, covering all floors and perimeters, logging to Kismet's database.
3. Let the capture run long enough to observe client associations, not just beacons (15-30 minutes per zone minimum).
4. Export the device list; classify each AP as authorized, neighbor, personal hotspot, or unknown.
5. Investigate unknowns: check BSSID OUI, signal strength trends, encryption, and whether they clone corporate SSIDs.
6. Review client devices for risky behavior: probing for corporate SSIDs off-site, ad-hoc networks, or tethering in secure areas.
7. Archive the Kismet logs with hashes; they serve as the baseline for the next sweep's comparison.
8. Produce a report: inventory deltas, rogue candidates with locations, and recommended actions.
9. Diff the new device list against the prior baseline automatically; investigate every new BSSID before the next sweep.
10. Feed confirmed rogue findings into the incident process and update the authorized AP inventory for accuracy.
11. Enable Kismet's alert plugins for common attacks (deauth floods, probe attacks) during the survey.
12. Record GPS coordinates with each observation to make rogue localization repeatable.
13. Compare client probe requests against the corporate SSID list to find devices leaking network names.

## Expected outputs
- Kismet capture database and device inventory export.
- Rogue/misconfigured AP findings with estimated locations.
- Baseline report for future comparison sweeps.
- Updated authorized AP inventory reflecting validated changes.
- GPS-tagged observation log for repeatable rogue localization.
- Client probe-leakage report for security awareness follow-up.
- Kismet alert-plugin tuning notes for ongoing deployments.

## Pitfalls
- Kismet sees only what its adapter hears; multi-floor sites need multiple passes or sensors.
- BSSID OUIs can be spoofed; treat OUI as a hint, not proof of device type.
- Bluetooth and 5 GHz require appropriate hardware; a 2.4 GHz-only adapter gives a partial picture.
- Retain captures securely; they contain client MACs and location-correlated data.
- Kismet alert plugins can flag common attacks in real time; review and tune them rather than relying on post-hoc analysis alone.
- GPS-correlated captures are sensitive location data; protect them like other surveillance records.
- Alert plugins need tuning per environment; defaults generate noise in dense RF areas.
- Battery-powered survey rigs die mid-sweep; carry spares and verify logging resumed.

## References
- Kismet official documentation (kismetwireless.net/docs).
- NIST SP 800-153, Guidelines for Securing Wireless Local Area Networks.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
