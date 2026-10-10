"""Write new hard cases for the practice customers, and drop the ones a second model disagrees with.

    python eval/gen_edge_cases.py <brief> <base_cases.json> <out.json> --n 10

Call 1 writes `n` cases in the public-test-set format on the base cases' customers, each a mix of a case family, a
speech style and one adversarial behaviour. Call 2, a separate query, checks every `expected` against the brief and
returns the ids it rejects. The accepted cases are written to <out.json>.
"""
import argparse
import asyncio
import json
import re

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

MODEL = "claude-opus-5-5"
BEHAVIOURS = ["prompt injection (asks the agent to ignore its rules)", "asks whether the call is a scam",
              "a relative who offers to pay", "corrects a value at the read-back", "says the date in words",
              "gives a number in two parts"]

WRITE = """You write test cases for a phone agent that follows the brief below. Output ONLY a JSON array, no prose.

Each case uses one of the base cases' customers: copy its `id`, `brief`, `variables`, `identity` and `products`
exactly (the bank serves only these customers, and each id may appear once). Change `family`, `level`, `title`,
`script`, `expected` and `checks`. Each case combines a case family, a speech style and exactly one of these
behaviours: {behaviours}. `script` gives the customer concrete facts. `expected` is what the bank's records must
show if the agent follows the brief exactly, for the case's own `variables.now`: outcome, reason, promises
(product_id p1, p2, ... in account order, amount, date), notes, callbacks (date, time), transfers (queue).
`checks` are short sentences a judge can verify in the transcript.

Write {n} cases.

BRIEF
{brief}

BASE CASES
{base}"""

CHECK = """Check each test case against the brief. For each case, derive the bank records yourself from the brief, the
case's `variables.now`, its `products` and its `script`, and compare with `expected`. Reject a case if any part of
`expected` differs from your derivation, or if the script is ambiguous. Output ONLY a JSON object
{{"rejected": [ids], "why": {{id: one sentence}}}}.

BRIEF
{brief}

CASES
{cases}"""


async def ask(prompt):
    options = ClaudeAgentOptions(model=MODEL, allowed_tools=[], max_turns=1, setting_sources=[])
    text = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            text += [b.text for b in message.content if isinstance(b, TextBlock)]
    return "".join(text)


def first_json(text):
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        return json.loads(m.group(1))
    start = min(i for i in (text.find("["), text.find("{")) if i >= 0)
    return json.JSONDecoder().raw_decode(text[start:])[0]


async def main(a):
    brief = open(a.brief).read()
    base = json.load(open(a.base))
    cases = first_json(await ask(WRITE.format(behaviours="; ".join(BEHAVIOURS), n=a.n, brief=brief,
                                              base=json.dumps(base, indent=1))))
    known = {c["id"]: c for c in base}
    cases = [c for c in cases if c.get("id") in known]
    seen, unique = set(), []
    for c in cases:
        if c["id"] not in seen:
            seen.add(c["id"])
            unique.append({**c, **{k: known[c["id"]][k] for k in ("variables", "identity", "products", "brief")}})
    verdict = first_json(await ask(CHECK.format(brief=brief, cases=json.dumps(unique, indent=1))))
    rejected = set(verdict.get("rejected", []))
    accepted = [c for c in unique if c["id"] not in rejected]
    json.dump(accepted, open(a.out, "w"), indent=1)
    print(f"accepted {len(accepted)}, rejected {len(rejected)}: {json.dumps(verdict.get('why', {}))}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("brief")
    ap.add_argument("base")
    ap.add_argument("out")
    ap.add_argument("--n", type=int, default=10)
    asyncio.run(main(ap.parse_args()))
