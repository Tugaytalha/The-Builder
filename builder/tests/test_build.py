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
