"""Live CLI regression: all ten ``levi king`` surfaces from a clean HOME.

Hermetic: every run gets a fresh HOME; subprocesses inherit PYTHONPATH
from conftest like tests/test_cli.py does.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _env(home: str):
    env = dict(os.environ)
    env["HOME"] = home
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "core"), *sys.path])
    # keep the sandbox clean of stray config
    env.pop("LEVI_GITHUB_TOKEN", None)
    return env


def _run(home: str, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "levi.cli.main", *argv],
        cwd=ROOT,
        env=_env(home),
        capture_output=True,
        text=True,
        timeout=120,
    )


def _review_id(output: str) -> str:
    m = re.search(r"review id:\s*(\S+)", output)
    assert m, f"no review id in output:\n{output}"
    return m.group(1)


def test_king_all_ten_surfaces():
    with tempfile.TemporaryDirectory(prefix="king_cli_") as home:
        # 1. status (fresh HOME)
        p = _run(home, "king", "status")
        assert p.returncode == 0, p.stderr
        assert "rank=D2" in p.stdout

        # 2. pulse with no stories -> guidance, no auto-create
        p = _run(home, "king", "pulse")
        assert p.returncode == 0, p.stderr
        assert "story --create" in p.stdout

        # create a story, then pulse harvests
        p = _run(home, "story", "--create", "A lighthouse keeps the last signal.",
                 "--genre", "literary")
        assert p.returncode == 0, p.stderr
        p = _run(home, "king", "pulse")
        assert p.returncode == 0, p.stderr
        assert "bank(s) harvested" in p.stdout

        # 3. manuscript (model engine)
        p = _run(home, "king", "manuscript")
        assert p.returncode == 0, p.stderr
        assert "harvested:" in p.stdout

        # ledger now aggregates both engines
        p = _run(home, "king", "status")
        assert "rank=D2" in p.stdout  # small totals stay D2
        assert "harvest story_fabric" in p.stdout
        assert "harvest model_engine" in p.stdout

        # 4. social -> queued pending pack
        p = _run(home, "king", "social", "--platform", "x")
        assert p.returncode == 0, p.stderr
        assert "queued for review" in p.stdout
        rid = _review_id(p.stdout)

        # 5a. pending pack + --yes -> approval gate refuses, exit 1
        p = _run(home, "king", "social-post", "--id", rid, "--yes")
        assert p.returncode == 1, p.stdout
        assert "approve it first" in (p.stdout + p.stderr)

        # approve, then WITHOUT --yes -> confirmation gate refuses, exit 2
        p = _run(home, "king", "approve", rid)
        assert p.returncode == 0, p.stderr
        p = _run(home, "king", "social-post", "--id", rid)
        assert p.returncode == 2, p.stdout
        assert "requires explicit confirmation" in (p.stdout + p.stderr)

        # 5b. approved + --yes -> loopback success
        p = _run(home, "king", "social-post", "--id", rid, "--yes")
        assert p.returncode == 0, (p.stdout + p.stderr)
        assert "loopback" in p.stdout.lower()

        # 6. reim pass-through
        p = _run(home, "king", "reim", "--tracks", "2", "--seed", "a fork")
        assert p.returncode == 0, p.stderr
        assert "REIM" in p.stdout

        # 7/8. deny + approve pass-throughs (a scene exists from manuscript)
        p = _run(home, "king", "deny")
        assert p.returncode == 0, p.stderr
        assert "Denied" in p.stdout
        p = _run(home, "king", "manuscript", "--scenes", "1")
        assert p.returncode == 0, p.stderr
        p = _run(home, "king", "approve")
        assert p.returncode == 0, p.stderr
        assert "Approved" in p.stdout

        # 9. rupture pass-through
        p = _run(home, "king", "rupture", "--lens", "mccarthy")
        assert p.returncode == 0, p.stderr
        assert "Wyrd-Rupture" in p.stdout

        # 10. d5 promotion, then reset
        p = _run(home, "king", "d5")
        assert p.returncode == 0, p.stderr
        assert "D5 baseline promotion" in p.stdout
        p = _run(home, "king", "status")
        assert "PROMOTED" in p.stdout
        p = _run(home, "king", "d5", "--reset")
        assert p.returncode == 0, p.stderr
        assert "cleared" in p.stdout


def test_king_help_lists_all_ten():
    with tempfile.TemporaryDirectory(prefix="king_cli_") as home:
        p = _run(home, "king", "--help")
        assert p.returncode == 0, p.stderr
        for action in ("status", "pulse", "manuscript", "social", "social-post",
                       "reim", "deny", "approve", "rupture", "d5"):
            assert action in p.stdout, f"{action} missing from king --help"
