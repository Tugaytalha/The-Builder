"""Freya api_call tools made from any OpenAPI tool file.

The tool names, fields, enums and the server URL all come from the file. Nothing here knows a brief.
"""
import json
import re


def _resolve(spec, node):
    """Follow local `$ref` pointers such as `#/components/schemas/X`."""
    while isinstance(node, dict) and "$ref" in node:
        ref = node["$ref"]
        if not ref.startswith("#/"):
            raise ValueError(f"tool API: only local $ref is supported, got {ref}")
        target = spec
        for part in ref[2:].split("/"):
            target = target[part]
        node = target
    return node


def _json_schema(spec, holder):
    holder = _resolve(spec, holder) or {}
    if "schema" in holder:                  # Swagger 2: the schema sits on the response or the body parameter
        return _resolve(spec, holder["schema"])
    content = holder.get("content") or {}
    media = content.get("application/json") or next(iter(content.values()), {})
    return _resolve(spec, media.get("schema") or {})


def _base_url(spec):
    """OpenAPI 3 `servers`, or Swagger 2 `schemes` + `host` + `basePath`."""
    servers = spec.get("servers") or []
    if servers and servers[0].get("url"):
        return servers[0]["url"].rstrip("/")
    if spec.get("host"):
        scheme = (spec.get("schemes") or ["https"])[0]
        return f"{scheme}://{spec['host']}{spec.get('basePath', '')}".rstrip("/")
    raise ValueError("tool API has no servers entry (and no Swagger 2 host)")


def _request_body(spec, op):
    body_params = [p for p in op.get("parameters") or [] if _resolve(spec, p).get("in") == "body"]
    return _json_schema(spec, op.get("requestBody") or (_resolve(spec, body_params[0]) if body_params else {}))


def _flatten(spec, schema, parents, required, out):
    """Collect the leaf fields of a request body. An object field with `properties` (an envelope such as
    {"data": {...}}) is opened: its leaves are fields too, and `out[leaf]` keeps the path of objects above it."""
    for name, sub in (schema.get("properties") or {}).items():
        sub = _resolve(spec, sub)
        is_required = required and name in (schema.get("required") or [])
        if sub.get("type", "object") == "object" and sub.get("properties"):
            _flatten(spec, sub, parents + (name,), is_required, out)
            continue
        if name in out:
            raise ValueError(f"tool API: field {name} appears twice in one request body")
        out[name] = (sub, parents, is_required)


def load_api(path):
    """Operation name -> {"url", "method", "fields", "parents", "required", "response"}. Every character of a route
    that cannot be in a tool name ("/", ".") becomes "_". Fields are the body's leaves; `parents` keeps the nesting."""
    spec = json.load(open(path, encoding="utf-8"))
    base = _base_url(spec)
    api = {}
    for route, methods in (spec.get("paths") or {}).items():
        for method, op in methods.items():
            if method.lower() not in ("post", "get", "put", "patch", "delete"):
                continue
            leaves = {}
            _flatten(spec, _request_body(spec, op), (), True, leaves)
            ok = (op.get("responses") or {}).get("200") or {}
            api[re.sub(r"[^A-Za-z0-9_]", "_", route.strip("/"))] = {
                "url": base + "/" + route.lstrip("/"), "method": method.upper(),
                "fields": {k: v[0] for k, v in leaves.items()},
                "parents": {k: v[1] for k, v in leaves.items()},
                "required": [k for k, v in leaves.items() if v[2]],
                "response": _json_schema(spec, ok)}
    return api


def _leaf(schema, default):
    leaf = {"type": schema.get("type") or "string", "default": default}
    description = schema.get("description") or ""
    if schema.get("format"):
        description = (description + " Format: " + schema["format"] + ".").strip()
    if description:
        leaf["description"] = description
    if schema.get("enum"):
        leaf["enum"] = list(schema["enum"])
        leaf["description"] = (description + " One of: " + ", ".join(map(str, schema["enum"])) + ".").strip()
    if schema.get("items"):
        leaf["items"] = schema["items"]
    return leaf


def _post_hook(post_code):
    lines = ["try:", "    if isinstance(result, dict):", "        result.pop('header', None)",
             "        d = result.get('data')", "        if not isinstance(d, dict):", "            d = dict()",
             "            result['data'] = d"]
    lines += ["        " + line for line in post_code.splitlines()]
    lines += ["except Exception:", "    pass"]
    return "\n".join(lines) + "\n"


def make_tool(api, name, *, baked=None, post_code="", description=""):
    op = api[name]
    baked = baked or {}
    unknown = sorted(set(baked) - set(op["fields"]))
    if unknown:
        raise ValueError(f"{name}: baked field(s) {unknown} not in the tool API; its fields are {sorted(op['fields'])}")
    body = {"type": "object", "properties": {}, "required": []}
    for f, s in op["fields"].items():
        holder = body
        for parent in op["parents"][f]:
            # an envelope object is required when a required field sits in it, also when that field is baked
            if parent not in holder["properties"]:
                holder["properties"][parent] = {"type": "object", "properties": {}, "required": []}
            if f in op["required"] and parent not in holder["required"]:
                holder["required"].append(parent)
            holder = holder["properties"][parent]
        holder["properties"][f] = _leaf(s, baked.get(f, "{{" + name + "__" + f + "}}"))
        if f in op["required"] and f not in baked:
            holder["required"].append(f)
    return {
        "type": "function", "config": {"timeoutMs": 30000, "maxRetries": 0},
        "function": {
            "name": name, "handler": "__function__:api_call", "description": description,
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "default": op["url"]},
                "method": {"type": "string", "default": op["method"]},
                "headers": {"type": "object", "properties": {
                    "Content-Type": {"type": "string", "default": "application/json"}}},
                "body": body}}},
        "post_process_code": _post_hook(post_code)}


def body_leaves(properties):
    """The leaf fields of a built tool's body (name -> leaf), also inside envelope objects."""
    out = {}
    for name, leaf in properties.items():
        if leaf.get("type") == "object" and "properties" in leaf and "default" not in leaf:
            out.update(body_leaves(leaf["properties"]))
        else:
            out[name] = leaf
    return out


def field_values(api, name, field):
    return list(api[name]["fields"].get(field, {}).get("enum") or [])
