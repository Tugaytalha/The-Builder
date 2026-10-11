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

## 3. Set up and run

The step-by-step guide, for macOS, Linux and Windows, is in the [README](../README.md#setup-from-scratch). The final-case checklist is `notes/hidden-runbook.md` (written for macOS).

## 4. Which OS runs it

Commit `84bdbf2` made Windows work. Before it, the builder did not import on Windows. The macOS and Linux code paths are unchanged.

```mermaid
flowchart TD
    Q{"OS"} --> M["macOS<br/>team's build machine<br/>(not re-tested here)"]
    Q --> L["Linux<br/>Ubuntu 24.04, Python 3.12<br/>121 builder tests pass"]
    Q --> W["Windows<br/>Python 3.12<br/>121 builder tests pass"]
    W -.->|"before 84bdbf2"| B["import fcntl failed<br/>no signal.SIGALRM<br/>cp1254 broke Turkish text"]
    W -->|"fixed by"| F["msvcrt lock<br/>timer timeout<br/>UTF-8 file I/O<br/>short path for the agent shell"]

    style M stroke:#2e7d32,stroke-width:3px
    style L stroke:#2e7d32,stroke-width:3px
    style W stroke:#2e7d32,stroke-width:3px
    style B stroke:#c62828,stroke-width:3px
    style F stroke:#b26a00,stroke-width:3px
```

| OS | Checked | Result |
|---|---|---|
| macOS | Live builds by the team | Works. Not re-tested on 11 October. The code it runs is the same as before. |
| Linux | Fresh export of the commit in WSL Ubuntu (Python 3.12): 121 builder tests, 38 eval tests, contamination 0 | Pass. Needs `python3-venv`. The `fcntl` and `SIGALRM` paths are still the ones used. |
| Windows | 121 builder tests, 38 eval tests, contamination 0. A one-turn Claude Agent SDK run whose Bash tool ran `$BUILDER_PYTHON` and imported `builder` | Pass. |

**How the Windows paths are kept apart:**

- `deploy.py`: `fcntl.flock` is tried first; only if `fcntl` does not exist, `msvcrt.locking` waits in a loop.
- `check.py`: `SIGALRM` is used when it exists; otherwise a `threading.Timer` calls `_thread.interrupt_main` and the code turns it into `SnippetTimeout`.
- `build.py`: `PYTHONUTF8=1`, the UTF-8 stdout and the short DOS-style `BUILDER_PYTHON` path (a path with a space cannot be split by the agent's shell) apply only when `sys.platform == "win32"`.
- Every `read_text`, `write_text` and `open` in `builder/` names `encoding="utf-8"`. That is the encoding macOS and Linux already used.
- Two new tests cover the timeout and the lock on every OS.

**Not verified:** a full live build on Windows (it needs Freya workflow quota; the one-turn agent run above covers the agent shell only), and Python 3.10 and 3.11.
