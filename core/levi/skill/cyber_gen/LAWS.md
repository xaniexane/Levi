# Batch-3 Generator Laws — 100,000 cyber playbooks

Standing laws for the combinatorial generation of `playbooks/cyber/*.md`
(scenarios x assets x environments x tiers = 50 x 40 x 10 x 5 = 100,000).

## Content laws

1. **Original defensive work only.** Every word is authored for LEVI, blue-team
   lens: detection, analysis, hardening. The source repo
   (github.com/mukul975/Anthropic-Cybersecurity-Skills) is never fetched,
   read, or copied — topics are invented originals, zero contact.
2. **No offensive tradecraft.** No exploit code, payload generators,
   step-by-step attack instructions, or zero-day material. Markers from the
   test suite (`exploit code`, `payload generator`, `step-by-step attack`,
   `zero-day exploit`) must not appear outside explicit prohibitions.
3. **Every file stands alone.** Each playbook is a usable runbook: concrete
   artifact paths, real commands, named log sources and event IDs, specific
   hardening actions. No lorem ipsum, no empty "insert detail here" templates.
4. **Composition is real content.** Each dimension (scenario, asset,
   environment, tier) contributes substantive, dimension-specific prose. The
   assembled playbook must read as one coherent playbook, not four stapled
   paragraphs.

## Identity laws

5. **Deterministic.** Same code + same dimension data = byte-identical output,
   every run. No randomness, no timestamps in content, no network calls.
6. **Unique slugs.** `slug = scenario-asset-environment-tier`; every
   dimension value has a globally unique slug fragment, so all 100,000
   (`skill_id = cyber_` + slug with underscores) are unique by construction.
   The generator also enforces uniqueness with a set and fails on collision.
7. **Filenames match skill_load.** `[A-Za-z0-9_-]+\.md`; `skill_id` equals
   `cyber_` + stem with `-` replaced by `_`.
8. **Frontmatter contract.** All nine keys present: skill_id, name,
   description, risk, permissions, requires_confirmation, tags, version.
   `version: 1.0.0`. Risk in {info, low, moderate, high, critical}.

## Quality laws (mirror the test suite)

9. **Required sections.** `## Purpose`, `## When to use`, `## Prerequisites`,
   `## Procedure`, `## Expected outputs`, `## Pitfalls`, `## References`
   (plus `## Key tools & commands`). Missing section = generation failure.
10. **Procedure depth.** >= 5 numbered steps (generator targets >= 8).
11. **Substance floor.** Handler output (full file text) >= 1000 chars and
    contains the playbook title. Generator targets ~1600-2400 chars of dense,
    terse, usable prose — every line earns its place (disk is scarce).
12. **Risk gating.** Any playbook with risk `moderate` MUST carry
    `requires_confirmation: true`. Moderate is reserved for scenarios
    involving live evidence acquisition or active containment.
13. **Provenance footer.** Every file ends with the original-work footer.

## Performance laws

14. **CLI startup stays fast.** Registration reads a precomputed manifest
    (`cyber_index.jsonl`), never 100k frontmatter parses at import. Manifest
    is validated against the file count (fast glob); on mismatch the loader
    falls back to a full directory scan (slow but correct).
15. **Handlers stay lazy.** Skill handlers read the playbook file on invoke,
    not at registration.

## Process laws

16. **Validate at generation time.** Every generated string is validated in
    memory BEFORE writing: frontmatter parse, all sections present, step
    count, length floor, offensive-marker scan, id/filename agreement,
    uniqueness. Any failure aborts the run loudly.
17. **Tests sample deterministically.** The suite validates the full manifest
    and deep-checks a deterministic index-based sample of files (no RNG).
18. **Commits stay local, temp-index route only.** Never amend, never touch
    siblings' files, never delete. `git show --stat` after every commit.
19. **Honest counts.** Report only measured numbers: test output, file counts,
    byte sizes. Never estimate.
