# INCOME BATCH C — Audit Services (slots 41–52)

Twelve original, from-scratch, stdlib-only automated income generators.
Each audits a **user-supplied local path** (`params["target"]`) and writes
a real findings report (`report.md` + `summary.json`) under
`<levi_home>/.levi/income/work/<id>/`.

Defensive / blue-team only: the scanners **report, never exploit**.
No network calls, no paid APIs, no third-party code. Income is never
recorded by the generators — `run()` returns a `WorkReport` with a
quoted price (pricing advice only); Chauncey records income via
`engine.record_income(basis="confirmed")`.

Module: `core/levi/income/gen_audits.py` · tests:
`tests/test_income_audits.py` (23 tests).

## The 12 generators

| Slot | ID | Entry price | What it does | What it earns |
|---|---|---|---|---|
| 41 | `seo-basics-scanner` | $3.00 | Scans local HTML for SEO fundamentals: `<title>`, meta description, viewport, single `<h1>`, heading-order skips, image alts. Scored /100. | Site owners pay for a pre-launch SEO checklist; agencies resell it per-client. |
| 42 | `accessibility-spotter` | $3.00 | Flags common a11y issues: missing alts, unlabelled inputs, empty buttons/links, heading skips, missing `lang`. Honest static-heuristic caveat. | Accessibility audits are compliance-adjacent work; small shops charge per page. |
| 43 | `broken-link-hunter` | $3.50 | Finds broken **internal** links across local HTML docs: missing files and dangling `#fragment` anchors. External URLs out of scope. | Docs teams / static-site owners pay for link-rot sweeps before releases. |
| 44 | `readme-health-auditor` | $2.00 | Scores README completeness (title, install, usage, config, contributing, license, badges, code samples…) /100. | Open-source maintainers and freelancers sell "first-impression" polish. |
| 45 | `dependency-hygiene-reporter` | $2.50 | Pinned (`==`) vs floating (`>=`, bare) deps from `requirements*.txt`. Flags reproducibility risk. | DevOps-lite report sold to teams fighting "works on my machine". |
| 46 | `backup-readiness-auditor` | $3.00 | Backup gaps: files ≥10 MiB, missing manifests, total footprint. Readiness score /100. | Peace-of-mind report for creators/small businesses with no backup plan. |
| 47 | `secrets-surface-reporter` | $4.00 | **Defensive** scan for exposed secret patterns (keys, tokens, `password=` assignments). Reports file+line+pattern only — values are never stored or exfiltrated. | Highest-value item: pre-commit / pre-publish secret sweeps for teams. |
| 48 | `doc-coverage-reporter` | $3.00 | Undocumented public functions/classes/methods in Python files (AST-based), per-file and overall docstring coverage %. | Sold to maintainers and as a CI-adjacent quality gate. |
| 49 | `todo-debt-collector` | $2.00 | Harvests TODO/FIXME/HACK/XXX/BUG markers into a P1/P2/P3 prioritized tech-debt report. | Teams pay for a debt inventory before planning sprints. |
| 50 | `git-hygiene-reporter` | $3.50 | Commit/branch hygiene from git history: weak-message detection, branch inventory, hygiene score /100. | Engineering leads buy hygiene reports for onboarding/audit. |
| 51 | `license-header-auditor` | $2.50 | Inventories license headers (SPDX, copyright, license blocks) across a project; lists files with gaps. | Compliance-adjacent; open-source projects need this before release. |
| 52 | `perf-checklist-generator` | $3.00 | Static performance checklist for a static-site dir: oversized images, external/render-blocking scripts, inline styles, total weight. | Sold to static-site owners; pairs with the SEO scanner as a bundle. |

## Honest limits

- **Static heuristics, not ground truth.** The SEO/a11y/perf scanners parse
  markup; they cannot run a page, measure Core Web Vitals, or test with
  assistive technology. Reports say so.
- **Local only.** Every generator needs a local path; nothing is fetched
  from the web. `broken-link-hunter` checks internal links only.
- **The secrets scanner is defensive.** It reports *where* secret-shaped
  patterns live; it never captures values, never phones home, never
  attempts use. Rotate anything real, move secrets to a vault.
- **Prices are quotes, not sales.** Every `WorkReport.quoted_amount_usd`
  is pricing advice inside the $1–5 doctrine band. The engine records
  income only on Chauncey's explicit `basis="confirmed"`.
- **Dry runs are clean.** `dry_run=True` computes everything but writes no
  report files (the engine's run log is the only write).
