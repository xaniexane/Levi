# FACTORY GENESIS

**Continuous production line for agents and skills.** Not one-off builds — an
always-on line. Ordered by Chauncey 2026-09-24 ("factory genesis production of
agents and skills"). Bootstrapped v1 by coordinator 🌊.

## The line

```
INTAKE → SPEC → BUILD → GATES → REGISTRY → RECEIPTS
  │        │       │        │         │           │
  │        │       │        │         │           └─ receipts/<id>.md + memory log
  │        │       │        │         └─ glyph assigned; skill registered / agent banked
  │        │       │        └─ law→guard→prove: tests green + registry verification
  │        │       └─ ONE builder per build thread; the rest queue
  │        └─ specs/<id>.md from spec_template.md (laws declared up front)
  └─ intake/queue.jsonl (append-only; status: queued→spec'd→building→proving→registered→done)
```

## Intake sources

1. **DemandPulse signals** — scored opportunities become agent/skill specs.
2. **DDD inbox** — `~/workspace/ddd-inbox/` (revenue-driven requests; drop a
   `.md` brief, the coordinator transcribes it to a spec).
3. **Chauncey's orders** — chat directives transcribed to specs by the
   coordinator.

Each intake line: `id`, `kind` (`agent`|`skill`), `working_title`, `source`,
`rationale`, `status`, `created_at`. Append-only — statuses advance, lines are
never deleted.

## Build discipline

- One builder per build thread. Everything else queues sequentially.
- Every builder gets a glyph at dispatch; `Agent-Glyph: <glyph>` trailer on
  every commit; roster at `~/workspace/agent-glyphs.md` updated same motion.
- Hot branch (`~/workspace/levi`): temp-index commits only, explicit paths,
  never touch siblings' files or the staged set. Verify the trailer after
  every commit.
- **No pushes** without his explicit order + fresh credential + IP re-audit.
- **Nothing deletes** — removed material is stored with provenance, never
  destroyed.
- Dynasty eyes-only: canon/IP material never leaves the repo or enters
  public surfaces.

## Gates — law→guard→prove

Every spec declares its **laws** (invariants) up front. The builder implements,
then proves: the proof is tests green **plus** registry verification —

- skill: imports cleanly, registers in the SkillRegistry, count/list checks pass;
- agent: definition validates, banks into the registry with a verifiable
  fingerprint.

No proof, no registration. A failed proof sends the spec back to `building`,
never forward.

## Naming sovereignty

Chauncey births every name. The factory mints under **provisional working
titles**; final names await his word. This is recorded on every spec.

## What runs automatically vs what needs him

**Automatic:** intake harvesting (signals → spec drafts), spec drafting, build
dispatch one at a time, tests, registry of *definitions*, receipts, queue
advancement.

**Needs his word:** final names; new dynasty seats carrying authority; anything
public, anything spending money, anything touching accounts; pushes;
enforcement flips; deploying a minted agent as a live actor. The factory mints
definitions (code) — it never deploys live autonomous actors on its own.
Advisory-only until he says otherwise.

## Layout

```
core/levi/factory/               # pre-existing WriteBuild fusion pipeline (untouched)
core/levi/factory/genesis/       # ← Factory Genesis lives here
  README.md            # this design
  __init__.py          # INTAKE_QUEUE / SPECS_DIR / RECEIPTS_DIR
  spec_template.md     # spec skeleton (laws first)
  receipt_format.md    # receipt skeleton
  registry_hooks.py    # mint_skill() / mint_agent() + verification
  intake/queue.jsonl   # the line
  specs/<id>.md        # one per intake item
  receipts/<id>.md     # one per completed mint
```

Note: `core/levi/factory/` already housed the WriteBuild pipeline
(`writebuild.py`, `pipeline.py`, `review.py`, `sandbox.py`, `bag.py` —
registry category `factory` shared, no id collisions). Genesis is a
subpackage so neither line disturbs the other.
