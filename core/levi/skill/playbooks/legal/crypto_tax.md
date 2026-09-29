---
skill_id: legal_crypto_tax
name: Crypto and Digital-Asset Taxation
description: IRS property treatment of virtual currency, taxable events, staking/mining income, and broker reporting duties.
category: legal
risk: moderate
permissions: []
requires_confirmation: false
jurisdiction: [US-federal]
sources: [https://www.irs.gov/newsroom/frequently-asked-questions-on-virtual-currency-transactions, https://www.law.cornell.edu/uscode/text/26/6045]
requires_attorney_review: true
disclaimer_version: 1.0
last_verified: 2026-09-28
tags: [tax, crypto, nft, virtual-currency, irs]
version: 1.0.0
---

> **General legal information — not legal advice.** This playbook is educational
> material about US federal tax treatment of digital assets. It is not legal or
> tax advice, creates no professional relationship, and does not substitute for
> a licensed attorney or CPA. Crypto tax rules are actively evolving — verify
> current guidance before filing.

# Crypto and Digital-Asset Taxation

## Purpose

State the IRS framework for taxing virtual currency and NFTs plainly:
what counts as a taxable event, how gains are measured, how staking and
mining rewards are treated, and what the broker-reporting rules require.
NFT sale proceeds, treasury operations, and token distributions all land
inside this framework.

## The doctrine

- **Property, not currency.** Under IRS Notice 2014-21, convertible
  virtual currency is treated as *property* for federal tax purposes.
  General tax principles for property transactions apply.
- **Taxable events** include: selling crypto for fiat, trading one
  digital asset for another, and spending crypto on goods or services.
  Each disposition requires computing gain or loss against basis.
  Merely buying and holding, or transferring between your own wallets,
  is not a taxable event.
- **Character of gain:** held over a year → long-term capital treatment;
  a year or less → short-term (ordinary rates). Basis is generally cost;
  gifted or inherited digital assets carry the donor/decedent basis
  rules of property generally.
- **Staking rewards and mining:** the IRS treats staking rewards as
  gross income when the taxpayer gains dominion and control (see IRS
  guidance following *Jarrett*-era litigation and Rev. Rul. 2023-14);
  mining rewards are ordinary income at fair market value on receipt,
  with self-employment tax implications for trade-or-business miners.
- **NFTs:** sale of an NFT you created is generally ordinary income
  (like selling inventory or services); resales of purchased NFTs are
  capital dispositions. Royalty streams are ordinary income.
- **Broker reporting (§ 6045, as amended):** digital-asset brokers face
  information-reporting obligations (Form 1099-DA framework); the
  regulatory scope and timelines have been phased — check current IRS
  implementation status rather than assuming the original effective dates.
- **Recordkeeping is the real compliance burden.** Every trade, swap,
  and spend needs date, fair-market value, and basis. Exchanges'
  records are incomplete; the taxpayer owns the ledger.

## Checklist

1. **Classify every event.** Disposition vs. non-event; income vs.
   capital; short vs. long term.
2. **Track basis relentlessly.** One ledger for all wallets and
   exchanges; consistent accounting method (FIFO is the default
   assumption — specific identification requires adequate records).
3. **Report staking/mining as ordinary income** at receipt value; set
   aside estimated tax quarterly.
4. **Treat NFT primary sales as ordinary income** if you are the
   creator; track royalties as received.
5. **Check broker-reporting status** for any platform you use — but do
   not assume a 1099 arriving means your records are complete.
6. **Disclose foreign holdings properly** if thresholds apply (FBAR/
   FATCA analysis for foreign exchange accounts is fact-specific —
   get professional advice).

## Red flags

- "Crypto isn't taxed until I cash out to dollars" — every crypto-to-
  crypto trade is already a taxable disposition.
- No records beyond exchange CSVs — insufficient for basis defense.
- Treating staking rewards as non-taxable until sale.
- Assuming NFT creator proceeds are capital gains — generally ordinary.
- Relying on a tax tool's output without understanding its accounting
  method assumptions.

## Authorities

- IRS virtual-currency FAQs:
  https://www.irs.gov/newsroom/frequently-asked-questions-on-virtual-currency-transactions
- IRS Notice 2014-21 (PDF): https://www.irs.gov/pub/irs-drop/n-14-21.pdf
- 26 U.S.C. § 6045 (broker returns):
  https://www.law.cornell.edu/uscode/text/26/6045
- IRS digital-asset guidance hub: https://www.irs.gov/businesses/small-businesses-self-employed/digital-assets
