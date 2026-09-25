# Vault — `core/levi/vault/`

LEVI's secrets store: passphrase-derived encryption for the small
secrets LEVI must hold (API keys, tokens). Nothing secret ever lives
in memory, config files, or logs in plaintext.

## Purpose

One honest place for credentials: encrypted at rest, decrypted only in
memory for the exact operation that needs them, never printed, logged,
or persisted alongside.

## Key APIs

- `VaultSeal(passphrase, directory=None)` (`core/levi/vault/seal.py`)
  - `put(name, text) -> Path` — encrypt and store (name is sanitized)
  - `get(name) -> str` — decrypt to memory only
  - `list_names() -> list` — names, never values
  - `encrypt_bytes(data) / decrypt_bytes(data)`
  - raises `VaultError` (a `ValueError`) on wrong passphrase / tampering
- CLI: `levi vault keys create|list|revoke ...`

## CLI usage

```bash
levi vault keys create <name>     # prompts for the secret, never echoes
levi vault keys list              # names only
levi vault keys revoke <name>
```

## Honest limits

- The vault protects secrets **at rest**; it does not protect a
  compromised machine or a shoulder-surfer. Passphrase strength is on
  the owner — LEVI never stores or recovers it.
- Encrypted blobs still live on disk: treat backups of the vault
  directory as sensitive (the rclone `crypt` overlay adds a second
  layer off-machine — see `docs/BACKUP.md`).
- There is no sharing model: one owner, one passphrase. Anything that
  needs to leave the machine should be re-issued, not exported.
