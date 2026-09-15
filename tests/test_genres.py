"""Genre gap closure: kernel registry <-> UI list <-> prose claims.

Blueprint §5.3 rule: never quote a prose number for the registry — load and
count programmatically. Every test below derives the expected values from the
real data; nothing asserts a hardcoded genre count.

Run:  python3 tests/test_genres.py     (has a real __main__ runner)
      python3 -m pytest tests/test_genres.py -q
"""

from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.graph.genres import GenreCategory, GenreRegistry  # noqa: E402

TS_GENRES = ROOT / "web" / "src" / "lib" / "levi" / "genres.ts"

# Files that state a genre count in prose. Every "N genre(s)" claim in these
# files must equal the real, counted registry size.
CLAIM_FILES = [
    ROOT / "core" / "levi" / "graph" / "genres.py",
    ROOT / "core" / "levi" / "graph" / "story_fabric.py",
    ROOT / "core" / "levi" / "brain" / "seed_hyperdrive.py",
    # NOTE: web/.../Onboarding.tsx was removed from this list 2026-09-15 — the
    # UI redesign no longer quotes a genre count in onboarding copy, so there
    # is no prose number to keep honest. Re-add it if a count returns.
    ROOT / "web" / "src" / "lib" / "levi" / "types.ts",
    ROOT / "web" / "src" / "lib" / "levi" / "local.ts",
    ROOT / "web" / "src" / "lib" / "levi" / "monetize.ts",
]

_TESTS = []


def genre_test(fn):
    _TESTS.append(fn)
    return fn


@genre_test
def test_registry_loads_and_counts():
    reg = GenreRegistry()
    counted = reg.count()
    assert counted == GenreRegistry.EXPECTED_COUNT, (
        f"registry count {counted} != EXPECTED_COUNT {GenreRegistry.EXPECTED_COUNT}"
    )
    assert counted > 0
    info = reg.integrity_check()
    assert info["ok"] is True, info
    assert info["actual"] == info["expected"] == counted
    print(f"  registry count: {counted}")


@genre_test
def test_ids_unique_and_resolvable():
    reg = GenreRegistry()
    ids = reg.ids()
    assert len(ids) == len(set(ids)) == reg.count()
    for gid in ids:
        g = reg.get(gid)
        assert g is not None, f"registry.get({gid!r}) returned None"
        assert g.id == gid
    assert reg.get("not_a_real_genre") is None
    print(f"  all {len(ids)} ids unique and resolve via get()")


@genre_test
def test_category_counts_sum_to_total():
    reg = GenreRegistry()
    cats = reg.categories()
    assert sum(cats.values()) == reg.count(), cats
    assert len(cats) == len(GenreCategory)
    print(f"  categories: {sorted(cats.items())}")


@genre_test
def test_section_comments_match_computed_counts():
    # The "# Core / classical (16)" style comments in genres.py are claims —
    # verify each against the real per-category counts, section order follows
    # _GENRE_TABLE order.
    from levi.graph.genres import _GENRE_TABLE

    src = (ROOT / "core" / "levi" / "graph" / "genres.py").read_text()
    table_src = src.split("_GENRE_TABLE")[1].split("class GenreRegistry")[0]
    claimed = [int(m.group(1)) for m in re.finditer(r"# .*\((\d+)\)", table_src)]
    reg = GenreRegistry()
    cats = reg.categories()
    seen = []
    for _gid, cat in _GENRE_TABLE:
        if cat.value not in seen:
            seen.append(cat.value)
    assert claimed, "no per-section count comments found — test needs updating"
    assert len(claimed) == len(seen), (
        f"{len(claimed)} section comments vs {len(seen)} categories"
    )
    for cat_value, n_claimed in zip(seen, claimed, strict=True):
        actual = cats[cat_value]
        assert actual == n_claimed, (
            f"category {cat_value}: comment says {n_claimed}, table has {actual}"
        )
    print(f"  {len(claimed)} section comments all match computed counts")


@genre_test
def test_ui_genre_list_matches_kernel_exactly():
    # The UI-facing genre list (web/src/lib/levi/genres.ts) must be a clean
    # subset of the kernel registry — in fact it must mirror it exactly.
    reg = GenreRegistry()
    kernel_ids = set(reg.ids())
    ts = TS_GENRES.read_text()
    genblock = ts.split("export const GENRES")[1]
    ui_ids = re.findall(r'id:\s*"([a-z_0-9]+)"', genblock)
    assert len(ui_ids) == len(set(ui_ids)), "duplicate ids in UI GENRES list"
    ui_set = set(ui_ids)
    missing_from_ui = sorted(kernel_ids - ui_set)
    extra_in_ui = sorted(ui_set - kernel_ids)
    assert not missing_from_ui, f"kernel genres absent from UI: {missing_from_ui}"
    assert not extra_in_ui, f"UI genres unknown to kernel: {extra_in_ui}"
    assert len(ui_set) == reg.count()
    print(f"  UI GENRES mirrors kernel: {len(ui_set)}/{reg.count()} ids identical")


@genre_test
def test_ui_category_labels_match_kernel():
    reg = GenreRegistry()
    ts = TS_GENRES.read_text()
    genblock = ts.split("export const GENRES")[1]
    pairs = re.findall(r'id:\s*"([a-z_0-9]+)",\s*category:\s*"([a-z_0-9]+)"', genblock)
    assert len(pairs) == reg.count(), f"parsed {len(pairs)} UI rows"
    for gid, cat in pairs:
        g = reg.get(gid)
        assert g is not None, gid
        assert g.category.value == cat, (
            f"{gid}: UI category {cat!r} != kernel {g.category.value!r}"
        )
    print(f"  all {len(pairs)} UI rows carry kernel-identical categories")


@genre_test
def test_ui_integrity_guard_matches_real_count():
    # genres.ts ships a runtime guard `if (GENRES.length !== N)` — the N it
    # bakes in must equal the real registry count.
    reg = GenreRegistry()
    ts = TS_GENRES.read_text()
    m = re.search(r"GENRES\.length !== (\d+)", ts)
    assert m, "UI integrity guard not found in genres.ts"
    guard_n = int(m.group(1))
    assert guard_n == reg.count(), (
        f"UI guard expects {guard_n}, registry has {reg.count()}"
    )
    print(f"  UI runtime guard ({guard_n}) == registry count")


@genre_test
def test_prose_claims_match_counted_number():
    # "NEVER quote a prose number" — every place that states a genre count
    # must state the real one.
    reg = GenreRegistry()
    n = reg.count()
    problems = []
    for path in CLAIM_FILES:
        assert path.exists(), f"claim file missing: {path}"
        text = path.read_text()
        found = [int(m.group(1)) for m in re.finditer(r"(\d+)[- ]genres?\b", text)]
        found += [int(m.group(1)) for m in re.finditer(r"(\d+) formal genres", text)]
        assert found, f"no genre-count claim left in {path.name} — test needs updating"
        for f in found:
            if f != n:
                problems.append(f"{path.name}: claims {f}, registry has {n}")
    assert not problems, "count claims disagree with registry:\n" + "\n".join(problems)
    print(f"  {len(CLAIM_FILES)} files all claim {n} — matches registry")


@genre_test
def test_cloud_model_reports_registry_derived_count():
    from levi.cloud.model import FullCloudModel

    out = FullCloudModel().genres_list()
    reg = GenreRegistry()
    expected_line = f"Genres: {reg.count()}/{GenreRegistry.EXPECTED_COUNT}"
    assert expected_line in out, out.splitlines()[0]
    assert "Integrity: OK" in out
    assert "core_classical" in out, "category breakdown silently missing again"
    print("  cloud model genres_list derives count from registry")


@genre_test
def test_story_fabric_rejects_unknown_genre():
    # The failure mode §5.3 bans: a genre the kernel lacks must not silently
    # fall back — story_fabric.create_story must refuse it loudly.
    from levi.graph.story_fabric import StoryFabric

    fab = StoryFabric()
    try:
        fab.create_story(premise="x", genre="eco_horror")
    except (ValueError, KeyError, AssertionError) as e:
        print(f"  unknown genre refused loudly ({type(e).__name__})")
        return
    raise AssertionError("create_story accepted an unknown genre without error")


def main() -> int:
    failures = 0
    print(f"genre gap-closure tests ({len(_TESTS)} tests)")
    for fn in _TESTS:
        name = fn.__name__
        try:
            fn()
        except AssertionError as e:
            failures += 1
            print(f"FAIL {name}: {e}")
        except Exception:
            failures += 1
            print(f"ERROR {name}:")
            traceback.print_exc()
        else:
            print(f"ok   {name}")
    print(f"\n{len(_TESTS) - failures}/{len(_TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
