---
skill_id: cyber_performing_steganography_detection
name: Steganography Detection
description: Detect hidden data in images, audio, and documents during forensic investigations and data-loss monitoring.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, steganography, detection]
version: 1.0.0
---

## Purpose
- Find covert channels where attackers hide data in innocuous-looking files.
- Support investigations into data exfiltration and covert communications.
- Build detection capability for the file types most abused for steganography.

## When to use
- When investigating suspected data exfiltration with no obvious transfer method.
- When analyzing media from a suspect device for hidden communications.
- When threat intelligence reports steganography use by relevant actors.
- When tuning DLP to catch exfiltration via image and document uploads.

## Prerequisites
- Forensic copies of the suspect media files with hashes recorded.
- Steganalysis tooling: zsteg, steghide, binwalk, and statistical analysis utilities.
- Baseline knowledge of the file formats under examination.
- An isolated lab for extracting and examining any discovered payloads.

## Procedure
1. Inventory the suspect files: types, sizes, sources, and why they are suspicious.
2. Check file metadata and structure for anomalies: wrong extensions, appended data, and oversized files.
3. Run format-specific tools: zsteg for PNG and BMP, stegseek or steghide for JPEG, and audio tools for WAV and MP3.
4. Perform statistical analysis: chi-square, RS analysis, and sample-pair methods for LSB embedding.
5. Examine images visually and with filters for artifacts of hidden data.
6. Attempt extraction with common passwords and empty passphrases where tools support it.
7. Analyze any extracted payloads in the isolated lab: identify file types and intent.
8. Correlate with the investigation: who created the files, when, and how they moved.
9. Document methods and results, including negative results, since absence of evidence matters too.
10. For DLP tuning, translate findings into detection rules for the observed techniques.
11. Brief stakeholders on the covert channel found and how to monitor for it.
12. Archive the media and analysis for the case file.

## Expected outputs
- A steganalysis report with findings or documented negative results.
- Extracted payloads analyzed in isolation.
- DLP or monitoring rules for the observed techniques.
- A quick-reference guide to which tools cover which file types.
- Chain-of-custody documentation for media examined.

## Pitfalls
- Running extraction tools on original evidence; work on copies to preserve integrity.
- Declaring files clean after one tool finds nothing; different tools cover different techniques.
- Ignoring the context; steganography findings need the who, when, and how to be meaningful.
- Modifying file timestamps during analysis; work on copies and record hashes.

## References
- NIST SP 800-101 guidance where mobile media is involved
- NIST SP 800-86 Guide to Integrating Forensic Techniques into Incident Response
- Academic literature on LSB steganalysis methods
- Tool documentation for zsteg, steghide, and binwalk
- SANS FOR508 advanced forensic analysis materials
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
