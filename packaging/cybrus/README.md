# Packaging: Cybrus standalone distribution

Local-only. Do not publish — no registry upload is authorized.

## What this is

`pyproject.toml` in this directory describes the `cybrus` standalone
distribution: the product shim (`cybrus/`, giving `python -m cybrus` and
the `cybrus` console script) plus the engine (`levi/cybrus/`) shipped under
a PEP 420 namespace `levi` package, so it installs cleanly next to — or
instead of — a full LEVI checkout.

## Build

From the repo root:

```sh
mkdir -p /tmp/cybrus-dist/src
cp -r core/cybrus /tmp/cybrus-dist/src/cybrus
mkdir -p /tmp/cybrus-dist/src/levi
cp -r core/levi/cybrus /tmp/cybrus-dist/src/levi/
# namespace package: do NOT copy core/levi/__init__.py
cp packaging/cybrus/pyproject.toml /tmp/cybrus-dist/
cp README_CYBRUS_STANDALONE.md /tmp/cybrus-dist/README.md
cd /tmp/cybrus-dist && python -m pip wheel . --no-deps -w dist/
```

Install the wheel on the target machine, then:

```sh
cybrus status
cybrus quickstart --service github --username <you>
```

The master password comes from `CYBRUS_MASTER_PASSWORD` or a prompt —
never from argv, never logged.

## Rules

- stdlib-only core. `cryptography` is optional (`pip install cybrus[accelerated]`);
  without it the vault reports `stdlib-fallback` via `vault.backend`.
- Version single-sourced from `core/levi/cybrus/product.py::PRODUCT_VERSION`.
- Pricing is NOT in this manifest — it is Chauncey's decision, pending.
