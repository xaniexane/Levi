# DDD daemon input queues

The two daily daemons read their work from CSV queues. **The queues start
empty and stay Chauncey's to fill.** A daemon never invents a row: with an
empty or missing queue it logs an honest "nothing to work" receipt and exits.

## Where the live queues go

```
~/workspace/ddd/queues/prospects.csv    ← audit-daemon reads this
~/workspace/ddd/queues/inventory.csv   ← listing-daemon reads this
~/workspace/ddd/queues/leads.csv       ← leads-daemon reads this
```

Copy the templates from `queue_templates/` (headers only, zero data rows)
and add real rows. One row per line, plain CSV.

## prospects.csv — audit-daemon (up to 3 rows/day)

| column       | meaning                                                        |
|--------------|----------------------------------------------------------------|
| business     | Business name, as Chauncey knows it                            |
| url          | The site's URL — **only sites Chauncey names get read**        |
| contact_name | Who to address the outreach draft to (optional)                |
| notes        | Anything the audit should know (optional)                      |

The daemon performs one polite info-only read per URL (page speed, SEO
basics, broken-link inventory, mobile) and drafts a finished $49 AuditNow
audit draft + an outreach draft per site. Drafts land in
`~/workspace/ddd-inbox/` and wait on Chauncey's word — nothing is sent.

## inventory.csv — listing-daemon (up to 5 rows/day)
| column      | meaning                                             |
|-------------|-----------------------------------------------------|
| item        | Item name                                           |
| description | Item description for the listing body               |
| keywords    | Search keywords, comma-separated                    |
| condition   | e.g. new, like new, used — drives pricing notes     |
| cost_basis  | What it cost, numeric (drives the pricing estimate) |
| photo_ref   | Reference to the item's photo (optional)            |

The daemon drafts marketplace listing copy + advisory pricing guidance
(labeled ESTIMATE) per item. Drafts land in `~/workspace/ddd-inbox/` and
wait on Chauncey's word — nothing is ever posted.

## leads.csv — leads-daemon (up to 5 rows/day)

| column       | meaning                                                  |
|--------------|----------------------------------------------------------|
| business     | Business name                                            |
| review_text  | The review text to answer (optional)                     |
| rating       | Star rating, numeric (drives reply tone; optional)       |
| source       | Where the review/lead was found (optional)               |
| contact_name | Who to address the pitch draft to (optional)             |
| notes        | Anything the draft should know (optional)                |

The daemon drafts a DRAFT-labeled review-reply response (hard rule: the
machine drafts, a human posts — never posted by the daemon) plus a
lead-gen pitch draft per row. Drafts land in `~/workspace/ddd-inbox/` and
wait on Chauncey's word — nobody is ever contacted.

## Honest zero-state

- Queue file missing → receipt `status: no-queue`.
- Queue present but zero data rows → receipt `status: empty-queue`.
- Either way: nothing drafted, nothing invented, receipt stored under
  `~/workspace/ddd/queues/.receipts/<daemon>-YYYY-MM-DD.json`.
