#!/usr/bin/env bash
# Wrapper for chat.py: sets the Freya key and paths. Usage: bash t.sh start|say|end|show <run> [...]
# WF_ID=<workflow_id> picks the workflow (default: the tested final-case workflow).
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
source "$REPO/env.sh"
export KIT_DIR="$REPO/kit" PYTHONIOENCODING=utf-8
export WF_ID="${WF_ID:-8d54a9e5-1001-473f-975a-8aadf36e83fe}"
exec python "$(dirname "$0")/chat.py" "$@"
