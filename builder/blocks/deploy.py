"""The only way a workflow reaches Freya: it must pass every loop-1 check first.

    python -m builder.blocks.deploy <run_dir> <slot>
"""
import hashlib
import json
import sys
from pathlib import Path

from builder.blocks import check
from builder.blocks.check import REPO, freya

STATE_FILE = REPO / ".freya-agents.json"


class GateError(Exception):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


def gate(run_dir):
    return [f"{key}: {p}" for key, problems in check.run_checks(run_dir).items() for p in problems]


def deploy(run_dir, slot):
    problems = gate(run_dir)
    if problems:
        raise GateError(problems)
    run = Path(run_dir)
    text = (run / "workflow.json").read_text()
    saved = freya.save_workflow(slot, json.loads(text), state_file=str(STATE_FILE))
    record = {"workflow_id": saved["workflow_id"], "agent_id": saved["agent_id"], "version": saved.get("version", 1),
              "sha256": hashlib.sha256(text.encode()).hexdigest()}
    (run / "deployed.json").write_text(json.dumps(record, indent=1))
    return record


if __name__ == "__main__":
    try:
        print(json.dumps(deploy(sys.argv[1], sys.argv[2])))
    except GateError as exc:
        print("refused by the gate:")
        for p in exc.problems:
            print("  - " + p)
        sys.exit(1)
