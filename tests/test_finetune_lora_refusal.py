"""Refusal test for levi.brain.train.finetune_lora.

finetune_lora.py raises SystemExit at import BY DESIGN (2026-09-15 user
directive: LEVI's native brain instead of third-party weights — do not
implement it). This test pins that refusal: the module must refuse to run
with "superseded" in the message. runpy would kill the pytest process, so
it executes in a subprocess.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET = REPO_ROOT / "core" / "levi" / "brain" / "train" / "finetune_lora.py"


def test_finetune_lora_refuses_at_import_with_superseded_message():
    assert TARGET.exists(), "finetune_lora.py must exist as a pinned stub"
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import runpy, sys; runpy.run_path(sys.argv[1], run_name='__main__')",
            str(TARGET),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode != 0, "stub must refuse to run, not succeed"
    combined = (proc.stderr or "") + (proc.stdout or "")
    assert "superseded" in combined.lower(), (
        "refusal message must say the stub is superseded; got: %r" % combined
    )
