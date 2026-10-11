"""Build a Freya phone agent from one brief and one tool API file.

    python3 builder/build.py <brief_path> <tool_api_path>

A deterministic shell around one Claude Agent SDK run. The agent writes the run folder and deploys through the
gate. This file then deploys the last workflow if it changed, exports the deployed version to
submission/<slot>.workflow.json, and ends the trace. A watchdog stops the agent at 25 minutes; after 28 minutes no
new deploy starts, so the gate, the deploy and the export end before 30 minutes.
"""
import asyncio
import dataclasses
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from builder.blocks.check import freya  # noqa: E402
from builder.blocks.deploy import GateError, deploy  # noqa: E402
from builder.trace import Trace  # noqa: E402

WATCHDOG_S = 25 * 60
LATE_S = 28 * 60          # no new deploy after this: the last deployed version is exported
EXPORT_TRIES, EXPORT_WAIT_S = 3, 20
MODEL = os.environ.get("BUILDER_MODEL", "claude-opus-5-5")
TEST_COMMANDS = ("builder.blocks.check", "builder.blocks.smoke", "builder.blocks.deploy")


def _purpose(message, redact):
    """One line on the call's purpose. Redact before the cut: a cut key is not found by the redaction."""
    from claude_agent_sdk import TextBlock, ToolUseBlock
    for block in message.content:
        if isinstance(block, ToolUseBlock):
            return redact(f"{block.name} {json.dumps(block.input)}")[:120]
    for block in message.content:
        if isinstance(block, TextBlock) and block.text.strip():
            return redact(block.text.strip())[:100]
    return "thinking"


# FREYA_BANK_TEAM_KEY is for the eval scripts only: the build agent does not get it.
AGENT_ENV = {"BASH_DEFAULT_TIMEOUT_MS": "600000", "BASH_MAX_TIMEOUT_MS": "900000", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
             "PYTHONPATH": str(REPO), "BUILDER_PYTHON": sys.executable, "FREYA_BANK_TEAM_KEY": ""}


async def run_agent(run_dir, trace, deadline):
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, ToolResultBlock, ToolUseBlock, UserMessage, query
    options = ClaudeAgentOptions(
        cwd=str(REPO / "builder"), model=MODEL, skills=["build-phone-agent"], setting_sources=["project"],
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash", "Task", "Agent"],
        permission_mode="dontAsk", max_turns=200,
        env=AGENT_ENV)
    minutes = int((deadline - time.time()) / 60)
    utc = lambda t: time.strftime("%H:%M", time.gmtime(t))
    prompt = (f"Use the build-phone-agent skill. Run folder: {run_dir}. Slot: {run_dir.name.rsplit('-', 2)[0]}. "
              f"It is {utc(time.time())} UTC now. Time left: {minutes} minutes: the build stops at {utc(deadline)} UTC.")
    commands = {}
    transcript = open(run_dir / "agent.jsonl", "a")   # every message, for debugging; the trace is the summary
    async for message in query(prompt=prompt, options=options):
        transcript.write(trace.redact(json.dumps({"type": type(message).__name__, **dataclasses.asdict(message)}, default=str)) + "\n")
        transcript.flush()
        if isinstance(message, AssistantMessage):
            trace.log("model_call", model=message.model, purpose=_purpose(message, trace.redact))
            for block in message.content:
                if isinstance(block, ToolUseBlock) and block.name == "Bash":
                    commands[block.id] = str(block.input.get("command", ""))
        elif isinstance(message, UserMessage) and isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, ToolResultBlock) and any(c in commands.get(block.tool_use_id, "") for c in TEST_COMMANDS):
                    content = block.content if isinstance(block.content, str) else json.dumps(block.content)
                    trace.log("test", command=commands[block.tool_use_id][:200],
                              output="\n".join(str(content).splitlines()[-20:]))
        elif isinstance(message, ResultMessage):
            trace.log("agent_done", turns=message.num_turns, seconds=round(message.duration_ms / 1000),
                      cost_usd=message.total_cost_usd, error=message.is_error)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _counts(workflow):
    nodes = list(workflow.get("nodes", {}).values()) + list(workflow.get("global_nodes", {}).values())
    tools = {t["function"]["name"] for n in nodes for t in (n.get("tools") or []) + (n.get("pre_actions") or [])}
    tools |= {t["function"]["name"] for t in workflow.get("tools") or []}
    return len(nodes), len(tools)


def run(brief, api, agent=run_agent):
    t0 = time.time()
    slot = brief.stem
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    run_dir = REPO / "builder" / "runs" / f"{slot}-{stamp}"
    run_dir.mkdir(parents=True)
    shutil.copy(brief, run_dir / "brief.md")
    shutil.copy(api, run_dir / "tool_api.json")
    trace = Trace(REPO / "traces" / f"{slot}-{stamp}.jsonl",
                  [os.environ.get("FREYA_API_KEY", ""), os.environ.get("FREYA_BANK_TEAM_KEY", "")])
    trace.log("start", brief=str(brief), tool_api=str(api), model=MODEL, run_dir=str(run_dir))

    try:
        asyncio.run(asyncio.wait_for(agent(run_dir, trace, t0 + WATCHDOG_S), timeout=WATCHDOG_S - (time.time() - t0)))
    except (asyncio.TimeoutError, TimeoutError):
        trace.log("watchdog", message=f"agent stopped after {round(time.time() - t0)} s")
    except Exception as exc:
        trace.log("agent_error", message=repr(exc)[:1000])

    workflow_file, deployed_file = run_dir / "workflow.json", run_dir / "deployed.json"
    deployed = json.loads(deployed_file.read_text()) if deployed_file.exists() else None
    changed = workflow_file.exists() and (not deployed or deployed.get("sha256") != _sha(workflow_file))
    if changed and deployed and time.time() - t0 > LATE_S:
        trace.log("late_skip", message="no time for the gate and a deploy", kept="the last deployed version")
    elif changed:
        try:
            deployed = deploy(str(run_dir), slot)
            trace.log("deployed", by="build.py", **deployed)
        except GateError as exc:
            trace.log("gate_refused", problems=exc.problems[:30], kept="the last deployed version")
        except Exception as exc:
            trace.log("deploy_error", message=repr(exc)[:1000])
    if not deployed:
        trace.log("failed", message="no workflow version passed the gate in this run")
        trace.log("end", seconds=round(time.time() - t0))
        return 1

    out = REPO / "submission" / f"{slot}.workflow.json"
    out.parent.mkdir(exist_ok=True)
    for i in range(EXPORT_TRIES):     # Freya gave 5xx and network errors for hours on 11 October
        try:
            freya.export_workflow(deployed["workflow_id"], str(out))
            break
        except Exception as exc:
            trace.log("export_retry" if i < EXPORT_TRIES - 1 else "export_error", message=repr(exc)[:500])
            if i == EXPORT_TRIES - 1:
                trace.log("end", seconds=round(time.time() - t0))
                return 1
            time.sleep(EXPORT_WAIT_S)
    nodes, tools = _counts(json.loads(out.read_text()).get("workflow", {}))
    trace.log("created", workflow_id=deployed["workflow_id"], agent_id=deployed["agent_id"], nodes=nodes, tools=tools,
              export=str(out))
    trace.log("end", seconds=round(time.time() - t0))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(run(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()))
