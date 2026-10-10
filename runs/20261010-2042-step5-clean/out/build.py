"""Build the Brief A and Brief B workflows.

    python3 out/build.py        writes out/brief-a.workflow.json and out/brief-b.workflow.json

Brief B is Brief A with up to three products, so both come from one generator.
Rules that code can enforce (dates, deadlines, outcomes) live in code nodes and routes, not in prompts.
"""
import json, pathlib

BANK = "https://freya-bank-mock.freyavoice.workers.dev/v1"
OUT = pathlib.Path(__file__).resolve().parent

# ---------------------------------------------------------------- code snippets (no double braces allowed)

SETUP_CODE = r'''
import datetime, re
WD = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MON = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
HOL = ['2026-10-26', '2026-11-11', '2026-11-26', '2026-12-25', '2027-01-01']
def is_bd(d):
    return d.weekday() < 5 and d.isoformat() not in HOL
def say(d):
    return WD[d.weekday()] + ' ' + str(d.day) + ' ' + MON[d.month - 1] + ' ' + str(d.year)
def nth_bd_after(d, n):
    k = 0
    while n > 0:
        k += 1
        if is_bd(d + datetime.timedelta(days=k)):
            n -= 1
    return d + datetime.timedelta(days=k)
def last_bd_of_week(d):
    monday = d - datetime.timedelta(days=d.weekday())
    best = None
    for i in range(5):
        x = monday + datetime.timedelta(days=i)
        if is_bd(x):
            best = x
    return best
try:
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?', str(vars.get('now') or ''))
    today = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    hhmm = (m.group(4) or '00') + ':' + (m.group(5) or '00')
    early = nth_bd_after(today, 12)
    late = nth_bd_after(today, 7)
    a1 = last_bd_of_week(today)
    if a1 is None or a1 <= today:
        a1 = last_bd_of_week(today + datetime.timedelta(days=7))
    nbd = nth_bd_after(today, 1)
    vars['today_iso'] = today.isoformat()
    vars['early_deadline_iso'] = early.isoformat()
    vars['early_deadline_say'] = say(early)
    vars['late_deadline_iso'] = late.isoformat()
    vars['late_deadline_say'] = say(late)
    vars['attempt1_iso'] = a1.isoformat()
    vars['attempt1_say'] = say(a1)
    lines = ['Today is ' + say(today) + ' (' + today.isoformat() + '), time ' + hhmm + '.',
             'Business days are Monday to Friday, except Freya Bank holidays: ' + ', '.join(HOL) + '.',
             'Calendar from today:']
    for i in range(0, 36):
        d = today + datetime.timedelta(days=i)
        tag = 'business day' if is_bd(d) else ('HOLIDAY, not a business day' if d.isoformat() in HOL else 'weekend, not a business day')
        lines.append('- ' + d.isoformat() + ' ' + WD[d.weekday()] + (' (today)' if i == 0 else '') + ': ' + tag)
    lines.append('Weekday words ("this X" is in the current calendar week, Monday to Sunday; "next X" is in the following calendar week):')
    monday = today - datetime.timedelta(days=today.weekday())
    for i in range(7):
        t = monday + datetime.timedelta(days=i)
        n = t + datetime.timedelta(days=7)
        lines.append('- this ' + WD[i] + ' = ' + t.isoformat() + ', next ' + WD[i] + ' = ' + n.isoformat())
    lines.append('"tomorrow" = ' + (today + datetime.timedelta(days=1)).isoformat() + '.')
    vars['date_facts'] = '\n'.join(lines)
    if hhmm < '19:00':
        today_cb = 'today ' + today.isoformat() + ' at a time later than ' + hhmm + ' and not later than 19:00'
    else:
        today_cb = 'not today (it is after 19:00)'
    vars['callback_facts'] = ('A callback is allowed only on: ' + today_cb + '; or on ' + say(nbd) + ' (' + nbd.isoformat()
                              + ') from 10:00 to 19:00, both included. Every other day or time is outside the window. '
                              + '"Tomorrow" means ' + (today + datetime.timedelta(days=1)).isoformat() + '.')
except Exception:
    vars['date_facts'] = 'Date facts are not available.'
    vars['callback_facts'] = 'Callback facts are not available.'
'''

ACCOUNT_CODE = r'''
import json, re
def load_products():
    for key in ('products', 'fetch_account_response.data.products'):
        v = vars.get(key)
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except Exception:
                try:
                    import ast
                    v = ast.literal_eval(v)
                except Exception:
                    v = None
        if isinstance(v, list) and v:
            return v
    items = dict()
    for k in list(vars.keys()):
        mm = re.search(r'products\.(\d+)\.(\w+)$', str(k))
        if mm:
            items.setdefault(int(mm.group(1)), dict())[mm.group(2)] = vars.get(k)
    return [items[i] for i in sorted(items)]
def money(x):
    return '%.2f' % float(x)
try:
    ps = [p for p in load_products() if isinstance(p, dict)]
    facts, sayings = [], []
    for p in ps:
        t = str(p.get('type'))
        if t == 'credit_card':
            name = 'credit card ending ' + str(p.get('card_last4'))
            floor, floor_name = p.get('minimum_payment'), 'minimum payment'
        else:
            name = 'personal loan' if t == 'personal_loan' else 'car loan'
            floor, floor_name = p.get('instalment_amount'), 'instalment amount'
        days = int(float(p.get('days_late')))
        early = days <= 7
        dl_iso = vars.get('early_deadline_iso') if early else vars.get('late_deadline_iso')
        dl_say = vars.get('early_deadline_say') if early else vars.get('late_deadline_say')
        f = ['Product ' + str(p.get('product_id')) + ': ' + name + '.',
             '  Full past-due amount: ' + money(p.get('past_due')) + '. Days late: ' + str(days) + '.',
             '  Band: ' + ('early' if early else 'late') + '. Persuasion attempts allowed: ' + ('1' if early else '2') + '.',
             '  Deadline (the latest date you may record): ' + str(dl_say) + ' (' + str(dl_iso) + ').',
             '  Floor (' + floor_name + '): ' + money(floor) + '. Never record less than this.',
             '  Attempt 1 date: ' + str(vars.get('attempt1_say')) + ' (' + str(vars.get('attempt1_iso')) + ').']
        if not early:
            f.append('  Attempt 2: the floor ' + money(floor) + ' on the deadline ' + str(dl_say) + ' (' + str(dl_iso) + ').')
        facts.append('\n'.join(f))
        sayings.append((name, money(p.get('past_due')), days))
    vars['product_count'] = str(len(ps))
    vars['account_facts'] = '\n'.join(facts) if facts else 'No account data is available.'
    if len(ps) == 1:
        vars['product_id'] = str(ps[0].get('product_id'))
        n, a, d = sayings[0]
        vars['debt_statement'] = ('Thank you, your identity is verified. I am calling from the collections team about a late payment on your '
                                  + n + '. The past-due amount is ' + a + ', and the payment is ' + str(d) + ' days late. Can you make this payment today?')
    elif ps:
        parts = ['Your ' + n + ' has a past-due amount of ' + a + ' and is ' + str(d) + ' days late.' for n, a, d in sayings]
        vars['debt_statement'] = ('Thank you, your identity is verified. I am calling from the collections team about late payments on '
                                  + str(len(ps)) + ' products. ' + ' '.join(parts) + ' Can you pay all of them today?')
    else:
        vars['debt_statement'] = 'Thank you, your identity is verified.'
except Exception:
    vars['product_count'] = '0'
    vars['account_facts'] = 'No account data is available.'
    vars['debt_statement'] = 'Thank you, your identity is verified.'
'''

# ---------------------------------------------------------------- post-hooks: tell the model what a result means

def hook(body):
    return "try:\n    if isinstance(result, dict):\n        result.pop('header', None)\n        d = result.get('data')\n        if not isinstance(d, dict):\n            d = dict()\n            result['data'] = d\n        ok = str(d.get('ok')).lower() == 'true'\n" + body + "except Exception:\n    pass\n"

VERIFY_HOOK = hook(
    "        if d.get('hint') == 'day_month_swapped':\n"
    "            d['what_to_do_next'] = 'Day and month seem swapped. Ask the customer to say the month of birth as a word. This is not a wrong answer.'\n"
    "        elif not ok:\n"
    "            d['what_to_do_next'] = 'The service could not read that answer. Ask the customer to say it again. It is not a wrong answer.'\n"
    "        elif str(d.get('all_verified')).lower() == 'true':\n"
    "            d['what_to_do_next'] = 'Both answers are correct.'\n"
    "        elif str(d.get('verified')).lower() == 'true':\n"
    "            d['what_to_do_next'] = 'Correct. Now ask for the last four digits of the phone number on file.'\n"
    "        elif str(d.get('wrong_answers_left')) == '0':\n"
    "            d['what_to_do_next'] = 'The check has failed. Say nothing about the account.'\n"
    "        else:\n"
    "            d['what_to_do_next'] = 'Wrong answer. Ask the SAME question again. Do not say what the right answer is.'\n")

PROMISE_HOOK = hook(
    "        if ok:\n"
    "            d['what_to_do_next'] = 'The promise is recorded.'\n"
    "        else:\n"
    "            d['what_to_do_next'] = 'The promise is NOT recorded. Never say it is recorded. If this is the first failure for this product, call create_promise again now with the same values. If it already failed once before for this product, tell the customer you could not record it.'\n")

CALLBACK_HOOK = hook(
    "        d['what_to_do_next'] = 'The callback is booked.' if ok else 'The callback is NOT booked. Call schedule_callback once more with the same values.'\n")

PLAIN_HOOK = hook("        d['what_to_do_next'] = 'Done.' if ok else 'The call to the bank system failed.'\n")

CLOSE_PRE = ("try:\n    b = config.get('body')\n    if isinstance(b, dict):\n        r = str(b.get('reason') or '')\n"
             "        if b.get('outcome') in ('promise', 'paid') or r in ('', 'none') or '{' in r:\n            b.pop('reason', None)\nexcept Exception:\n    pass\n")

# ---------------------------------------------------------------- builders

def leaf(typ, default, description=None, enum=None):
    x = {"type": typ, "default": default}
    if description: x["description"] = description
    if enum: x["enum"] = enum
    return x

def api_tool(name, path, body, description="", post=None, retries=0, required=None):
    t = {"type": "function", "config": {"timeoutMs": 12000, "maxRetries": retries},
         "function": {"name": name, "handler": "__function__:api_call", "description": description,
                      "parameters": {"type": "object", "properties": {
                          "url": leaf("string", BANK + path), "method": leaf("string", "POST"),
                          "headers": {"type": "object", "properties": {"Content-Type": leaf("string", "application/json")}},
                          "body": {"type": "object", "properties": {"customer_id": leaf("string", "{{customer_id}}"), **body},
                                   "required": required or []}}}}}
    if post: t["post_process_code"] = post
    return t

def var_is(variable, *values):
    return {"logic": "or", "conditions": [{"variable": variable, "operator": "equals", "operand": v} for v in values]}

def is_true(variable):
    return var_is(variable, "true", "True")

def go(target, description, condition):
    return {"target_node": target, "description": description, "condition": condition}

def tool_go(target, description):
    return {"target_node": target, "description": description, "is_tool_call": True,
            "condition": {"operator": "matches_intent", "description": description}}

def succeeded(tool):
    return {"logic": "or", "conditions": [{"variable": tool + "_success_count", "operator": "greater_than", "operand": 0}]}

def conversation(name, task, tools=(), transitions=(), on_enter=None, extraction=None, max_turns=30, cap_target=None):
    n = {"name": name, "node_type": "conversation", "task_message": task, "tools": list(tools),
         "transitions": list(transitions), "on_enter": on_enter or {"type": "llm"}, "on_enter_first_entry_only": True,
         "max_node_turns": max_turns}
    if cap_target: n["max_turn_transition"] = cap_target
    if extraction: n["extraction_schema"] = extraction
    return n

def code_node(name, code, nxt, extra_transitions=()):
    return {"name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": nxt,
            "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
            "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
                             "parameters": {"type": "object", "properties": {"code": leaf("string", code), "timeout_ms": leaf("number", 10000)}}}}],
            "transitions": list(extra_transitions) + [go(nxt, "always", {"operator": "always"})]}

THANKS = "Thank you for your time, CUSTOMER_NAME. Goodbye."

# end node key -> (outcome, reason, farewell)
ENDS = {
    "end_promise": ("promise", "none", None),  # farewell set per brief below
    "end_paid": ("paid", "none", "Payments can take one business day to appear, so there is nothing more to do today. " + THANKS),
    "end_restructuring": ("transferred", "restructuring", "A colleague will continue this call now. Thank you, goodbye."),
    "end_human": ("transferred", "human", "A colleague will continue this call now. Thank you, goodbye."),
    "end_support": ("transferred", "support", "A colleague from the customer support team will continue this call now. Thank you, goodbye."),
    "end_refused": ("no_promise", "refused", THANKS),
    "end_hardship": ("no_promise", "hardship", THANKS),
    "end_dispute": ("no_promise", "dispute", THANKS),
    "end_service_error": ("no_promise", "service_error", "I am sorry that I could not record the promise today. " + THANKS),
    "end_failed": ("not_verified", "failed", "I am sorry, I could not verify your identity, so I cannot continue. Please use the Freya Bank mobile app or visit a branch. " + THANKS),
    "end_declined": ("not_verified", "declined", "I understand. I cannot continue without the security check. " + THANKS),
    "end_callback": ("not_reached", "callback", "Thank you, we will call back then. Goodbye."),
    "end_no_callback": ("not_reached", "no_callback", "Thank you for your time. Goodbye."),
    "end_wrong_number": ("not_reached", "wrong_number", "I am sorry for the trouble. Thank you, goodbye."),
    "end_deceased": ("not_reached", "deceased", "I am sorry for your loss. Thank you, goodbye."),
    "end_unclear": ("not_reached", "unclear", "Thank you for your time. Goodbye."),
}

def end_code(outcome, reason, farewell):
    return ("vars['close_outcome'] = %r\nvars['close_reason'] = %r\n"
            "vars['farewell'] = %r.replace('CUSTOMER_NAME', str(vars.get('title') or '') + ' ' + str(vars.get('last_name') or ''))\n") % (outcome, reason, farewell)

# ---------------------------------------------------------------- prompts

SYSTEM = """You are the digital assistant of Freya Bank, on an outbound phone call. Speak English. Keep every turn to one or two short sentences. Never use brackets, stage directions or lists.
You call {{title}} {{first_name}} {{last_name}}. Address the customer as {{title}} {{last_name}}. The current date and time is {{now}}. Never use any other clock.
Always:
- If someone asks whether you are a robot or an AI, say you are Freya Bank's digital assistant, then continue.
- If someone asks whether this is a scam, say they can verify this call by phoning Freya Bank's customer service number, then continue.
- If you cannot answer a question from the information you have, say you do not have that information. Never invent figures, dates or reasons.
- Never offer a discount, a waiver, an instalment plan or any other term.
- When a rule says to call a tool, call it. Call one tool per message. After every tool result, speak to the customer or call the next tool. Never end a turn with nothing.
- A tool result can contain what_to_do_next. Follow it.
- The call ends by itself after you call a transition_to_end tool. Do not say goodbye yourself."""

GREETING_TASK = """You asked whether you are speaking with {{title}} {{last_name}}. Do not say why you are calling. Do not say collections, debt, payment, loan, card or any amount. Do not call a tool in this turn.
- If the person did not clearly confirm (for example they said hello, go ahead, or asked who you are), answer any question first in one sentence, then ask again: "Am I speaking with {{title}} {{last_name}}?"
- If the person asks what the call is about, say you can explain only to {{title}} {{last_name}}, and ask again."""

GREETING_EXTRACTION = [{
    "name": "party", "type": "string", "min_confidence": 0.5,
    "enum_values": ["customer", "someone_else", "wrong_number", "deceased", "refuses", "unclear"],
    "description": ("Who answered, judged from the person's latest message. customer: the person clearly confirms they are the person the "
                    "agent asked for, with yes, that's me, speaking, or their own name. Hello, go ahead, who is this, or a question is NOT a "
                    "confirmation: use unclear. someone_else: a different person answered (for example a relative), or says the customer "
                    "is not there. wrong_number: says the number does not belong to that person or they do not know them. deceased: says "
                    "the person has died. refuses: says they do not want to talk. unclear: anything else.")}]

IDENTITY_TASK = """The person confirmed they are {{title}} {{last_name}}. You must check identity before you say anything about the account. Do not say collections, debt, payment, loan, card or any amount.
Steps:
1. Ask for the date of birth. When the customer answers, call verify_identity with field date_of_birth and the answer as YYYY-MM-DD. Convert spoken dates yourself. If the date is said only in numbers, read it as day, then month, then year.
2. When the date of birth is correct, ask for the last four digits of the phone number on file. When the customer answers, call verify_identity with field phone_last4 and the four digits.
3. A wrong answer: ask the same question again. Never tell the customer the right answer.
Ask one question at a time. Call verify_identity for every answer the customer gives, also when you think it is wrong.
If the customer will not answer, or asks what the call is about in place of an answer, explain once that the questions protect their account and ask again. If they refuse or ask a second time, call transition_to_end_declined.
If the customer says twice that they do not want to talk, call transition_to_end_declined.
If the customer asks for a human, ask once whether you can help first. If they insist, call transfer_human."""

THIRD_PARTY_TASK = """The person on the line is NOT {{title}} {{last_name}}. Never say why you are calling. Never mention collections, a debt, a payment, a product or an amount, even if the person asks or offers to pay. Never ask security questions. Say only that you need to speak with {{title}} {{last_name}} in person.
Ask when {{title}} {{last_name}} can be reached.
{{callback_facts}}
- If the person names a day and a time inside the window, call schedule_callback with the date as YYYY-MM-DD and the time as HH:MM (24 hour). "Morning around eleven" is 11:00.
- If the person names only a day, ask for the time. If they name only a time, ask for the day.
- If the day or time is outside the window, say so and ask once for another time inside it. If the second answer is also outside the window, call transition_to_end_no_callback. If the person does not know any time, call transition_to_end_no_callback.
- If the person says the number does not belong to {{title}} {{last_name}}, call transition_to_end_wrong_number.
- If the person says {{title}} {{last_name}} has died, call transition_to_end_deceased at once and ask nothing else."""

def negotiate_task(brief):
    multi = brief == "b"
    t = """The customer's identity is verified. You already stated the debt and asked whether the customer can pay today.

ACCOUNT FACTS
{{account_facts}}

DATE FACTS
{{date_facts}}

RULES FOR THE PROMISE
1. You propose every amount. Never ask how much the customer can pay. If the customer asks you to choose, propose the full past-due amount.
2. Yes to paying today: the promise is the full past-due amount, today.
3. A date or an amount the customer names is never a refusal. Check it with rules 4 to 8.
4. A valid date is today or later, a business day in the calendar, and not after the product's deadline.
5. A weekend day or holiday that is not after the deadline: say it is not a business day and offer the next business day from the calendar.
6. A date after the deadline: say the latest date you can record is the deadline, and offer the deadline. If the customer refuses the deadline, that is a flat refusal (rule 10).
7. A vague period ("next week", "the week after next", "end of the month", "when my salary comes"): ask once for the exact day. If they still give no day, propose the deadline. Use the weekday table for "this" and "next".
8. An amount from the floor up to the full past-due amount, both included: accept it. Below the floor: say it cannot be recorded and offer the floor once. If the customer does not accept the floor, that is a flat refusal (rule 10).
9. If the customer says the full amount is too much: offer the floor once and say the rest stays overdue. This offer is not a persuasion attempt. If the customer refuses the floor, that is a flat refusal (rule 10).
10. A flat refusal or a non-answer uses one persuasion attempt. A no to paying today with no date and no amount is a flat refusal.
   - Attempt 1: propose the full past-due amount on the attempt 1 date. If the customer already said the full amount is too much, propose the floor on the attempt 1 date.
   - Attempt 2, late band only: propose the floor on the deadline.
   - When the allowed attempts are used up, stop. Never repeat an offer the customer already refused.
11. Illness, a death in the family or job loss: say one short sentence of sympathy. Make no persuasion attempt. Offer once to connect them with the customer support team. If they accept, call transfer_support. If they decline, the result is hardship. If they still name a date or an amount themselves, handle it as a promise.
12. "I already paid" (this past-due amount): say payments can take one business day to appear. Take no promise. The result is paid.
13. "This debt is not mine", "I never had this product", or the product was closed or paid off in the past: do not argue, take no promise. The result is dispute.
14. A request for a new payment plan or lower instalments: do not describe any plan. Call transfer_restructuring.
15. A request for a human: ask once whether you can help first. If they insist, call transfer_human.
16. If the customer says twice that they do not want to talk, the result is refused.

CONFIRM AND RECORD
17. When the amount and the date are agreed, read back the product, the amount and the date (weekday, day and month), and ask "Do you confirm?".
18. Call create_promise only after a clear yes. Send the date as YYYY-MM-DD.
19. If the customer changes the date or the amount at the read-back, check the new value with the rules above and read back again.
20. Never say a promise is recorded unless create_promise returned ok true. If create_promise failed, call it once more with the same values. If it fails a second time, say you could not record it.
"""
    if not multi:
        t += """
ENDING THE CALL
- Promise recorded: the call ends by itself.
- create_promise failed twice: call transition_to_end_service_error.
- Paid (rule 12): call transition_to_end_paid.
- Dispute (rule 13): call transition_to_end_dispute.
- Hardship and the customer declined the support team (rule 11): call transition_to_end_hardship.
- Attempts used up (rule 10), or rule 16: call transition_to_end_refused."""
    else:
        t += """
MORE THAN ONE PRODUCT
21. You already asked whether the customer can pay all products today. If yes, each product is its full past-due amount today. If not, go through the products one by one, in the order of the account facts. Do not ask about today again. Each product starts at attempt 1 of rule 10, and attempts are counted per product. Each product has its own band, deadline, floor and attempts.
22. If the customer names one date for all products and it is after one product's deadline, that product gets its own deadline and the others keep the named date. Say this in the read-back.
23. Do not read back product by product. When every product has a promise or has ended without one, read back all promises together in one message and ask "Do you confirm?" once. After a clear yes, call create_promise once per product, one call per message, with that product_id.
24. A dispute or "already paid" on one product does not end the call. Continue with the next product.
25. Notes: every product that ends without a recorded promise gets one add_note call with its product_id and a reason: refused, hardship, dispute, paid or service_error (create_promise failed twice). Call add_note after the create_promise calls. This also applies when no product gets a promise.
26. Transfers (transfer_restructuring, transfer_support, transfer_human): call no add_note at all, before or after. Promises agreed but not yet recorded are not recorded.

ENDING THE CALL
When every product has a recorded promise or a note:
- At least one promise recorded: say which promises are recorded, then call transition_to_end_promise.
- No promise recorded and every note is paid: call transition_to_end_paid.
- Otherwise take the first product, in account order, whose note is not paid, and call the transition for its reason: transition_to_end_refused, transition_to_end_hardship, transition_to_end_dispute or transition_to_end_service_error."""
    return t

# ---------------------------------------------------------------- workflow

def build(brief):
    multi = brief == "b"
    transfer = lambda queue, name: api_tool(name, "/transfer_to_agent", {"queue": leaf("string", queue)}, post=PLAIN_HOOK,
        description={"restructuring": "Transfer to the restructuring team. CALL it when the customer asks for a new payment plan or lower instalments.",
                     "support": "Transfer to the customer support team. CALL it only when a customer in hardship accepts the offer.",
                     "general": "Transfer to a human. CALL it only when the customer insists on a human after you asked once whether you can help."}[queue])
    t_restr, t_supp, t_human = transfer("restructuring", "transfer_restructuring"), transfer("support", "transfer_support"), transfer("general", "transfer_human")
    to_transfers = [go("end_restructuring", "transferred to restructuring", succeeded("transfer_restructuring")),
                    go("end_support", "transferred to support", succeeded("transfer_support")),
                    go("end_human", "transferred to a human", succeeded("transfer_human"))]

    verify = api_tool("verify_identity", "/verify_identity", {
        "field": leaf("string", "{{field}}", "Which question this answer is for: date_of_birth or phone_last4.", ["date_of_birth", "phone_last4"]),
        "answer": leaf("string", "{{answer}}", "date_of_birth as YYYY-MM-DD. phone_last4 as four digits.")},
        "Check one security answer. CALL it every time the customer answers a security question.", VERIFY_HOOK, required=["field", "answer"])
    callback = api_tool("schedule_callback", "/schedule_callback", {
        "date": leaf("string", "{{date}}", "Callback date as YYYY-MM-DD."),
        "time": leaf("string", "{{time}}", "Callback time as HH:MM, 24 hour.")},
        "Book a callback. CALL it when the person names a day and a time inside the allowed window.", CALLBACK_HOOK, required=["date", "time"])
    promise_body = {"amount": leaf("number", "{{amount}}", "The agreed amount, a number such as 420.00."),
                    "date": leaf("string", "{{date}}", "The agreed date as YYYY-MM-DD.")}
    promise_body["product_id"] = leaf("string", "{{product_id}}", "The product_id from the account facts, for example p1. Copy it unchanged.")
    promise = api_tool("create_promise", "/create_promise", promise_body,
        "Record one payment promise. CALL it only after the customer said yes to the read-back.", PROMISE_HOOK, required=["amount", "date", "product_id"])
    neg_tools = [promise, t_restr, t_supp, t_human]
    if multi:
        neg_tools.append(api_tool("add_note", "/add_note", {
            "product_id": leaf("string", "{{note_product_id}}", "The product_id from the account facts, for example p2. Copy it unchanged."),
            "reason": leaf("string", "{{note_reason}}", "One of: refused, hardship, dispute, paid, service_error.", ["refused", "hardship", "dispute", "paid", "service_error"])},
            "Record why a product ended without a promise. CALL it once for each such product, never on a transfer.", PLAIN_HOOK, required=["product_id", "reason"]))

    single_promise_ok = {"logic": "or", "conditions": [
        {"logic": "and", "conditions": [{"variable": "product_count", "operator": "equals", "operand": "1"},
                                        {"variable": "create_promise_response.data.ok", "operator": "equals", "operand": v}]} for v in ("true", "True")]}
    neg_transitions = [go("end_promise", "the only promise is recorded", single_promise_ok)] + to_transfers + [
        tool_go("end_service_error", "create_promise failed twice and the customer was told"),
        tool_go("end_paid", "the customer already paid"),
        tool_go("end_dispute", "the customer disputes the debt"),
        tool_go("end_hardship", "hardship and the customer declined the support team"),
        tool_go("end_refused", "the persuasion attempts are used up, or the customer said twice they do not want to talk")]
    if multi:
        neg_transitions.insert(1, tool_go("end_promise", "at least one promise is recorded and every product is handled"))

    party = lambda v: var_is("party", v)
    turns2 = {"variable": "greeting.total_turns", "operator": "greater_than", "operand": 1}
    nodes = {
        "setup": code_node("setup", SETUP_CODE, "greeting"),
        "greeting": conversation("greeting", GREETING_TASK,
            on_enter={"type": "tts", "text": "Hello, I am a digital assistant calling from Freya Bank, and this call is recorded. Am I speaking with {{title}} {{last_name}}?"},
            extraction=GREETING_EXTRACTION, max_turns=6, cap_target="end_unclear", transitions=[
                go("identity", "the customer confirmed", party("customer")),
                go("end_deceased", "the customer has died", party("deceased")),
                go("end_wrong_number", "wrong number", party("wrong_number")),
                go("third_party", "someone else answered", party("someone_else")),
                go("end_declined", "refused twice", {"logic": "or", "conditions": [{"logic": "and", "conditions": [{"variable": "party", "operator": "equals", "operand": "refuses"}, turns2]}]}),
                go("end_unclear", "still unclear after the second ask", {"logic": "or", "conditions": [{"logic": "and", "conditions": [{"variable": "party", "operator": "equals", "operand": "unclear"}, turns2]}]}),
                go("greeting", "ask again", {"operator": "always"})]),
        "third_party": conversation("third_party", THIRD_PARTY_TASK, tools=[callback], max_turns=12, cap_target="end_no_callback", transitions=[
            go("end_callback", "callback booked", is_true("schedule_callback_response.data.ok")),
            tool_go("end_deceased", "the customer has died"),
            tool_go("end_wrong_number", "the number does not belong to the customer"),
            tool_go("end_no_callback", "no callback time inside the window")]),
        "identity": conversation("identity", IDENTITY_TASK, tools=[verify, t_human], max_turns=20, cap_target="end_declined",
            on_enter={"type": "tts", "text": "Thank you. First I need to ask two security questions. What is your date of birth?"},
            transitions=[go("fetch_account", "both answers verified", is_true("verify_identity_response.data.all_verified")),
                         go("end_failed", "three wrong answers", var_is("verify_identity_response.data.wrong_answers_left", "0")),
                         go("end_human", "transferred to a human", succeeded("transfer_human")),
                         tool_go("end_declined", "the customer declined the security questions")]),
        "fetch_account": {"name": "fetch_account", "node_type": "api_request", "passthrough": True, "passthrough_default_transition": "prepare_account",
            "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
            "pre_actions": [api_tool("get_account", "/get_account", {}, "Get the late products.", retries=1)],
            "response_mapping": [{"path": "data.products", "variable": "products"}],
            "transitions": [go("prepare_account", "always", {"operator": "always"})]},
        "prepare_account": code_node("prepare_account", ACCOUNT_CODE, "negotiate",
            [go("end_service_error", "no account data", var_is("product_count", "0"))]),
        "negotiate": conversation("negotiate", negotiate_task(brief), tools=neg_tools, transitions=neg_transitions, max_turns=50,
            cap_target="end_refused", on_enter={"type": "tts", "text": "{{debt_statement}}"}),
        "goodbye": {"name": "goodbye", "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "transitions": [],
            "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call", "parameters": {"type": "object", "properties": {
                "message_mode": leaf("string", "custom"), "spoken_message": leaf("string", "{{farewell}}")}}}}},
    }
    promise_bye = ("You will receive a text message confirming this promise. " + THANKS) if multi else \
                  ("Your promise is recorded. You will receive a text message confirming this promise. " + THANKS)
    for key, (outcome, reason, farewell) in ENDS.items():
        nodes[key] = code_node(key, end_code(outcome, reason, farewell or promise_bye), "goodbye")

    close = api_tool("close_call", "/close_call", {
        "outcome": leaf("string", "{{close_outcome}}", "How the call ended.", ["promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"]),
        "reason": leaf("string", "{{close_reason}}", "transferred: restructuring, human or support. no_promise: refused, hardship, dispute or service_error. not_verified: failed or declined. not_reached: callback, no_callback, wrong_number, deceased or unclear. none for promise and paid.")},
        "Record how the call ended, from the conversation.", required=["outcome"])
    close["config"]["alwaysRunsAt"] = ["end_of_call"]
    close["pre_process_code"] = CLOSE_PRE

    return {"initial_node": "setup", "system_prompt": SYSTEM, "nodes": nodes, "global_nodes": {}, "tools": [close],
            "test_variables": {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"}}

if __name__ == "__main__":
    for b in ("a", "b"):
        (OUT / f"brief-{b}.workflow.json").write_text(json.dumps(build(b), indent=1))
        print("wrote", OUT / f"brief-{b}.workflow.json")
