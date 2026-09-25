# Chrome extension bridge — install

The extension is real code; installing it is on you. Honest map:
`chrome_host.py` speaks Chrome's native-messaging protocol, this
directory is the extension. Steps:

## 1. Register the native host (one-time per machine)

Chrome finds the host through a manifest file named
`com.levi.automation.json` (the host name in `chrome_host.py` and in
`manifest.json`'s world — `background.js` connects to it by name).

Create the file with this content, pointing `path` at your checkout:

```json
{
  "name": "com.levi.automation",
  "description": "LEVI automation native-messaging host",
  "path": "/home/<you>/workspace/levi/core/levi/automation/bridges/chrome_host.py",
  "type": "stdio",
  "allowed_origins": ["chrome-extension://<EXTENSION_ID>/"]
}
```

- Make the host executable: `chmod +x chrome_host.py`
  (it carries `#!/usr/bin/env python3`; the LEVI repo must be importable
  — install the `levi` package or set `PYTHONPATH` to the repo's `core/`,
  e.g. via a small wrapper shell script in `path` if needed).
- Copy it to the per-OS location:
  - **Linux:** `~/.config/google-chrome/NativeMessagingHosts/`
  - **macOS:** `~/Library/Application Support/Google/Chrome/NativeMessagingHosts/`
  - **Windows:** registry key
    `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.levi.automation`
    whose default value is the manifest file's path.
- `<EXTENSION_ID>` is assigned when you load the extension (step 2);
  paste it into `allowed_origins` and reload.

## 2. Load the extension

1. Open `chrome://extensions`, enable **Developer mode**.
2. **Load unpacked** → select this `chrome_ext/` directory.
3. The toolbar button fires the configured default flow; the context
   menu ("Fire LEVI workflow with this page") fires with the page URL
   as data; the popup lists/adds flow ids, fires any of them, and
   shows the last host result.

## 3. Verify

Send a ping through the host directly:

```bash
python3 -c "
import struct, json, subprocess
msg = json.dumps({'type': 'ping'}).encode()
p = subprocess.run(['./chrome_host.py'], input=struct.pack('<I', len(msg)) + msg,
                   capture_output=True)
n, = struct.unpack('<I', p.stdout[:4])
print(p.stdout[4:4+n].decode())
"
```

Expected: `{"ok": true, "type": "pong"}`.

## Limits (honest)

- Firing a workflow requires the LEVI workflow engine's
  `dispatch_trigger` to exist; until the engine work lands the host
  answers `fire-workflow` with
  `{"ok": false, "error": "workflow engine dispatch not yet available"}` —
  a clean refusal, never a fake fire.
- The extension stores its flow list in `chrome.storage.local`; there is
  no server-side flow catalog. Add flow ids in the popup.
- Native messaging requires a real desktop Chrome/Chromium; it does not
  run in Chrome on Android.
