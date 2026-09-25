# CLI wiring notes — `levi legion`

`core/levi/cli/main.py` was already modified by a sibling worker when the
legion package landed, so main.py was NOT edited (shared-branch
discipline). The legion CLI is complete and self-contained in
`core/levi/legion/cli.py`; it needs three minimal hooks in main.py,
following the exact pattern of the other modules (backup, jobs,
strategy):

## 1. Import (top of file, next to the other module hooks)

```python
# >>> LEVI legion module — minimal hook (Legion bot product); logic in levi/legion/
from levi.legion.cli import cmd_legion, register_legion_parser
# <<< LEVI legion module
```

## 2. Parser registration (in the parser-building section, next to
`register_backup_parser(sub)` etc.)

```python
# >>> LEVI legion module — minimal hook (Legion bot product)
register_legion_parser(sub)
# <<< LEVI legion module
```

## 3. Dispatch (in the dispatch dict, next to `"backup": cmd_backup`)

```python
# >>> LEVI legion module — minimal hook (Legion bot product)
"legion": cmd_legion,
# <<< LEVI legion module
```

## What it enables

- `levi legion configure --name "..." --type restaurant --tone warm --greeting "..."`
  — white-label a Legion install (validates; saved to `~/.levi/legion/installs.jsonl`)
- `levi legion team --name "..." --type salon --need booking --need pricing`
  — assemble the tailored crew from the roster via the hive adapter
- `levi legion team --sitelift lift_<id> --name "..."`
  — propose the crew from a Site Lift report (tailored offer)
- `levi legion pack restaurant` / `levi legion pack --list`
  — specialist add-on packs
- `levi legion quote --type shop --pack restaurant --name "..."`
  — paper quote: advisor pricing, 70/30 split shown, Cybrus plan+preview
  recorded, paper-unpaid license issued. Moves nothing.

## Until wired

All of the above also works programmatically:

```python
from levi.legion.cli import cmd_legion
from levi.legion.product import configure
from levi.legion.team import BusinessProfile, assemble_team
from levi.legion.packs import get_pack
from levi.legion.sitelift_link import propose_team, fixture_report
from levi.legion.sale import quote_legion, plan_checkout, split_paper, issue_license
```
