# Editions Ring Policy (open creational ring)

All under OMEGA Powered by Alpha. Levi heads all; Levi is the blueprint
that outlives them.

## The three rings

**Open creational.** Bare-minimal source: structure + architecture only.
This directory (`schema/`), the manifest and ring modules, the design
doc, and this policy. Outside minds run free: author editions, propose
rosters, build integrations, send plans back upstream. What never
ships here: agent implementations, curated sector rosters, sector
workflows, proprietary prompts, weights, the crown jewels.

**Closed.** The diehard developers and the keeper. Full source: the
edition catalog (`catalog.py`), the 471-agent catalog, the original
stack. The crown jewels never leave.

**Government.** Political and security-grade AI and SI. Everything in
the closed ring, plus the twelve-gate hardening checklist
(`rings.py:GOVERNMENT_HARDENING_CHECKLIST`). Hardened, auditable,
sovereign. The bar is public; the builds that clear it are not.

## Rules

1. An edition is a team template, not a separate product.
2. Editions never train on sector data. This is enforced in code and
   sold as the feature.
3. Every edition names what it deliberately refuses to include, and why.
   A refusal without a reason is not a refusal.
4. Safety boundary is absolute: defensive / authorized purple-team only.
   No offensive capability ships in any ring, ever.
5. Roster slots select by category, never by raw agent id, so catalog
   re-stamping never breaks an edition.
6. The proving bar follows every edition: green, lawful, keeper-reviewed.
