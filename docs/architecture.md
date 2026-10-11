# How the builder is put together, and where it runs

State at 11 October 2026, 17:15 UTC. Diagrams are Mermaid: GitHub draws them.

## 1. Components

```mermaid
flowchart TB
    subgraph IN["Input"]
        CASE["Case folder<br/>(md, Word, PDF, Excel)"]
        MOCK["mock/<br/>Cloudflare Worker<br/>/openapi.json"]
    end

    subgraph SHELL["builder/build.py (deterministic shell)"]
        DOCS["blocks/docs.py<br/>folder to brief.md"]
        TRACE["trace.py<br/>trace, keys redacted"]
        WD["25 min watchdog"]
    end

    subgraph AGENT["One Claude Agent SDK run (claude-opus-5-5)"]
        SKILL["skill: build-phone-agent<br/>SKILL.md, freya.md, example/"]
        REV["subagent: reviewer"]
        BLK["blocks/<br/>tools, nodes, patterns,<br/>datelib, coderun, lint"]
        CHK["blocks/check.py<br/>loop-1 checks"]
        SMK["blocks/smoke.py<br/>chat smoke tests"]
    end

    GATE["blocks/deploy.py<br/>the gate"]
    FREYA["Freya platform<br/>kit/freya.py"]
    OUT["submission/SLOT.workflow.json<br/>traces/SLOT-TIME.jsonl"]

    CASE --> DOCS --> SKILL
    MOCK -->|tool API| SKILL
    SKILL --> BLK --> CHK --> GATE
    SKILL <--> REV
    GATE --> FREYA --> SMK
    SMK --> SKILL
    FREYA -->|export| OUT
    TRACE -.-> OUT
    WD -.->|stops the agent| AGENT
```

| Part | Where | Role |
|---|---|---|
| Shell | `builder/build.py`, `builder/trace.py` | Brief and tool API into a run folder, one agent run, final deploy through the gate, export, trace. |
| Agent instructions | `builder/.claude/skills/build-phone-agent/` | The procedure, the platform knowledge, a worked example. |
| Reviewer and limits | `builder/.claude/agents/reviewer.md`, `builder/.claude/settings.json` | Independent review before hand-off. Denies reading `runs/`, `eval/`, `context/`; blocks `curl` and `wget`. |
| Tested blocks | `builder/blocks/` | Documents to text, tools from any API file, node factories, proven patterns, date helpers, linter, checks, deploy gate, smoke tests. |
| Platform client | `kit/freya.py` | The organizers' Freya API client. |
| Bank mock | `mock/` | Cloudflare Worker with one Durable Object. The phone agent may call only this. |
| Not needed to run | `eval/`, `notes/`, `builder/tests/` | Evaluation, notes, tests. |

## 2. One run

```mermaid
sequenceDiagram
    participant U as You
    participant B as build.py
    participant A as Agent (skill)
    participant G as Gate (check + deploy)
    participant F as Freya

    U->>B: python3 builder/build.py {case_folder} {mock_url}
    B->>B: case folder to brief.md, GET mock/openapi.json
    B->>A: start run (watchdog 25 min)
    loop until every check says OK
        A->>A: ledger, spec.json, build_agent.py, workflow.json
        A->>G: builder.blocks.check
    end
    A->>G: builder.blocks.deploy
    G->>F: create or update workflow (same slot, same workflow)
    A->>F: smoke tests in chat
    A-->>B: done
    B->>G: deploy again if workflow.json changed
    B->>F: export workflow
    B-->>U: created workflow_id=... end seconds=... (exit 0)
```

## 3. Set up from scratch

1. Python 3.10 or newer (tested on 3.12). On Debian and Ubuntu: `sudo apt install python3-venv`.
2. `python3 -m venv .venv`, activate it, `pip install -r requirements.txt`.
3. Copy `kit/env.example` to `env.sh`, fill in `FREYA_API_KEY` and `FREYA_BANK_TEAM_KEY`. On macOS and Linux: `source env.sh`. PowerShell does not read `env.sh`; set the three variables with `$env:NAME = "value"`.
4. A Claude login (`claude auth login`, the binary is in the SDK package) or `ANTHROPIC_API_KEY`.
5. Run: `python3 builder/build.py {case_folder} {mock_url}`.
6. Node and `npx wrangler deploy` are needed only to redeploy `mock/`.

The final-case steps are in `notes/hidden-runbook.md` (written for macOS).

## 4. Which OS runs it

```mermaid
flowchart TD
    Q{"OS"} --> M["macOS<br/>team's build machine<br/>(not re-tested here)"]
    Q --> L["Linux<br/>Ubuntu 24.04, Python 3.12<br/>119 builder tests pass"]
    Q --> W["Windows<br/>fails as committed"]
    W --> W1["import fcntl: ModuleNotFoundError"]
    W --> W2["signal.SIGALRM does not exist"]
    W --> W3["default encoding cp1254:<br/>Turkish text becomes mojibake,<br/>then UnicodeEncodeError"]
    W1 & W2 & W3 --> P["Prototype fix: 10 files, ~71 lines<br/>119 tests pass on Windows and Linux<br/>(not applied to the repo)"]

    style M fill:#dff5e1,stroke:#2e7d32,color:#000
    style L fill:#dff5e1,stroke:#2e7d32,color:#000
    style W fill:#fde0dc,stroke:#c62828,color:#000
    style P fill:#fff4d6,stroke:#b26a00,color:#000
```

| OS | Checked | Result |
|---|---|---|
| macOS | Live builds by the team | Works. Not re-tested on 11 October. |
| Linux | Fresh install of the committed files in WSL Ubuntu (Python 3.12), `pytest builder/tests` | 119 pass. Needs `python3-venv`. |
| Windows | Same tests, as committed | The import of `builder.blocks.deploy` fails, so nothing runs. |

**Not verified:** a full live build on Windows (the agent's Bash tool needs Git Bash, and a `$BUILDER_PYTHON` path with backslashes may break there); Python 3.10 and 3.11.

**Windows fix, if wanted** (prototype, tested, not in `builder/`):

- `deploy.py`: `fcntl.flock` becomes a `msvcrt.locking` fallback that waits in a loop.
- `check.py`: without `SIGALRM`, a `threading.Timer` calls `_thread.interrupt_main` and the code turns it into `SnippetTimeout`.
- Every `read_text`, `write_text` and `open` gets `encoding="utf-8"`; the agent's child processes get `PYTHONUTF8=1`; stdout is reconfigured to UTF-8.
- The test fixtures are written as UTF-8.
