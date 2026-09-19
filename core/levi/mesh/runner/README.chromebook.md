# Fleet node on a Chromebook — the three doors

The Chromebook is the right anchor: sips power, stays awake, nothing
precious to protect. Try the doors in order — stop at the first one
that opens.

With 30 GB total storage, set `offer.storage_mb` to **5120** (5 GB) in
`node_config.json`, not the 10 GB default. Leave the rest.

## DOOR 1 — Linux on ChromeOS (cleanest, no wipe)

1. Open **Settings**, search **"Linux"**.
2. If you see **"Linux development environment"** → Turn on → follow
   the setup (takes a few minutes, downloads Debian).
3. Open the **Terminal** app it installs:
   ```
   sudo apt update && sudo apt install -y python3
   ```
4. In the ChromeOS **Files** app, copy the `levi-node` folder into
   **Linux files**.
5. In Terminal:
   ```
   cd ~/levi-node
   cp node_config.example.json node_config.json
   ```
   Edit `node_config.json`: `device_id` (e.g. `chromebook-01`),
   `known_peers` (your other node's LAN IP + port), `storage_mb`: 5120.
6. Check then run:
   ```
   python3 check_env.py --config node_config.json
   ./start_node.sh
   ```
   (If `./start_node.sh` refuses: `bash start_node.sh`.)

## DOOR 2 — Termux from the Play Store (no dev mode, no wipe)

For Chromebooks with no Linux option but Android apps enabled.

1. Install **Termux** from the Play Store.
2. In Termux:
   ```
   pkg update && pkg install -y python
   ```
3. Get the `levi-node` folder into Termux's home: download the zip in
   Chrome, then in the Files app move it somewhere Termux can see, or
   simplest — in Termux:
   ```
   termux-setup-storage
   ```
   then copy from `~/storage/downloads/`.
   ```
   cd ~/levi-node
   cp node_config.example.json node_config.json
   ```
4. Edit `node_config.json` as in Door 1 (storage 5120 MB).
5. Check then run:
   ```
   python check_env.py --config node_config.json
   bash start_node.sh
   ```
6. Keep it alive: run `termux-wake-lock` in a second Termux session
   (shows a notification, stops Android dozing the node), and keep the
   Chromebook plugged in.

## DOOR 3 — Developer mode + full Linux (LAST resort)

Esc+Refresh+Power, then Ctrl+D at the recovery screen. **This
powerwashes the Chromebook — everything local is wiped.** Only if
Doors 1 and 2 are both closed. After it boots unlocked, install your
Linux of choice (Crouton/MrChromebox path) and follow Door 1 from
step 3.

## Keeping the anchor awake

- Stay plugged in. A node that sleeps is a node the fleet re-farms
  around — fine, but an anchor should stay up.
- If the lid must close: Settings → Device → Power → "Sleep when lid
  is closed" → Keep awake (not all models offer this; otherwise leave
  the lid open).
- The runner prints its peer count every 30 seconds — glance at it the
  first day to confirm it's meshing.

## Verify

From your other node: its peer list should show the Chromebook's node
id within seconds of startup. Two sides seeing each other = the fleet
is real.
