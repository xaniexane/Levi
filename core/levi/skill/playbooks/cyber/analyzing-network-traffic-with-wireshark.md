# Analyzing Network Traffic with Wireshark

## Purpose

Perform structured, repeatable packet-level analysis with Wireshark — from capture hygiene through display-filter triage to stream reconstruction and IOC extraction — for incident response and forensic review.

## When to use

- You have a pcap from an incident, a firewall, or a lab detonation and need to understand what happened on the wire.
- Validating IDS alerts or flow-record findings at the packet level.
- Teaching or documenting: Wireshark's stream views make findings explainable to non-network analysts.

## Prerequisites

- Written authorization for the capture and the systems involved.
- The pcap with verified hash; capture metadata (interface, snaplen, filter used, timezone).
- Wireshark installed (tshark for scripted work on servers); sufficient RAM for large captures — use capture filters or `editcap` splitting when needed.
- Baseline knowledge of the environment's normal protocols.

## Procedure

1. Inspect capture metadata first: Statistics → Capture File Properties (or `capinfos`). Note duration, packet count, snaplen — truncated packets (snaplen < 65535) limit payload analysis.
2. Get the protocol hierarchy: Statistics → Protocol Hierarchy. Unexpected protocols (e.g., BitTorrent on a server VLAN) set the investigation direction.
3. Review conversations: Statistics → Conversations, sorted by bytes. The top talkers usually contain the incident's data movement.
4. Triage with display filters in stages:
   `dns` → scan query names for DGA patterns and odd record types.
   `http` → review URIs, user agents, and response codes.
   `tls.handshake` → check SNI values against destination IPs.
5. Follow the suspicious stream: right-click → Follow → TCP/UDP Stream. Read the full session; save the raw stream for the case file.
6. Examine timing: Statistics → I/O Graph or the TCP stream's time column. Regular intervals indicate beaconing; bursts indicate bulk transfer.
7. Extract transferred files: File → Export Objects → HTTP/SMB. Hash every exported object immediately.
8. Check for anomalies: Analyze → Expert Information flags retransmissions and malformed packets; look specifically for overlapping IP fragments and abnormal TCP flag combinations.
9. Use display-filter expressions to isolate IOC candidates, e.g.:
   `ip.addr == 203.0.113.45`, `dns.qry.name contains "example"`, `http.request.method == POST`.
10. Correlate each finding with endpoint logs (Sysmon Event ID 3, firewall) by timestamp and 5-tuple before declaring it malicious.
11. Use name resolution cautiously: disable automatic DNS resolution during analysis (or use a local hosts file) so investigation targets are not leaked to the corporate resolver.
12. Compare against a known-good capture side-by-side to distinguish environment quirks (chatty printers, mDNS chatter) from incident artifacts.
13. Profile protocol activity over time: Statistics → I/O Graph with per-protocol display filters shows when each channel was active.
14. Use Analyze → Decode As to force the right dissector on non-standard ports — misdissected traffic hides in plain sight.
15. Graph TCP behavior: Statistics → TCP Stream Graphs → Round Trip Time exposes latency anomalies indicating tunneling or proxying.
16. Apply temporary coloring rules for your IOCs — malicious flows become visually obvious when presenting to stakeholders.
17. Add custom columns (e.g., `http.host`, `dns.qry.name`) to the packet list for faster triage.
18. Export key dissections as text (`tshark -r in.pcap -Y <filter> -T text -V`) for inclusion in the written report.
19. Save the display-filter set and coloring rules with the case file — the next analyst replays your exact views.
20. Document the exact display filters used alongside each conclusion so another analyst can reproduce the view.
21. Export evidence: filtered pcaps via File → Export Specified Packets, with hashes recorded.

## Key tools & commands

- Wireshark GUI: Protocol Hierarchy, Conversations, Follow Stream, Export Objects, I/O Graph, Expert Information.
- `tshark -r in.pcap -Y "<filter>" -w out.pcap` — scripted filtering.
- `tshark -r in.pcap -q -z io,stat,60` — per-minute traffic profile.
- `capinfos in.pcap` — capture metadata.
- `editcap -c 100000 in.pcap split.pcap` — split oversized captures.
- `dumpcap -i <iface> -b filesize:100000 -w ring.pcap` — ring-buffer capture for long incidents.
- `mergecap -w merged.pcap a.pcap b.pcap` — combine captures chronologically.
- `tshark -r in.pcap -q -z expert` — expert-info summary from the CLI.
- `reordercap in.pcap out.pcap` — fix out-of-order captures before timing analysis.

## Expected outputs

- Triage notes: protocol hierarchy, top conversations, anomalies.
- Reconstructed streams of interest with saved raw bytes.
- Exported files with SHA-256 hashes.
- IOC list with the display filter that surfaced each one.
- Baseline-vs-incident comparison notes (environment quirks vs. real artifacts).
- Name-resolution handling note (how resolver leakage was avoided).
- Reproducible filter log in the case file.

## Pitfalls

- Analyzing a truncated capture (small snaplen) and concluding "no payload" — check snaplen first.
- Confusing checksum errors caused by capture offload (TSO/LRO) with attacks.
- Following one stream and missing parallel C2 channels — always review the full conversation table.
- Timezone confusion between capture host and analyst workstation.
- Exporting objects to an uncontained directory when the pcap came from malware.
- Automatic name resolution leaking investigation targets to the corporate resolver.
- Display-filter vs. capture-filter syntax confusion producing empty results.
- Opening multi-gigabyte pcaps in the GUI before triaging with tshark — the UI will hang.
- Trusting "Decode As" guesses on ambiguous ports — verify against the endpoint's actual service.
- Forgetting to clear display filters before exporting — a filtered view silently drops packets.
- Relying on the default column layout — add custom columns (e.g., http.host) for triage speed.
- Ignoring Expert Info severity levels — errors and warnings mean different things.
- Analyzing decrypted TLS without documenting the key source — note how decryption was achieved.
- Sorting by the wrong column and missing the actual top talker.
- Forgetting that "Follow Stream" shows reassembled data, not raw packets.
- Applying a display filter and forgetting it's active — "where did my packets go."
- Not saving the capture filter used — irreproducible captures.
- Overlooking Statistics → Endpoints for quick IP/MAC inventories.
- Trusting protocol dissectors on tunneled traffic — verify with "Decode As."
- Capturing on the wrong interface — verify with `dumpcap -D` before a long session.
- Display filters versus capture filters — a wrong capture filter loses data permanently.
- TCP reassembly hiding packet-level anomalies — toggle it when hunting evasion.
- Huge captures freezing the GUI — use `tshark`/`dumpcap` with ring buffers for long runs.
- Name resolution rewriting addresses — disable it when documenting indicators.
- Forgetting snaplen truncation — truncated packets break signature matching silently.

See also: analyzing-network-traffic-for-incidents.md, analyzing-network-traffic-of-malware.md

## References

- Wireshark User's Guide: https://www.wireshark.org/docs/wsug_html_chunked/
- Wireshark display filter reference: https://www.wireshark.org/docs/dfref/
- Wireshark Wiki — sample captures for training: https://wiki.wireshark.org/SampleCaptures
- MITRE ATT&CK T1071 (Application Layer Protocol), T1041 (Exfiltration Over C2 Channel)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
