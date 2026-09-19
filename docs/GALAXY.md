# LEVI Galaxy — the ecosystem substrate

## Purpose

LEVI is not just a product; it is a **platform**. The Galaxy is the
substrate that makes LEVI the most feature-rich skill/tool/service-providing
agentic platform: third parties publish skills, tools, and services as
*Galaxy packages*, and LEVI (and other packages) consume them through one
deny-closed service directory — never by importing each other's modules.

This fits LEVI's standing economics: the core is local SI, stdlib-only,
**free to produce**; value is captured in the layers on top (curated feeds,
managed delivery, premium packs). Galaxy packages inherit that shape —
anyone can publish, anyone can run locally, and the directory keeps every
call accounted for. Per Chauncey's perpetual directive, LEVI *is* the thing
that never stops growing: the Galaxy is how that growth is organized.

The runtime half of the Galaxy layer lives in `core/levi/galaxy/`:

- `service.py` — `GalaxyServices`: install, the service directory, the
  capability-gated call path, governor metering.
- `__main__.py` — `python -m levi.galaxy` CLI.
- (landing separately from the packaging/namespacing builders)
  `package.py` — manifest loading/validation; `namespace.py` — id
  namespacing, collision detection, install/upgrade resolution policy.

## Key APIs

### Install a package — the real pipeline

```python
from levi.galaxy import install as galaxy_install
from levi.galaxy.service import GalaxyServices

record = galaxy_install.install("./acme-summarizer", home="~/.levi", policy=None)
# source may be a directory, a .tar.gz/.zip, or a git URL (cloned --depth 1).
# Deny-closed: bad manifest, namespace collision, or permission requests
# beyond policy all refuse with precise errors. The tree is SHA-256 hashed
# and the record appended to ~/.levi/galaxy/registry.jsonl; files land in
# ~/.levi/galaxy/packages/<id>/<version>/.

svc = GalaxyServices()
pkg = svc.register_installed(record, home="~/.levi")
# Integrity is re-verified BEFORE anything is imported (TamperError on
# mismatch); entry points come from the installed levi-skill.json; verbs
# register on port galaxy.<id>.
```

A package manifest (`levi-skill.json`) carries `entry_points` mapping verb
names to `"module:function"` targets:

```json
{
  "name": "summarizer",
  "version": "1.2.0",
  "kind": "skill",
  "description": "Summarizes long text locally.",
  "author": "acme.example",
  "entry_points": {
    "summarize": "acme_summarizer:run",
    "languages": "acme_summarizer:list_languages"
  },
  "capabilities": ["galaxy.acme.example.summarizer.*"],
  "permissions": {"network": false, "fs": [], "subprocess": false},
  "min_levi_version": "0.1.0"
}
```

Every entry point is resolved all-or-nothing — one bad target aborts the
registration. `GalaxyServices.install(manifest_dict)` remains for
programmatic use (manifests injected in-process, e.g. tests); the
`install()` + `register_installed()` path above is the production pipeline.

**Two stores, one truth.** The install registry (`levi.galaxy.registry`,
JSONL) records *what is installed*; the service directory is the runtime
view of *what is callable*. `svc.sync_from_registry(home=...)` registers
every installed-but-unregistered package (per-record deny-closed — one bad
package is skipped with its reason, never blocking the rest). The CLI's
read commands sync first, so the two can never silently disagree.

### Call a service verb — always through the directory

```python
from levi.galaxy.service import GalaxyServices

svc = GalaxyServices()  # store ~/.levi/galaxy, metered on the governor ledger

# The publisher (or LEVI itself) grants the caller a capability first:
cap = svc.issue_capability("my-skill-executor", ["galaxy.acme.summarizer.*"])

result = svc.call(
    "galaxy.acme.summarizer",
    "summarize",
    kwargs={"text": "..."},
    capability=cap,
    grantee="my-skill-executor",
)
```

`call()` verifies the capability **before** invoking anything:

1. `telescript.verify()` — malformed, tampered, expired, revoked, or
   wrong-grantee tokens raise the original typed exceptions
   (`MalformedToken`, `InvalidSignature`, `ExpiredToken`, `RevokedToken`,
   `WrongGrantee`). Nothing is executed; the refusal is metered.
2. `telescript.permits()` on the action `galaxy.<id>.<verb>` — not covered
   by a granted pattern → `ActionRefused` (deny-closed).
3. `PortRegistry.send_command()` — `UnknownPort` / `UnknownVerb` on miss.
4. The attempt is recorded on the governor ledger
   (`provider="galaxy"`, `tool_name="galaxy.<id>.<verb>"`,
   `agent_id=<grantee>`, `error` set on refusals).

Refusal types are re-exported from `levi.galaxy.service` so callers catch
one family; they are never wrapped into vagueness.

### Cross-package calls

Skill A calls skill B's verb **through the directory, never by direct
import**:

```python
# inside skill A's verb implementation; `directory` is the GalaxyServices
# instance handed to it by the caller (e.g. the agent loop)
result = directory.call(
    "galaxy.acme.summarizer",
    "summarize",
    kwargs={"text": text},
    capability=my_own_capability,  # must ALSO cover galaxy.acme.summarizer.*
    grantee="skill-a-executor",
)
```

Privilege does not leak across the boundary: A's capability must explicitly
cover B's action, or the inner call is refused — even though the outer call
was permitted.

### The directory

- `list_services()` → `{port: {package, version, verbs, pin, broken, ...}}`
  — introspection only, no callables.
- `search(query)` → substring match over installed id/name/description/verbs.
- `info(id)`, `remove(id)`, `revoke(token_or_nonce)`.

## CLI usage

```bash
python -m levi.galaxy list
python -m levi.galaxy services
python -m levi.galaxy search summarize
python -m levi.galaxy install ./acme-summarizer        # dir, .tar.gz/.zip, or git URL
python -m levi.galaxy info acme.example.summarizer
python -m levi.galaxy remove acme.example.summarizer  # directory + registry + files
```

`install` runs the full pipeline (materialize → validate → namespace check →
permission policy → hash pin → register verbs). `remove` is a full uninstall.
Exit code is 0 on success, 1 on any failure, with the error on stderr.

## The permission model (least-privilege, deny-closed)

- **Capabilities are bearer permits with a grantee.** Minted by the
  directory (`issue_capability(grantee, actions, ttl)`), signed with HMAC.
  Default TTL 1h; session-scoped unless `LEVI_TELESCRIPT_SECRET` is set.
- **Actions are `galaxy.<id>.<verb>`.** Patterns: exact
  (`galaxy.acme.summarizer.summarize`), prefix wildcard
  (`galaxy.acme.summarizer.*`), regex (`re:^galaxy\.acme\..*$`). Empty
  actions permit nothing.
- **Deny-closed everywhere.** No capability → no call. No matching pattern
  → no call. Unknown port/verb → typed refusal, never silent ignore.
- **Revocation** is by token nonce (`revoke()`), checked on every call.
- **Hash pinning** at install; pin re-verified on every load.

## How a third party publishes

1. **Manifest** — author writes the install record above (`id` matching
   `[A-Za-z0-9][A-Za-z0-9._-]*`, non-empty `entry_points` of
   `"module:function"`).
2. **Install** — the user (or LEVI) runs `python -m levi.galaxy install
   manifest.json`. The directory validates, resolves, registers, pins.
3. **Hash pin** — the sha256 pin is shown at install and stored; `info`
   re-displays it so the user can compare against the publisher's
   announced pin out-of-band.
4. **Capability grant** — the user/operator mints a capability for the
   intended caller with the narrowest action set that suffices
   (e.g. `["galaxy.acme.summarizer.summarize"]`). Grants are explicit,
   expiring, revocable — never ambient authority.

Publisher trust remains the user's judgment: the directory guarantees
*integrity* (the bits are what was installed) and *authorization* (only
granted actions run), not *benign intent* of the code itself. Entry points
run in-process — review what you install, as with any package manager.

## Pending wiring patches

Seams I could not touch (files owned by other builders / sibling in-flight
work). Each is a precise patch for the coordinator to schedule:

1. **Agent-loop hookup (owned: `core/levi/agent/tools.py`).**
   Skills must reach the directory instead of importing each other. Needed
   addition, in the tool-execution path where a skill's verbs run: hand the
   skill a bound `GalaxyServices` instance plus its own capability token
   (grantee = the skill executor's identity), so cross-package calls go
   through `GalaxyServices.call`. Without this, `service.py`'s cross-package
   rule is convention, not enforcement. Suggested shape:
   ```python
   # in the per-skill tool context construction:
   tool_ctx["galaxy"] = galaxy_services  # GalaxyServices instance
   tool_ctx["galaxy_capability"] = svc.issue_capability(skill_executor_id, granted_actions)
   ```
   plus documentation in the skill authoring guide that `galaxy.call` is the
   only sanctioned cross-package route.

2. **Pre-call governor gates (owned: `core/levi/governor/*`).** — LANDED
   2026-09-18. `service.py` meters every attempt on the usage ledger (clean
   seam, wired today). `GalaxyServices.call` now also consults
   `BudgetEnforcer` and `CooldownManager` before invoking a verb: in
   `GalaxyServices.call`, before step 3, `budgets.authorize()` /
   `cooldowns.acquire(scope=f"galaxy:{port}")` refuse deny-closed as
   `BudgetDenied` / `CooldownDenied` (both `GalaxyError` subclasses, both
   metered like every other refusal). The enforcers are injected the way
   the `Meter` is: an explicit `budgets=`/`cooldowns=` wins, otherwise the
   real governor state attaches under the same home. Tests:
   `tests/test_galaxy_governor_gates.py` (6).

3. **Public package registry (not yet built).**
   `search` today only searches *installed* packages. A real Galaxy needs a
   registry index (signed manifest feed) that `search`/`install` can query
   over the network. Until then, `install <source>` takes a local manifest
   file (or stdin) and the "hash pin" is compared out-of-band.

4. **`levi.galaxy.__init__` merge.**
   A sibling builder's `__init__.py` imported `package.py`/`namespace.py`
   before those files existed, which made the whole `levi.galaxy` package
   unimportable (including `service.py` and the CLI). I made those imports
   degrade gracefully (try/except ImportError, additive only — the sibling's
   intended exports are untouched) so the package imports with or without
   the sibling files. When `package.py`/`namespace.py` land, the imports
   will succeed normally; the coordinator should still review the final
   merged `__init__` and consider re-exporting `GalaxyServices` there.

5. **Capability UX (future).**
   No CLI subcommand mints capabilities yet (`issue_capability` is
   API-only). A `python -m levi.galaxy grant --grantee X --actions ...`
   subcommand is the natural next step once the agent-loop hookup (1)
   defines who the grantees are.

## Honest limits

- **Entry points run in-process.** A malicious package runs with LEVI's own
  privileges. The directory gates *which* verbs run and *who* may call
  them; it does not sandbox the code. Treat `install` like `pip install`.
- **No public registry yet** — see pending patch 3.
- **Capabilities are session-scoped by default** (per-process HMAC secret
  unless `LEVI_TELESCRIPT_SECRET` is set) — same semantics as
  `levi.revival.telescript`.
- **Metering never breaks the call path.** If the governor ledger is
  unwritable, the attempt is silently unrecorded rather than refusing a
  valid call. This is a deliberate fail-open choice for the ledger only;
  authorization stays fail-closed.
- **Corrupt store starts empty.** If `~/.levi/galaxy/packages.json` is
  unreadable JSON, the directory starts with no packages rather than
  crashing; tampered (pin-mismatched) records are kept but marked broken.
- **Port ACLs unused.** `PortRegistry` supports caller allowlists; Galaxy
  registers ports without them because capabilities are the gate. Both
  layers could be combined later, but one clear gate beats two fuzzy ones.
- Tests: `tests/test_galaxy_service.py` — 21 hermetic tests (install,
  validation, duplicate refusal, capability gates for tamper/expiry/
  wrong-grantee/revocation/scope, unknown port/verb, cross-package calls
  with and without inner permission, metering of successes and refusals,
  persistence reload, pin-tamper → broken).
