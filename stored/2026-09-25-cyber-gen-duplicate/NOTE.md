# Duplicate dimension file — relocated, not deleted

- Moved from: `core/levi/skill/cyber_gen/dimensions_scenarios_b.py`
- When: 2026-09-25, by the 🛡️ cyber-skills worker, minutes after creation.
- Why: it duplicated scenarios 26–50 already present as `SCENARIOS_B` in
  `core/levi/skill/cyber_gen/dimensions_scenarios_a.py` (verified: 50 unique
  scenario slugs across SCENARIOS_A + SCENARIOS_B, matching the 50-scenario plan).
- Nothing else was in the file; no other work depends on it.
- Kept under the nothing-thrown-away law.
