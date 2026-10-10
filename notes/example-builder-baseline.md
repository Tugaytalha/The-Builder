# Example builder baseline (10 October 2026)

This file records what we measured on the first day, before we built our own builder. The numbers are the bar that our builder must beat. The raw data is in `runs/`.

## Summary

- The kit's example builder already passes the practice cases in one run: 10/10 on Brief A and 3/3 on Brief B.
- One run does not prove much. With `--reps 3` (the final scoring rule), Brief A fell to 8/10.
- With real speech styles, Brief A fell to 6–9/10 and Brief B to 1–2/3.
- The main weak point is the identity step under real speech. The second is attempt limits that the agent does not count.
- The example builder writes most rules into prompts. Under pressure, the model forgets them. Our builder must put countable rules into code and routes.

## Setup that works

| Item | How |
| --- | --- |
| Keys | `env.sh` in the repo root (git ignores it). Copy `context/kit/env.example`. `FREYA_API_URL` is optional: `freya.py` has the same default. |
| Working kit | `kit/` is a copy of `context/kit/`. Run everything from `kit/`. Never write into `context/`. |
| Python for the builder | The system Python 3.9 is too old for `claude-agent-sdk`. Use a uv-managed Python 3.12: `uv venv --python 3.12 --managed-python .venv`, then `uv pip install --python .venv/bin/python claude-agent-sdk`. Homebrew Python 3.12 failed (`platform.mac_ver()` empty). |
| Claude login for the builder | The SDK runs its own Claude Code program. It uses the login of the config folder in `CLAUDE_CONFIG_DIR`. Unset `ANTHROPIC_API_KEY`, then check with `.venv/lib/python3.12/site-packages/claude_agent_sdk/_bundled/claude auth status`. |
| Kit scripts (`run_cases.py`, `freya.py`) | The system `python3` is enough. They use the standard library only. |

Commands:

```bash
source env.sh
# Build (example builder). Brief B builds on Brief A, so pass both.
cd kit && ../.venv/bin/python examples/agent_builder.py briefs/brief-a.md briefs/brief-b.md
# Test an agent. --reps 3 is the final scoring rule. --style is one of the five styles below.
python3 kit/tools/run_cases.py <agent_id> --brief A --reps 3 --out runs/<name>.json
```

## Rules we learned for testing

1. **Move earlier outputs out of `kit/` before each builder run.** The builder reads `kit/results/`. In our first run, it read our test results and used the failure reasons as hints. The final benchmark gives no such file. Move `kit/results/`, `kit/out/` and `kit/traces/` to `runs/<date-time>/`. Do not move them while a builder run is in progress.
2. **`.freya-agents.json` is local state. Never commit it.** It maps a slot (for example `brief-a`) to a workflow ID. A builder with the same file updates that workflow, so a shared file lets one teammate overwrite the other's agent. Git ignores it now.
3. **One simulation runs at a time in the workspace.** `run_cases.py` waits by itself ("another simulation is running … waiting 30 s"). Agree on turns with your teammate.
4. **Do not filter `run_cases.py` output with `grep`.** It stops on any Freya API error except "another simulation is running". If you filter its output, you lose the error text. Use `tee` to a log file.
5. **Test with `--reps 3`.** A single passing run hid most of the failures below.
6. **The judge can be slow.** In the evening, one round took 6–10 minutes in place of 1.5, and one simulation stayed "running" for about 15 minutes after its conversations ended. The organizers said the site was partly down.

## Freya API facts

- The Freya API is larger than `kit/docs/api.md`. The full index is at `https://docs.freyavoice.ai/llms.txt`. Useful read routes: `GET /api/v2/workflow`, `GET /api/v2/agents`, `GET /api/v2/simulations`, `GET /api/v2/call/{id}` (full transcript with tool calls). All need `workspaceId`.
- A workflow agent (`entityType: workflow`) shows on the dashboard under **Build → Workflows**, not under **Agents**.
- Rename safely through the API: `PUT /api/v2/agents/{id}` with `{workspaceId, name}`, and `PUT /api/v2/workflow/{id}` with `{name, workflow}` and the unchanged workflow. It keeps the published version. On a workflow that was never updated, Freya saves an unpublished draft version (it adds a default `agent_config`). The published version does not change.
- `PUT /api/v2/simulations/{id}` accepts `status` (`draft`, `running`, `paused`, `completed`).
- The credits route (`/workspaces/credits`) returns 404 on the staging server.

## Our agents on Freya

| Name | Agent ID | What it is |
| --- | --- | --- |
| `ra-test-agent` | `318fbb2d-5b7f-4b00-986d-8a47939ef9c5` | The kit's example agent (`examples/base-agent.json`). |
| `ra-example-builder-hints-a` | `e1500e24-ac06-4c06-86ac-917bbff3a14a` | Example builder, Brief A. It saw our earlier results, so it is not a clean baseline. |
| `ra-example-builder-clean-a` | `09d001fd-4713-463c-9699-2199dc162d2f` | Example builder, clean run, Brief A. This is the baseline. |
| `ra-example-builder-clean-b` | `f4df6522-4410-4396-a33f-f22c3ca2ace2` | Example builder, clean run, Brief B. This is the baseline. |

## Results

### The example agent (`ra-test-agent`)

0/10 on Brief A. It has two steps and four tools, so it cannot do callbacks, transfers, retries or the date rules.

### The example builder, clean run

The clean build took 12 minutes and 21 turns (about $2.10 at API prices). It made both agents from one generator script (`runs/20261010-2042-step5-clean/out/build.py`).

| Test | Brief A (10 customers) | Brief B (3 customers) |
| --- | --- | --- |
| Plain, 1 run | 10/10 | 3/3 |
| Plain, `--reps 3` (strict) | **8/10** (rounds: 8, 9, 10) | **3/3** |
| `pieces`: numbers in two parts | 7/10 | 1/3 |
| `corrects`: a wrong value, then the correct one | 7/10 | 2/3 |
| `talkative`: small talk, mentions the 30th | 6/10 | 2/3 |
| `asks_back`: asks questions back | 9/10 | 2/3 |
| `in_words`: amounts and dates in words | 10/10 | 2/3 |

The style tests ran once each. The hints run on Brief A scored 10/10 in one run and 9/10 with `--reps 3`.

## Weak points, from the most to the least frequent

These are general. None of them is a rule from one brief, so our builder can fix them for any hidden brief.

1. **The identity step fails with real speech.** Seen in both briefs and in four styles (PUB-01, PUB-03, PUB-04, PUB-08, PUB-10, PUB-11, PUB-12).
   - The agent did not send an answer that looked incomplete or was corrected to `verify_identity`. The bank counted fewer wrong answers, and one unverified customer then heard about the debt (PUB-03). This is the most serious failure.
   - The agent did not join a number given in two parts before the tool call (PUB-01 `pieces`).
   - Small talk or a question back made the agent ask the security question again, or fail the check (`talkative`, `asks_back`).
   - An identity failure ends the call, so even a simple customer fails.
2. **Attempt limits are not counted.** The agent made more offers or asked more times than the brief allows: three proposals on a late-band loan (PUB-12, four of five Brief B styles), the minimum amount offered twice (PUB-06), the support team offered three times (PUB-05).
3. **A forbidden word in a fixed sentence.** The greeting said "this call is recorded". The case rule says the agent must not say "recorded" before a successful `create_promise`. It failed PUB-10 in most runs. The judge reads the exact words.
4. **Numbers from real speech.** The agent recorded a partial or uncorrected amount (PUB-04 `pieces`: 400 in place of 1,250; PUB-06 `corrects`: 640 in place of 637.50) or the wrong deadline for one product (PUB-13 `pieces`).

What worked well: code steps that calculate dates, deadlines and amounts from `now`; routes on tool results; a retry after a failed `create_promise`.

## What the kit cannot test

1. **Several calendar days.** All 13 cases run on Wednesday 14 October 2026 at 11:00. The final test uses several days.
2. **New customers.** The practice bank serves PUB-01 to PUB-13 only (FAQ).
3. **Unseen briefs.** The final test uses two hidden briefs. One is raw bank material: a mail, a policy extract, a memo that changes it, and a code list.

Ideas to close these gaps (not started):

- Rewrite Brief A as raw bank material with the same rules. The 10 bank cases can still score it. Keep it as a held-out test brief: never tune the builder on it.
- Make variants with changed values (deadlines, holidays, outcome table). Check them with a rule checklist and test chats (`POST /api/v2/chat/message`).
- Run the generated date code locally with many values of `now`.

## Open questions

- Can the two final runs come from different computers, with the same commit, traces and exports? No official source answers it. The kickoff said the submission details come on 11 October.

## Where the raw data is

| Folder | Content |
| --- | --- |
| `runs/20261010-2032-steps2-4/` | Example agent test, the hints build (trace, generator script, workflow), its `--reps 3` test. |
| `runs/20261010-2042-step5-clean/` | The clean build: trace, `build.py`, both workflows, its first test runs. |
| `runs/20261010-step6-7/` | `--reps 3` and all style tests on the clean agents. Each JSON file has every call ID; read a transcript with `freya.get_call(call_id)`. |
