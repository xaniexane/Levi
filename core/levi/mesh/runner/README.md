# Fleet node runner — join a machine to the LEVI mesh

One folder, no install. The node runs **alongside** whatever is already on
the machine — it touches nothing outside its own folder and the data
directory named in the config.

## STEP 0 — protect the machine first (your job, do this before anything)

This laptop carries licensed software worth real money. Before it joins
the fleet, make a **full disk image** (clone) to an external drive. Any
tool that images the whole disk works — the point is: if anything ever
goes wrong, the $30k of factory software comes back byte-for-byte.

Do not skip this. The node joins after the clone exists.

## STEP 0.5 — check the Windows version

Press Win+R, type `winver`, Enter.

- **Windows 7 or newer:** good — continue to Step 1.
- **Windows 2000 / XP / Vista-era:** Python 3.8+ (the floor for a node)
  does not install there. This machine **cannot** host a node — use the
  Chromebook as the fleet anchor instead and keep the fossil on its
  factory software.

`check_env.py` (Step 4) verifies this automatically and will tell you
plainly if the machine is a no-go.

## STEP 1 — install Python 3.8 or newer

From python.org, run the installer, and **check "Add python.exe to PATH"**
during setup. Verify in a terminal:

```
python --version
```

## STEP 2 — copy this folder to the laptop

Copy the whole `levi-node` folder (USB stick works) anywhere — Desktop,
Documents, wherever. Nothing is installed; the folder *is* the program.

## STEP 3 — write the config

Copy `node_config.example.json` to `node_config.json` and edit it:

| field | what to put |
|---|---|
| `device_id` | a unique name, e.g. `fossil-laptop-01` |
| `device_name` | human name, e.g. `Fossil Laptop` |
| `bind_port` | leave `47911` unless something already uses it |
| `known_peers` | the LAN IP and port of your other node, e.g. `[["192.168.1.50", 47910]]` |
| `offer.storage_mb` | how much disk the fleet may use (default 10240 = 10 GB, capped inside `mesh_data`) |
| `offer.memory_mb` | RAM the fleet may use — match the machine: 512 on a healthy box, **128** on a 1 GB machine (see thin profile below) |
| `offer.cpu_units` | spare CPU to share (1.0 = about one core; **0.5** on old single-cores) |

Find the laptop's own LAN IP with `ipconfig` (the `IPv4 Address` line) —
you'll give *that* address to the other node's config as its peer.

### Thin machines (1–2 GB RAM, old CPUs)

Copy `node_config.thin-example.json` to `node_config.json` instead of
the standard example. It offers half a CPU and 128 MB RAM — honest
numbers for a starved machine. The node itself sips ~30–50 MB, so it
runs fine; it just doesn't promise what it hasn't got. Such a box is
a contributor, not an anchor — the anchor should be your most
always-on machine.

## STEP 4 — readiness check

```
python check_env.py --config node_config.json
```

Every hard check must PASS. Peer-unreachable is a warning only (the
other node may simply not be up yet).

## STEP 5 — join the fleet

Double-click **`start_node.bat`**, or:

```
python run_node.py --config node_config.json
```

Leave the window open (minimize it). The node heartbeats every 5 seconds
and works tasks for the fleet. Ctrl+C leaves cleanly.

If Windows Firewall asks, allow Python on **private** networks only.

## STEP 6 — verify from the other machine

On your main machine, run its node and check discovery: the laptop's
node id should appear in the peer list within a few seconds. The runner
also prints its peer count every 30 seconds — both sides seeing each
other means the fleet is real.

## What the node does and doesn't do

- **Does:** listen on one TCP port, answer heartbeats, run small
  registered compute functions for farmers, store nothing outside
  `mesh_data/`.
- **Doesn't:** install anything, need admin, touch the registry, phone
  home, or reach the internet at all (fleet-internal only, by design).

## Optional — start on boot

Task Scheduler → Create Task → trigger "At log on" → action
`pythonw.exe C:\path\to\levi-node\run_node.py --config C:\path\to\levi-node\node_config.json`.
Use `pythonw.exe` (not `python.exe`) so no window opens.

## If it doesn't work

- `check_env.py` FAIL lines say exactly what's wrong — fix those first.
- Both machines must be on the **same wifi/LAN**.
- `bind_port` must be free and the same port must not be firewalled
  between the two machines.
