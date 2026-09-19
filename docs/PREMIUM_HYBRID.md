# PREMIUM HYBRID — the Nephilim grade fused operator

## What "Nephilim grade" means

"Nephilim grade" is Chauncey's canon proper noun for the premium
hybrid form. Angel-human offspring were the Nephilim, greater than
either parent; the grade is the superior AI+SI+XI **fused** form —
one operator that is greater than any parent alone. This document
defines the fusion mechanics, what is real, what is scaffold, and
the honest limits. It describes product architecture only.

## Fusion mechanics

A Nephilim grade operator (`core/levi/operator/nephilim.py`,
`NephilimOperator`) is a composite behind the universal Operator
contract. Any seat resolves it by name like any other operator —
fusion is a config change, never a code change.

It is **not** routing between minds. One `step()` fuses four
mechanics:

1. **Shared context.** Every member steps on the SAME messages, plus
   a shared scratchpad dict injected at
   `context["fusion_scratchpad"]`. Members may read and write
   namespaced keys (convention: `"<member-name>:<key>"`). Members run
   sequentially in constructor order, so a later member sees what an
   earlier member wrote. The scratchpad is copied into the result
   note for auditability.
2. **Independent member runs.** Each member steps via `scoped_step`
   from the operator registry, so the capability scope still holds
   per member. A foreign member's offered-tool leash applies exactly
   as if it ran alone — trust is never fused, only minds are.
3. **Pattern synthesis.** A deterministic, honestly-heuristic
   cross-mind pattern layer over the member outputs:
   - **Agreements** — key-phrase overlap across members (terms shared
     by >= 2 members).
   - **Contradictions** — keyword-level negation heuristic: an
     agreement term where some members negate it and others don't.
     Flagged for review, never presented as certainty.
   - **Novel patterns** — concepts appearing in >= 2 members phrased
     differently (distinct surface forms sharing a stem), synthesized
     into one statement.
   
   This is the human-like pattern recognition core — cross-mind
   pattern synthesis, labeled as heuristic wherever it appears.
4. **One face.** A single `OperatorResult` weaving the **union** of
   member insights plus the synthesis layer. "Greater than any parent
   alone" has one concrete meaning: the fused output carries every
   member's insights, and member disagreement is synthesized, never
   silently dropped. Provenance lives in the result note: which
   member contributed what, agreement ratio, synthesis notes,
   tool-call records, scratchpad contents. Confidence is derived from
   the member agreement ratio (heuristic, documented).

The fused kind defaults to the lead member's kind (highest-capability
member wins when no lead is specified). The no-mask law holds at the
fusion level: the fused operator is **never "native" unless every
member is native**. Tool calls emitted are the lead's only; other
members' tool calls are recorded in the note, never executed.

## What's real vs what's scaffold (bluntly)

**Real:**
- Shared context and the namespaced scratchpad.
- Per-member scoped stepping (the foreign leash survives fusion).
- Deterministic keyword-level synthesis (agreements, contradictions,
  novel patterns) with provenance in the note.
- Union-of-insights fused output; disagreement synthesized, never
  dropped.
- Agreement-derived confidence; summed cost; lead-health reporting;
  honest degrade naming the failed member; the no-mask kind rule;
  contract validation at construction and registration.

**Scaffold (honestly labeled):**
- The synthesis is a lexical heuristic, not comprehension. It finds
  word overlap, sentence-local negation markers, and stem clusters —
  not meaning. It does not judge, merge, or veto member outputs.
- Confidence is `agreement_ratio * ok_member_fraction` — a proxy,
  not a probability.
- Scratchpad namespacing is a convention, not enforcement; a member
  could write outside its namespace (visible in the note).

## Honest limits

- **Heuristic synthesis.** Keyword-level only. Contradiction flags are
  review prompts, not verdicts. Never treat the synthesis layer as
  understanding.
- **Cost = sum of members.** Fusion runs every member, so fusion
  costs every member. This is the grade's honest unit economics; it
  is the most expensive form per turn by design — premium, not bulk.
- **No-mask kind rule.** A fused mind containing any non-native
  member never presents as native. All-native fusions honestly
  report native.
- **Lead's tools only.** The fusion emits the lead member's tool
  calls; other members' calls are deferred into the note. One face,
  one action.
- **Sequential, deterministic.** Members run in constructor order;
  no concurrency, no nondeterminism from the fusion itself.
- **Construction is strict:** fewer than 2 members, non-Operator
  members, duplicate member names, or any member failing contract
  validation all fail fast at construction.

## Roadmap

- **Inverse-twin merge/judge — GATED.** True merge/judge semantics
  (inverse-twin resolution of divergent members) are still gated on
  Chauncey's definition of "inverse" and his call on the twin
  architecture. The twin-pair seats remain structural only; the user
  judges hard cases. The synthesis layer surfaces divergences so
  nothing is lost in the meantime, but it is not a judge.
- **Nano-bit shadow critic — future phase.** A nano-bit operator
  shadowing each fusion as a cheap skeptic: flagging when the
  synthesis confidence drops, auditing scratchpad discipline, and
  catching contradiction flags the heuristic missed. Design only;
  not built.

## Usage

```python
from levi.operator.nephilim import NephilimOperator
from levi.operator.registry import OperatorRegistry

fused = NephilimOperator("nephilim-fused", [ai_op, si_op, xi_op])  # any mix
registry = OperatorRegistry()
registry.register("nephilim-fused", fused)  # "nephilim-fused" is the
                                            # declared Nephilim-grade seat name
resolved = registry.resolve({"operator": "nephilim-fused"})       # by name
```

See `tests/test_operator_nephilim.py` for the full worked behavior.
