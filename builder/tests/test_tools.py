import json
from pathlib import Path

import pytest

from builder.blocks.tools import field_values, load_api, make_tool

FIX = str(Path(__file__).parent / "fixtures" / "tool_api.json")
KIT_API = Path(__file__).resolve().parents[2] / "kit" / "tools" / "openapi.json"


def body_of(tool):
    return tool["function"]["parameters"]["properties"]["body"]["properties"]


def test_enum_and_description_on_leaf():
    body = body_of(make_tool(load_api(FIX), "check_member", baked={"member_id": "{{member_id}}"}))
    assert body["member_id"]["default"] == "{{member_id}}"
    assert body["kind"]["enum"] == ["a", "b"] and body["kind"]["default"] == "{{check_member__kind}}"
    assert body["code"]["description"] == "The code the member says."


def test_url_from_servers():
    t = make_tool(load_api(FIX), "log_visit")
    assert t["function"]["parameters"]["properties"]["url"]["default"] == "https://api.example.test/v9/log_visit"


def test_object_field_is_kept():
    assert body_of(make_tool(load_api(FIX), "log_visit"))["meta"]["type"] == "object"


def test_missing_servers_is_a_clear_error(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"paths": {}}))
    with pytest.raises(ValueError, match="servers"):
        load_api(str(p))


def test_unknown_tool_is_a_key_error():
    with pytest.raises(KeyError):
        make_tool(load_api(FIX), "nope")


def test_post_hook_is_guarded():
    code = make_tool(load_api(FIX), "check_member", post_code="d['what_to_do_next'] = 'Ask again.'")["post_process_code"]
    assert "try:" in code and "result.pop('header', None)" in code


def test_post_hook_adds_line_to_data():
    code = make_tool(load_api(FIX), "check_member", post_code="d['what_to_do_next'] = 'Ask again.'")["post_process_code"]
    result = {"status": "success", "data": {"ok": True}, "header": {"x": "y"}}
    exec(code, {"result": result})
    assert result == {"status": "success", "data": {"ok": True, "what_to_do_next": "Ask again."}}


def test_writes_are_not_retried():
    assert make_tool(load_api(FIX), "log_visit")["config"]["maxRetries"] == 0


def test_field_values():
    api = load_api(FIX)
    assert field_values(api, "check_member", "kind") == ["a", "b"] and field_values(api, "check_member", "code") == []


def test_kit_api_builds_all_tools():
    api = load_api(str(KIT_API))
    assert len(api) == 7
    for name in api:
        assert make_tool(api, name, baked={"customer_id": "{{customer_id}}"})["function"]["name"] == name
