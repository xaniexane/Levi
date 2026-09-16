# LEVI for VS Code

LEVI inside your editor. Three commands, one local CLI, zero telemetry, zero
network calls from the extension itself — every command shells out to your
local `levi` binary and streams its output into the **LEVI** output channel.

| Command | Title | What it runs |
|---|---|---|
| `levi.councilBuild` | LEVI: Council Build (multi-model code review) | `levi council build --task "..."` |
| `levi.buildApp` | LEVI: Build App (autonomous app builder) | `levi build "..."` |
| `levi.generateImage` | LEVI: Generate Image | `levi image --prompt "..." --backend ...` |

If the `levi` binary is missing, or a subcommand doesn't exist in your CLI
version, the extension tells you plainly (install/upgrade LEVI) instead of
failing silently.

## Install (manual — no marketplace)

Option A — package and install:

```bash
cd extensions/vscode
npx vsce package        # produces levi-vscode-0.1.0.vsix (devDependency only, not committed)
code --install-extension levi-vscode-0.1.0.vsix
```

Option B — copy straight into VS Code:

```bash
mkdir -p ~/.vscode/extensions/levi-vscode-0.1.0
cp extensions/vscode/{package.json,extension.js,README.md} ~/.vscode/extensions/levi-vscode-0.1.0/
# then reload VS Code
```

No `npm install`, no `node_modules` — the extension is plain JavaScript with
no dependencies and no build step.

## Settings

- `levi.cliPath` (default `"levi"`) — path to your local LEVI CLI. Point it at
  a full path (e.g. `/home/you/levi/levi`) if `levi` isn't on PATH.

## Suggested keybindings

No keymap is forced (to avoid collisions). Add these to your `keybindings.json`
if you want them:

```json
[
  { "key": "ctrl+alt+l c", "command": "levi.councilBuild" },
  { "key": "ctrl+alt+l b", "command": "levi.buildApp" },
  { "key": "ctrl+alt+l i", "command": "levi.generateImage" }
]
```

## Version honesty

- `levi.generateImage` works with any LEVI CLI that has `core/levi/media`
  (`levi image`).
- `levi.councilBuild` needs a CLI with the council feature (`core/levi/council`,
  `levi council build`).
- `levi.buildApp` needs a CLI with the builder feature (`core/levi/builder`,
  `levi build`).

If your CLI predates a subcommand, the extension reports the mismatch and
tells you to upgrade LEVI — it never pretends the feature ran.
