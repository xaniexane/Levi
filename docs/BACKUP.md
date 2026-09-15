# LEVI Backup — encrypted off-machine snapshots

`levi backup` snapshots the LEVI state dir (`~/.levi`) into timestamped,
hash-manifested tarballs and ships them off-machine through **rclone** —
always behind rclone's `crypt` overlay (client-side encryption). The remote
backend only ever sees ciphertext.

**Design rule:** plaintext never leaves this machine unencrypted. `levi backup`
refuses to sync to any remote that is not a verified `crypt` overlay — even a
misconfigured-public bucket would only hold encrypted blobs.

## What gets backed up

Everything under `~/.levi` **except** the heavies:

| Excluded | Why |
|---|---|
| `models/`, `*.pt`, `*.bin`, `*.gguf`, `*.safetensors`, `*.onnx`, `*.ckpt` | model weights — re-downloadable, huge |
| `cache/`, `__pycache__/`, `*.pyc`, `*.log`, `*.zip` | caches and diagnostics |
| `backups/`, `restore-staging/` | snapshots of snapshots would recurse |

Always included: the offline corpus, the growth journal (baby book),
memory, agent sessions, demand findings, bounty scopes/findings,
references, and config. A typical snapshot is kilobytes, not gigabytes.

## Quick start

```bash
# 1. snapshot right now (works with zero setup)
levi backup now

# 2. check status
levi backup status

# 3. run the daily job (snapshot always; sync when a remote is configured)
levi backup daily
```

## Setting up the encrypted remote (Google Cloud Storage)

### 1. Install rclone

```bash
# Linux (persistent spot — /usr/local/bin is wiped on VM restarts)
curl -sL -o /tmp/rclone.zip https://downloads.rclone.org/rclone-current-linux-amd64.zip
unzip -o /tmp/rclone.zip "rclone-*-linux-amd64/rclone" -d /tmp/rclone-dl
mkdir -p ~/bin && cp /tmp/rclone-dl/rclone-*-linux-amd64/rclone ~/bin/
chmod +x ~/bin/rclone
# make sure ~/bin is on PATH
```

`levi backup` finds rclone on `PATH`, falling back to `~/bin/rclone`.

### 2. Create a PRIVATE GCS bucket

In the Google Cloud Console (or `gcloud`):

1. Create a bucket, e.g. `levi-backups-<yourname>`.
2. **Uniform bucket-level access: ON** (disables per-object ACLs entirely).
3. **Public access prevention: enforced** — the bucket cannot go public even
   by accident.
4. Add a lifecycle rule: delete objects older than 90 days (the crypt
   filenames are opaque; old snapshots are just rotation).
5. Create a service account with **only** `roles/storage.objectAdmin` on
   *that bucket* (least privilege), and download its JSON key.

### 3. Configure rclone: GCS + crypt overlay

```bash
rclone config
# n) New remote
# name: gcs
# Storage: Google Cloud Storage ("google cloud storage")
# service_account_file: /path/to/service-account-key.json
# (accept defaults for the rest; "Auto config" n for headless)

# n) New remote
# name: levi-crypt
# Storage: Crypt ("crypt")
# remote: gcs:levi-backups-<yourname>
# filename_encryption: standard   (encrypts filenames too)
# directory_name_encryption: true
# password:  <— ENTER YOUR PASSPHRASE INTERACTIVELY HERE
# password2 (salt): <— optional second secret, also interactive
```

**The passphrase is the crown jewel.** rclone obscures it in its config file
(`~/.config/rclone/rclone.conf`), but anyone with that file + the config can
decrypt. It is never stored in the LEVI repo, never in `~/.levi/backup.json`
(which only records the remote *name*), and never in logs. Use a long
passphrase from a password manager. Lose it and the backups are
unrecoverable — that is the price of real client-side encryption.

### 4. Point LEVI at it and verify

```bash
levi backup configure --remote levi-crypt
# -> verifies the remote is actually a crypt overlay before accepting it

levi backup now   # snapshots AND syncs
```

## Fallback: archive.org (S3-compatible, private/dark)

If GCS is unavailable, archive.org exposes an S3-compatible API at
`s3.us.archive.org`. Items **must stay private/dark** — set
`x-archive-meta-collection` appropriately and never mark the item public.

```bash
rclone config
# n) New remote
# name: ia
# Storage: Amazon S3 Compliant Storage Providers ("s3")
# provider: Other ("other")
# endpoint: https://s3.us.archive.org
# access_key_id:     <your archive.org S3 access key>
# secret_access_key: <your archive.org S3 secret>
# region: (leave empty)

# n) New remote
# name: levi-crypt
# Storage: Crypt ("crypt")
# remote: ia:levi-backups-<yourname>
# (same crypt settings as above — filenames encrypted, interactive passphrase)
```

Then `levi backup configure --remote levi-crypt` as above. The crypt overlay
means archive.org also only ever sees ciphertext.

Get S3 keys at https://archive.org/account/s3.php (logged in).

## Verify your privacy checklist

- [ ] `levi backup status` shows `remote check: OK — ... crypt overlay ...`
- [ ] GCS bucket has uniform access + public access prevention enforced
- [ ] Service account key is scoped to the one bucket only
- [ ] `rclone lsd levi-crypt:` shows opaque encrypted names (not real filenames)
- [ ] `rclone cat levi-crypt:levi-backups/<file>` returns ciphertext, not JSON
- [ ] rclone.conf (`~/.config/rclone/rclone.conf`) has mode 0600 and is itself
      backed up somewhere safe (without it + the passphrase, restores fail)

## Restore

```bash
# list local snapshots
levi backup status

# verify + stage a snapshot for inspection (never touches live state)
levi backup restore --snapshot 20260915T230000Z

# pull from the remote first, then stage
levi backup restore --snapshot 20260915T230000Z --from-remote

# actually write it into live state (asks for typed confirmation;
# takes a safety snapshot of current state first)
levi backup restore --snapshot 20260915T230000Z --apply
```

Staged snapshots land in `~/.levi/restore-staging/<id>/extracted/` — inspect
them there before applying. Applying skips `backups/` and
`restore-staging/` themselves, so the snapshot store is never overwritten.

## Daily automation

Spec: `core/levi/backup/cron_spec.json` — `levi backup daily` at 03:00 local.
Snapshot always runs (even with no remote / no rclone); sync runs only when a
verified crypt remote is configured. Sync failures are recorded in
`~/.levi/backup_state.json` and retried on the next run — the job never
crashes the scheduler.

## Threat model (honest)

- Protects against: machine loss, disk failure, accidental deletion,
  bucket misconfiguration (ciphertext only), provider-side snooping.
- Does **not** protect against: losing the crypt passphrase (unrecoverable),
  an attacker with root on this machine *before* encryption, or rclone.conf
  theft combined with the passphrase. Guard both.
- Snapshots exclude model weights by design — re-pull them after a restore
  (`levi agent model pull`).
