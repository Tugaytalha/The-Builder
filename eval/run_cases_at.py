"""kit/tools/run_cases.py, with each case's own `now` (spike S5: the bank accepts another day).

    python3 eval/run_cases_at.py <agent_id> --cases <file> [same options as run_cases.py]

It wraps run_cases' `http` so that a new practice session takes `now` from the case's `variables.now`.
Nothing in kit/ changes.
"""
import json
import re
import sys
import time
import urllib.error
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


STUCK_S = 8 * 60


def unstick(api, now=time.time):
    """Wrap freya.api. A simulation that stays "running" for STUCK_S after its start although every run has ended
    (seen on the platform) is set to "completed", so the runner can read its results."""
    first = {}

    def wrapped(method, path, body=None, **params):
        out = api(method, path, body, **params)
        m = re.fullmatch(r"/api/v2/simulations/([\w-]+)", path)
        if method == "GET" and m:
            sim = out.get("simulation") or out
            first.setdefault(m.group(1), now())
            if sim.get("status") == "running" and now() - first[m.group(1)] > STUCK_S:
                its = api("GET", path + "/iterations")
                its = its.get("iterations") or its.get("items") or its
                runs = api("GET", f"{path}/iterations/{its[0]['id']}", limit=100).get("runs", [])
                if runs and all(r.get("endedAt") for r in runs):
                    print("simulation ended its runs but stays running: cancelling it", flush=True)
                    api("POST", path + "/cancel", {})        # a PUT to completed did not hold (round 6)
                    sim["status"] = "completed"
        return out
    return wrapped


def retry_reads(api, wait=time.sleep, tries=45):
    """Wrap freya.api. A GET that fails with a server error (500, 502, 503, 504: seen in rounds 5b, 5c and 6) or a network
    error (round 6: DNS) is tried again;
    a write is tried again only after a 503 (refused before anything was written).
    The waits cover an outage of about 22 minutes (round 6: 504s for more than 2.5 minutes stopped a score run)."""
    def wrapped(method, path, body=None, **params):
        for i in range(tries):
            try:
                return api(method, path, body, **params)
            except (RuntimeError, urllib.error.URLError) as e:
                server_or_dns = isinstance(e, urllib.error.URLError) or re.search(r"-> 50[0234]", str(e))
                refused = re.search(r"-> 503", str(e))      # a 503 is refused before anything is written
                if i == tries - 1 or not (refused or (method == "GET" and server_or_dns)):
                    raise
                print(f"{method} {path} failed ({str(e)[-30:]}), trying again", flush=True)
                wait(min(30, 10 * (i + 1)))
    return wrapped


def main(argv):
    import freya
    import run_cases
    freya.api = unstick(retry_reads(freya.api))
    cases = argv[argv.index("--cases") + 1] if "--cases" in argv else str(KIT / "public-test-set.json")
    nows = {c["id"]: c["variables"]["now"] for c in json.load(open(cases)) if c.get("variables", {}).get("now")}
    run_cases.http = wrap(run_cases.http, nows)
    sys.argv = ["run_cases.py"] + argv
    run_cases.main()


if __name__ == "__main__":
    main(sys.argv[1:])
