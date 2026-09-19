# Genesis CLI wiring

`levi genesis` is wired directly into `core/levi/cli/main.py` (no patch
needed — the file was clean when wired).

**Parser region** (in `main()`, right after the lifepack parsers):

```python
# === GENESIS-REGION-BEGIN: genesis pack forge parsers ===
gen_p = sub.add_parser("genesis", help="Genesis pack forge: lifetime 1-copy buy")
gen_sub = gen_p.add_subparsers(dest="genesis_action")
gen_asm = gen_sub.add_parser("assemble", help="Assemble a genesis pack from a spec")
gen_asm.add_argument("--spec", default=None, help="Spec JSON file")
gen_asm.add_argument("--spec-json", default=None, help="Spec JSON inline")
gen_asm.add_argument("--out", default=None, help="Packs root override")
gen_sub.add_parser("list", help="List assembled genesis packs")
gen_insp = gen_sub.add_parser("inspect", help="Inspect + verify a genesis pack")
gen_insp.add_argument("pack", nargs="?", default=None, help="Pack id or directory")
gen_sub.add_parser("parts", help="Show the genesis parts bin (capability families)")
# === GENESIS-REGION-END ===
```

**Dispatch region** (in the `cmds` build, right after `LIFEPACK-REGION-END`):

```python
# === GENESIS-REGION-BEGIN: genesis pack forge dispatch ===
try:
    from levi.genesis.cli import cmd_genesis as _cmd_genesis

    cmds["genesis"] = _cmd_genesis
except Exception:
    pass
# === GENESIS-REGION-END ===
```

Handler: `core/levi/genesis/cli.py::cmd_genesis(args)` — actions
`assemble` / `list` / `inspect` / `parts`, dispatched on `args.genesis_action`.

If `cli/main.py` is ever locked by a sibling's in-flight edit, replicate
these two regions verbatim and keep them delimited so the next merge stays
clean.
