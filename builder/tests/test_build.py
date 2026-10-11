import asyncio
import hashlib
import json

import pytest

from builder import build

WORKFLOW = {"initial_node": "a", "nodes": {"a": {"name": "a", "tools": [{"function": {"name": "t1"}}]}}}


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "brief-x.md").write_text("brief")
    (tmp_path / "in" / "api.json").write_text("{}")
    monkeypatch.setattr(build, "REPO", tmp_path)
    exported = []

    def export(workflow_id, path):
        exported.append(workflow_id)
        open(path, "w").write(json.dumps({"workflow": WORKFLOW}))
    monkeypatch.setattr(build.freya, "export_workflow", export)
    monkeypatch.setattr(build, "deploy", lambda run_dir, slot: pytest.fail("deploy must not run"))
    return tmp_path, exported


def kinds(tmp_path):
    trace = next((tmp_path / "traces").glob("*.jsonl"))
    return [json.loads(line)["kind"] for line in trace.read_text().splitlines()]


def run(tmp_path, agent):
    return build.run(tmp_path / "in" / "brief-x.md", tmp_path / "in" / "api.json", agent=agent)


def test_build_exports_last_deployed_when_agent_crashes(repo):
    tmp_path, exported = repo

    async def agent(run_dir, trace, deadline):
        text = json.dumps(WORKFLOW)
        (run_dir / "workflow.json").write_text(text)
        (run_dir / "deployed.json").write_text(json.dumps({"workflow_id": "w1", "agent_id": "a1",
                                                           "sha256": hashlib.sha256(text.encode()).hexdigest()}))
        raise RuntimeError("agent crashed")
    assert run(tmp_path, agent) == 0
    assert exported == ["w1"] and "agent_error" in kinds(tmp_path) and "created" in kinds(tmp_path)
    assert (tmp_path / "submission" / "brief-x.workflow.json").exists()


def test_build_deploys_changed_workflow(repo, monkeypatch):
    tmp_path, exported = repo
    monkeypatch.setattr(build, "deploy", lambda run_dir, slot: {"workflow_id": "w2", "agent_id": "a2", "sha256": "x"})

    async def agent(run_dir, trace, deadline):
        (run_dir / "workflow.json").write_text(json.dumps(WORKFLOW))
    assert run(tmp_path, agent) == 0 and exported == ["w2"]


def test_build_keeps_deployed_version_when_gate_refuses(repo, monkeypatch):
    tmp_path, exported = repo

    def refuse(run_dir, slot):
        raise build.GateError(["lint: broken"])
    monkeypatch.setattr(build, "deploy", refuse)

    async def agent(run_dir, trace, deadline):
        (run_dir / "deployed.json").write_text(json.dumps({"workflow_id": "w1", "agent_id": "a1", "sha256": "old"}))
        (run_dir / "workflow.json").write_text(json.dumps(WORKFLOW))
    assert run(tmp_path, agent) == 0 and exported == ["w1"] and "gate_refused" in kinds(tmp_path)


def test_build_fails_loudly_when_nothing_deployed(repo):
    tmp_path, exported = repo

    async def agent(run_dir, trace, deadline):
        return None
    assert run(tmp_path, agent) == 1
    assert exported == [] and "failed" in kinds(tmp_path)


def test_build_stops_agent_at_deadline(repo, monkeypatch):
    tmp_path, exported = repo
    monkeypatch.setattr(build, "WATCHDOG_S", 1)

    async def agent(run_dir, trace, deadline):
        text = json.dumps(WORKFLOW)
        (run_dir / "workflow.json").write_text(text)
        (run_dir / "deployed.json").write_text(json.dumps({"workflow_id": "w1", "agent_id": "a1",
                                                           "sha256": hashlib.sha256(text.encode()).hexdigest()}))
        await asyncio.sleep(30)
    assert run(tmp_path, agent) == 0
    assert "watchdog" in kinds(tmp_path) and "created" in kinds(tmp_path)


def deployed_agent(text=json.dumps(WORKFLOW)):
    async def agent(run_dir, trace, deadline):
        (run_dir / "workflow.json").write_text(text)
        (run_dir / "deployed.json").write_text(json.dumps({"workflow_id": "w1", "agent_id": "a1",
                                                           "sha256": hashlib.sha256(text.encode()).hexdigest()}))
    return agent


def test_build_tries_the_export_again_after_a_freya_error(repo, monkeypatch):
    # review: on 11 October Freya gave 5xx errors for hours; one failed export lost the submission file
    tmp_path, exported = repo
    calls = []

    def export(workflow_id, path):
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("GET /api/v2/workflow/w1 -> 504: error code: 504")
        open(path, "w").write(json.dumps({"workflow": WORKFLOW}))
    monkeypatch.setattr(build.freya, "export_workflow", export)
    monkeypatch.setattr(build, "EXPORT_WAIT_S", 0)
    assert run(tmp_path, deployed_agent()) == 0 and "created" in kinds(tmp_path)


def test_build_ends_the_trace_when_the_export_fails(repo, monkeypatch):
    tmp_path, exported = repo

    def export(workflow_id, path):
        raise RuntimeError("GET /api/v2/workflow/w1 -> 504: error code: 504")
    monkeypatch.setattr(build.freya, "export_workflow", export)
    monkeypatch.setattr(build, "EXPORT_WAIT_S", 0)
    assert run(tmp_path, deployed_agent()) == 1
    assert kinds(tmp_path)[-2:] == ["export_error", "end"]


def test_counts_accept_null_tools():
    w = {"nodes": {"a": {"name": "a", "tools": None, "pre_actions": None}}, "tools": None}
    assert build._counts(w) == (1, 0)


def test_build_skips_a_late_redeploy(repo, monkeypatch):
    # review: after the watchdog, a full gate and deploy could pass 30 minutes
    tmp_path, exported = repo
    monkeypatch.setattr(build, "LATE_S", -1)

    async def agent(run_dir, trace, deadline):
        await deployed_agent()(run_dir, trace, deadline)
        (run_dir / "workflow.json").write_text(json.dumps(WORKFLOW) + " ")      # changed after the last deploy
    assert run(tmp_path, agent) == 0 and exported == ["w1"] and "late_skip" in kinds(tmp_path)


def test_watchdog_leaves_time_for_the_gate_and_the_export():
    assert build.WATCHDOG_S + 5 * 60 <= 30 * 60


def test_agent_does_not_get_the_team_key():
    # review: only the eval scripts use FREYA_BANK_TEAM_KEY; the build agent must not see it
    assert build.AGENT_ENV["FREYA_BANK_TEAM_KEY"] == ""


def test_purpose_redacts_before_it_cuts():
    from claude_agent_sdk import ToolUseBlock

    class M:
        content = [ToolUseBlock(id="1", name="Bash", input={"command": "x" * 100 + " sekret_team_key_1234567890"})]
    redact = lambda s: s.replace("sekret_team_key_1234567890", "[REDACTED]")
    assert "sekret" not in build._purpose(M, redact)
