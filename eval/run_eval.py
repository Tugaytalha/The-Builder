"""Loop 2: build every suite brief with the real run command, score each agent, write the report.

    python eval/run_eval.py --round <n> [--heldout] [--styles] [--only name,name] [--no-build]

Writes eval/results/<n>/: <name>.build.log, <name>.json, <name>-<style>.json, report.md, summary.json.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PYTHON = str(REPO / ".venv" / "bin" / "python")
STYLES = ["pieces", "corrects", "talkative", "asks_back", "in_words"]
CLASSES = [
    ("identity", ("verif", "identity", "security")),
    ("third party", ("callback", "relative", "wrong number", "deceased")),
    ("attempts", ("attempt", "offer", "persuasion")),
    ("dates", ("date", "deadline", "holiday")),
    ("amounts", ("amount", "floor", "minimum", "promises [")),
    ("wording", ("said", "word", "sentence")),
    ("tool honesty", ("recorded", "failed", "service")),
    ("closing", ("outcome", "close_call", "notes")),
    ("platform", ("slow", "no verdict", "hung up")),
]


def classify(reason):
    text = reason.lower()
    for name, words in CLASSES:
        if any(w in text for w in words):
            return name
    return "other"


def report(rows, previous):
    before = {r["name"]: r for r in (previous or {}).get("rows", [])}
    lines = ["| entry | set | passed | total | build s | build exit | change |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        old = before.get(r["name"])
        change = "" if not old or old.get("passed") is None or r.get("passed") is None else f"{r['passed'] - old['passed']:+d}"
        lines.append(f"| {r['name']} | {r['set']} | {r.get('passed', '-')} | {r.get('total', '-')} | {r.get('build_s', '-')} "
                     f"| {r.get('build_exit', '-')} | {change} |")
    groups = {}
    for r in rows:
        for f in r.get("failures", []):
            for reason in f["reasons"]:
                groups.setdefault(classify(reason), []).append(f"{r['name']} {f['id']}: {reason[:200]}")
    lines.append("")
    for name in sorted(groups, key=lambda k: -len(groups[k])):
        lines.append(f"## {name} ({len(groups[name])})")
        lines += ["- " + x for x in groups[name]] + [""]
    return "\n".join(lines)


def _failures(result_file):
    data = json.load(open(result_file))
    out = {}
    for rows in data.get("all_rows", [data.get("rows", [])]):
        for row in rows:
            if not row["pass"]:
                out.setdefault(row["id"], []).extend(row["failed"])
    return data.get("passed"), data.get("total"), [{"id": k, "reasons": v} for k, v in out.items()]


def _move_kit_results():
    src = REPO / "kit" / "results"
    if src.exists():
        shutil.move(str(src), str(REPO / "runs" / (time.strftime("%Y%m%d-%H%M%S") + "-kit-results")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", required=True)
    ap.add_argument("--heldout", action="store_true")
    ap.add_argument("--styles", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--no-build", action="store_true")
    a = ap.parse_args()
    if subprocess.run([PYTHON, str(REPO / "eval" / "contamination.py")]).returncode:
        sys.exit("contamination found: fix builder/ first")
    suite = [e for e in json.load(open(REPO / "eval" / "suite.json"))
             if (e["set"] == "dev" or a.heldout) and (not a.only or e["name"] in a.only.split(","))]
    out = REPO / "eval" / "results" / a.round
    out.mkdir(parents=True, exist_ok=True)
    rows = {e["name"]: {"name": e["name"], "set": e["set"]} for e in suite}

    if not a.no_build:
        _move_kit_results()
        procs = {}
        for e in suite:
            log = open(out / f"{e['name']}.build.log", "w")
            procs[e["name"]] = (subprocess.Popen([PYTHON, "builder/build.py", e["brief"], e["api"]], cwd=REPO, stdout=log,
                                                 stderr=subprocess.STDOUT), time.time())
        for name, (p, t0) in procs.items():
            rows[name]["build_exit"] = p.wait()
            rows[name]["build_s"] = round(time.time() - t0)

    for e in suite:
        export = REPO / "submission" / f"{e['name']}.workflow.json"
        if not export.exists():
            continue
        agent_id = json.load(open(export))["agent_id"]
        runs = [("", ["--reps", "3"])] + ([(f"-{s}", ["--style", s]) for s in STYLES] if a.styles and e["set"] == "dev" else [])
        for suffix, extra in runs:
            result = out / f"{e['name']}{suffix}.json"
            with open(out / f"{e['name']}{suffix}.score.log", "w") as log:
                subprocess.run(["python3", "eval/run_cases_at.py", agent_id, "--cases", e["cases"], "--brief", e["case_brief"],
                                "--out", str(result)] + extra, cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
            if result.exists():
                passed, total, failures = _failures(result)
                if not suffix:
                    rows[e["name"]].update(passed=passed, total=total, failures=failures)
                else:
                    rows[e["name"]].setdefault("styles", {})[suffix[1:]] = passed

    rounds = sorted((p for p in (REPO / "eval" / "results").iterdir() if p.is_dir() and p.name != a.round
                     and (p / "summary.json").exists()), key=lambda p: p.stat().st_mtime)
    previous = json.load(open(rounds[-1] / "summary.json")) if rounds else None
    summary = {"round": a.round, "at": time.strftime("%Y-%m-%d %H:%M:%S"), "rows": list(rows.values())}
    json.dump(summary, open(out / "summary.json", "w"), indent=1)
    (out / "report.md").write_text(report(summary["rows"], previous))
    print((out / "report.md").read_text())


if __name__ == "__main__":
    main()
