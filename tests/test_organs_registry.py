"""Hermetic tests for the organ registry (deny-closed dispatch).

No network, no HOME writes. Verifies all four organs are listed, unknown
names are denied, and importing the registry never pulls in organ modules.
"""

import sys

import pytest

from levi.organs.registry import (
    ORGAN_REGISTRY,
    list_organs,
    run_organ,
)


class TestRegistryContents:
    def test_all_four_organs_listed(self):
        assert set(ORGAN_REGISTRY) == {
            "echoverse", "mandella", "reim", "riem",
        }

    def test_registry_shape(self):
        for name, meta in ORGAN_REGISTRY.items():
            assert set(meta) == {"entry", "describe", "risk"}, name
            assert meta["entry"].startswith("levi.organs.")
            assert meta["risk"] == "low"
            assert isinstance(meta["describe"], str) and meta["describe"].strip()

    def test_list_organs(self):
        organs = list_organs()
        assert {o["name"] for o in organs} == set(ORGAN_REGISTRY)
        for o in organs:
            assert set(o) == {"name", "entry", "describe", "risk"}

    def test_echoverse_maps_to_run_echo(self):
        assert ORGAN_REGISTRY["echoverse"]["entry"] == "levi.organs.echo:run_echo"
        assert "echoverse.py" not in ORGAN_REGISTRY["echoverse"]["entry"]
        assert "no separate" in ORGAN_REGISTRY["echoverse"]["describe"].lower() or \
               "do not" in ORGAN_REGISTRY["echoverse"]["describe"].lower()


class TestDenyClosed:
    @pytest.mark.parametrize("bad", [
        "graph", "echoverse2", "", "ECHO", None, 42, "reim ",
    ])
    def test_unknown_organ_denied(self, bad):
        with pytest.raises(ValueError):
            run_organ(bad)


class TestLazyImports:
    def test_import_registry_adds_no_new_organ_modules(self):
        # Run in a subprocess: levi.organs.__init__ itself imports echo and
        # mandella (pre-existing; additive-only forbids touching it), so the
        # checkable guarantee is: importing the registry module itself adds
        # no further organ modules beyond what the package import loads.
        import subprocess

        code = (
            "import sys; "
            "import levi.organs; "
            "before = set(sys.modules); "
            "import levi.organs.registry; "
            "new = sorted(m for m in sys.modules if m not in before); "
            "organs = [m for m in new if m.startswith('levi.organs.') "
            "and m != 'levi.organs.registry']; "
            "print(','.join(organs) if organs else 'clean')"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, cwd="/home/hatch/workspace/levi/core",
            timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        got = proc.stdout.strip()
        assert got == "clean", got

    def test_registry_has_no_module_level_organ_imports(self):
        # registry.py must resolve entries lazily inside functions.
        import ast
        from pathlib import Path

        src = Path("core/levi/organs/registry.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for name in getattr(node, "names", []):
                    target = name.name
                    assert not target.startswith("levi.organs.echo"), target
                    assert not target.startswith("levi.organs.mandella"), target
                    assert not target.startswith("levi.organs.reim"), target
                    assert not target.startswith("levi.organs.riem"), target

    def test_run_organ_dispatches(self):
        result = run_organ("echoverse", seed="hello", cycles=1)
        assert result["organ"] == "echo"
        assert result["seed"] == "hello"

        result = run_organ("mandella", domain="security", seed="x")
        assert result["organ"] == "mandella"

        result = run_organ(
            "reim",
            record={
                "source": "ci",
                "what": "job timed out waiting on queue",
                "context": "release window",
                "ts": "2026-09-15T19:00:00Z",
                "severity": "high",
            },
        )
        assert result["organ"] == "reim"
        assert result["compost_class"] == "resource-exhaustion"

        result = run_organ("riem", compost_records=[result])
        assert len(result) == 1
        assert result[0]["applied"] is False


class TestCli:
    def test_cli_list(self, capsys):
        from levi.organs.__main__ import main

        assert main(["list"]) == 0
        out = capsys.readouterr().out
        for name in ("echoverse", "mandella", "reim", "riem"):
            assert name in out

    def test_cli_run_json(self, capsys):
        import json

        from levi.organs.__main__ import main

        assert main(["run", "mandella", "--domain", "build", "--json"]) == 0
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload["organ"] == "mandella"

    def test_cli_unknown_organ_fails(self):
        from levi.organs.__main__ import main

        assert main(["run", "graph"]) == 2

    def test_cli_bad_kwargs_json(self):
        from levi.organs.__main__ import main

        assert main(["run", "reim", "--kwargs-json", "{not json"]) == 2
