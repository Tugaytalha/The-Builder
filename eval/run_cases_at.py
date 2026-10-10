"""kit/tools/run_cases.py, with each case's own `now` (spike S5: the bank accepts another day).

    python3 eval/run_cases_at.py <agent_id> --cases <file> [same options as run_cases.py]

It wraps run_cases' `http` so that a new practice session takes `now` from the case's `variables.now`.
Nothing in kit/ changes.
"""
import json
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[1] / "kit"
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(KIT / "tools"))


def wrap(http, nows):
    def wrapped(path, body=None):
        out = http(path, body)
        if path == "/v1/practice/sessions" and isinstance(body, dict) and body.get("case") in nows:
            out["variables"]["now"] = nows[body["case"]]
        return out
    return wrapped


def main(argv):
    import run_cases
    cases = argv[argv.index("--cases") + 1] if "--cases" in argv else str(KIT / "public-test-set.json")
    nows = {c["id"]: c["variables"]["now"] for c in json.load(open(cases)) if c.get("variables", {}).get("now")}
    run_cases.http = wrap(run_cases.http, nows)
    sys.argv = ["run_cases.py"] + argv
    run_cases.main()


if __name__ == "__main__":
    main(sys.argv[1:])
