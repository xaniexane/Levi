# Presence Rooms — LAN drop-in rooms, no account, no server

**Remix delta.** Discord's business *is* hosting your conversations: the
account, the central servers, and the quality tiers are the product. LEVI
inverts it — the room substrate is yours. A hub runs on any machine on
your LAN (or loopback on one machine), peers discover it with multicast
beacons, rooms are drop-in, and the protocol is newline-delimited JSON
over TCP that you can read, log, and extend. No account, no signup, no
cloud, no quality paywall: there is nobody to pay because nobody hosts
you. Everything is stdlib-only (`socket`, `threading`, `json`).

## What this is

The honest local-first **room substrate**:

- **Peer discovery** — hubs announce themselves with UDP multicast
  beacons (`239.192.77.77:45555`); listeners build a peer table with a
  30s TTL. No registry, no central server — the LAN is the directory.
- **Drop-in rooms** — create/join/leave with a self-asserted display
  name. Identity here is a nametag, not a credential; the protocol says
  so plainly.
- **Text + presence signaling** — messages fan out to room members;
  `joined` / `left` / `timeout` presence events keep the room honest
  about who is actually there. Idle members are swept after 180s.

## Protocol

One JSON object per line over TCP. Client → server ops: `hello`,
`rooms`, `create`, `join`, `leave`, `say`, `who`, `heartbeat`.
Server → client pushes: `{"event":"message",...}` and
`{"event":"presence",...,"state":"joined|left|timeout"}`. See
`core/levi/presence/server.py` for the exact shapes.

## CLI

```bash
python -m levi.presence serve --name "Chauncey's lounge"
python -m levi.presence peers --seconds 8
python -m levi.presence create --host 192.168.1.10 --port 51234 --room lounge
python -m levi.presence join   --host 192.168.1.10 --port 51234 --room lounge
python -m levi.presence say    --host 192.168.1.10 --port 51234 --room lounge "hello"
```

Display name defaults to `~/.levi/presence/config.json`
(`{"display_name": "..."}`), else the login name.

## Honest triage: real-time voice — ARCHIVED AS UNBUILDABLE (stdlib-only)

The brief asked for LAN/self-hosted drop-in **voice**. This is the part
that cannot be built under the standing laws, and it is archived here
rather than stubbed:

1. **Python's stdlib has no audio capture or playback.** `wave` and
   `audioop` process audio *files*; there is no microphone or speaker
   API anywhere in the standard library. Capturing a voice stream
   requires a third-party binding (PyAudio/PortAudio, sounddevice) or a
   native helper — both violate stdlib-only.
2. **Real-time voice needs a codec and jitter handling.** Even with raw
   PCM flowing over the room socket, usable voice needs Opus (or
   similar) plus jitter buffers and echo cancellation. No stdlib path.
3. **A "voice room" that silently degrades to text would be a lie.**
   Shipping a stub that pretends at voice violates the no-stubs rule.

What *is* real and shipped: the room substrate above — discovery,
drop-in rooms, text, presence. It is the correct foundation: a future
native-audio extension (documented here as an extension point, not a
stub) could carry Opus frames as a new `{"event":"audio",...}` message
type over the same room protocol, with the same no-account discovery,
once a non-stdlib audio path is sanctioned. Until then, voice stays
archived.

## Honest gaps

- No encryption on the wire: LAN-trust model, documented in the code.
  (A future `tls` wrap of the hub socket is a clean addition.)
- No message history: rooms are live-only; persistence is a deliberate
  non-goal for drop-in rooms (a log shipper could subscribe as a client).
- Multicast beacons may not cross subnets/VLANs — same limitation every
  LAN-discovery protocol has; `peers` reports honestly when it hears
  nothing.
- Display names are self-asserted — fine for a living room, not for an
  adversarial network. Documented, not hidden.
