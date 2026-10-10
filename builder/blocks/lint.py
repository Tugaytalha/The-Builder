"""Static checks on a workflow dict. `lint` returns one problem string per finding.

`api` is the output of `tools.load_api`. `rules` is `spec.json["lint"]`.
"""
import json
import re


def _all_nodes(workflow):
    return list(workflow.get("nodes", {}).values()), list(workflow.get("global_nodes", {}).values())


def _targets(node):
    out = [t.get("target_node") for t in node.get("transitions", [])]
    out += [node[k] for k in ("passthrough_default_transition", "max_turn_transition") if node.get(k)]
    return [t for t in out if t]


def _functions(node):
    """Every tool-shaped dict on a node: tools, pre_actions and the terminal."""
    return list(node.get("tools", [])) + list(node.get("pre_actions", []))


def _find_none(value, path, out):
    if value is None:
        out.append(path)
    elif isinstance(value, dict):
        for k, v in value.items():
            _find_none(v, path + "." + str(k), out)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _find_none(v, path + "[" + str(i) + "]", out)


def _codes(tool):
    fn = tool.get("function", {})
    out = []
    if fn.get("handler") == "__function__:code_exec":
        code = fn.get("parameters", {}).get("properties", {}).get("code", {}).get("default")
        if isinstance(code, str):
            out.append(code)
    out += [tool[k] for k in ("pre_process_code", "post_process_code") if isinstance(tool.get(k), str)]
    return out


def _op_for(tool, api):
    url = tool.get("function", {}).get("parameters", {}).get("properties", {}).get("url", {}).get("default")
    for name, op in api.items():
        if op["url"] == url:
            return name, op
    return None, None


def _check_tool(where, tool, api, problems):
    fn = tool.get("function", {})
    if fn.get("handler") != "__function__:api_call":
        return
    name, op = _op_for(tool, api)
    if op is None:
        problems.append(f"{where}: tool {fn.get('name')} calls a URL that is not in the tool API")
        return
    body = fn.get("parameters", {}).get("properties", {}).get("body", {}).get("properties", {})
    for field, leaf in body.items():
        if field not in op["fields"]:
            problems.append(f"{where}: tool {fn.get('name')} sends field {field}, which {name} does not define")
            continue
        enum = op["fields"][field].get("enum")
        default = leaf.get("default")
        if enum and isinstance(default, str) and "{{" not in default and default not in enum:
            problems.append(f"{where}: tool {fn.get('name')} field {field} has value {default!r}, not in {enum}")
    for m in tool.get("response_mapping", []):
        if not str(m.get("path", "")).startswith("data."):
            problems.append(f"{where}: tool {fn.get('name')} maps path {m.get('path')!r}, which does not start with data.")


def lint(workflow, api, rules):
    problems = []
    nodes, globals_ = _all_nodes(workflow)
    by_name = {n.get("name"): n for n in nodes + globals_}

    # 2. None anywhere
    nones = []
    _find_none(workflow, "workflow", nones)
    for path in nones:
        problems.append(f"null value at {path}")

    for n in nodes + globals_:
        name = n.get("name")
        kind = n.get("node_type")
        # 1. passthrough must end with always
        if n.get("passthrough"):
            last = (n.get("transitions") or [{}])[-1]
            if (last.get("condition") or {}).get("operator") != "always":
                problems.append(f"{name}: passthrough node whose last transition is not always")
        # 6. tools / pre_actions placement
        if n.get("tools") and kind != "conversation":
            problems.append(f"{name}: tools on a {kind} node are dropped by the platform")
        if n.get("pre_actions") and kind == "conversation":
            problems.append(f"{name}: pre_actions on a conversation node are dropped by the platform")
        # 3. template braces in code
        for tool in _functions(n):
            for code in _codes(tool):
                if "{{" in code or "}}" in code:
                    problems.append(f"{name}: code contains '{{{{' or '}}}}'")
            _check_tool(name, tool, api, problems)  # 8. fields and enums
        # 7. node-level mapping paths
        for m in n.get("response_mapping", []):
            if not str(m.get("path", "")).startswith("data."):
                problems.append(f"{name}: maps path {m.get('path')!r}, which does not start with data.")
        # 11. cap without target
        if "max_node_turns" in n and not n.get("max_turn_transition"):
            problems.append(f"{name}: max_node_turns without max_turn_transition")
    for tool in workflow.get("tools", []):
        for code in _codes(tool):
            if "{{" in code or "}}" in code:
                problems.append("workflow tools: code contains '{{' or '}}'")
        _check_tool("workflow tools", tool, api, problems)

    # 4. reachability from the initial node (global nodes count as reachable)
    reach, todo = set(), [workflow.get("initial_node")] + [g.get("name") for g in globals_]
    while todo:
        cur = todo.pop()
        if cur in reach or cur not in by_name:
            continue
        reach.add(cur)
        todo += _targets(by_name[cur])
    for n in nodes:
        if n.get("name") not in reach:
            problems.append(f"{n.get('name')}: no path from the initial node reaches it")

    # 5. every node can reach an end_call node
    ends = {n.get("name") for n in nodes + globals_ if n.get("node_type") == "end_call"}
    can_end = set(ends)
    changed = True
    while changed:
        changed = False
        for n in nodes + globals_:
            if n.get("name") in can_end:
                continue
            ts = _targets(n)
            if any(t in can_end or t == "__previous__" for t in ts):
                can_end.add(n.get("name"))
                changed = True
    for n in nodes:
        if n.get("name") not in can_end:
            problems.append(f"{n.get('name')}: no end_call node is reachable from it")

    # 9. outcome and reason strings
    text = json.dumps(workflow)
    for pair in rules.get("outcomes", []):
        for value in pair:
            if value and not re.search(r"(?<![A-Za-z0-9_])" + re.escape(value) + r"(?![A-Za-z0-9_])", text):
                problems.append(f"outcome or reason {value!r} appears nowhere in the workflow")

    # 10. forbidden words before identity
    words = [w for w in rules.get("forbidden_before_identity", []) if w]
    if words:
        pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.IGNORECASE)
        spots = [("system_prompt", workflow.get("system_prompt", ""))]
        for name in rules.get("pre_identity_nodes", []):
            n = by_name.get(name, {})
            spots += [(name, (n.get("on_enter") or {}).get("text", "")), (name, n.get("task_message", "")),
                      (name, n.get("loop_prompt", ""))]
        for where, s in spots:
            for m in sorted(set(x.lower() for x in pattern.findall(s or ""))):
                problems.append(f"{where}: forbidden word {m!r} before identity")
    return problems
