# The-Builder

Our entry for the Freya "Build the Builder" hackathon: a builder that reads a bank's brief (one file, or a case folder of documents) and its tool API, and creates a Freya phone agent.

## Setup

1. Python 3.10 or newer.
2. `pip install -r requirements.txt` (the Claude Agent SDK and pytest).
3. Copy `kit/env.example` to `env.sh`, fill in `FREYA_API_KEY` and `FREYA_BANK_TEAM_KEY`, then `source env.sh`.
4. A Claude login for the SDK (`claude` login of the config folder in `CLAUDE_CONFIG_DIR`) or `ANTHROPIC_API_KEY`.

## Run

```
python3 builder/build.py {case_folder} {mock_url}          # the final case: a folder of documents and our mock
python3 builder/build.py {brief_path} {tool_api_path}     # a practice brief and the kit's tool API file
```

A case folder becomes one `brief.md` in the run folder: README and BRIEF first, Word and Excel converted to text, PDF and image files listed for the agent to open. The tool API comes from `{mock_url}/openapi.json`.

The run prints its trace to stdout and also writes it as JSON lines to `traces/<slot>-<time>.jsonl`. It exports the phone agent to `submission/<slot>.workflow.json`. The slot is the brief's file name without `.md`; the same slot updates the same workflow.

## Layout

| Path | What it is |
|---|---|
| `builder/build.py` | Entry point: trace, 27-minute watchdog, one Claude Agent SDK run, final deploy through the gate, export. |
| `builder/blocks/` | The tested building blocks: case folder to text (`docs.py`), tools from any API file, node factories, proven patterns, date helpers, linter, loop-1 checks, deploy gate, chat smoke tests. |
| `builder/.claude/skills/build-phone-agent/` | The skill the agent follows, the platform knowledge (`freya.md`) and a worked example on an invented brief. |
| `builder/.claude/agents/reviewer.md` | The independent reviewer the agent asks before it hands off. |
| `mock/` | The bank mock for the final case, a Cloudflare Worker with one Durable Object (`npx wrangler deploy`). `/openapi.json` gives the tool API; `/__log` and `/__reset` are for us. |
| `eval/` | Our evaluation loop: variant briefs and cases, the runner, the contamination check, the edge-case generator. |
| `notes/` | Platform spike results, baseline, evaluation log, the hidden-brief runbook. |

Tests: `python3 -m pytest builder/tests eval` (run `eval` tests from `eval/`).
