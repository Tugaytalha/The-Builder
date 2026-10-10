"""Sub-graphs and tool shapes that the platform spikes proved (notes/platform-spikes.md)."""
from builder.blocks.nodes import api_node, code_node, end_node, go, is_true
from builder.blocks.tools import make_tool

BLOCKED_URL = "https://blocked.invalid/refused-by-guard"


def start(next_node):
    """An empty initial code node. Chat skips the initial node's code (spike S6), so real setup comes after it."""
    return code_node("start", "pass", next_node)


def close_tool(api, name, baked):
    """The closing tool as an end-of-call lifecycle tool (spike S4: a line in an api_request node is spoken after its
    call). `baked` maps each body field to a "{{variable}}" that a closing code node sets. Empty fields are not sent."""
    tool = make_tool(api, name, baked=baked)
    tool["config"]["alwaysRunsAt"] = ["end_of_call"]
    tool["pre_process_code"] = (
        "try:\n    b = config.get('body')\n    if isinstance(b, dict):\n        for k in list(b.keys()):\n"
        "            v = b.get(k)\n            if v is None or str(v).strip() in ('', 'none', 'None') or '{' in str(v):\n"
        "                b.pop(k, None)\nexcept Exception:\n    pass\n")
    return tool


def close_sequence(name, values, goodbye):
    """A code node that sets the closing variables, then an end_call node that says `goodbye`.
    The call's endedReason is `name`."""
    body = "\n".join("vars[%r] = %r" % (k, v) for k, v in values.items())
    return [code_node(name, body, name + "_end"), end_node(name + "_end", name, goodbye)]


def state_tool(name, description, params, body):
    """A code_exec tool the model calls. The model's arguments are in the global dict `params` (spike S2).
    The model sees only "success" (spike S8): the effect must come from the variables `body` writes."""
    code = "try:\n" + "\n".join("    " + line for line in body.splitlines()) + "\n    pass\n"
    code += "except Exception as exc:\n    vars[%r] = repr(exc)[:300]\n" % (name + "_code_error")
    if "{{" in code or "}}" in code:
        raise ValueError(f"state tool {name}: code must not contain template braces")
    return {"type": "function", "function": {
        "name": name, "handler": "__function__:code_exec", "description": description,
        "parameters": {"type": "object", "properties": {**params, "code": {"type": "string", "default": code}},
                       "required": list(params)}}}


def guard_hook(condition_code):
    """A pre_process_code that sends the call to an unreachable URL when `condition_code` is true, so the bank records
    nothing (spike S1). The condition can read `vars` and `config['body']`. The model sees a failed call."""
    return ("try:\n    body = config.get('body') if isinstance(config.get('body'), dict) else dict()\n"
            "    if " + condition_code + ":\n        config['url'] = %r\nexcept Exception:\n    pass\n" % BLOCKED_URL)


def record_with_retry(name, tool, attempts, ok_target, fail_target):
    """An engine-run write (spike S10): the model never calls the tool, so it cannot skip a retry or send other values.
    `tool` comes from make_tool with every body field baked from variables the code set (the agreed values).
    Returns [reset code node `name`, api nodes `name_1` .. `name_<attempts>`]. Route to `name`. A success goes to
    `ok_target`; when every attempt failed, the call goes to `fail_target`.

    An api_request node leaves `<node>_response.data.ok` and `<node>_failure_count`. The reset node sets each
    `<node>_response.data.ok` to "pending" first, so a value left from an earlier product does not count."""
    steps = [f"{name}_{i}" for i in range(1, attempts + 1)]
    reset = code_node(name, "\n".join(f"vars[{s + '_response.data.ok'!r}] = 'pending'" for s in steps), steps[0])
    nodes = [reset]
    for i, step in enumerate(steps):
        nxt = steps[i + 1] if i + 1 < len(steps) else fail_target
        nodes.append(api_node(step, tool, nxt, transitions=[go(ok_target, is_true(step + "_response.data.ok"), "recorded")]))
    return nodes


ANSWER_CODE = r'''
import json
MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
KINDS = %r
q = str(params.get('question') or '')
kind = KINDS.get(q, ['text', 0])
parts = json.loads(vars.get('id_parts') or '[]')
parts = dict(parts) if isinstance(parts, list) else parts
mine = parts.get(q) or dict()
def num(x):
    s = ''.join(ch for ch in str(x or '') if ch.isdigit())
    return int(s) if s else None
for key in ('day', 'month', 'year'):
    v = str(params.get(key) or '').strip()
    if v:
        m = [i + 1 for i, name in enumerate(MONTHS) if v.lower().startswith(name[:3])] if key == 'month' else []
        mine[key] = m[0] if m else num(v)
new_digits = ''.join(ch for ch in str(params.get('digits') or '') if ch.isdigit())
if new_digits:
    have = mine.get('digits') or ''
    mine['digits'] = new_digits if (len(new_digits) >= kind[1] or not have) else have + new_digits
if str(params.get('text') or '').strip():
    mine['text'] = str(params.get('text')).strip()
answer, missing = '', ''
if kind[0] == 'date':
    missing = ', '.join(k for k in ('day', 'month', 'year') if not mine.get(k))
    if not missing and mine.get('year', 0) >= 1000:
        answer = '%%04d-%%02d-%%02d' %% (mine['year'], mine['month'], mine['day'])
    elif not missing:
        missing = 'the year with four digits'
elif kind[0] == 'digits':
    have = mine.get('digits') or ''
    if len(have) >= kind[1]:
        answer = have
    else:
        missing = 'the rest of the digits (' + str(kind[1] - len(have)) + ' more)'
else:
    answer = mine.get('text') or ''
    missing = '' if answer else 'the answer'
if answer:
    parts[q] = dict()
    vars['id_question'] = q
    vars['id_answer'] = answer
    vars['id_send'] = 'yes'
    vars['id_guide'] = 'Say only: one moment, please.'
else:
    parts[q] = mine
    vars['id_guide'] = ('The answer is not complete yet. Ask only for the missing part: ' + missing
                        + '. Do not repeat the question in full, and do not say the parts back.')
vars['id_parts'] = json.dumps(parts)
'''


def answer_tool(questions):
    """The model reports the parts of an identity answer; the code joins them over several turns and says when an
    answer is complete. `questions` maps each question value (as the tool API names it) to ["date", 0],
    ["digits", <count>] or ["text", 0]. A part given after a partial answer is joined to it. On a complete answer it sets id_question, id_answer and id_send = "yes".
    Every turn it writes id_guide, the next step for the model."""
    names = list(questions)
    return state_tool("answer_given", "CALL it every time the customer says anything that is part of a security answer.", {
        "question": {"type": "string", "enum": names, "description": "Which question this is for. One of: " + ", ".join(names) + "."},
        "day": {"type": "string", "description": "Day of the month the customer said in this message, as digits, or empty."},
        "month": {"type": "string", "description": "Month the customer said in this message, as a word or digits, or empty."},
        "year": {"type": "string", "description": "Year the customer said in this message, four digits, or empty. Never guess it."},
        "digits": {"type": "string", "description": "Digits the customer said in this message, digits only, or empty."},
        "text": {"type": "string", "description": "Any other kind of answer, as said, or empty."}},
        ANSWER_CODE % (questions,))


def identity_check(name, verify_tool, back_node, routes, guide_code):
    """The engine-run identity check. Route to `name` when id_send is "yes". `verify_tool` comes from make_tool with the
    question field baked as "{{id_question}}" and the answer field as "{{id_answer}}". After the call, `guide_code` runs
    with `r(field)` = the result field as a string and must set vars['id_guide'] (the next step for the model).
    `routes` are transitions on `<name>_check_response.data.<field>` (passed, failed); otherwise the call goes back to
    `back_node`, whose task shows {{id_guide}}."""
    prefix = name + "_check_response."
    after = ("def r(f):\n    return str(vars.get(%r + f))\n" % (prefix + "data.")
             + "if str(vars.get(%r)) != 'success':\n" % (prefix + "status")
             + "    vars['id_guide'] = 'The check is not available. Ask the same question again.'\n"
             + "else:\n" + "\n".join("    " + line for line in guide_code.splitlines()) + "\n")
    return [code_node(name, "vars['id_send'] = 'no'", name + "_check"),
            api_node(name + "_check", verify_tool, name + "_after"),
            code_node(name + "_after", after, back_node, transitions=routes,
                      fallbacks={"id_guide": "Ask the same question again."})]
