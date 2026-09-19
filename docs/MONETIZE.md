# LEVI Monetization Modules (`levi.monetize`)

Twelve concrete, LEVI-native income modules adapted from the 12
semi-automated income concepts. Every module is original code — the
concepts are adapted, never copied.

## Design rules

- **Clear income mechanism** per module (who pays, for what, how much).
- **Offline-first**: every module has genuinely useful local tooling
  (quoting, margin math, templates, blueprints) that runs with stdlib only.
- **Receipted**: every earning action writes a receipt to the shared
  JSONL ledger at `~/.levi/monetize/income.jsonl` (append-only, 0o600).
- **Risk-banded**: low (paid-upfront client service), medium (recurring /
  operational), elevated (platform- or traffic-dependent).
- **Chauncey-gated**: anything needing his accounts, credentials,
  identity, or client-facing approval is an explicit gated step —
  stubbed and listed, never silently performed. LEVI never invents income.

## The 12 modules (`core/levi/monetize/projects/`)

| # | Slug | Module | Mechanism | Risk |
|---|------|--------|-----------|------|
| 1 | `resume-service` | Document Polish Service | per-order packages ($15/$30/$50) | low |
| 2 | `social-media` | Social Media Management | monthly retainers ($100/$175/$275) | medium |
| 3 | `print-on-demand` | Print-on-Demand Storefront | per-unit margin over base cost | elevated |
| 4 | `kdp-publishing` | Self-Published Books | per-sale royalties, catalog compounds | elevated |
| 5 | `youtube-faceless` | Faceless Video Channel | ad revenue per 1k views post-threshold | elevated |
| 6 | `chatbot-service` | Chatbot Building Service | setup fee + monthly retainer | medium |
| 7 | `lead-generation` | Local Lead Generation | per-qualified-lead fees ($25-$300) | medium |
| 8 | `newsletter` | Newsletter Business | sponsors + affiliates by subscriber tier | elevated |
| 9 | `data-scraping` | Data Collection Service | per-job + weekly refresh contracts; defensive guards | medium |
| 10 | `whatsapp-automation` | WhatsApp Business Automation | setup + retainer; optional resell margin | medium |
| 11 | `podcast-notes` | Podcast Show Notes Service | per-episode ($15/$25/$40) + retainers | low |
| 12 | `business-plans` | Business Plan & Pitch Deck Service | per-plan ($75-$250) + deck add-on | low |

## CLI

```bash
PYTHONPATH=core python3 -m levi.monetize list
PYTHONPATH=core python3 -m levi.monetize show resume-service
PYTHONPATH=core python3 -m levi.monetize checklist lead-generation
PYTHONPATH=core python3 -m levi.monetize log --project resume-service --kind sale \
    --amount 30 --counterparty "A. Client" --note "standard package"
PYTHONPATH=core python3 -m levi.monetize summary
PYTHONPATH=core python3 -m levi.monetize recent --limit 10
```

## Defensive posture (project 09)

The data-collection module refuses by default: forbidden field names
(passwords, SSNs, card numbers, API keys...) are a hard refusal,
`robots.txt` is checked before any job is accepted, and any unreachable
robots.txt is treated as disallow until Chauncey approves. Public
business data only.

## What is NOT built here

Marketplace listings, store/account creation, ad spend, publishing
under Chauncey's identity, and anything touching real customer data —
all explicit Chauncey-gated steps per module (`PROJECT["chauncey_gated"]`,
`setup_checklist()`).
