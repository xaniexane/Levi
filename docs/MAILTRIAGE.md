# mailtriage — sovereign mail triage

## The giant pattern it inverts

Google built Inbox — snooze, bundles, smart reply — then killed it and
folded the features into Gmail, where the price of admission is being
scanned to train someone else's ad machine. The pattern: hold a beloved
capability hostage to surveillance.

**The remix:** the full triage surface runs against your OWN local
maildir/mbox, read-only, with zero network and zero accounts. Bundles are
readable local rules you can edit (not engagement classifiers). Snooze
state is inspectable JSON in `~/.levi/mailtriage`. Smart replies are
template drafts the user explicitly approves — rule-based, no model, and
labeled honestly.

## Usage

```
python -m levi.mailtriage --maildir ~/Maildir inbox
python -m levi.mailtriage --maildir ~/Maildir bundles
python -m levi.mailtriage --maildir ~/Maildir bundles newsletters
python -m levi.mailtriage snooze <message-id> --until "2026-09-20 09:00"
python -m levi.mailtriage snooze <message-id> --until-reply
python -m levi.mailtriage wake
python -m levi.mailtriage draft <message-id>
python -m levi.mailtriage save-draft <message-id> --index 0
python -m levi.mailtriage approve <draft-id>     # marks approved; never sends
```

Without `--maildir`/`--mbox`, the reader checks `~/Maildir`, `~/Mail`,
`~/.mail`, `~/mail` in order.

## Bundles

Default rules (`~/.levi/mailtriage/rules.json`, fully editable):

| bundle | rule |
|---|---|
| receipts | order/receipt/invoice/shipped/refund keywords |
| newsletters | List-Unsubscribe / List-ID headers |
| notifications | no-reply / notify / alerts senders |
| people | direct human mail (not list, not automated) |
| other | everything else |

## Snooze

- `snooze --until "YYYY-MM-DD HH:MM"` — hides until that local time.
- `snooze --until-reply` — hides until a reply from the sender is seen
  (best-effort Re:-subject detection; documented in code).
- `wake` clears due snoozes and lifts reply-snoozes.
- Snoozed mail is only *filtered from views*; your mail is never moved.

## Smart replies (templates, honest)

`suggest()` matches templates by keyword; `save-draft` stores a draft;
`approve` marks it approved and prints it. **This tool never sends mail.**
The approved text is for the user to paste into their own mail client.
Every draft carries the label `template-draft — NOT sent`.

## Safety lines

- The store reader is read-only: mutating mailbox methods are never called.
- Triage state lives separately under `~/.levi/mailtriage` (0700).
- No network. No accounts. No scanning of anything but your own mail,
  on your own disk, for your own triage.

## Honest gaps

- Reply-to-snooze detection is heuristic (Re: subjects); threads that
  change subject won't wake. `wake` is also a manual safety valve.
- mbox reading loads the whole box listing; very large mboxes are slow
  (no index yet — archived as a future improvement, not a blocker).
- No sending path exists by design; the approved draft is copy-paste.
