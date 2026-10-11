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


def test_an_object_with_properties_is_opened_and_rebuilt():
    api = load_api(FIX)
    assert sorted(api["log_visit"]["fields"]) == ["member_id", "room"]
    meta = body_of(make_tool(api, "log_visit"))["meta"]
    assert meta["type"] == "object" and meta["properties"]["room"]["default"] == "{{log_visit__room}}"


ENVELOPE = {"servers": [{"url": "https://shop.test"}], "paths": {"/shop/v2/orders.find": {"post": {"requestBody": {"content": {
    "application/json": {"schema": {"type": "object", "required": ["payload"], "properties": {
        "payload": {"type": "object", "required": ["orderNo"], "properties": {
            "orderNo": {"type": "string"}, "source": {"type": "string", "enum": ["Web"]}}},
        "meta": {"type": "object", "properties": {"lang": {"type": "string"}}}}}}}}}}}}


def envelope_api(tmp_path, spec=ENVELOPE):
    p = tmp_path / "x.json"
    p.write_text(json.dumps(spec))
    return load_api(str(p))


def test_an_envelope_body_gives_flat_fields_and_a_safe_tool_name(tmp_path):
    # a tool API can wrap every request in an envelope object, and its route names can hold dots
    op = envelope_api(tmp_path)["shop_v2_orders_find"]
    assert sorted(op["fields"]) == ["lang", "orderNo", "source"]
    assert op["required"] == ["orderNo"]  # lang sits in the optional `meta`


def test_make_tool_sends_the_envelope(tmp_path):
    tool = make_tool(envelope_api(tmp_path), "shop_v2_orders_find", baked={"orderNo": "{{shopperId}}"})
    body = tool["function"]["parameters"]["properties"]["body"]
    assert body["required"] == ["payload"]
    payload = body["properties"]["payload"]
    assert payload["properties"]["orderNo"]["default"] == "{{shopperId}}"
    assert payload["properties"]["source"]["default"] == "{{shop_v2_orders_find__source}}"
    assert payload["required"] == []
    assert body["properties"]["meta"]["properties"]["lang"]["default"] == "{{shop_v2_orders_find__lang}}"


def test_the_same_field_name_twice_is_a_clear_error(tmp_path):
    spec = json.loads(json.dumps(ENVELOPE))
    spec["paths"]["/shop/v2/orders.find"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]["meta"]["properties"]["orderNo"] = {"type": "string"}
    with pytest.raises(ValueError, match="orderNo"):
        envelope_api(tmp_path, spec)


def test_a_slow_answer_does_not_time_out():
    # a bank answer can take more than ten seconds and still succeed
    assert make_tool(load_api(FIX), "log_visit")["config"]["timeoutMs"] == 30000


def test_missing_servers_is_a_clear_error(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"paths": {}}))
    with pytest.raises(ValueError, match="servers"):
        load_api(str(p))


def test_unknown_tool_is_a_key_error():
    with pytest.raises(KeyError):
        make_tool(load_api(FIX), "nope")


def test_baked_field_not_in_the_api_is_a_clear_error():
    # A hidden tool API can rename a field; a baked value for the old name must not vanish from the request.
    with pytest.raises(ValueError, match="member_ref.*member_id"):
        make_tool(load_api(FIX), "check_member", baked={"member_ref": "{{member_id}}"})


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


def test_swagger_2_host_and_base_path_give_the_url(tmp_path):
    # review: a Swagger 2 tool API (host + basePath, no servers) failed every gate
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"swagger": "2.0", "host": "api.example.test", "basePath": "/v2", "schemes": ["https"],
                             "paths": {"/pay": {"post": {"parameters": [{"in": "body", "name": "body", "schema": {
                                 "type": "object", "properties": {"amount": {"type": "number"}}, "required": ["amount"]}}]}}}}))
    api = load_api(str(p))
    assert api["pay"]["url"] == "https://api.example.test/v2/pay" and api["pay"]["required"] == ["amount"]


def test_a_route_with_a_slash_gives_a_tool_name_without_one(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"servers": [{"url": "https://a.test"}], "paths": {"/v1/promises/create": {"post": {}}}}))
    assert list(load_api(str(p))) == ["v1_promises_create"]
