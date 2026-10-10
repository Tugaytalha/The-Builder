"""The skill's worked example must always build and pass loop 1 (without the platform dry run)."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from builder.blocks.check import run_checks

EXAMPLE = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "build-phone-agent" / "example"
REPO = Path(__file__).resolve().parents[2]


def test_example_builds_and_passes_checks(tmp_path):
    for f in EXAMPLE.iterdir():
        if f.is_file():
            shutil.copy(f, tmp_path / f.name)
    subprocess.run([sys.executable, "build_agent.py"], cwd=tmp_path, check=True,
                   env={**os.environ, "PYTHONPATH": str(REPO)})
    assert run_checks(str(tmp_path), dry_run=False) == {k: [] for k in ("ledger", "lint", "snippets", "rules_tests", "dry_run")}
