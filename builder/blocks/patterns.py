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
