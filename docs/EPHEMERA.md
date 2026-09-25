# EPHEMERA — True-Delete Ephemeral Channels

Snapchat proved the demand for disappearing messages — then built the
business on the opposite: cloud copies, server logs, retention backdoors,
and engagement metrics on your "private" chats. LEVI Ephemera is the
remix: ephemerality where deletion is the *mechanical truth*, not a UI
promise, because there is no cloud for a backdoor to live in.

## What it is

Local channels where every message:

1. is **encrypted at rest** with a key derived from a passphrase you
   supply (PBKDF2-HMAC-SHA256, 210k iterations),
2. carries a **per-channel TTL** (default 24h),
3. is **secure-overwritten** (3 random passes + zeros) then unlinked on
   expiry — not merely deleted,
4. emits a **hash-chained deletion receipt** you can verify, so the
   deletion is *provable to yourself*.

## What it is not (the honesty note)

- **Not military-grade E2EE.** stdlib Python has no audited authenticated
  cipher. The encryption is a *composition of reviewed primitives*
  (SHA-256, HMAC-SHA256, PBKDF2) in a CTR+MAC construction written for
  this project. It defeats plaintext-on-disk snooping, not a motivated
  cryptanalyst. There is no peer key exchange — this is at-rest
  encryption on your own machine, not Signal.
- **Cannot prevent screenshots.** Nothing local can. Instead of a fake
  "screenshot detection" promise, every message can carry a
  `forwarding_discouraged` flag (an explicit social contract, displayed
  on read), and every read is written to an access log.
- **Losing the passphrase loses the messages.** LEVI never stores it.
  That's the design.

## Usage

```bash
python -m levi.ephemera create family --ttl 86400
python -m levi.ephemera post family --author chauncey --body "dinner at 7?" --no-forward
python -m levi.ephemera read family <msg-id>
python -m levi.ephemera sweep            # delete everything expired
python -m levi.ephemera receipts family  # verify deletion chain
python -m levi.ephemera access family    # who read what
```

Data lives in `~/.levi/ephemera/channels/<name>/`.

## What the giants refuse

- Deletion that is mechanically real instead of a retention setting.
- Zero server-side copies to mine.
- Admitting what ephemerality *can't* do (screenshots), instead of
  selling a false guarantee.

## Open gaps

- No multi-device sync (sync would reintroduce a retention surface;
  a future design could use pairwise device exchange, not a server).
- Key rotation per channel is not yet implemented; changing the
  passphrase requires recreating the channel.
- The secure-overwrite is best-effort on SSDs (wear-leveling can retain
  blocks); on encrypted disks this is moot, on unencrypted SSDs it is a
  known limit — stated here so nobody is misled.
