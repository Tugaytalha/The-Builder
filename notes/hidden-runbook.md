# Final-case runbook (Sunday 11 October 2026)

The page changed after 10 October (checked 15:55 UTC on 11 October). The final is **one case in Turkish**: a zip with a folder of the bank's documents (Markdown, Word, PDF, Excel). There is no tool API file: we write the bank mock on Cloudflare Workers (`mock/`) and keep it running until the results are out. The phone agent may call only our mock.

The final case opens at 17:00 UTC. The submission closes at 20:00 UTC. After 17:00 we fix crashes only. Nothing from the final case goes into `builder/`: no rule, no value, no name.

## 16:30 preflight

Do every step on the machine that runs the final build, in a plain terminal (not inside Claude Code). Tick each line. If a line fails, fix it before 17:00. The commands are for macOS; on Windows use `.venv/Scripts/python` and `.venv/Lib/site-packages/...`.

**People and form**

1. One person runs the builds. One person watches the time, the logs and the keys.
2. Have these ready: the kit email (the form address), the team name, each member's name and email, the repository URL, the Submit tab or the final-case email open.

**Code**

3. `git status` is clean on the frozen commit.
4. `git fetch && git rev-parse HEAD origin/main` prints the same id twice. The organizers clone the pushed commit, not our disk. Note the id.
5. Fresh-clone check: `git clone <repo URL> /tmp/fresh && cd /tmp/fresh && <repo>/.venv/bin/python -m pytest -q builder/tests`. All pass. This shows that the builder needs no git-ignored file. Delete `/tmp/fresh` after.

**Environment**

6. `source env.sh`, then `unset ANTHROPIC_API_KEY CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SESSION_ID CLAUDE_CODE_CHILD_SESSION CLAUDE_CODE_MESSAGING_SOCKET CLAUDE_CODE_MESSAGING_TOKEN CLAUDE_PID`.
7. `env | grep -E 'FREYA_AGENT_|BUILDER_MODEL|FREYA_SIM_CONCURRENCY'` prints nothing. The phone agent must run on the model in `freya.py`, and the builder on its default model.
8. Claude login: `.venv/lib/python3.12/site-packages/claude_agent_sdk/_bundled/claude auth status` shows the Max account.
9. Freya: `.venv/bin/python -c "from builder.blocks.check import freya; ws = freya.workspace_id(); print(freya.api('GET', '/api/v2/workflow', workspaceId=ws, limit=100)['total'])"` prints a number. It must be at most 196: each build can make one new workflow, and the limit is 200 (17 at 11:45 UTC).

**Tests**

10. `.venv/bin/python -m pytest -q builder/tests eval` and `.venv/bin/python eval/contamination.py`: all pass, exit 0.

**Folders**

11. `mkdir -p briefs traces submission`. `tee` fails when `traces/` does not exist.
12. `ls traces submission` shows no rehearsal files. Move `kit/results/` to `runs/<time>-kit-results/` if it exists.
13. `grep FreyaBank .freya-agents.json` prints nothing, so the final build cannot update an old workflow.
16. Mock: `curl -s https://the-builder-mock.the-builder-freya.workers.dev/health` prints `{"ok":true}`. Wrangler is logged in (`npx wrangler whoami`).

**Machine**

14. The laptop is on power. Sleep is off for 3 hours (macOS: `caffeinate -dims &`). The network is stable.
15. No other simulation and no `persona_sim` or `run_eval` run from 17:00 until the builds end.

## The final case

1. Download the zip. Unzip it to `briefs/` exactly as received, so the folder is `briefs/<case folder>/`. Read `BRIEF.md` and `README.md`.
2. **Mock (by hand, allowed: the mock is not the builder).** From the service contract and the test customers, fill `mock/src/routes.js` (one handler per route, the contract's paths and fields), `mock/src/data.js` (the test customers) and `mock/src/openapi.js` (one operation per route, the contract's names, enums and descriptions). Then `cd mock && npx wrangler deploy`. Wait 1 minute: just after a deploy, Cloudflare can answer `error code: 1042` (rehearsal, 16:22 UTC; 0 of 20 calls failed after one minute). Then `curl -X POST <mock>/__reset`.
3. Test the mock with `curl`: each route with one test customer, a right and a wrong identity answer, one write, then `GET <mock>/__log`. Then reset it again.
4. Run the builder:

   ```
   .venv/bin/python builder/build.py briefs/<case folder> https://the-builder-mock.the-builder-freya.workers.dev 2>&1 | tee traces/final.log
   ```

5. Check the end of the log: `created workflow_id=... agent_id=... nodes=... tools=...`, `end seconds=...` under 1800, exit code 0, and `submission/<case folder>.workflow.json` exists. Check that every tool URL in the export starts with the mock URL: `grep -o '"url": *"[^"]*"' submission/<case folder>.workflow.json | sort -u`.
6. Key check: `grep -c fak_ traces/*` must print 0 for every file. `grep -c "$FREYA_BANK_TEAM_KEY" traces/*` must print 0. `grep -c sk-ant- traces/*` must print 0.
   Builder check: `git status --porcelain builder/ | grep -v '^?? builder/runs/'` must print nothing. Then `.venv/bin/python eval/contamination.py`.
7. Talk to the phone agent in chat as two test customers (one who pays, one who disputes), in Turkish. Read `GET <mock>/__log`. Then `POST <mock>/__reset`.
8. If the run failed with a Freya error (5xx, a DNS or socket timeout), it is not our crash: wait until Freya answers, and run again with no change.
9. If the run failed with a crash in our code: fix only the crash, with a commit that names the crash, then run again. A rerun updates the same workflow (same slot). Submit the agent and the trace of the same run.

## Allowed and not allowed after 17:00

- Allowed: fix a crash, for example a document or an OpenAPI shape our code did not expect.
- Not allowed: anything from the final case in `builder/` (holiday dates, outcome names, field names, wording). Do not edit a phone agent on the platform. Do not hand-edit an exported file.

## Submit before 20:00 UTC (aim for 19:00)

1. Commit `submission/<case folder>.workflow.json`, `traces/final.log` (and the `.jsonl` trace) and `mock/`. Push. Check that the organizers can open the repository.
2. `POST <mock>/__reset`, so the evaluation starts from the test customers. Keep the mock running until the results are out.
3. Send `submission.json` to the address in the kit email:

   ```
   {
     "team": "<team name>",
     "members": [{"name": "<name>", "email": "<email>"}, {"name": "<name>", "email": "<email>"}],
     "repo": "<repository URL>",
     "commit": "<commit id of the submission commit>",
     "run_command": "python3 builder/build.py {case_folder} {mock_url}",
     "workflow": "submission/<case folder>.workflow.json",
     "trace": "traces/final.log",
     "mock_url": "https://the-builder-mock.the-builder-freya.workers.dev"
   }
   ```
