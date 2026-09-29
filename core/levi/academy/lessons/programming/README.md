# Programming course — teachable academy layer

Chauncey's 14-lesson Python course, living natively inside LEVI as
structured, queryable lessons. The PDF
(`~/workspace/your_files/programming-full-course/programming-full-course.pdf`)
remains the readable edition under the nothing-thrown-away law; this
package is how LEVI teaches and queries the course through its own
commands.

## Files

- `lessons.json` — the 14 lessons in order: number, stable id slug,
  title, subtitle, core idea (his words), prose blocks, examples
  (code id, title, python/shell kind, code, stdin/args/files where the
  lesson needs them, captured output), exercises (the "your try" tasks
  with hints, plus the capstone's five exercises).
- `manifest.json` — provenance: generator version, source path +
  sha256 of the course source, per-lesson counts, directive.
- `build_programming_lessons.py` — deterministic builder. Pure
  extraction from the course source; reruns produce byte-identical
  `lessons.json`. Rebuild: `python3 build_programming_lessons.py`.
- `__init__.py` — loader: `load_lessons`, `syllabus`, `get_lesson`,
  `next_lesson`, `search`, `format_lesson`.
- `cli.py` — `levi academy programming ...` dispatch.

## Commands

```sh
levi academy programming                 # syllabus: the 14 lessons
levi academy programming lesson 3        # teach lesson 3 (or: lesson functions)
levi academy programming next            # next lesson from the start
levi academy programming next --after 5  # the lesson after lesson 5
levi academy programming search dict     # find lessons about dicts
python -m levi.academy programming lesson 14
```

## Laws

- **Originals first**: every word here is extracted from his 14 lessons.
  The builder never rewrites pedagogy.
- **Nothing thrown away**: the PDF and the course build source stay
  untouched; this layer is additive.
- **Law → guard → prove**: `tests/test_academy_programming.py` guards
  14 lessons in order, unique ids, examples/outputs/exercises intact,
  builder determinism, and the CLI surface.
