"""Run code-node snippets locally, with the same date helpers the workflow gets."""
from pathlib import Path

from builder.blocks import datelib

DATES_SOURCE = Path(datelib.__file__).read_text(encoding="utf-8")


def with_dates(body):
    return DATES_SOURCE + "\n" + body


def run_snippet(code, vars):
    scope = {"vars": dict(vars)}
    exec(code, scope)
    return scope["vars"]


def run_post_hook(tool, body):
    """Run a tool's post-hook as the platform does after a successful call: `result['data']` is the API's whole
    JSON body. Returns `result`, e.g. to assert the `ok` flag a route reads."""
    scope = {"result": {"data": body}}
    exec(tool["post_process_code"], scope)
    return scope["result"]


def node_code(workflow, name):
    """The code of a code node, to run with run_snippet in a test."""
    return workflow["nodes"][name]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]


def tool_code(workflow, tool_name):
    """The code of a code_exec tool on any node. Run it with run_snippet(code, vars) after setting vars['params']."""
    for node in workflow["nodes"].values():
        for tool in node.get("tools", []):
            if tool["function"]["name"] == tool_name:
                return tool["function"]["parameters"]["properties"]["code"]["default"]
    raise KeyError(tool_name)


def run_tool(code, vars, params):
    """Run a code_exec tool's code locally. The platform gives the model's arguments as the global `params`."""
    scope = {"vars": dict(vars), "params": dict(params)}
    exec(code, scope)
    return scope["vars"]
