# capproto/1 — the capability-gated service protocol

## The giant pattern it inverts

Twitter and Reddit proved the playbook: open the API, let developers build
their businesses on it, then reprice or revoke access at will. Discord
followed the same arc. MCP won by being a *protocol* instead of a product —
but it is still a vendor-shaped artifact you connect *to*.

**The remix:** a service protocol nobody owns. capproto/1 is stdlib-only,
vendorless, and capability-gated: every call carries a bearer capability
token issued by the *service owner* — never a platform. There is no central
API to reprice because there is no center. Revocation is the local issuer's
own right, recorded in an owner-only audit ledger on this machine.

What the giants structurally cannot ship: **attenuation** (macaroon-style
narrowing). Handing someone a strictly-less-powerful credential — a subset
of actions, an earlier expiry — makes API resale and repricing impossible
by construction. A platform that sells access tiers cannot sell you the
tool that dissolves tiers.

## Protocol spec — capproto/1

Framing: newline-delimited UTF-8 JSON, one message per line, 1 MiB line cap
(fail-closed).

```
client -> server  {"v":"capproto/1","id":str,"op":"hello","agent":str}
client -> server  {"v":"capproto/1","id":str,"op":"call","svc":str,
                   "verb":str,"token":str,"args":object}
client -> server  {"v":"capproto/1","id":str,"op":"revoke","token":str}
client -> server  {"v":"capproto/1","id":str,"op":"bye"}
server -> client  {"v":"capproto/1","id":str,"ok":true,"result":any}
server -> client  {"v":"capproto/1","id":str,"ok":false,
                   "error":str,"error_type":str}
```

`error_type` ∈ `protocol | auth | refused | unknown_verb | bad_args | server`.

Authorization model:
- The token on a `call` is HMAC-verified (`levi.revival.telescript`).
- The *action* checked is `"<svc>.<verb>"`, e.g. `kvnote.put`.
- Malformed, tampered, expired, revoked, wrong-grantee, or unpermitted
  tokens are REFUSED without invoking the verb. Deny-closed throughout.
- Attenuation (see below) can only ever *narrow* a token.

## Transports

- Primary: AF_UNIX socket at `<home>/sockets/<name>.sock` (dir 0700, socket 0600).
- Fallback: TCP on 127.0.0.1, ephemeral port in `<home>/sockets/<name>.port`.
- Never leaves the machine.

## Capability tokens

Minted with `levi.revival.telescript.issue` (HMAC-SHA256). The secret comes
from `LEVI_TELESCRIPT_SECRET`; without it, tokens verify only in-process
(documented, not hidden — share the env var for server+client).

### Attenuation

```python
from levi.capproto.tokens import attenuate
child = attenuate(parent_token, actions=["kvnote.get"], ttl_seconds=60)
```

Refused (fail-closed) when the request would *widen*: a pattern the parent
does not carry, or an expiry past the parent's. Attenuations chain — the
ledger records parent nonce → child nonce.

## CLI

```
python -m levi.capproto issue --issuer me --grantee agent --action 'kvnote.*' --ttl 600
python -m levi.capproto attenuate --token <tok> --action kvnote.get --ttl 60
python -m levi.capproto verify --token <tok>
python -m levi.capproto serve            # demo kvnote service on a local socket
python -m levi.capproto call --verb list --token <tok>
python -m levi.capproto demo             # full issue->attenuate->refuse->revoke story
python -m levi.capproto ledger           # audit trail
```

## Files (under `~/.levi/capproto/`)

- `mints.jsonl` — append-only issuance/attenuation/revocation audit ledger
- `sockets/<name>.sock` — live endpoints
- Homes resolve at call time (`--home`, `LEVI_HOME`, or `~/.levi`).

## Honest gaps

- Tokens are bearer instruments: whoever holds the bytes holds the power.
  The ledger tells you *what was minted*, not *who holds copies*. Don't
  mint broad long-lived tokens and email them around.
- No delegation-by-reference (a token pointing at another token instead of
  embedding patterns) — attenuated copies embed their own claims.
- The demo `kvnote` service stores notes in memory; persistence is the
  service author's job, not the protocol's.
