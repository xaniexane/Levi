# LEVI Vault — total-security backup

The keeper's law: **a clean copy lives here** (the working copy in the
repo); **the vault copy is the encrypted backup**, carried on external
drives. This directory holds the tooling and the locked folder. The
bundles themselves go to drives — never into git.

## Layout

```
vault/
  backup.py      create encrypted snapshots
  restore.py     list / verify / restore snapshots
  vault.py       crypto + manifest + locked-folder library
  snapshots/     owner-only (0o700); bundles are 0o600; git-ignored
  README.md      this file
```

## The locked folder

`snapshots/` is created `0o700`, every bundle `0o600`, every temp file
`0o600` and deleted after use. `restore.py list` reports the live
permissions of each bundle (`locked=true` means the perms are exactly
right). If anything ever shows `locked=false`, re-chmod before trusting
the machine.

## Crypto (honestly labeled)

Mirrors `core/levi/cybrus/veil.py`:

- **AES-256-GCM** via the `cryptography` package when importable
  (bundle magic `LV2`). Without it, the **stdlib HMAC-CTR fallback**
  (magic `LV1`) — fallback-grade, labeled as such, never a silent
  downgrade. An `LV2` bundle on a machine without `cryptography` fails
  closed with an install hint.
- **KDF:** `hashlib.scrypt` (n=2^15, r=8, p=1) where available,
  PBKDF2-HMAC-SHA256/600k fallback. Pinned in the bundle header.
- Every bundle carries a **SHA-256 manifest per file** (inside the
  encrypted tarball). `verify` decrypts and checks every hash before
  anything is trusted; `restore` re-verifies on disk after extraction.

The **passphrase is never invented or stored**: it comes from
`LEVI_VAULT_PASSPHRASE` or an interactive prompt (twice on create).
Minimum 8 characters. It lives in memory only.

## Quick start

```bash
# 1. create a snapshot (prompts for passphrase twice)
python3 vault/backup.py create --label pre-wire-launch

# non-interactive (CI / scripts you control):
LEVI_VAULT_PASSPHRASE='...' python3 vault/backup.py create --label nightly

# 2. list snapshots (no passphrase needed — headers are plaintext metadata)
python3 vault/restore.py list

# 3. verify a bundle (decrypts, checks every file hash, extracts nothing)
python3 vault/restore.py verify vault/snapshots/<bundle>.lvault

# 4. restore
python3 vault/restore.py restore vault/snapshots/<bundle>.lvault --dest /tmp/levi-restore
```

## What gets packed

The full working tree **including `.git`** (history is part of the
restore), minus regenerable heavies (documented in `vault.py`):

- `node_modules/`, `__pycache__/`, `*.pyc`, `.venv/`
- `runs/` (generated run outputs)
- model weights / build artifacts (`*.gguf`, `*.pt`, `*.safetensors`,
  `*.bin`, `*.onnx`, `*.ckpt`, `*.a`)
- the vault's own `snapshots/` (no snapshots of snapshots)

## Where the bundles go (the keeper's drives)

After `create`, copy the `.lvault` bundle to **at least two** external
destinations, e.g.:

1. An encrypted USB drive kept with the keeper (first copy).
2. A second drive kept off-site (family, safe-deposit, trusted location).
3. Optional third: a cloud object store **only** behind client-side
   encryption you control — the vault bundle is already encrypted, so
   this is belt-and-suspenders, not primary.

Verify on the drive after copying: run `restore.py verify` against the
drive copy at least once, then yearly. A backup you never test is a
rumor. See `docs/CLEARANCE.md` for who may ever touch these bundles
(tier 0 — the keeper's eyes only).
