# red/grey batch-1 build provenance (2026-09-28/29)

How the first red-team (129) and grey-team (50) playbooks were authored.

- `topics_red1.py` … `topics_red7.py`: the 129 original red topic
  definitions (title, slug, risk, blue pairing, procedure outline).
- `topics_grey1.py` … `topics_grey3.py`: the 50 original grey topic
  definitions.
- `generate_playbooks.py`: renders the topic definitions into the final
  `core/levi/skill/playbooks/red/*.md` and `grey/*.md` files, enforcing
  the required frontmatter keys, filename-derived ids
  (`red_<slug>` / `grey_<slug>`), required sections, and the
  authorization/exercise guard footers.
- `resolve_pairings.py`: heuristic resolver that paired each red topic
  with an existing blue (cyber_*) skill, plus manual overrides for the
  ~41 weak heuristic matches.
- `pairings.json`: the final 129 red → blue pairings (`tests_blue`).
- `cyber_ids_extracted_2026-09-28.txt`: the extracted cyber skill-id set
  the pairings were resolved against (live corpus had ~100,823 ids;
  recount from the live corpus before reusing this snapshot).

All content is original work authored for LEVI from scratch. No external
repository was read, contacted, or copied during authoring. No
Dynasty/IP material.

Future batches: add new `topics_redN.py` / `topics_greyN.py` files and
re-run the generator + pairing resolver; the loaders
(`red_skills.py`, `grey_skills.py`) pick new files up dynamically, and
the test suite (`tests/test_red_grey_skills.py`) verifies the laws for
whatever is on disk.
