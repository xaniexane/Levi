# Analyzing USB Device Connection History

## Purpose

Reconstruct which USB storage devices were connected to a Windows machine, when, by which user
context, and what the device identified itself as. USB history answers the classic exfiltration and
malware-introduction questions: was an unknown drive plugged in around the incident window, and did
data leave on it?

USB analysis sits at the intersection of device forensics and user attribution. The registry tells
you the device was presented to the OS; the rest of the playbook tells you who was logged on and
what the timeline implies — but only file-access artifacts can show data actually moved.

## When to use

- Data-exfiltration investigations where removable media is a suspected vector.
- Malware incidents where the initial vector may have been a USB device (autorun-era or HID-spoofing
  devices).
- Policy-violation reviews: detecting unauthorized storage devices on controlled endpoints.
- Asset-inventory audits of which removable devices have touched sensitive systems.
- Insider-threat cases where large file collections were accessed shortly before resignation or
  termination.

## Prerequisites

- Written authorization to examine the endpoint(s), stating the legal basis and scope (which
  machines, which time window). USB history can reveal personal devices — handle findings under your
  organization's privacy rules.
- A forensic image or a targeted triage collection (registry hives SYSTEM and SOFTWARE,
  `setupapi.dev.log`, Event Logs) acquired with hashes and chain-of-custody documentation. Prefer
  offline analysis of the image over live registry reads on the suspect host.
- Timestamps in the correct timezone: USB artifact timestamps are stored in UTC; convert explicitly
  when comparing to local-time incident timelines.
- The incident window defined up front so you can bound the analysis.
- An authorized-device inventory (if one exists) to distinguish known-good drives from unknowns.

## Procedure

1. Acquire the artifacts. From the image, collect: `C:\Windows\System32\config\SYSTEM` and
   `SOFTWARE` hives, `C:\Windows\INF\setupapi.dev.log`, the
   `Microsoft-Windows-DriverFrameworks-UserMode/Operational` event log, and each user's `NTUSER.DAT`
   (for MountPoints2). Hash everything at collection.
2. Enumerate USBSTOR devices. In the SYSTEM hive, walk `ControlSet001\Enum\USBSTOR`: each subkey is
   a device class (e.g., `Disk&Ven_SanDisk&Prod_Cruzer...`) and each device subkey's name embeds the
   serial number. Record device description, serial, and the `FriendlyName` value. The serial
   distinguishes individual physical drives of the same model.
3. Map devices to connection instances. Under each USBSTOR device key, the `Properties` and parent
   `USB\VID_xxxx&PID_xxxx\<instance>` keys tie the storage device to a specific USB port and
   controller instance. Cross-reference `Enum\USB` for the vendor/product IDs and the first-install
   timestamp.
4. Extract first/last connection times. The `setupapi.dev.log` records device installation events
   with timestamps — search for the device's hardware ID to find when Windows first installed it.
   For ongoing connections, parse the DriverFrameworks-UserMode Operational log: Event ID 2003
   (driver load / device arrival) and 2010/2004 patterns mark connections and removals with
   timestamps.
5. Determine user attribution. In each user's `NTUSER.DAT`, check
   `Software\Microsoft\Windows\CurrentVersion\Explorer\MountPoints2`: subkeys named by device GUID
   or drive-letter associations show which user accounts saw the device. Correlate the device's
   connection timestamps with logon sessions (Security log 4624) to attribute the connection to a
   user.
6. Recover volume details. From the SYSTEM hive's `MountedDevices`, map `\DosDevices\X:` values to
   volume GUIDs and device signatures to recover which drive letter the USB device received. Check
   for per-volume artifacts if the image includes the device's own file system (it usually does not
   — the host side is what you have).
7. Correlate with file-access artifacts. For in-window devices, check LNK files, jump lists,
   shellbags, and RecentDocs for files opened from the device's drive letter during the connection
   window. This is the bridge from "device connected" to "data accessed."
8. Build the timeline. Merge: device installations (setupapi), arrivals/removals (DriverFrameworks
   events), user mount evidence (MountPoints2), logon sessions, and file-access artifacts into one
   chronological view bounded by the incident window. Flag devices whose first appearance falls
   inside the window and devices never seen in the baseline inventory.
9. Check policy and DLP telemetry. If the organization runs device-control or DLP agents, pull their
   logs for the same window: blocked-device events, file-copy-to-removable alerts, and volume-size
   anomalies. Agent telemetry can show what the registry cannot — actual bytes written.
10. Assess and report. For each in-window device: was it a known/authorized device (compare serials
    against the asset inventory), what user context was active, how long was it connected, and what
    file-access evidence exists. Write the findings with the attribution confidence stated —
    registry evidence shows the device was presented to the OS, not what files were copied.

## Key tools & commands

- Registry examination: Eric Zimmerman's Registry Explorer (with its USB device bookmarks) or
  `regripper` plugins (`usbstor`, `mountdev2`) against exported hives.
- `strings` / text search on `setupapi.dev.log`: `grep -i -A 5 "usbstor" setupapi.dev.log` to find
  installation entries with timestamps.
- Event log parsing: `evtx_dump` or PowerShell `Get-WinEvent -LogName
  'Microsoft-Windows-DriverFrameworks-UserMode/Operational' | Where-Object {$_.Id -eq 2003}` for
  arrival events.
- USB timeline tools or a manual spreadsheet merge for the final timeline.
- LNK/jump-list/shellbag parsers (LECmd, JLECmd, ShellBagsExplorer) for the file-access correlation
  step.
- `sha256sum` on every collected hive and log at acquisition.

## Expected outputs

- A device inventory: USBSTOR descriptions, serials, VID/PID, per device.
- Installation timestamps from setupapi.dev.log per device.
- Arrival/removal event timelines from the DriverFrameworks log.
- Per-user MountPoints2 findings with logon-session correlation.
- Drive-letter/volume mappings from MountedDevices.
- File-access correlation: LNK/shellbag/RecentDocs hits tied to the device's drive letter.
- DLP/device-control telemetry for the window (if available).
- A merged USB timeline bounded by the incident window, flagging unknown in-window devices.
- An assessment: authorized vs. unknown devices, user attribution, data-movement evidence,
  confidence levels.

## Pitfalls

- Serial numbers are not always unique: some cheap drives report identical or blank serials — treat
  same-model devices with identical serials as indistinguishable.
- Timestamps live in different places with different semantics (first install vs. last arrival);
  mixing them up shifts your timeline by months.
- MountPoints2 shows a user saw the device, not that they used it — do not overstate attribution.
- A device connected while the machine was imaged or by the forensic process itself will appear in
  the logs; exclude your own handling by time-bounding.
- Registry evidence proves device presentation, not data transfer — pair with file-access artifacts
  (LNK files, jump lists, shellbags) before claiming exfiltration.
- Write-blocked forensic access still creates a USBSTOR entry on the analysis workstation, not the
  suspect image — keep your handling artifacts out of the suspect timeline.
- DLP "bytes written" figures measure what the agent saw; encrypted or renamed-then-copied files can
  be mischaracterized. Treat agent numbers as approximate.

## References

- Microsoft documentation on `setupapi.dev.log` and device installation logging.
- Microsoft documentation on the DriverFrameworks-UserMode operational channel (Events
  2003/2004/2010).
- NIST SP 800-86 — evidence handling for host forensics.
- Eric Zimmerman's tool documentation (Registry Explorer) for USB artifact locations.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
