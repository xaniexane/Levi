# Collective Intelligence — Spec-Only Design

Status: **SPEC ONLY. No cloud upload or distribution mechanism is built or
ordered.** This document describes what the subsystem would do if Chauncey
orders it built. Until then it is a design on paper, nothing more.

## 1. Purpose

LEVI is local-first: every user runs their own instance, on their own
device, with their own memory, their own growth loop, their own brain
training on Echoverse-generated simulation corpora.

The collective intelligence component answers one question: *when one
user's LEVI learns something genuinely true and useful, how do all other
users' LEVIs get it — without leaking anyone's private data and without
poisoning the shared source of truth?*

Plain version: one user learns something locally → the learning, distilled
and scrubbed, is offered up → Chauncey's cloud holds the single source of
truth → the learning is refined (with help from Rex or Grok as refinement
assist) → every other user receives the refined edition on their next
cloud update.

This is federated learning with a refinement gate. He is the provider, not
the renter: the cloud is his, the source of truth is his, the gate criteria
are his.

## 2. Architecture flow

The loop, end to end:

1. **Local learning.** A user's LEVI produces a candidate learning the
   ordinary way: growth-loop reflection, a verified fact, a procedural
   improvement, a correction — the same consolidation that already writes
   growth-tagged memory entries and the journal. Nothing new happens on
   the device side except *marking* an entry as a candidate for submission.
2. **Submission.** The user reviews the candidate and attests it
   (stage 1 of the gate below). Attestation is explicit and per-edition —
   one tap per item, never a blanket "share everything."
3. **Cloud intake.** The attested edition lands in an intake queue on
   Chauncey's cloud. It is NOT part of the shared knowledge yet. It sits
   in quarantine: visible to the gate process, invisible to all users.
4. **Refinement.** Rex/LEVI refines the edition: cleans it, normalizes
   phrasing, distills it to its essential content, strips anything
   identifying or private. Refinement changes form, never the claim —
   if the claim needs changing, that is a correction, and corrections
   restart at stage 2.
5. **Verification.** Every edition is verified and cross-checked
   individually (stage 3 of the gate). Only editions that pass all
   checks commit.
6. **Commit to source of truth.** The verified edition is signed,
   versioned, and committed as the cloud's authoritative edition. The
   cloud is the single source of truth; local instances hold copies.
7. **Distribution.** Other users pull the new edition on their next
   cloud update. Pull-on-update: the client asks, the cloud answers.
   No pushes, no background sync surprises.

## 3. The submission gate — binding law

LAW, from Chauncey, 2026-09-22: **every single user-submitted knowledge
edition must be verified and cross-checked before committing to cloud
and others. No exceptions. No batch approvals. No sampling.**

The gate runs in this order, and the order is load-bearing:

### Stage 1 — The submitting user verifies first

- The user attests the edition is **correct** and is **theirs to share**.
- Attestation is per-edition: one explicit action per item.
- No blanket consent, no "share my learnings by default" shortcut past
  this stage, no bulk sign-off of a queue.

*Rejection path:* the user declines to attest, or never attests. The
edition stays local only. It is never retried without the user
re-submitting it. Nothing about the unattested edition leaves the
device — not metadata, not fingerprints, not "a user declined."

### Stage 2 — We refine it

- Rex/LEVI cleans, normalizes, and distills the edition: tight phrasing,
  consistent fields, essential content only.
- Refinement strips identifying and private content per the data
  minimization rules (§4). If anything cannot be safely stripped, the
  edition is rejected here, not "fixed later."
- Refinement may not alter the claim. If refining reveals the claim is
  wrong, incomplete, or ambiguous, the edition is corrected and re-enters
  at stage 2 as a new revision — the original revision is not silently
  edited in place.

*Rejection path:* the edition cannot be distilled without carrying
private data, or the claim collapses under cleanup. It goes back to the
submitting user's local instance with the reason recorded. It does not
sit in the cloud intake indefinitely — quarantine has a defined
lifetime, after which unattended editions are returned, not archived
into the shared pool.

### Stage 3 — We verify and cross-check every edition

- Each edition is checked individually: claim consistency (does it
  contradict already-committed editions?), provenance soundness (does
  the attestation chain hold?), safety (does it encode anything
  harmful, manipulative, or false?), and corroboration (is there
  independent grounding — existing corpus, reproducible check, or
  a second source?).
- No sampling. Ten editions means ten verifications. One thousand
  means one thousand.
- Verification is against the current committed source of truth, so
  contradictions are caught before commit, not patched after.

*Rejection path:* the edition fails any check. It is rejected with the
specific check named, returned to the submitting user's local instance
with the reason, and NOT committed. A rejected edition may be
resubmitted as a new revision (back to stage 1) once the user addresses
the reason — resubmission is never automatic.

### Stage 4 — Commit, signed and versioned

- ONLY editions that pass stages 1–3 commit.
- The commit is signed and versioned per the sketch in §5, so every
  distributed edition carries its provenance: who attested, who
  refined, who verified, when, and under which gate revision.
- Once committed, the edition is part of the source of truth and
  ships to other users on their next pull.

*Rejection path:* none — if it reached stage 4, it passed. (Rollback
and revocation after commit are UNDECIDED, §6.)

## 4. Data minimization rules

These hold regardless of any open decision below. They are constraints,
not preferences:

1. **Never raw private user data.** What leaves the device is distilled
   knowledge — the lesson, the fact, the procedure — never the raw
   material it came from: no messages, no journals, no conversation
   transcripts, no device identifiers, no names, no locations, no
   anything that traces back to a person.
2. **Distillation is lossy on purpose.** The refinement stage is
   expected to destroy information: specifics become general patterns,
   examples become synthetic illustrations, personal context is dropped.
   If the lesson cannot survive that loss, it is not shareable.
3. **The gate sees quarantine, not the device.** Nothing on the user's
   device is inspectable from the cloud side. The cloud sees only what
   the user explicitly submitted in stage 1. There is no "send us more
   context so we can verify" — verification works with the submitted
   edition or the edition fails.
4. **Metadata is data.** Submission timestamps, device types, usage
   patterns, attestation history — none of it ships. The signed edition
   carries provenance fields (§5) and nothing else.
5. **The submitting user owns retraction at stage 1.** Before
   attestation, the user can withdraw the candidate freely, and
   withdrawal leaves no trace in the cloud. (Post-commit revocation is
   UNDECIDED, §6.)

## 5. Versioning / signing sketch

Descriptive sketch only — exact scheme is UNDECIDED (§6):

- Every committed edition is an immutable record: content hash,
  monotonic version number, and a signature from the cloud authority
  (Chauncey's key, whatever form it takes).
- The record carries provenance: submitting user pseudonym (never
  identity), attestation timestamp, refinement notes summary, verifier
  identity (Rex/LEVI), gate revision under which it passed.
- Editions are append-only. A correction or update is a NEW edition
  that references the old one; history is never rewritten, so any
  client can audit what it received and when.
- Clients verify signature and hash on pull, before merging into local
  memory. A failed check means the edition is refused locally and the
  failure is reported — the client does not "try anyway."

## 6. Open decisions — UNDECIDED, gated on Chauncey

None of the following is settled. Each needs his explicit word before
any build touches it:

1. **Opt-in vs default sharing.** Is submission off until the user turns
   it on, or on with per-edition attestation still required? (Stage 1
   attestation is required either way — this decides the default posture.)
2. **Exactly what distilled fields may leave the device.** §4 sets the
   boundaries (never raw private data); the precise field list for a
   submitted edition — what is included, what is mandatory, what is
   forbidden — is undecided.
3. **Refinement criteria.** The exact rules for stage 2: what counts as
   clean, how aggressive distillation is, who (Rex vs Grok vs LEVI)
   refines which kinds of editions, and what the refinement gate
   revision looks like as a documented artifact.
4. **Signature/versioning scheme.** Key type, key custody (who holds the
   signing key and how), version numbering, hash algorithm, how clients
   fetch and pin the authority key.
5. **Rollback and revocation mechanics.** What happens when a committed
   edition turns out wrong or harmful: who can revoke, how revocation
   propagates to clients that already pulled it, whether revoked
   editions are tombstoned or fully withdrawn, and how clients confirm
   they applied the rollback.
6. **Pull/update mechanics.** How often clients check, whether updates
   are manual or automatic, how a user reviews incoming editions before
   merging them into local memory, and what happens on a failed or
   partial pull.

## 7. Non-goals — explicit

- **No cloud intake is built.** No upload endpoint, no intake queue,
  no quarantine store. The submission path does not exist in code.
- **No distribution mechanism is built.** No pull API, no update
  channel, no client merge logic. Distribution does not exist in code.
- **No signing infrastructure is built.** No keys, no authority, no
  verification on the client.
- **No refinement pipeline is built.** Stages 2–3 exist as law on
  paper, not as running services.
- Nothing in this document authorizes building any of the above.
  The build order comes from Chauncey, in his words, and until then
  this stays a spec.

---

Spec authored 2026-09-22. Status: design only — no implementation exists
or is authorized.

🧠
