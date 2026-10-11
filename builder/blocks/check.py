"""Loop-1 checks on a run folder. They need no bank customer, so they work on any brief.

    python -m builder.blocks.check <run_dir> [--no-dry-run]

Run folder contract: brief.md, tool_api.json, ledger.md, spec.json, build_agent.py, workflow.json and an
optional test_rules.py.
"""
import _thread
import json
import os
import signal
import subprocess
import sys
import threading
from datetime import date, timedelta
from pathlib import Path

from builder.blocks.coderun import run_snippet
from builder.blocks.lint import lint
from builder.blocks.tools import load_api

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "kit"))
import freya  # noqa: E402

MECHANISMS = {"code", "route", "tool", "fixed-line", "prompt", "none-needed"}
HEADER = ["id", "rule", "source", "mechanism", "where"]


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def ledger_problems(text):
    rows = [_cells(line) for line in text.splitlines() if line.strip().startswith("|")]
    if not rows or [c.lower() for c in rows[0]] != HEADER:
        return ["ledger: the first table row must be | " + " | ".join(HEADER) + " |"]
    body = [r for r in rows[1:] if not all(set(c) <= set("-: ") for c in r)]
    if not body:
        return ["ledger: no rule rows"]
    problems, seen = [], set()
    for r in body:
        r = (r + [""] * 5)[:5]
        rid, _, _, mechanism, where = r
        if rid in seen:
            problems.append(f"ledger {rid}: duplicate id")
        seen.add(rid)
        if not mechanism:
            problems.append(f"ledger {rid}: empty mechanism")
        elif mechanism not in MECHANISMS:
            problems.append(f"ledger {rid}: unknown mechanism {mechanism!r}")
        if not where:
            problems.append(f"ledger {rid}: empty where")
    return problems


def _code_nodes(workflow):
    for node in workflow.get("nodes", {}).values():
        if node.get("node_type") != "code":
            continue
        for action in node.get("pre_actions", []):
            code = action.get("function", {}).get("parameters", {}).get("properties", {}).get("code", {}).get("default")
            if isinstance(code, str):
                yield node["name"], code


def _days(sample_now):
    first = date.fromisoformat(str(sample_now)[:10])
    days = [first + timedelta(days=i) for i in range(14)] + [date(first.year, 12, 31)]
    return [d.isoformat() + "T11:00" for d in days]


UTF8_ENV = {"PYTHONUTF8": "1"} if sys.platform == "win32" else {}     # Windows reads files in a legacy code page
SNIPPET_TIMEOUT_S = 10     # one code node on one day; the platform stops code at 10 s too
RULES_TIMEOUT_S = 120


class SnippetTimeout(BaseException):     # not an Exception: the node's own `except Exception` must not catch it
    pass


def _run_with_timeout(code, vars):
    """run_snippet, stopped after SNIPPET_TIMEOUT_S: an endless loop must not hang the gate."""
    if not hasattr(signal, "SIGALRM"):      # Windows has no SIGALRM: a timer interrupts the main thread instead
        timer = threading.Timer(SNIPPET_TIMEOUT_S, _thread.interrupt_main)
        timer.start()
        try:
            return run_snippet(code, vars)
        except KeyboardInterrupt:
            raise SnippetTimeout(f"no end after {SNIPPET_TIMEOUT_S} s (time limit)")
        finally:
            timer.cancel()

    def stop(signum, frame):
        raise SnippetTimeout(f"no end after {SNIPPET_TIMEOUT_S} s (time limit)")
    old = signal.signal(signal.SIGALRM, stop)
    signal.alarm(SNIPPET_TIMEOUT_S)
    try:
        return run_snippet(code, vars)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def snippet_problems(workflow, sample_vars):
    """Run the code nodes in workflow order, once per day. Report each distinct crash once, with its first day."""
    first_seen, slow = {}, set()
    for now in _days(sample_vars.get("now")):
        vars = {**sample_vars, "now": now}
        for name, code in _code_nodes(workflow):
            if name in slow:
                continue                    # one time limit per node is enough: the gate must end in time
            try:
                vars = _run_with_timeout(code, vars)
                error = vars.pop(name + "_code_error", None)
            except SnippetTimeout as exc:
                error = repr(exc)
                slow.add(name)
            except Exception as exc:
                error = repr(exc)
            if error:
                first_seen.setdefault((name, error), now)
    return [f"{name}: {error} (first when now is {now})" for (name, error), now in first_seen.items()]


def _rules_tests(run):
    if not (run / "test_rules.py").exists():
        return []
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_rules.py"], cwd=run,
                           capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(REPO), **UTF8_ENV}, timeout=RULES_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return [f"test_rules: no end after {RULES_TIMEOUT_S} s (time limit)"]
    return [] if r.returncode == 0 else ["test_rules: " + line for line in r.stdout.splitlines()[-20:]]


def _dry_run(workflow):
    try:
        freya.validate_workflow("dry-run", workflow)
        return []
    except RuntimeError as exc:
        return ["dry run: " + str(exc)[:1500]]


def run_checks(run_dir, dry_run=True):
    run = Path(run_dir)
    out = {k: [] for k in ("ledger", "lint", "snippets", "rules_tests", "dry_run")}
    if not (run / "ledger.md").exists():
        out["ledger"] = ["ledger.md is missing"]
    else:
        out["ledger"] = ledger_problems((run / "ledger.md").read_text(encoding="utf-8"))
    try:
        spec = json.loads((run / "spec.json").read_text(encoding="utf-8"))
        workflow = json.loads((run / "workflow.json").read_text(encoding="utf-8"))
        api = load_api(str(run / "tool_api.json"))
    except (OSError, ValueError) as exc:
        out["lint"] = [f"cannot load the run files: {exc}"]
        return out
    out["lint"] = lint(workflow, api, spec.get("lint", {}))
    out["snippets"] = snippet_problems(workflow, spec.get("sample_vars", {}))
    out["rules_tests"] = _rules_tests(run)
    if dry_run:
        out["dry_run"] = _dry_run(workflow)
    return out


def main(argv):
    result = run_checks(argv[0], dry_run="--no-dry-run" not in argv)
    for key, problems in result.items():
        print(f"{key}: " + ("OK" if not problems else ""))
        for p in problems:
            print("  - " + p)
    return 1 if any(result.values()) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
