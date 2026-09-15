---
skill_id: cyber_detecting_deepfake_audio_in_vishing_attacks
name: Detecting Deepfake Audio in Vishing Attacks
description: Detect AI-cloned voices in vishing calls with verification procedures, audio forensics, and process controls.
risk: info
permissions: []
requires_confirmation: false
tags: [fraud, deepfake, social-engineering]
version: 1.0.0
---
## Purpose

Defend against vishing calls using AI-cloned voices — "the CEO" urgently requesting a wire transfer, "IT support" asking for credentials. Combine call-verification procedures (the real defense), audio-forensic techniques, and detection tooling so a convincing fake voice still fails.

## When to use

- Protecting finance and executive teams from voice-fraud.
- Building vishing response procedures for the SOC and help desk.
- Investigating a suspected deepfake-voice incident.
- Training employees on AI-enabled social engineering.

## Prerequisites

- Defined verification procedures for sensitive requests (call-back policy, out-of-band confirmation).
- Call recording capability (where legally permitted) for forensic analysis.
- Awareness training materials covering AI voice cloning.
- Incident response contacts: telecom provider, bank fraud department, law enforcement liaison.

## Procedure

1. **Establish the call-back rule as policy.** No sensitive action (wire transfer, credential reset, data release) is ever authorized on an inbound call alone — the recipient hangs up and calls back on a known number. This single procedure defeats deepfakes regardless of their quality. Enforce it culturally: reward employees who challenge suspicious calls, never punish the delay.
2. **Train on deepfake tells (without over-relying on them).** Teach staff that cloned voices may have: unnatural pauses, flat emotional affect, mispronounced names or jargon, and odd responses to unexpected questions. But stress that modern clones defeat casual listening — the tells are a bonus, not the defense. The procedure in step 1 is the defense.
3. **Use challenge questions on suspicious calls.** If a caller claims to be an executive making an unusual request: ask something only the real person would know, or better, propose a pre-arranged verification (a code word for sensitive requests, rotated periodically). A deepfake can't answer what it was never trained on — but don't rely on trivia alone; combine with call-back.
4. **Deploy audio-forensic analysis for investigations.** For recorded suspicious calls, analyze: spectral artifacts of neural vocoders, unnatural prosody patterns, and inconsistencies in background noise. Use deepfake-audio detection tools as investigative aids — they provide supporting evidence, not courtroom-proof verdicts. Preserve the original recording with chain of custody.
5. **Monitor for the attack's infrastructure.** Vishing campaigns leave traces: spoofed caller IDs (work with the telecom provider on STIR/SHAKEN verification), the phone numbers used (check against fraud-reporting databases), and any follow-up phishing (the call often pairs with a malicious email). Correlate vishing reports across the organization — campaigns target multiple employees.
6. **Protect the voice data itself.** Reduce cloning material: limit public recordings of executives (earnings calls, videos) where practical, watermark internal voice content, and brief executives that their public voice is clonable. You can't eliminate the training data, but you can avoid handing it over casually.
7. **Respond to a successful vishing incident.** If a transfer or credential disclosure occurred: stop/recall the transfer immediately via the bank's fraud team, reset compromised credentials with session revocation, preserve call recordings and logs, brief the impersonated executive, and file reports (FBI IC3, local law enforcement). Then run a lessons-learned: which procedure failed, and why?

## Expected outputs

- A mandatory call-back verification policy for sensitive requests, culturally enforced.
- Staff training on deepfake vishing with challenge-question procedures.
- Audio-forensic investigation capability and a rapid wire-recall response process.

## Pitfalls

- Relying on "I'll recognize their voice" — the whole point of cloning is that you can't.
- Punishing employees who delay for verification — you'll train them to comply with the next attack.
- No call-back numbers maintained — the procedure fails if nobody knows the real number.
- Treating detection tools as the defense — they're investigative aids; the process is the control.
- Ignoring the follow-up — vishing often pairs with email compromise; scope both.

## References

- FBI / CISA advisories on AI-enhanced social engineering and vishing
- NIST SP 800-63 (identity verification) applied to voice channels
- Published research on deepfake-audio detection techniques
- STIR/SHAKEN documentation for caller-ID authentication
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
