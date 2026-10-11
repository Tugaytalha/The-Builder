# The-Builder

Our entry for the Freya "Build the Builder" hackathon: a builder that reads a bank's brief (one file, or a case folder of documents) and its tool API, and creates a Freya phone agent.

## Setup from scratch

Tested from a fresh copy of the repository on Windows (`git clone`, Python 3.14) and on Linux (Ubuntu 24.04, Python 3.12). macOS runs the same code paths as Linux but was not re-tested for this guide.

**1. Install**

| | macOS / Linux (bash, zsh) | Windows (PowerShell) |
|---|---|---|
| Python 3.10 or newer (tested on 3.12 and 3.14) | `python3 --version` (Ubuntu and Debian also need `sudo apt install python3-venv`) | `python --version` |
| Clone | `git clone https://github.com/Tugaytalha/The-Builder.git && cd The-Builder` | the same |
| Virtual environment | `python3 -m venv .venv` | `python -m venv .venv` |
| Dependencies | `.venv/bin/pip install -r requirements.txt` | `.venv\Scripts\pip install -r requirements.txt` |

Below, `PY` means `.venv/bin/python` (macOS, Linux) or `.venv\Scripts\python` (Windows). No need to activate the environment.

**2. Keys.** Copy `kit/env.example` to `env.sh` (it is git-ignored) and fill in:

| Variable | Where it comes from |
|---|---|
| `FREYA_API_KEY` | Your Freya workspace, under API keys. It starts with `fak_`. |
| `FREYA_BANK_TEAM_KEY` | Make one up: at least 16 characters. Use the same one every time. |
| `FREYA_API_URL` | Leave as in the file (`https://staging-app.freyavoice.ai`). |

- macOS / Linux: `source env.sh`
- Windows: PowerShell does not read `env.sh`. Set the three variables in the same terminal, for example `$env:FREYA_API_KEY = "fak_..."`.

**3. Claude login.** The builder runs the Claude Agent SDK, which needs a Claude account or an API key. Either log in with the `claude` program that comes with the SDK, or set `ANTHROPIC_API_KEY`:

```
PY -c "import claude_agent_sdk, pathlib; print(pathlib.Path(claude_agent_sdk.__file__).parent / '_bundled')"
# in the folder it prints: claude auth login        (Windows: claude.exe auth login)
# check:                   claude auth status       shows "loggedIn": true
```

**4. Check that it works** (all three should succeed, none starts a build):

```
PY -m pytest -q builder/tests eval             # 159 tests pass
PY eval/contamination.py                       # "0 leaks", exit code 0
PY -c "from builder.blocks.check import freya; ws = freya.workspace_id(); print(freya.api('GET', '/api/v2/workflow', workspaceId=ws, limit=100)['total'])"
                                               # prints a number; the workspace limit is 200 workflows
```

## Run

Use a plain terminal, **not** inside a Claude Code session: variables such as `CLAUDECODE` make the SDK start a nested session. In a Claude Code terminal, clear them first (macOS / Linux: `unset ANTHROPIC_API_KEY CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SESSION_ID`; PowerShell: `Remove-Item Env:CLAUDECODE, Env:CLAUDE_CODE_ENTRYPOINT, Env:CLAUDE_CODE_SESSION_ID -ErrorAction SilentlyContinue`).

```
PY builder/build.py {case_folder} {mock_url}                       # the final case: a folder of documents and our mock
PY builder/build.py {brief_path} {tool_api_path}                   # a practice brief and the kit's tool API file
PY builder/build.py eval/briefs/v1-raw-a.md kit/tools/openapi.json # example: practice brief A
```

`traces/` and `submission/` are created by the run. Only when you pipe the output through `tee traces/final.log` must `traces/` exist first. The final case is run as `python3 builder/build.py {case_folder} {mock_url}`; `python3` and `PY` are the same when the right Python is first on the path.

- **Mock URL:** `https://the-builder-mock.the-builder-freya.workers.dev`. `{mock_url}/health` must answer `{"ok":true}`.
- **Time:** a build takes about 6 to 11 minutes and stops by itself at 25 minutes (28 minutes at the latest for the last deploy). It uses your Claude account and creates or updates one Freya workflow.
- **What a good run prints at the end:** `created workflow_id=... agent_id=... nodes=... tools=...`, then `end seconds=...` (under 1800), and the exit code is 0.
- **Where the results go:** the phone agent is exported to `submission/<slot>.workflow.json` and the trace is written as JSON lines to `traces/<slot>-<time>.jsonl`. The slot is the brief's file name without `.md`, or the case folder's name. A second run with the same slot updates the same workflow instead of making a new one.
- **Case folder:** it becomes one `brief.md` in the run folder: README and BRIEF first, Word and Excel converted to text, PDF and image files listed for the agent to open. The tool API comes from `{mock_url}/openapi.json`.

**If it fails**

| Message or symptom | Meaning |
|---|---|
| `401` and `invalid JWT` from Freya | `FREYA_API_KEY` is missing or wrong in this terminal. Set it again (step 2). |
| 5xx or a timeout from Freya | Not our crash. Wait and run again, with no change. |
| `error code: 1042` from the mock | Cloudflare right after a deploy. Wait one minute. |
| `agent_error` in the trace | The agent run crashed; the message is in the trace. Check the Claude login first (step 3). |
| `gate_refused` | The checks found problems; the trace lists them. The last deployed version is kept. |
| Many workflows in the workspace | The limit is 200, and a run with a new slot makes one. The last command of step 4 prints the count. |

The final-case checklist (preflight, submission) is `notes/hidden-runbook.md`. How the parts fit together and which operating systems are tested: `docs/architecture.md`.

## Layout

| Path | What it is |
|---|---|
| `builder/build.py` | Entry point: trace, 27-minute watchdog, one Claude Agent SDK run, final deploy through the gate, export. |
| `builder/blocks/` | The tested building blocks: case folder to text (`docs.py`), tools from any API file, node factories, proven patterns, date helpers, linter, loop-1 checks, deploy gate, chat smoke tests. |
| `builder/.claude/skills/build-phone-agent/` | The skill the agent follows, the platform knowledge (`freya.md`) and a worked example on an invented brief. |
| `builder/.claude/agents/reviewer.md` | The independent reviewer the agent asks before it hands off. |
| `mock/` | The bank mock for the final case, a Cloudflare Worker with one Durable Object (`npx wrangler deploy`), live at `https://the-builder-mock.the-builder-freya.workers.dev`. `/health` answers `{"ok":true}`; `/openapi.json` gives the tool API; `/__log` (every request) and `/__reset` (back to the test customers) are for us. |
| `eval/` | Our evaluation loop: variant briefs and cases, the runner, the contamination check, the edge-case generator. |
| `notes/` | Platform spike results, baseline, evaluation log, the hidden-brief runbook. |

Tests: `python3 -m pytest builder/tests eval` (run `eval` tests from `eval/`).
