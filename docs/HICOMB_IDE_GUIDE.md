# Hicomb IDE — operator's guide

Hicomb is Chauncey's code editor and it is also the builder. You speak
plain language, it turns that into a build plan, the plan runs through
the forge, and nothing lands without your approval where approval is
owed. Everything works offline. Everything is receipted.

## The shape

```
your words -> NL->IR plan -> forge (Pollen -> Surgeon -> Quetta) -> your approval -> write
```

Every stage snapshots before it acts. If anything goes wrong, any stage
rolls back to any earlier snapshot. Nothing is ever half-written.

## NL -> IR: talk, get a plan

The builder speaks the original Alpha command forms:

- `build engine <name>` — a whole engine
- `build module <name>` — a module
- `build service <name>` — a service
- `build <anything else>` — a project

Tiers decide how much rope the plan gets:

- **E3 / E4** — plan and apply freely. E4 is the default.
- **E5 / E6** — the plan is made, then it waits. Applying refuses
  until you approve the HITL request. This is fail-closed: no approval,
  no apply, no exceptions. (`force=True` is the explicit override and
  it is receipted as one.)

```python
from levi.hicomb.ide_nl import parse_intent, plan_intent, apply_job, ir_of

parse_intent("build module invoice_parser")          # what did it hear?
job = plan_intent("build module invoice_parser")     # the IR: a BuildJob
ir_of(job)                                           # the IR as a dict
print(apply_job(job.id, workspace="/path/to/work"))  # E4: applies. E5/E6: refuses until approved
```

The IR is the BuildJob itself — intent, kind, name, goal, tier, plan
steps. There is no second IR hiding anywhere.

The intent router is deterministic rules, not a model. It says so
plainly (`intent_source()`), and the pair programmer labels every
completion `local` until a real model backend is seated.

## The forge: Pollen -> Surgeon -> Quetta

`ForgeArm.forge_text(text, language)` runs the repair loop over text in
memory. It never writes to disk itself.

1. **Pollen** formats first. If the formatter refuses (broken syntax),
   the whole forge aborts and your text comes back byte-identical.
2. **Elite Surgeon** repairs multi-pass, syntax-gated. A pass that
   breaks parsing is rolled back, never kept.
3. **Quetta Pan** gives advisory suggestions and drives the learning:
   failures compost, the genome steers the next fix. A fix the genome
   has learned to suppress is withheld with its reason stated.

```python
from levi.hicomb.forge import ForgeArm
res = ForgeArm().forge_text("x=1  \nif x==None:\n    pass\n", "python")
res.ok, res.repaired, res.fixes_applied   # True, True, ['FORGE_WS', 'FORGE_NONE_CMP']
```

## Saving: Pollen runs before every write

`save_pipeline(buffer, path)` is the only sanctioned path from buffer
to disk. Pollen formats; if it refuses, the write aborts and the file
stays byte-identical (the abort check is explicit, not `assert` — it
holds under `python -O` too). An optional Quetta refine pass sits
between format and write — advisory only, applied only with your
confirm callback, and its output re-runs Pollen's gates before the
write. A crashing refiner never breaks the save: the pass is skipped
(reported via `on_quetta_skip`) and the write proceeds on the formatted
text.

## Plugin studio: scaffold -> test -> publish

```python
from levi.hicomb.plugin_studio import scaffold_plugin, test_plugin, publish_plugin

scaffold_plugin("my-tool", "tool", plugins_root="plugins/")
test_plugin("plugins/my-tool")       # runs the plugin's own tests
publish_plugin("plugins/my-tool")   # ships it to the local store
```

No network at any step. The web studio itself
(`core/levi/hicomb/web/hicomb-studio.html`) is one self-contained file —
no CDN, no build step, opens from `file://` on the phone.

## Self-upgrade: you approve every path

The IDE proposes its own upgrades as projected paths. Each one carries
its projected outcome up front — simulated AND sandbox-tested before it
can ever be approved. The sandbox runner (`levi.hicomb.sandbox_test`)
executes each projection's checks in a copied sandbox directory, under
the `sandbox-test` snapshot stage, and writes a JSON receipt. Approval
is refused unless the projection's `sandbox_ok` is True: untested or
sandbox-failed paths are never approvable. Denial stays allowed and
routes the failed path into the denied/remix store.

The sandbox is provably offline, in two layers: (a) every Python-based
check runs with a sitecustomize socket guard that raises on any TCP/UDP
attempt — proven by a test that tries a real connection and fails;
(b) non-Python executables run under `unshare -n` where the platform
permits it, and are rejected outright where it doesn't (phones,
locked-down containers). Proxy variables are scrubbed, bytecode writes
disabled, and the receipt records which isolation guarded the run.

You approve or deny each path independently:

- **Approved** paths can apply. Nothing else can.
- **Denied** paths are never deleted. They live in the denied-path
  store as remixable material, and later projections can recombine
  them — every recombination records its parentage.
- Every decision is receipted with the simulated AND sandbox-tested
  outcomes that were shown at the checkpoint.

```python
from levi.hicomb.self_upgrade import SelfUpgradeLoop
loop = SelfUpgradeLoop()
p = loop.propose_projection("cache tweak", {"module": "pollen"},
                            projected_outcome="fewer re-formats")
st = loop.sandbox_test_projection(p.id)   # must pass first
assert st["sandbox_ok"] is True
loop.decide(p.id, approve=True, reason="tested clean")
loop.apply_projection(p.id)               # only approvals apply
```

Decisions are terminal — no re-decides, no silent upgrades.

Quetta Pan wiring is guarded (`levi.hicomb.qp_compat`): the forge, the
NL→IR loop, and self-upgrade import the sibling's `quetta_loop` only at
the point of use. On a checkout where it is absent, the modules still
import and the Quetta stage fails closed with a clear error naming the
missing module — never a bare ImportError at import time.

## Receipts: where everything lives

Default store `~/.levi/hicomb/ide/`:

- `.snapshots/` — per-stage snapshots + `receipts.jsonl` (hash-chained)
- `ide_receipts.jsonl` — NL->IR parse/plan/apply log
- `.self_upgrade/` — proposals, denied paths, decision receipts
- `.forge_compost.jsonl` / `.forge_genome.json` — the forge's learning

## What it does not do yet

- **Real-phone test.** Every milestone waits on Chauncey's hands on
  his Moto G. Nothing here is claimed proven on hardware.
- **Model backend.** The pair programmer is local-only until Chauncey
  seats a model. It will not pretend otherwise — and a broken backend
  degrades to local-only rather than breaking completions.
