# Hidden-brief runbook (Sunday 11 October 2026)

The hidden briefs open at 17:00 UTC. The submission closes at 20:00 UTC. After 17:00 we fix crashes only. Nothing from a hidden brief goes into `builder/`: no rule, no value, no name.

## Before 17:00

1. `git status` is clean on the frozen commit. Note the commit id.
2. `source env.sh`. Unset `ANTHROPIC_API_KEY` if the Max login should be used, and check it: `.venv/lib/python3.12/site-packages/claude_agent_sdk/_bundled/claude auth status`.
3. Move `kit/results/` to `runs/<time>-kit-results/` if it exists.
4. `.venv/bin/python -m pytest builder/tests -q` and `.venv/bin/python eval/contamination.py`: all pass, exit 0.

## Per hidden brief (n = 1, 2)

1. Put the files at `briefs/hidden-<n>.md` and `briefs/hidden-<n>.openapi.json` exactly as received.
2. Run, one brief at a time or both in parallel:

   ```
   .venv/bin/python builder/build.py briefs/hidden-<n>.md briefs/hidden-<n>.openapi.json 2>&1 | tee traces/hidden-<n>.log
   ```

3. Check the end of the log: `created workflow_id=... agent_id=... nodes=... tools=...`, `end seconds=...` under 1800, exit code 0, and `submission/hidden-<n>.workflow.json` exists.
4. Key check: `grep -c fak_ traces/*.log traces/*.jsonl` must print 0 for every file. `grep -c "$FREYA_BANK_TEAM_KEY" traces/*` must print 0. `grep -c sk-ant- traces/*` must print 0.
   Builder check: `git status --porcelain builder/ | grep -v '^?? builder/runs/'` must print nothing (the build agent changed no builder file). Then `.venv/bin/python eval/contamination.py`: it also reads `briefs/hidden-*.md`.
5. If the run failed with a Freya error (500, 502, 503, 504, a DNS or socket timeout; seen for hours on 11 October), it is not our crash: check `GET /api/v2/workspaces`, wait until it answers, and run again with no change.
6. If the run failed with a crash in our code (not a weak agent): fix only the crash, with a commit that names the crash, then run again. A rerun updates the same workflow (same slot). Submit the agent and the trace of the same run.

## Allowed and not allowed after 17:00

- Allowed: fix a crash, for example a table or a tool API shape our parser did not expect.
- Not allowed: anything from a hidden brief in `builder/` (holiday dates, outcome names, field names, wording). Do not edit a phone agent on the platform. Do not hand-edit an exported file.

## Submit before 20:00 UTC

1. Commit `submission/hidden-1.workflow.json`, `submission/hidden-2.workflow.json`, `traces/hidden-1.log`, `traces/hidden-2.log` (and the `.jsonl` traces). Push.
2. Send the form to the address in the kit email:

   ```
   {
     "team": "<team name>",
     "repo": "<repository URL>",
     "commit": "<commit id of the submission commit>",
     "run_command": "python3 builder/build.py {brief_path} {tool_api_path}",
     "workflows": {"hidden-1": "submission/hidden-1.workflow.json", "hidden-2": "submission/hidden-2.workflow.json"},
     "traces": {"hidden-1": "traces/hidden-1.log", "hidden-2": "traces/hidden-2.log"}
   }
   ```
