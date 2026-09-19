# The Forge — Echo → Alpha → Nexus, end to end

LEVI's full Omega pipeline in one honest run: a prompt becomes an Echo
blueprint, Alpha compiles it into artifacts, you preview and explicitly
approve, the artifacts land safely, and Nexus routes the follow-through —
with a signed receipt at the end.

```
python -m levi.revival forge "a landing page website for my bakery"
```

Interactive by default. Non-interactive approval is explicit, never default:

```
python -m levi.revival forge "a landing page" --dest ./site --approve --mode offline
```

## The seven stages

| Stage | Does | Does NOT |
|---|---|---|
| `echo` | Detect product types via a **keyword heuristic** (scores exposed), draft a structural blueprint, validate it | Understand intent beyond keywords; guarantee the design is good, complete, or safe to run |
| `alpha` | Run the matching generator(s) into an in-memory `{path: content}` map | Touch disk; execute or test the code; invent generators for types it can't build |
| `preview` | Render paths + content snippets; map per-file landing verdicts (`write` / `skip-existing` / `blocked`) | Write anything — ever. Pure function plus destination existence checks |
| `permission` | Record an explicit `approve=True` (or your typed `YES`) | Default-approve, infer approval from silence, or reuse approval across runs |
| `materialize` | Write approved files, re-read and byte-compare each, record sha256 per file, return a signed receipt | Execute the artifacts; verify the code *runs* — only that bytes match |
| `nexus` | Rank LEVI's lawful providers and explain the choice line-by-line | Claim confidence measures real accuracy — it's a **policy score**; run the artifact — routing only *picks* a provider |
| `receipt` | Combine every stage's `did` / `did_not` into one record | Paper over a refusal — a failed stage stops the run and stays visible |

## The human gate

Nothing lands on disk without your explicit say-so. The pipeline refuses
to write when `approve` is `False`, and the CLI's interactive flow asks
you to type `YES` — not `y`, not Enter. `--approve` exists only as an
explicit flag for non-interactive use; it is never on by default.

## Sourcing law (Nexus stage)

The Forge routes only through LEVI's own:

- `levi-local` — LEVI-native on-device capability. The headliner; it never
  shares the spotlight, and `offline` mode keeps everything on the machine.
- `levi-si-cloud` — LEVI SI Cloud, the only remote source, out of the
  spotlight, never the default.

Anything else is `reference`: studied, compared against, **never**
operational — ineligible in every mode. A mode with no eligible provider
is a deny-closed refusal, never a fallback to something ineligible.

## What the Forge honestly cannot do

- Judge whether your idea is good, legal, or safe to run. It builds what
  you describe; the judgment stays yours.
- Produce finished products. Generators emit **starter scaffolds** —
  working skeletons with honest headers, not complete applications.
- Verify code runs. The receipt proves bytes match what was approved; it
  says nothing about whether the code works.
- Reach the network. The whole pipeline is stdlib-only and local-first;
  the only "remote" in the picture is the Nexus *recommendation* of
  `levi-si-cloud` as a provider — the pipeline itself makes no network
  calls and never will.
- Remember across runs. Approval, blueprints, and receipts live in the
  moment; there is no persistent forge state.

## Programmatic use

```python
from levi.revival.omega import pipeline as forge

receipt = forge.run_pipeline(
    "a landing page website for my bakery",
    dest="./site",  # must already exist
    approve=True,  # explicit — nothing writes without it
    mode="offline",  # fast | balanced | deep | offline
    generator="webpage",  # optional pin; default: all matching
)
assert receipt["ok"]
print(receipt["stages"][-1]["data"]["explanation"])
```

`ValueError` is raised only for bad *arguments* (empty prompt, unknown
dest/mode/generator). Every flow refusal — denied permission, invalid
blueprint, no eligible provider — comes back as a structured receipt with
`ok: False` and the failed stage's reason, never an exception.
