---
skill_id: compressed.z1-governance
name: Z-1 Governance Engine (advisory)
description: The top compressed layer: oversight, enforcement, and compliance — the gate that says no before the world is touched.
risk: info
permissions: []
requires_confirmation: false
tags: [engines, compressed, z1, governance, policy]
version: 1.0.0
---
# Z-1 Governance Engine (advisory)

## Purpose

Z-1 is the top compression layer of the recovered engine canon (Map A,
Volume 2 "Engine Architecture"): the **Governance Engine** holds
oversight, enforcement, and compliance. It is the only engine whose
verdict can stop a run, and it is designed to default to *no*.

## The LEVI-native reading

LEVI's Governance reading is: *deny-closed at every gate.* A proposed
action carries its risk tag, its permissions, and its provenance; the
gate checks all three against policy and answers allow, deny, or
needs-human. Ambiguity is never resolved in favor of proceeding —
anything the gate cannot verify is refused with the reason named, so the
requester can fix it honestly. Governance never explains *how* to evade
itself; it explains what would make the answer yes.

## Protocol

1. Take the proposed action: what it does, what it touches, its risk tag,
   its permission claims, who asked for it.
2. Check each against the standing policy: permissions present,
   risk within ceiling, provenance clean, standing laws honored
   (local-first, no paid tolls, defensive-only for cyber content).
3. Verdict allow / deny / needs-human, with the exact failed check named
   on deny — never a bare "no".
4. Log the verdict; a denied action may be re-proposed once the named
   check is satisfied.

Advisory only: this skill advises the pattern; it does not execute, send,
or spend.
