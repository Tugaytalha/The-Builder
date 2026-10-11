"""The only way a workflow reaches Freya: it must pass every loop-1 check first.

    python -m builder.blocks.deploy <run_dir> <slot>
"""
import hashlib
import json
import sys
import time
from pathlib import Path

from builder.blocks import check
from builder.blocks.check import REPO, freya

STATE_FILE = REPO / ".freya-agents.json"


def _lock(f):
    """Wait for an exclusive lock on the open file. flock on macOS and Linux, msvcrt on Windows."""
    try:
        import fcntl
    except ImportError:
        import msvcrt
        while True:      # msvcrt gives up after 10 s by itself; flock waits as long as it takes
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                time.sleep(0.05)
    fcntl.flock(f, fcntl.LOCK_EX)


class GateError(Exception):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


def gate(run_dir):
    """Every check except `coverage` blocks a deploy: a build short of time must still deploy its agent, and
    `check` keeps showing the missing rule tests to the builder."""
    return [f"{key}: {p}" for key, problems in check.run_checks(run_dir).items() if key != "coverage" for p in problems]


def deploy(run_dir, slot):
    problems = gate(run_dir)
    if problems:
        raise GateError(problems)
    run = Path(run_dir)
    text = (run / "workflow.json").read_text(encoding="utf-8")
    with open(str(STATE_FILE) + ".lock", "w") as lock:   # parallel builds share the state file
        _lock(lock)
        saved = freya.save_workflow(slot, json.loads(text), state_file=str(STATE_FILE))
    record = {"workflow_id": saved["workflow_id"], "agent_id": saved["agent_id"], "version": saved.get("version", 1),
              "sha256": hashlib.sha256(text.encode()).hexdigest()}
    (run / "deployed.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    return record


if __name__ == "__main__":
    try:
        print(json.dumps(deploy(sys.argv[1], sys.argv[2])))
    except GateError as exc:
        print("refused by the gate:")
        for p in exc.problems:
            print("  - " + p)
        sys.exit(1)
