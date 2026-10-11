#!/usr/bin/env bash
# Wrapper for chat.py: sets the Freya key and paths. Usage: bash t.sh start|say|end|show <run> [...]
# WF_ID=<workflow_id> picks the workflow (default: the tested final-case workflow).
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
source "$REPO/env.sh"
export KIT_DIR="$REPO/kit" PYTHONIOENCODING=utf-8
exec python "$(dirname "$0")/chat.py" "$@"
