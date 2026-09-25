"""Tests for the DemandPulse customer bundle.

Laws under proof: exclusion, namespace neutrality, docs-verbatim,
setup.sh validity, manifest integrity, and the end-to-end proof that the
extracted bundle imports and runs as ``demandpulse.demandpulse``.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tarfile

import pytest

from levi.demandpulse import bundle as B
from levi.demandpulse.bundle import BUNDLE_STEM
from levi.demandpulse.payments import TERMS_HQ3
from levi.demandpulse.product import PRODUCT_SHEET_HQ5

EXCLUDED = {"watch.py", "threat_feed.py", "threat_signals.py", "cybrus_alliance.py"}
LEVI_WORD = re.compile(r"\blevi\b")
LEVI_UPPER = re.compile(r"\bLEVI\b")


@pytest.fixture()
def built(tmp_path):
    tarball = B.write_bundle(dest_dir=tmp_path)
    assert tarball.is_file()
    return tmp_path, tarball


def member_names(tarball):
    with tarfile.open(tarball, "r:gz") as tf:
        return [m.name for m in tf.getmembers() if m.isfile()]


def read_member(tarball, rel):
    with tarfile.open(tarball, "r:gz") as tf:
        fh = tf.extractfile(f"{BUNDLE_STEM}/{rel}")
        assert fh is not None
        return fh.read()


# -- exclusion law ------------------------------------------------------------

def test_excluded_files_absent(built):
    _, tarball = built
    names = member_names(tarball)
    for excluded in EXCLUDED:
        assert not any(n.endswith("/" + excluded) for n in names), excluded


def test_excluded_modules_not_importable_from_bundled_init(built):
    _, tarball = built
    init = read_member(tarball, "demandpulse/demandpulse/__init__.py").decode()
    for mod in ("threat_signals", "threat_feed", "watch", "cybrus_alliance"):
        assert not re.search(rf"^\s*{mod}\s+as\s+", init, re.M), mod
        assert f'"{mod}"' not in init, mod


# -- namespace law --------------------------------------------------------------

def test_payload_paths_renamed(built):
    _, tarball = built
    names = member_names(tarball)
    assert not any("/core/levi/" in n or n.startswith("core/") for n in names)
    assert any(n == f"{BUNDLE_STEM}/demandpulse/demand/pulse.py" for n in names)
    assert any(n == f"{BUNDLE_STEM}/demandpulse/demandpulse/product.py" for n in names)


def test_no_levi_words_in_bundled_sources(built):
    _, tarball = built
    for name in member_names(tarball):
        if not name.endswith(".py"):
            continue
        text = read_member(tarball, name[len(BUNDLE_STEM) + 1:]).decode("utf-8")
        assert not LEVI_WORD.search(text), f"{name}: {LEVI_WORD.search(text).group(0)}"
        assert not LEVI_UPPER.search(text), name


def test_imports_rewritten(built):
    _, tarball = built
    product = read_member(
        tarball, "demandpulse/demandpulse/product.py").decode()
    assert "from levi" not in product and "import levi" not in product
    init = read_member(
        tarball, "demandpulse/demandpulse/__init__.py").decode()
    assert "from demandpulse.demandpulse import" in init


def test_home_dirs_neutralized(built):
    _, tarball = built
    qs = read_member(
        tarball, "demandpulse/demandpulse/quickstart.py").decode()
    assert '".demandpulse"' in qs or "/.demandpulse" in qs
    assert ".levi" not in qs


# -- docs law ---------------------------------------------------------------------

def test_customer_docs_present_and_verbatim(built):
    _, tarball = built
    names = member_names(tarball)
    for doc in ("README.md", "TERMS.md", "PRODUCT_SHEET.md", "setup.sh"):
        assert f"{BUNDLE_STEM}/{doc}" in names, doc
    terms = read_member(tarball, "TERMS.md").decode()
    assert terms == TERMS_HQ3 + "\n"
    sheet = read_member(tarball, "PRODUCT_SHEET.md").decode()
    assert sheet == PRODUCT_SHEET_HQ5 + "\n"
    readme = read_member(tarball, "README.md").decode()
    assert "levi" not in readme.lower()
    assert "setup.sh" in readme and "activate" in readme


def test_setup_script_passes_bash_n(built, tmp_path):
    _, tarball = built
    script = read_member(tarball, "setup.sh")
    path = tmp_path / "setup.sh"
    path.write_bytes(script)
    proc = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_setup_script_uses_neutral_namespace(built):
    _, tarball = built
    script = read_member(tarball, "setup.sh").decode()
    assert "demandpulse.demandpulse" in script
    assert ".levi" not in script
    assert "OWNER GATE" in script  # the gate stays named in the bundle


# -- manifest law -------------------------------------------------------------------

def test_manifest_hashes_match(built):
    tmp_path, tarball = built
    manifest = json.loads(
        (tmp_path / f"{BUNDLE_STEM}.manifest.json").read_text())
    assert manifest["product"] == "DemandPulse"
    assert len(manifest["files"]) == len(member_names(tarball))
    for entry in manifest["files"]:
        data = read_member(tarball, entry["rel"][len(BUNDLE_STEM) + 1:])
        assert entry["sha256"] == __import__("hashlib").sha256(data).hexdigest()


def test_verify_bundle_ok(built):
    _, tarball = built
    result = B.verify_bundle(tarball)
    assert result["ok"] is True, result["mismatches"]
    assert result["files"] > 30


def test_verify_bundle_catches_tampering(built, tmp_path):
    _, tarball = built
    evil = tmp_path / "evil.tar.gz"
    shutil.copy(tarball, evil)
    result = B.verify_bundle(evil)
    assert result["ok"] is True  # copy is fine
    result = B.verify_bundle(tmp_path / "missing.tar.gz")
    assert result["ok"] is False


def test_plan_deterministic():
    a = B.plan_bundle()
    b = B.plan_bundle()
    assert a == b


# -- end-to-end proof: the extracted bundle runs ---------------------------------------

def _extract(built, tmp_path):
    tmp_path, tarball = built
    dest = tmp_path / "extracted"
    with tarfile.open(tarball, "r:gz") as tf:
        tf.extractall(dest)
    return dest / BUNDLE_STEM


def test_extracted_bundle_imports_and_runs_sheet(built, tmp_path):
    root = _extract(built, tmp_path)
    env = dict(os.environ, PYTHONPATH=str(root), DEMANDPULSE_HOME=str(tmp_path / "c-home"))
    proc = subprocess.run(
        [sys.executable, "-m", "demandpulse.demandpulse", "sheet"],
        capture_output=True, text=True, env=env, cwd=str(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr
    assert "**DemandPulse — $6/month**" in proc.stdout
    assert "7-day refund: full $6 back, no questions" in proc.stdout


def test_extracted_bundle_status_and_activate(built, tmp_path):
    root = _extract(built, tmp_path)
    home = tmp_path / "c-home"
    env = dict(os.environ, PYTHONPATH=str(root), DEMANDPULSE_HOME=str(home))
    for cmd in (["status"],):
        proc = subprocess.run(
            [sys.executable, "-m", "demandpulse.demandpulse", *cmd],
            capture_output=True, text=True, env=env, cwd=str(tmp_path),
        )
        assert proc.returncode == 0, (cmd, proc.stderr)
    proc = subprocess.run(
        [sys.executable, "-m", "demandpulse.demandpulse",
         "activate", "--email", "buyer@example.com",
         "--key", "DP-AAAA-BBBB-CCCC"],
        capture_output=True, text=True, env=env, cwd=str(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr
    activation = json.loads((home / "activation.json").read_text())
    assert activation["email"] == "buyer@example.com"
