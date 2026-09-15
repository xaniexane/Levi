# LEVI's Soul — an owner-editable prompt override

`~/.levi/soul.md` is LEVI's **soul**: a plain markdown file you own, whose
text is **prepended to every agent system prompt** on this machine —
single-shot `run_subtask` runs, the `levi agent run` CLI, and chat turns
(chat builds on the same loop, so it inherits this automatically).

It answers "who is LEVI *for you*": tone, persona, house rules, the
things you always want said or never said. It sits *above* the built-in
instructions (tool use, honesty rules, safety gates), which stay intact
underneath.

## Where it lives

- Default path: `~/.levi/soul.md`
- Per-machine: the file is read from the home directory of whoever runs
  LEVI. It is never synced, never uploaded, and never committed to the
  repo — what you write there stays on your machine.

## Managing it

```bash
levi soul              # show the path + current override (or "not set")
levi soul edit-note    # short reminder: edit the file with your own editor
```

There is deliberately no in-CLI editor. The soul is yours, plain text,
editable with whatever you trust — open `~/.levi/soul.md` and write.

Changes take effect on the next run; no restart or rebuild needed. A
missing, empty, or unreadable file behaves exactly like no soul at all —
LEVI never refuses to run because the file is broken.

## Example

```markdown
# Chauncey's LEVI

- Warm and direct. Never hedge with "as an AI"; just answer.
- Prefer short answers; expand only when asked.
- When I say "ship it", run the full test suite first, then commit.
- Never suggest cloud services before the local option — local-first is
  the whole point.
```

With that file in place, every system prompt the agent sees begins:

```
[Owner soul — ~/.levi/soul.md]
# Chauncey's LEVI
...

You are LEVI, a local-first Synthetic Intelligence (SI) assistant — ...
```

## Honest limits

- **It is a prompt prefix, not a separate identity system.** There is no
  soul engine, no memory of past souls, no arbitration between souls —
  just text stuck in front of the system prompt, marked so the model can
  see where the owner's words end and LEVI's built-in instructions begin.
- **It cannot override safety gates.** The soul text is prompt text; the
  tool-gating, confirmation, and no-live-trading discipline live in code
  underneath it and are not reachable from the file.
- **A malicious or broken soul.md only affects prompt text.** The worst a
  bad file can do is make LEVI talk strangely on this machine. It cannot
  execute anything, change tools, or leave the machine. If something
  weird is happening, rename the file and the weirdness is gone.
- **Other people, other souls.** Because it is read from `$HOME`, every
  user on a shared machine can have their own soul without touching
  anyone else's.
