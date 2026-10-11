set -e
cd /Users/resit/orca/workspaces/The-Builder/mola/runs/session-tools/spike-ab && PYTHONPATH=/Users/resit/orca/workspaces/The-Builder/mola /Users/resit/orca/workspaces/The-Builder/mola/.venv/bin/python build_agent.py | tail -1
cd /Users/resit/orca/workspaces/The-Builder/mola && source env.sh && PYTHONPATH=. .venv/bin/python -c "
import json; from builder.blocks.check import freya
w=json.load(open('/Users/resit/orca/workspaces/The-Builder/mola/runs/session-tools/spike-ab/workflow.json')); print(freya.save_workflow('spike-list', w, state_file='/Users/resit/orca/workspaces/The-Builder/mola/runs/session-tools/spike-agents.json'))" | tail -c 300
