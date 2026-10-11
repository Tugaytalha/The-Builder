# The-Builder

Our entry for the Freya "Build the Builder" hackathon: a builder that reads a bank's brief (one file, or a case folder of documents) and its tool API, and creates a Freya phone agent.

## Setup and run

The full guide, from a fresh machine to a finished build, for macOS, Linux and Windows, is in **[HOW_TO_RUN.md](HOW_TO_RUN.md)**: install, keys, Claude login, checks, the run, the final case, and what to do when it fails.

```
python3 builder/build.py {case_folder} {mock_url}          # the final case: a folder of documents and our mock
python3 builder/build.py {brief_path} {tool_api_path}     # a practice brief and the kit's tool API file
```

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
