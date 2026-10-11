# Handoff: improvement rounds (Sun 11 Oct)

Read this first in a new session. Then read `notes/eval-log.md` (one row per round, with every root cause) and `docs/superpowers/plans/2026-10-11-builder.md` (Tasks 15 and 16).

## Where we are

- Branch `execute-builder-plan`, worktree `/Users/resit/orca/workspaces/The-Builder/mola`.
- Plan Tasks 1–14 are done. Task 15 (improvement rounds) is in progress. Task 16 (freeze) is at 14:00 UTC.
- Round 5 is done for A (scores in `eval/results/5/`). A DNS outage stopped the other scores, so A+B, V2 and edge-a were scored again on the same agents as round `5b` (`eval/results/5b/`). Results and root causes are in the round 5 row of `notes/eval-log.md`.
- Five fixes since the round 5 builds: 3e76500, 3939bb6, 317d3e5, c2999b5 (lint rule 13), e3f7897 (lesson 4l). No build has used them yet: round 6 is their first measurement. Watch V2 (the read-back loop) and the A+B goodbye (no `{{close_extra}}`). Not analyzed yet: edge-a PUB-10 (3 of 3 runs) and PUB-08 (2 of 3).
- The Freya API returned 504 and 503 errors in rounds 5b and 5c. `run_cases_at.py` does not retry a failed GET, so one error loses the whole score file.
- Another agent (`76ed8678…`, not ours) runs simulations in the same Freya workspace. Our runner waits for it ("another simulation is running in this workspace"), so rounds take longer.

## Next rounds

| Round | What |
|---|---|
| 6 | `--heldout --styles` (dev + V1, V3). Do not design fixes from held-out failures. |
| 7 | dev, last fixes |
| 8 | only if time: a check run, no new fixes. Stop changes at about 12:30 UTC. |

At 14:00 UTC: Task 16 (all tests, `eval/contamination.py`, rehearse V1 and V3 into `traces/rehearsal-*.log`, delete rehearsal exports from `submission/`, commit). Then one fresh reviewer on the most capable model checks the whole branch. Tell the reviewer about the security point: blanket Bash with dontAsk was accepted by the plan; the mitigations are the settings.json deny rules, the brief-is-data skill rule, and key redaction.

## Work rules (from the user)

- Write to the user in ASD-STE100 Simplified Technical English. Concise.
- Commit after each fix; no approval needed. No AI attribution.
- Before each run that uses the Freya simulation slot, or a builder run: say what it does and how long it takes. Report every test and its result in a table.
- For each failure: find the root cause in the transcript, write a failing test first, fix, verify with a chat test, commit.
- Nothing from any brief goes into `builder/`. Run `eval/contamination.py`. Do not quote brief text in `freya.md`.
- Never edit `builder/` while builds run (the build agent imports the library live). Never build a slot while it is scored.
- `run_eval.py` moves `kit/results/` to `runs/` itself.

## Commands

- Env for builds and evals: `source env.sh && unset ANTHROPIC_API_KEY CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SESSION_ID CLAUDE_CODE_CHILD_SESSION CLAUDE_CODE_MESSAGING_SOCKET CLAUDE_CODE_MESSAGING_TOKEN CLAUDE_PID` (the SDK uses the Max account, no API key).
- Tests: `.venv/bin/python -m pytest -q builder/tests eval`.
- Failing calls of a result file: rows in `all_rows` with `pass` false; each has `call_id` and `failed`.

## Helper scripts (`runs/session-tools/`, git-ignored)

- `txc.py <call_id>...`: compact transcript (customer, agent, tool calls, routes). Run with `source env.sh; .venv/bin/python runs/session-tools/txc.py <id>`.
- `chat.py <workflow_id> <case> <lines.json>`: chat test against the practice bank; prints the bank ledger, the `customer_said` calls and the guides. Run with `PYTHONPATH=.`. Put `"Hello?"` first in the lines: the first message gets the greeting.
- Spike workflow for chat tests: `spike-ab/` (an A+B build), slot `spike-list`, workflow `a774da7a-c908-477e-9747-110ad97b7778`, state `spike-agents.json`. After a change in the library or in `spike-ab/build_agent.py`, run `bash runs/session-tools/redeploy.sh`.
- `pub*.json`: customer lines used in earlier chat tests.

## Known limits (do not fix)

The simulator cuts talkative messages before the answer. The agent model sometimes returns no speakable content. The judge sometimes misreads. The chat route gives 502 when a call ends. Corrects PUB-12 (A+B) expects two phone asks when the customer corrects in one message.
