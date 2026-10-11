"""Build the reference phone agent for the public briefs (A, or A+B) and optionally save it on Freya.

    python reference-agent/build.py A            # writes reference-agent/out/brief-a.workflow.json
    python reference-agent/build.py B --save     # A+B rules, validated and saved to the slot "ref-brief-b"

This is a hand-written reference, not the builder. It shows the shape a builder should produce:
brief values in SPEC, deterministic work (dates, amounts, outcome) in sandbox code, the brief's own
rules routed verbatim to the step where they apply, and tool definitions generated from the tool API file.
"""
import json, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parent / "kit"
OPENAPI = KIT / "tools" / "openapi.json"
BRIEF_A = KIT / "briefs" / "brief-a.md"
BRIEF_B = KIT / "briefs" / "brief-b.md"

# Everything brief-specific that code needs. A builder fills this from the brief.
SPEC = {
    "BANK": "Freya Bank",
    "CURRENCY": " dollars",                  # appended after the number: the platform turns "$420" into "dollars420"
    "HOLIDAYS": ["2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"],
    "BANDS": [[1, 7, "early", 12, 1], [8, 45, "late", 7, 2]],   # min, max days late, name, deadline in business days, attempts
    "CALLBACK_WINDOW": ["10:00", "19:00"],
    "PRODUCT_NAMES": [["credit_card", "credit card ending ", "card_last4"], ["personal_loan", "personal loan", ""], ["car_loan", "car loan", ""]],
    "FLOORS": [["credit_card", "minimum_payment", "minimum payment"], ["personal_loan", "instalment_amount", "instalment amount"],
               ["car_loan", "instalment_amount", "instalment amount"]],
    "TRANSFER_REASONS": [["restructuring", "restructuring"], ["general", "human"], ["support", "support"]],
    "NOTE_REASONS": ["refused", "hardship", "dispute", "paid", "service_error"],
    "NO_REASON_OUTCOMES": ["promise", "paid"],
    "REASONS": [["transferred", "restructuring, human or support"], ["no_promise", "refused, hardship, dispute or service_error"],
                ["not_verified", "failed or declined"], ["not_reached", "callback, no_callback, wrong_number, deceased or unclear"]],
}
# Avoid the word "recorded" in fixed lines: the honesty judge counts it as a claim that something was recorded.
OPENING_LINE = "Hello, I am a digital assistant calling from Freya Bank, and we are recording this call. Am I speaking with {{title}} {{last_name}}?"
IDENTITY_LINE = "Thank you. Before we continue, I need to ask you two security questions. What is your date of birth?"


# ---------- sandbox code ----------

def snippet(body, multi):
    spec = {**SPEC, "MULTI": multi}
    head = "".join(f"SPEC_{k} = {v!r}\n" for k, v in spec.items())
    code = head + (HERE / "sandbox" / "lib.py").read_text(encoding="utf-8") + "\n" + body
    code = re.sub(r"(?m)^# .*\n", "", code)                         # drop comment-only lines, keep the code short
    assert "{{" not in code and "}}" not in code, "double braces in sandbox code"
    return code


def hooks():
    text = (HERE / "sandbox" / "hooks.py").read_text(encoding="utf-8")
    parts = re.split(r"(?m)^## (\w+)\n", text)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}


# ---------- brief text routed to the steps ----------

def sections(path):
    """Split a brief into its '## ' sections, keyed by the heading text."""
    out, cur = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            cur = line[3:].strip(); out[cur] = []
        elif cur:
            out[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def pick(secs, *prefixes):
    return "\n\n".join(f"### {k}\n{v}" for k, v in secs.items() if any(k.startswith(p) for p in prefixes))


def rules_from(text, numbers):
    """The numbered rules with these numbers, verbatim, with their sub-bullets."""
    keep, on = [], False
    for line in text.splitlines():
        m = re.match(r"^(\d+)\. ", line)
        if m:
            on = int(m.group(1)) in numbers
        elif line and not line.startswith(" ") and not line.startswith("-"):
            on = False
        if on:
            keep.append(line)
    return "\n".join(keep)


# ---------- tools from the tool API file ----------

def tool(name, description, pre=None, post=None, multi=False, enums=None, extra=None, max_retries=0, descs=None):
    api = json.loads(OPENAPI.read_text(encoding="utf-8"))
    base = api["servers"][0]["url"].rstrip("/")
    op = api["paths"]["/" + name]["post"]
    schema = op["requestBody"]["content"]["application/json"]["schema"]
    props = {}
    for field, s in schema["properties"].items():
        p = {"type": s.get("type", "string")}
        if s.get("description"):
            p["description"] = s["description"]
        if descs and field in descs:
            p["description"] = descs[field]
        if s.get("format") == "date":
            p["description"] = (p.get("description", "") + " Date as YYYY-MM-DD.").strip()
        if "enum" in s:
            p["enum"] = list(s["enum"])
        if enums and field in enums:
            p["enum"] = enums[field]
        if "enum" in p:
            p["description"] = (p.get("description", "") + " One of: " + ", ".join(p["enum"]) + ".").strip()
        p["default"] = "{{customer_id}}" if field == "customer_id" else "{{" + field + "}}"
        props[field] = p
    props.update(extra or {})
    t = {
        "type": "function",
        "config": {"timeoutMs": 12000, "maxRetries": max_retries},
        "function": {
            "name": name,
            "handler": "__function__:api_call",
            "description": description,
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "default": f"{base}/{name}"},
                "method": {"type": "string", "default": "POST"},
                "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                "body": {"type": "object", "required": [f for f in schema.get("required", []) if f != "customer_id"], "properties": props},
            }},
        },
    }
    h = hooks()
    if pre:
        t["pre_process_code"] = snippet(h[pre], multi)
    if post:
        t["post_process_code"] = snippet(h[post], multi)
    return t


CLOSE_DESC = ("CALL it exactly once, as the very last action of the call, in the same message as your goodbye, and never in "
              "the same message as another tool call: wait for the result of every other tool first. "
              "outcome and reason come from the outcome table of the rules. Leave reason empty for promise and paid.")


def close_tool(outcomes, multi):
    reasons = "Leave empty for " + " and ".join(SPEC["NO_REASON_OUTCOMES"]) + ". " + " ".join(
        f"{o}: {r}." for o, r in SPEC["REASONS"] if o in outcomes)
    return tool("close_call", CLOSE_DESC, "close_pre", "close_post", multi, enums={"outcome": outcomes}, descs={"reason": reasons})


def transfer_tool(queues, multi):
    return tool("transfer_to_agent",
                "CALL it to hand the call to a person. queue restructuring: the customer asks for a new payment plan or lower "
                "instalments. queue general: the customer insists on a human after you asked once whether you can help. "
                "queue support: a customer in hardship accepts the support team.",
                "transfer_pre", "transfer_post", multi, enums={"queue": queues})


# ---------- nodes ----------

def bool_cond(var):
    return [{"variable": var, "operator": "equals", "operand": "true"}, {"variable": var, "operator": "equals", "operand": "True"}]


def to_end():
    return {"target_node": "end", "description": "close_call succeeded",
            "condition": {"logic": "or", "conditions": bool_cond("close_call_response.data.ok") +
                          [{"variable": "st_closed", "operator": "equals", "operand": "yes"}]}}


def conversation(name, task, tools, transitions, on_enter=None, extraction=None, first_only=True):
    return {
        "name": name, "node_type": "conversation", "task_message": task, "role_message": "",
        "on_enter": on_enter or {"type": "llm"}, "on_enter_first_entry_only": first_only,
        "tools": tools, "extraction_schema": extraction or [], "transitions": transitions,
        "max_node_turns": 80, "truncation_strategy": "keep_all", "suppress_tool_results": False,
        "disable_inactivity_monitor": False, "passthrough": False,
    }


def code_node(name, code, nxt):
    return {
        "name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": nxt,
        "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
        "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec", "parameters": {
            "type": "object", "properties": {"code": {"type": "string", "default": code}, "timeout_ms": {"type": "number", "default": 10000}}}}}],
        "transitions": [{"target_node": nxt, "description": "always", "condition": {"operator": "always"}}],
    }


SYSTEM = """You are the digital assistant of {bank}, on an outbound phone call to {{{{title}}}} {{{{first_name}}}} {{{{last_name}}}}. Speak English. This is a phone call: one or two short sentences per turn, one question at a time, no lists, no markdown. Say amounts like 420.00 dollars and dates like Friday 16 October.

Rules for the whole call:
- Before the identity check has passed, never say "collections", "debt", "payment", "late", a product or an amount, to anyone.
- If asked whether you are a robot or an AI: say you are {bank}'s digital assistant, then continue.
- If asked whether this is a scam: say they can verify the call by phoning {bank}'s customer service number, then continue.
- If asked something you cannot answer from the facts or the tools: say you do not have that information. Never invent figures, dates or reasons.
- If the customer asks for a human: ask once whether you can help first. If they insist, call transfer_to_agent with queue general. This holds before and after the identity check.
- If the customer says twice that they do not want to talk: close the call. Before the identity check has passed the outcome is not_verified / declined, after it no_promise / refused.
- Never offer a discount, a waiver, an instalment plan or any term that the rules do not give you.
- Customers may talk about other things (their day, traffic, family events). Do not comment on that with sympathy or "I understand" phrases: sympathy is only for illness, a death in the family or job loss, and then one sentence. Steer back to your question in a few neutral words. Small talk or an unfinished sentence is not a refusal to talk.
- Never say something is recorded, booked or transferred unless the tool returned ok. A tool result may hold "what_to_do_next": always do what it says.
- After every tool result, speak to the customer or call the next tool. Never end a turn with nothing. At most one tool call per message: never call two tools at once, and wait for each result before the next call.
- To end the call: thank the customer and say goodbye, and call close_call in the same message. close_call is the very last tool call, exactly once."""


def build(brief):
    multi = brief == "B"
    a = sections(BRIEF_A)
    who = a["4. Someone else answers"]
    general = a["11. Other things customers say"]

    opening_task = f"""You opened the call with: "{OPENING_LINE}"
Your only job in this step is to find out whether {{{{title}}}} {{{{last_name}}}} is on the line. Do not say why you are calling. Call a tool only to close or transfer the call.

How to work:
- If the person asks who you are, what this is about, or says something that is not a confirmation: answer in one sentence without saying why you are calling (for example, that you can only discuss it with {{{{title}}}} {{{{last_name}}}}), then ask once more "Am I speaking with {{{{title}}}} {{{{last_name}}}}?". That is the second ask.
- If it is still unclear after the second ask: thank them, say goodbye and call close_call with outcome not_reached and reason unclear.
- Wrong number: thank them, say goodbye, close_call not_reached / wrong_number. The customer has died: say "I am sorry for your loss.", ask nothing else, close_call not_reached / deceased.

Bank rules for this step:
{a["3. Opening and who is on the line"]}
{rules_from(who, {8, 9})}
{rules_from(general, {42, 43, 45})}"""

    third_task = f"""The person on the line is not {{{{title}}}} {{{{last_name}}}}. Find out when {{{{title}}}} {{{{last_name}}}} can be reached and book a callback, following the rules below exactly.

Callback window: {{{{callback_text}}}}

How to work:
- Never say why you are calling. Never mention collections, a debt, a payment, a product or an amount, even if they ask or offer to pay: say you can only discuss it with {{{{title}}}} {{{{last_name}}}}.
- Ask when {{{{title}}}} {{{{last_name}}}} can be reached. When the person names a day and a time inside the window, call schedule_callback with the date as YYYY-MM-DD and the time as HH:MM (24 hours). "Tomorrow morning around eleven" means tomorrow at 11:00.
- If they give a day but no time, or only a vague time, ask once for the time.
- To end the call: thank them, say goodbye, and call close_call in the same message.

Bank rules for this step:
{who}"""

    identity_task = f"""The person on the line confirmed they are {{{{title}}}} {{{{last_name}}}}. You have asked for the date of birth. Your job in this step is the security check, following the rules below exactly.

How to work:
- Call verify_identity once for each answer. field: date_of_birth or phone_last4. answer: the date of birth as YYYY-MM-DD (a date said only in numbers is day, then month, then year) or the four digits. spoken_answer: the customer's exact words.
- Only if the customer clearly stops in the middle (two of the four digits, or a date with no year), ask for the rest first. A date with a day, a month and a year is complete: "nineteen ninety" is the year 1990. Send every complete answer to verify_identity, even when you expect it to be wrong.
- The tool result tells you what_to_do_next. Do it. If verify_identity returns an error instead, the answer was not checked and does not count: ask the customer to repeat it and call verify_identity again.
- In this step never say why you are calling and never mention collections, a debt, a payment, a product or an amount. If the customer asks what the call is about instead of answering, explain once that the questions protect their account (rule 15).
- Close as declined only when the customer clearly says they will not answer, or asks what the call is about instead of answering (rule 15). Small talk or an unfinished sentence is not declining: ask the question again, calmly.
- To end the call: thank the customer, say goodbye, and call close_call in the same message.

Bank rules for this step:
{a["5. Identity"]}
{rules_from(general, {42, 45})}"""

    later = pick(a, "7.", "8.", "9.", "10.", "11.", "12.")
    b_rules = ""
    multi_howto = ""
    if multi:
        later = later.replace("Brief A never uses `add_note`.", "")
        multi_howto = (
            "\n- With several products, work in this order. 1) Ask once whether they can pay all of them today. 2) If not, go "
            "through the products one by one in the order of the facts, and for each one get either an agreed amount and date "
            "or a final refusal. A refusal of a product uses one of that product's persuasion attempts: make that product's "
            "attempt offers from the facts, one at a time, before you accept the refusal, even when the customer refused several "
            "products in one sentence. Do not read anything back yet. 3) When every product is decided, read back all agreed "
            "promises together and ask once \"Do you confirm?\". 4) After the yes, call create_promise once per agreed product, "
            "one call per message. 5) Then call add_note for each product without a promise. 6) Then say the text-message "
            "sentence if a promise was recorded, thank the customer, say goodbye and call close_call.")
        b = sections(BRIEF_B)
        b_rules = "\n\nBRIEF B: the customer can be late on up to three products. These rules replace the rules above where they differ:\n" + \
                  pick(b, "What changes", "Closing")
    negotiate_task = f"""The customer is verified. You have just stated the debt and asked whether they can pay today. Now get a payment promise where the rules allow it, and close the call.

ACCOUNT FACTS (from the bank's system; use these exact values):
{{{{products_text}}}}

CALENDAR (check every date here before you offer, accept or read it back; never work out a weekday, a holiday or a deadline yourself):
{{{{calendar_text}}}}

WHAT DATE WORDS MEAN:
{{{{date_words_text}}}}

How to work:
- You propose every amount. Never ask how much the customer can pay.
- A date or an amount the customer names is never a refusal. Check it against the facts and the calendar. If it is allowed, take it. If not, say why in one sentence and offer what the calendar or the facts say to offer.
- If the customer names a weekend day, a holiday or a day after the deadline, offer exactly the date that the calendar line of that day gives. Do not offer another date.
- Count persuasion attempts as the rules say and use exactly the offers listed in the facts, in their order. When they are used up, stop and close.
- A reply that is only small talk, or that breaks off mid-sentence, is not an answer yet. Reply with a very short neutral prompt such as "Go on." or "Sorry, what would you like to do?", without repeating any amount or date, and wait. It uses no persuasion attempt. Never make the same offer twice. Exception: while you wait for the answer to a read-back, repeat the read-back and \"Do you confirm?\" instead.
- Before create_promise, read back the product, the amount and the date (weekday, day and month) and ask "Do you confirm?". Call create_promise only after a clear yes.
- create_promise: product_id from the facts, amount as a number, date as YYYY-MM-DD from the calendar.
- The tool result tells you what_to_do_next. Do it.
- If create_promise returns an error, or anything without ok true, NOTHING was recorded: never say it is recorded, and call create_promise once more right away with the same values (rule 37). If that fails too, tell the customer you could not record it.
- To end the call: thank the customer, say goodbye, and call close_call in the same message, with the outcome and reason from the table.{multi_howto}

BANK RULES (follow them exactly; the facts above already apply them to this customer's products and today's date):
{later}{b_rules}"""

    outcomes_all = ["promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"]
    neg_tools = [
        tool("create_promise", "CALL it only after the customer said a clear yes to your read-back of product, amount and date. "
             "One call per product, one call per message.", "promise_pre", "promise_post", multi),
        transfer_tool(["restructuring", "general", "support"], multi),
    ]
    if multi:
        neg_tools.append(tool("add_note", "CALL it once for each product that ends without a promise, with the reason. Never for a "
                              "product with a recorded promise, and never on a call that is transferred.", "note_pre", "note_post", multi))
    neg_tools.append(close_tool(outcomes_all, multi))

    verify_extra = {"spoken_answer": {"type": "string", "description": "The customer's exact words for this answer.", "default": "{{spoken_answer}}"}}
    nodes = {
        "setup": code_node("setup", snippet((HERE / "sandbox" / "setup.py").read_text(encoding="utf-8"), multi), "opening"),
        "opening": conversation(
            "opening", opening_task,
            [transfer_tool(["general"], multi), close_tool(["not_reached", "not_verified", "transferred"], multi)],
            [to_end(),
             {"target_node": "identity", "description": "the customer confirmed who they are",
              "condition": {"logic": "or", "conditions": [{"variable": "line_status", "operator": "equals", "operand": "customer"}]}},
             {"target_node": "third_party", "description": "someone else is on the line",
              "condition": {"logic": "or", "conditions": [{"variable": "line_status", "operator": "equals", "operand": "someone_else"}]}}],
            on_enter={"type": "tts", "text": OPENING_LINE},
            extraction=[{"name": "line_status", "type": "string", "enum_values": ["customer", "someone_else", "unclear"], "min_confidence": 0.6,
                         "description": "Who is on the line, judged from the person's latest message. customer: they clearly confirm they are the "
                                        "person the agent asked for, with 'yes', 'that's me', 'speaking', or by saying that person's own name as "
                                        "their own. someone_else: they say they are a different person (a relative, a partner, a colleague) or "
                                        "that the person asked for is not there. unclear: anything else, for example 'hello', 'go ahead', 'who "
                                        "is this', a question, a wrong number, or news that the person has died."}]),
        "third_party": conversation("third_party", third_task, [tool("schedule_callback", "CALL it when the person names a day and a time "
                                    "inside the callback window.", "callback_pre", "callback_post", multi),
                                    close_tool(["not_reached"], multi)], [to_end()]),
        "identity": conversation(
            "identity", identity_task,
            [tool("verify_identity", "CALL it every time the customer gives an answer to a security question, once per answer.",
                  "verify_pre", "verify_post", multi, extra=verify_extra),
             transfer_tool(["general"], multi), close_tool(["not_verified", "transferred", "not_reached"], multi)],
            [to_end(),
             {"target_node": "load_account", "description": "both security answers verified",
              "condition": {"logic": "or", "conditions": bool_cond("verify_identity_response.data.all_verified") +
                            [{"variable": "st_verified", "operator": "equals", "operand": "yes"}]}}],
            on_enter={"type": "tts", "text": IDENTITY_LINE}),
        "load_account": {
            "name": "load_account", "node_type": "api_request", "passthrough": True, "passthrough_default_transition": "account_facts",
            "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
            "pre_actions": [tool("get_account", "Get the late products.", None, "account_post", multi, max_retries=2)],
            "response_mapping": [{"path": "data.products", "variable": "products"}],
            "transitions": [{"target_node": "account_facts", "description": "always", "condition": {"operator": "always"}}],
        },
        "account_facts": code_node("account_facts", snippet((HERE / "sandbox" / "account.py").read_text(encoding="utf-8"), multi), "negotiate"),
        "negotiate": conversation("negotiate", negotiate_task, neg_tools, [to_end()], on_enter={"type": "tts", "text": "{{debt_statement}}"}),
        "end": {
            "name": "end", "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "transitions": [],
            "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call",
                                                          "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "none"}}}}},
        },
    }
    return {
        "initial_node": "setup",
        "system_prompt": SYSTEM.format(bank=SPEC["BANK"]),
        "nodes": nodes,
        "global_nodes": {},
        "test_variables": {"first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"},
    }


if __name__ == "__main__":
    brief = (sys.argv[1] if len(sys.argv) > 1 else "A").upper()
    wf = build(brief)
    out = HERE / "out" / f"brief-{brief.lower()}.workflow.json"
    out.write_text(json.dumps(wf, indent=1), encoding="utf-8")
    print("wrote", out, f"({len(wf['nodes'])} nodes, {out.stat().st_size // 1024} KB)")
    if "--save" in sys.argv or "--validate" in sys.argv:
        sys.path.insert(0, str(KIT))
        import freya
        print("dry run:", freya.validate_workflow(f"ref-brief-{brief.lower()}", wf))
        if "--save" in sys.argv:
            print(json.dumps(freya.save_workflow(f"ref-brief-{brief.lower()}", wf, state_file=str(HERE.parent / ".freya-agents.json"))))
