# LEVI Revival — retired software ideas, reborn as LEVI capabilities

Ten ideas from dead, forgotten, or under-applied software, rebuilt as real working
LEVI modules under `core/levi/revival/`. All stdlib-only, local-first, defensive.
Hermetic tests in `tests/test_revival_*.py`.

The pattern: each revival takes a mechanism that was ahead of its time, drops the
parts that died with its era, and wires the live mechanism into LEVI's organism —
always deny-closed, always honest about limits.

## 1. Telescript → capability-bounded agent execution (`revival/telescript.py`)

General Magic's mobile agents carried *permits* and *authorities* — you could only do
what you were explicitly granted. In LEVI: signed, expiring capability tokens
(HMAC-SHA256, `base64url(claims).base64url(sig)`) around tool calls.

- `issue(issuer, grantee, actions, ttl)` → token; `verify()` fail-closes on malformed
  payloads, bad signatures (constant-time compare), expiry, wrong grantee, revocation.
- Action patterns: exact, `prefix.*` wildcards, `re:` regex (validated at grant time).
- `guarded_call(token, action, fn, *args)` verifies *then* executes — or refuses
  without ever invoking the tool. `GuardedExecutor` holds multiple tokens.
- Secret from `LEVI_TELESCRIPT_SECRET` or a per-process random secret (session-scoped
  by default, documented).
- Honest limit: tokens are session-scoped; persistent delegation needs a shared
  secret store + persistent revocation list later.

## 2. Plan 9 → per-task namespaces + 9P-style IPC (`revival/plan9.py`)

Per-process namespaces were Plan 9's great invention; now in the Linux kernel, used
directly. In LEVI, two parts:

- `Namespace`: run tools in subprocesses with restricted cwd (auto-created sandbox,
  cleaned up), scrubbed env (minimal default + opt-in allowlist), wall-clock timeouts
  that kill the whole process group, optional Linux `RLIMIT_CPU`/`RLIMIT_AS`,
  path-escape rejection on staged files.
- 9P-*style* message surface (explicitly not a real 9P server): newline-delimited
  JSON frames over `socket.socketpair()` — `create_channel()`, id-correlated
  request/response, timeouts, out-of-order reply buffering, `serve()` with error
  replies and unknown-type refusal.
- Honest limit: does not sandbox loopback network, world-readable file reads, or
  syscalls. Real containment needs seccomp/containers.

## 3. Erlang/OTP → supervision trees (`revival/otp.py`)

"Let it crash": children are simple; the supervisor is smart. In LEVI:

- `Supervisor` over `ChildSpec` declarations (name, target callable, restart mode,
  `max_restarts`/`restart_window`, shutdown timeout).
- Strategies `one_for_one` / `one_for_all` / `rest_for_one`, faithful to OTP.
- Children run in threads as `target(stop_event, ...)`; any exception becomes a
  structured `CrashReport`. Exceeding restart intensity → child marked `DEFUNCT`,
  supervisor shuts down gracefully and reports (exactly OTP semantics).
- Steppable `tick()` core for deterministic tests + optional monitor thread.
- `lazy_levi_target("module:attr")` wires existing LEVI callables without editing them.
- Honest limit: threads, not processes — a segfaulting native extension kills the
  supervisor too. Local-services-only by design.

## 4. Hearsay-II → shared hypothesis blackboard (`revival/blackboard.py`)

Opportunistic multi-agent coordination over a shared hypothesis surface — the
antidote to brittle fixed pipelines:

- `post_hypothesis()` posts confidence-scored hypotheses that are **never silently
  overwritten** — competing hypotheses coexist, surfaced via `conflicts()` pairs.
- Knowledge sources register via `register_ks(name, interests, action, bid=...)`
  (interests: topic strings, `"*"` wildcards, or predicates).
- `bid()`/`run_cycle()` scheduler runs the highest bidder (deterministic tie-break);
  `run_until()` loops to quiescence or a cycle cap.
- Demo: classify → enrich → summarize assembled opportunistically — KSs registered in
  reverse pipeline order still execute correctly purely from bidding.
- Honest limit: default bidding is naive; confidence is KS-claimed, never calibrated.

## 5. ARexx → named application command ports (`revival/arexx.py`)

Amiga's named app command ports as LEVI's inter-module automation protocol:

- `PortRegistry.register_port("memory", {"store": fn, ...}, acl=[...])`;
  `send_command("memory", "store", args)` resolves verbs by name.
- Typed refusals: `UnknownPort`, `UnknownVerb`, deny-closed `AccessDenied` when an
  allowlist ACL is set (no ACL = open).
- `run_script()` executes port/verb steps sequentially with per-step `StepResult`
  capture and `stop_on_error` control.
- Optional socketpair backing: `serve_registry()` + `RemoteRegistry` (lazy-imports
  `plan9`), refusal types preserved across the wire.

## 6. Lotus Agenda → auto-categorization with inspectable rules (`revival/agenda.py`)

Auto-pilot filing with a glass cockpit — every filing decision explainable:

- `Rule` (name, conditions over keywords/regex/tags/source/importance, target
  category, priority) validated eagerly at construction.
- `RuleEngine.file_entry(entry)` → `(category, Explanation)` naming the winning rule,
  which conditions matched, and which runner-ups also matched.
- Fail-open: non-dict entries / no-match / errors → `"uncategorized"` with an
  explanation of why. Every decision hits an in-memory audit log + optional JSONL
  audit file.
- 8 sensible default rules (incidents > decisions > learnings > ideas > gratitude >
  tasks > highlights > journal); JSON persistence via `save`/`load`.

## 7. BeOS/BFS → reactive live queries (`revival/bfs.py`)

Queries that stay live and notify on new matches — the filesystem-as-database idea,
aimed at memory:

- `subscribe(QuerySpec, callback)` → id; specs combine keywords/tags/entry_type/
  min_importance as AND; `notify(entry)` fans out to matching subscribers.
- A raising callback is recorded in `errors()` and never breaks delivery to others.
- Durable subscriptions persist specs + handler names; `load()` re-arms only those
  whose handler was re-registered (`register_handler`), missing handlers skipped
  with warnings, never silently.
- `LiveStore` wraps LEVI's real `MemoryStore` read-only (lazy import, memory module
  untouched): `store_entry()` persists then notifies.

## 8. Newton soups → application-independent object stores (`revival/soups.py`)

Data that outlives the apps that wrote it:

- `Soup(name)`: `put(obj, schema, schema_version)` / `get` / `query(predicate)` /
  `query_schema` / `delete`. Objects carry their own schema name + version, never
  coerced (explicit `compatible()` / `query_schema(min_version)` instead).
- One JSON file per soup under `~/.levi/soups/`, 0o600 perms, atomic tmp+replace writes.
- Fail-closed on corruption: bad file quarantined to `<name>.corrupt-<ts>.json`,
  `SoupCorruptError` raised. `list_soups()` marks corrupt soups without raising.

## 9. Xanadu/Memex → transclusion + associative trails (`revival/xanadu.py`)

Provenance-preserving knowledge — quote by reference, follow trails:

- `Transclusion.quote(doc_id, start, end)` returns a `Quote` with text + provenance
  (`citation()` renders `"text" — title [doc_id:start–end]`); `transclude()` records
  quoter→quoted links so every doc knows its `quoted_by`.
- `TrailStore.follow_trail()` yields `(Document, annotation)` pairs in order and
  raises rather than skipping broken links. Trails and docs persist as JSON.
- Additive RAG integration: `trail_from_citations()` builds a trail from
  `rag ask()` citation ids; `ask_and_trail()` lazy-imports `levi.rag.pipeline` and
  raises an honest `RuntimeError` if rag is unavailable — never fabricates citations.

## 10. Soar → impasse→subgoal→chunking (`revival/soar.py`)

Agents that compile deliberation into reusable skills:

- `Deliberation` records `(state, operator, result)` steps toward a goal; on success,
  `chunk()` generalizes the trace into a `Procedure` (documented heuristic: numbers,
  quoted strings, digit-bearing identifiers abstract to `$x1…` in goal-appearance
  order; everything else stays literal — deliberately conservative).
- `ProcedureLibrary` persists procedures as JSON; `recall(goal)` returns the best
  match with variable bindings and a score (all literals match in order; variables
  bind consistently).
- Demo: problem 1 (`deploy service api version 3`) deliberated and chunked; problem 2
  (`…version 4`) solved purely from the chunked procedure — no re-deliberation.
- Honest limit: chunking replays *what worked once* without verifying preconditions;
  chunks must only replay through an executor enforcing LEVI's
  Plan→Preview→Permission→Execute→Verify→Receipt policy (the module never executes).

## Safety posture

- Telescript capabilities are deny-closed; Soar chunks never execute (data only).
- OTP supervision is local-services-only. Plan 9 namespaces are a sandbox aid, not a
  security boundary (documented).
- The cyber boundary is unchanged: defensive blue-team only.
- No autonomous outbound actions beyond existing LEVI policy anywhere in this package.
