# LEVI on Android via Termux

Run the full LEVI core (CLI, agent runtime, memory, growth loop, the 818
skill playbooks) directly on your phone. LEVI's core is **stdlib-only
Python**, which is exactly what makes this possible — no compilers, no
wheels, no dependency hell on ARM Android.

## Install (10 minutes)

1. Install **Termux** (get it from F-Droid — the Play Store build is
   outdated).
2. Download **both** files on the phone: `levi-termux.tar.gz` and
   `setup.sh` (attached together).
3. In Termux:
   ```bash
   termux-setup-storage          # grants access to ~/storage/downloads
   cd ~/storage/downloads
   bash setup.sh levi-termux.tar.gz
   ```
   Or, once the repo is pushed to GitHub, skip the tarball:
   ```bash
   bash setup.sh --clone
   ```
4. Restart Termux (or `export PATH="$HOME/bin:$PATH"`), then:
   ```bash
   levi status
   ```

`setup.sh` installs python+git, unpacks LEVI to `~/levi`, drops a `levi`
launcher in `~/bin`, and smoke-tests. No virtualenv, no pip install —
`PYTHONPATH=$HOME/levi/core` is all it needs.

## Updating

- Tarball path: download the new snapshot, re-run `setup.sh` (it
  replaces `~/levi`; your data in `~/.levi` is untouched).
- Clone path: `cd ~/levi && git pull`.

## What works / what doesn't

| Feature | Termux status |
|---|---|
| CLI, `ask`, personas, skills (818 playbooks) | ✅ stdlib-only |
| Agent runtime, `agent chat`, sessions | ✅ |
| Growth loop (`growth cycle`) | ✅ rules engine; model-assisted needs a runner |
| Memory store, brain corpus/table | ✅ |
| News ingest | ✅ needs network |
| Vault encryption | ⚠️ needs `pip install cryptography` (builds from source on-device; slow but works — needs `pkg install rust openssl`) |
| `levi-local` on-device model | ❌ `llama-server` has no Android build; LEVI falls back to the offline rule engine and says so |
| Brain training (`brain/train`, torch) | ❌ no torch wheels for Android |
| Vyve Messenger Android app build | ❌ needs the Android SDK — build that on a PC |

## Notes

- Data lives in `~/.levi` inside Termux (separate from any PC install).
- First run of anything model-flavored without a runner uses the
  deterministic offline engine — honest, documented, no fake AI.
- `termux-wake-lock` keeps long `agent chat` sessions alive with the
  screen off.
