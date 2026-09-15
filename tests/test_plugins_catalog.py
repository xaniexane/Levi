"""Tests for the plugin catalog read-model (levi.plugins.catalog).

The catalog is the view the ``levi plugins`` and ``levi symbiosis
--orphans`` commands read. Regression anchor: both commands used to die
with ``ModuleNotFoundError: No module named 'levi.plugins.catalog'``
because the module was referenced but never built.
"""

import subprocess
import sys
from pathlib import Path

# Repo-relative import of the uninstalled core package (mirrors
# tests/test_genres.py) so `python3 tests/test_plugins_catalog.py` works.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "core") not in sys.path:
    sys.path.insert(0, str(_ROOT / "core"))

from levi.plugins.catalog import CatalogEntry, PluginCatalog  # noqa: E402

ROOT = _ROOT
CLI = [sys.executable, "-m", "levi.cli.main"]


def _cli(*args, env=None):
    import os

    e = dict(os.environ)
    e["PYTHONPATH"] = str(ROOT / "core") + os.pathsep + e.get("PYTHONPATH", "")
    if env:
        e.update(env)
    return subprocess.run(
        [*CLI, *args], capture_output=True, text=True, env=e, timeout=60
    )


def test_catalog_lists_registered_connectors():
    entries = PluginCatalog().list()
    assert entries, "catalog is empty — registry has no connectors"
    assert all(isinstance(e, CatalogEntry) for e in entries)
    ids = [e.id for e in entries]
    assert len(ids) == len(set(ids)), "duplicate connector ids in catalog"
    assert "github" in ids


def test_catalog_entries_carry_required_fields():
    for e in PluginCatalog().list():
        assert e.id and e.display_name and e.credential_env_var
        assert isinstance(e.requires_confirmation, bool)


def test_catalog_format_is_human_readable():
    text = PluginCatalog().format()
    assert "github" in text.lower()
    assert "GITHUB_TOKEN" in text  # names the credential env var, never its value


def test_catalog_format_unknown_category_is_honest():
    text = PluginCatalog().format(category="no_such_category")
    assert "no_such_category" in text


def test_cli_plugins_command_runs():
    proc = _cli("plugins")
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "github" in proc.stdout.lower()
    assert "Traceback" not in proc.stderr


def test_cli_symbiosis_orphans_runs():
    proc = _cli("symbiosis", "--orphans")
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "Traceback" not in proc.stderr


if __name__ == "__main__":
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    print(f"plugin catalog tests ({len(fns)} tests)")
    for fn in fns:
        try:
            fn()
        except Exception:
            failures += 1
            print(f"FAIL {fn.__name__}:")
            traceback.print_exc()
        else:
            print(f"ok   {fn.__name__}")
    print(f"\n{len(fns) - failures}/{len(fns)} passed")
    sys.exit(1 if failures else 0)
