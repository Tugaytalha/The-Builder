"""Factories for Freya workflow nodes, transitions and conditions.

Each factory returns plain dicts that follow kit/docs/workflow-format.md: no None values, every
passthrough ends with an `always` transition, variable checks sit inside an OR group, and code
holds no template braces.
"""


def _clean(d):
    return {k: v for k, v in d.items() if v is not None}


# ------------------------------------------------------------------ conditions and transitions

def cond(var, op, operand=None):
    return _clean({"variable": var, "operator": op, "operand": operand})


def any_of(*conds):
    return {"logic": "or", "conditions": list(conds)}


def all_of(*conds):
    return any_of({"logic": "and", "conditions": list(conds)})


def is_true(var):
    return any_of(cond(var, "equals", "true"), cond(var, "equals", "True"))


def go(target, condition, description):
    return {"target_node": target, "description": description, "condition": condition}


def always(target):
    return {"target_node": target, "description": "always", "condition": {"operator": "always"}}


def intent(target, description):
    return go(target, {"operator": "matches_intent", "description": description}, description)


# ------------------------------------------------------------------ node parts

def field(name, type, description, enum=None, min_confidence=0.6):
    return _clean({"name": name, "type": type, "description": description, "enum_values": enum,
                   "min_confidence": min_confidence})


def tts(text):
    return {"type": "tts", "text": text}


def _leaf(type, default):
    return {"type": type, "default": default}


# ------------------------------------------------------------------ nodes

def conversation(name, task, *, tools=(), extract=(), transitions=(), on_enter=None, first_entry_only=False,
                 max_turns=None, max_turn_target=None):
    if max_turns is not None and not max_turn_target:
        raise ValueError(f"node {name}: max_turns needs max_turn_target")
    return _clean({
        "name": name, "node_type": "conversation", "task_message": task,
        "tools": list(tools) or None, "extraction_schema": list(extract) or None,
        "on_enter": on_enter, "on_enter_first_entry_only": True if first_entry_only else None,
        "max_node_turns": max_turns, "max_turn_transition": max_turn_target,
        "transitions": list(transitions)})


def _wrap(name, body, fallbacks):
    lines = ["try:"] + ["    " + line for line in body.splitlines()] + ["    pass", "except Exception as exc:"]
    lines += ["    vars[%r] = %r" % (k, v) for k, v in (fallbacks or {}).items()]
    lines += ["    vars[%r] = repr(exc)[:300]" % (name + "_code_error")]
    return "\n".join(lines) + "\n"


def code_node(name, body, next_node, transitions=(), fallbacks=None):
    """A silent passthrough code node. On an exception it writes each fallback and `<name>_code_error`."""
    code = _wrap(name, body, fallbacks)
    if "{{" in code or "}}" in code:
        raise ValueError(f"code node {name}: code must not contain '{{{{' or '}}}}'")
    return {
        "name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": next_node,
        "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
        "pre_actions": [{"type": "function", "function": {
            "name": "code_exec", "handler": "__function__:code_exec",
            "parameters": {"type": "object", "properties": {
                "code": _leaf("string", code), "timeout_ms": _leaf("number", 10000)}}}}],
        "transitions": list(transitions) + [always(next_node)]}


def api_node(name, tool, next_node, mapping=(), transitions=()):
    """A passthrough api_request node. `mapping` is a list of (path, variable) pairs."""
    return {
        "name": name, "node_type": "api_request", "passthrough": True, "passthrough_default_transition": next_node,
        "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "pre_actions": [tool],
        "response_mapping": [{"path": p, "variable": v} for p, v in mapping],
        "transitions": list(transitions) + [always(next_node)]}


def end_node(name, reason_name, spoken=""):
    props = {"message_mode": _leaf("string", "custom" if spoken else "none")}
    if spoken:
        props["spoken_message"] = _leaf("string", spoken)
    return {
        "name": name, "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
        "transitions": [],
        "terminal": {"type": "function", "function": {
            "name": reason_name, "handler": "__function__:end_call",
            "parameters": {"type": "object", "properties": props}}}}


# ------------------------------------------------------------------ workflow

def _targets(node):
    out = [t["target_node"] for t in node.get("transitions", [])]
    for key in ("passthrough_default_transition", "max_turn_transition"):
        if node.get(key):
            out.append(node[key])
    return out


def workflow(initial, system_prompt, nodes, global_nodes=(), test_variables=None, tools=()):
    by_name, globals_by_name = {}, {}
    for table, items in ((by_name, nodes), (globals_by_name, global_nodes)):
        for n in items:
            if n["name"] in by_name or n["name"] in globals_by_name:
                raise ValueError(f"duplicate node name {n['name']}")
            table[n["name"]] = n
    if initial not in by_name:
        raise ValueError(f"initial node {initial} is not a node")
    known = set(by_name) | set(globals_by_name)
    for n in list(nodes) + list(global_nodes):
        for t in _targets(n):
            if t not in known and t != "__previous__":
                raise ValueError(f"node {n['name']}: transition to unknown node {t}")
    return _clean({"initial_node": initial, "system_prompt": system_prompt, "nodes": by_name,
                   "global_nodes": globals_by_name, "tools": list(tools) or None,
                   "test_variables": test_variables})
