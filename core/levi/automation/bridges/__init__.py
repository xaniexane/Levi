"""LEVI automation bridges: Chrome extension, MacroDroid, cross-device.

Bridges are LEVI-native original code (stdlib only) that connect the
workflow engine (``..flows.dispatch_trigger``) to outside triggers and
devices. Every bridge imports the engine lazily inside functions so this
package stays importable even while the engine's dispatch surface lands.

What's real vs. external (honest map):

- REAL: the native-messaging host protocol, the event builders, the
  MacroDroid outbound POST, the device registry + outbox writer.
- EXTERNAL (documented, not performed): installing the Chrome extension,
  configuring macros in the MacroDroid app, Termux picking up outbox
  files on the phone, serving the inbound webhook URL.
"""
