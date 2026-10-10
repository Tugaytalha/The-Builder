"""Generates out/brief-a.workflow.json. Run from the kit folder."""
import json, sys

BASE = "https://freya-bank-mock.freyavoice.workers.dev/v1/"

# ---------------------------------------------------------------- code (runs in the setup and account_facts nodes)
FACTS_CODE = r'''
import datetime, json, re
HOL = set(['2026-10-26', '2026-11-11', '2026-11-26', '2026-12-25', '2027-01-01'])
WD = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MO = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
ONE = datetime.timedelta(days=1)

def is_bd(d):
    return d.weekday() < 5 and d.isoformat() not in HOL

def add_bd(d, n):
    x = d
    c = 0
    while c < n:
        x = x + ONE
        if is_bd(x):
            c += 1
    return x

def next_bd_from(d):
    x = d
    while not is_bd(x):
        x = x + ONE
    return x

def say(d):
    return WD[d.weekday()] + ' ' + str(d.day) + ' ' + MO[d.month - 1] + ' ' + str(d.year) + ' (' + d.isoformat() + ')'

def money(x):
    return '{:,.2f}'.format(float(x))

def last_bd_of_week(monday):
    x = monday + datetime.timedelta(days=4)
    while not is_bd(x):
        x = x - ONE
    return x

def parse_list(v):
    if isinstance(v, dict):
        return [v]
    if isinstance(v, list):
        return v
    if isinstance(v, str) and v.strip():
        s = v.strip()
        for t in (s, s.replace("'", '"').replace('True', 'true').replace('False', 'false').replace('None', 'null')):
            try:
                r = json.loads(t)
                return parse_list(r)
            except Exception:
                pass
    return []

def find_products():
    for k in ('products', 'get_account_response.data.products', 'load_account_response.data.products'):
        r = parse_list(vars.get(k))
        if r:
            return r
    items = dict()
    for k in list(vars.keys()):
        m = re.search(r'products[\.\[](\d+)\]?\.(\w+)$', str(k))
        if m:
            items.setdefault(int(m.group(1)), dict())[m.group(2)] = vars.get(k)
    return [items[i] for i in sorted(items)]

try:
    now = datetime.datetime.fromisoformat(str(vars.get('now'))[:16])
except Exception:
    now = datetime.datetime.now()
today = now.date()
hhmm = now.strftime('%H:%M')
nbd = add_bd(today, 1)
if hhmm < '19:00':
    first = '10:00' if hhmm < '10:00' else 'later than ' + hhmm
    today_cb = 'today, ' + say(today) + ', at a time ' + first + ' and not later than 19:00'
else:
    today_cb = 'no time is left today'
vars['callback_facts'] = ('Now is ' + say(today) + ', ' + hhmm + '. A callback can be booked only for: ' + today_cb +
    '; or the next business day, ' + say(nbd) + ', from 10:00 to 19:00 (both included). Tomorrow means ' + say(today + ONE) +
    '. Every other day and time is outside the window.')

prods = find_products()
p = prods[0] if prods else None
if p:
    typ = str(p.get('type') or '')
    past_due = float(p.get('past_due') or 0)
    days_late = int(float(p.get('days_late') or 0))
    if typ == 'credit_card':
        words = 'credit card ending ' + str(p.get('card_last4') or '')
        floor = float(p.get('minimum_payment') or 0)
        floor_name = 'minimum payment'
    else:
        words = 'car loan' if typ == 'car_loan' else 'personal loan'
        floor = float(p.get('instalment_amount') or 0)
        floor_name = 'instalment amount'
    early = days_late <= 7
    deadline = add_bd(today, 12 if early else 7)
    monday = today - datetime.timedelta(days=today.weekday())
    a1 = last_bd_of_week(monday)
    if a1 <= today:
        a1 = last_bd_of_week(monday + datetime.timedelta(days=7))
    lines = []
    for i in range(0, (deadline - today).days + 1):
        d = today + datetime.timedelta(days=i)
        tag = 'today, ' if i == 0 else ''
        if is_bd(d):
            st = 'allowed'
        else:
            why = 'bank holiday' if d.isoformat() in HOL else 'weekend'
            st = 'NOT allowed: ' + why + ', offer the next business day ' + say(next_bd_from(d))
        lines.append('- ' + say(d) + ': ' + tag + st)
    lines.append('- Every date after ' + say(deadline) + ' is NOT allowed: it is after the deadline, offer the deadline ' + say(deadline) + '.')
    this_next = []
    for w in range(7):
        t = monday + datetime.timedelta(days=w)
        this_next.append('- "this ' + WD[w] + '" = ' + t.isoformat() + ('' if t >= today else ' (in the past)') + '; "next ' + WD[w] + '" = ' + (t + datetime.timedelta(days=7)).isoformat())
    vars['product_id'] = str(p.get('product_id') or 'p1')
    vars['account_state'] = 'loaded'
    vars['debt_line'] = ('Thank you, you are verified. I am calling from the collections team about a late payment on your ' + words +
        '. The past-due amount is ' + money(past_due) + ', and the payment is ' + str(days_late) + ' days late. Can you make this payment today?')
    att = ('1 persuasion attempt (early band, 1 to 7 days late).' if early else '2 persuasion attempts (late band, 8 to 45 days late).')
    a2 = ('There is NO attempt 2 for this customer.' if early else
          'Attempt 2: propose the floor amount ' + money(floor) + ' on the deadline ' + say(deadline) + '.')
    vars['account_facts'] = '\n'.join([
        'Product: ' + words + ' (product_id ' + vars['product_id'] + ').',
        'Full past-due amount: ' + money(past_due) + '. Days late: ' + str(days_late) + '.',
        'Floor (' + floor_name + '): ' + money(floor) + '.',
        'Today: ' + say(today) + '.',
        'Deadline (latest promise date): ' + say(deadline) + '.',
        'This customer gets ' + att,
        'Attempt 1: propose the full amount ' + money(past_due) + ' (or the floor ' + money(floor) + ' if the customer already said the full amount is too much) on ' + say(a1) + '.',
        a2,
        'An amount is allowed when it is from ' + money(floor) + ' up to ' + money(past_due) + ', both included.',
        '',
        'Calendar (use it for every date; never compute a date yourself):',
    ] + lines + ['', 'Weekday words:'] + this_next)
else:
    vars['product_id'] = ''
    vars['account_state'] = 'missing'
    vars['debt_line'] = 'Thank you, you are verified. I am sorry, I cannot load your account details at the moment.'
    vars['account_facts'] = 'The account could not be loaded. Do not state any amount or product. Apologise, thank the customer, say goodbye and call close_call with outcome no_promise and reason service_error.'
'''

# ---------------------------------------------------------------- hooks
VERIFY_POST = r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            result['what_to_do_next'] = 'The check service did not answer. Nothing was checked. Ask the customer to repeat the same answer, then call verify_identity again.'
        else:
            left = d.get('wrong_answers_left')
            if d.get('hint') == 'day_month_swapped':
                n = 'The day and the month look swapped. Ask the customer to say the month of their date of birth as a word. This is not a wrong answer.'
            elif d.get('ok') is False and d.get('verified') is None:
                n = 'The answer could not be read. It is not a wrong answer. Ask for the same answer again and send a date of birth as YYYY-MM-DD.'
            elif d.get('all_verified'):
                n = 'Both answers are correct.'
            elif d.get('verified'):
                n = 'Correct. Now ask the next security question: the last four digits of the phone number on file.'
            elif left is not None and int(left) <= 0:
                n = 'Third wrong answer. The check has ended. Do not state any debt, amount or product. Tell the customer to use the mobile app or a branch, thank them, say goodbye, and call close_call with outcome not_verified and reason failed.'
            else:
                n = 'Wrong answer. Wrong answers left: ' + str(left) + '. Say that the answer does not match and ask the same question again.'
            d['what_to_do_next'] = n
except Exception:
    pass
'''

PROMISE_POST = r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if isinstance(d, dict) and d.get('ok') is True:
            d['what_to_do_next'] = 'The promise is recorded.'
        else:
            result['what_to_do_next'] = ('The promise was NOT recorded. Never say it is recorded. If this is the first failed create_promise in this call, call create_promise again now with the same values. '
                'If create_promise already failed once before, tell the customer you could not record the promise, apologise, thank them, say goodbye, and call close_call with outcome no_promise and reason service_error.')
except Exception:
    pass
'''

TRANSFER_POST = r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if isinstance(d, dict) and d.get('ok') is True:
            d['what_to_do_next'] = 'The transfer is done. Tell the customer a colleague will take over, thank them, say goodbye, and call close_call with outcome transferred and the reason of this transfer: restructuring, human (for queue general) or support.'
        else:
            result['what_to_do_next'] = 'The transfer did not work. Tell the customer you could not transfer the call. Do not say a colleague will take over.'
except Exception:
    pass
'''

CLOSE_PRE = r'''
try:
    b = config.get('body')
    if isinstance(b, dict):
        def yes(k):
            return str(vars.get(k, '')).lower() == 'true'
        q = str(vars.get('transfer_to_agent_args.queue') or '')
        if q and yes('transfer_to_agent_response.data.ok'):
            b['outcome'] = 'transferred'
            b['reason'] = 'human' if q == 'general' else q
        elif yes('create_promise_response.data.ok'):
            b['outcome'] = 'promise'
        elif str(vars.get('verify_identity_response.data.wrong_answers_left', '')) == '0' and not yes('verify_identity_response.data.all_verified'):
            b['outcome'] = 'not_verified'
            b['reason'] = 'failed'
        if b.get('outcome') in ('promise', 'paid'):
            b.pop('reason', None)
except Exception:
    pass
'''

CLOSE_POST = "try:\n    if isinstance(result, dict):\n        result.pop('header', None)\nexcept Exception:\n    pass\n"

# ---------------------------------------------------------------- tool builders
def api_tool(name, desc, body_props, required, retries=0, post="", pre=""):
    props = {"customer_id": {"type": "string", "default": "{{customer_id}}"}}
    props.update(body_props)
    t = {
        "type": "function",
        "config": {"timeoutMs": 12000, "maxRetries": retries},
        "function": {
            "name": name, "handler": "__function__:api_call", "description": desc,
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "default": BASE + name},
                "method": {"type": "string", "default": "POST"},
                "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                "body": {"type": "object", "properties": props, "required": required},
            }},
        },
    }
    if post: t["post_process_code"] = post
    if pre: t["pre_process_code"] = pre
    return t

OUTCOME_HELP = ("promise: a promise was recorded. paid: the customer says they already paid this amount. "
                "transferred: transfer_to_agent succeeded. no_promise: verified customer, no promise. "
                "not_verified: the identity check did not pass or the customer declined it. not_reached: the right person was not reached.")
REASON_HELP = ("Leave empty for promise and paid. transferred: restructuring, human or support. "
               "no_promise: refused, hardship, dispute or service_error. not_verified: failed or declined. "
               "not_reached: callback, no_callback, wrong_number, deceased or unclear.")
close_call = api_tool(
    "close_call",
    "Record how the call ended. CALL it exactly once, at the very end, in the same message as your goodbye. Nothing may follow it.",
    {"outcome": {"type": "string", "enum": ["promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"], "default": "{{outcome}}", "description": OUTCOME_HELP},
     "reason": {"type": "string", "enum": ["", "restructuring", "human", "support", "refused", "hardship", "dispute", "service_error", "failed", "declined", "callback", "no_callback", "wrong_number", "deceased", "unclear"], "default": "{{reason}}", "description": REASON_HELP}},
    ["outcome"], pre=CLOSE_PRE, post=CLOSE_POST)

transfer = api_tool(
    "transfer_to_agent",
    "Hand the call to a person. CALL it only when a rule says to transfer: restructuring for a new plan or lower instalments, general when the customer insists on a human, support when a customer in hardship accepts the support team.",
    {"queue": {"type": "string", "enum": ["restructuring", "general", "support"], "default": "{{queue}}", "description": "One of: restructuring, general, support."}},
    ["queue"], post=TRANSFER_POST)

callback = api_tool(
    "schedule_callback",
    "Book a callback for the customer. CALL it when the person on the line gives a day and a time that is inside the callback window.",
    {"date": {"type": "string", "default": "{{callback_date}}", "description": "Callback date as YYYY-MM-DD."},
     "time": {"type": "string", "default": "{{callback_time}}", "description": "Callback time as HH:MM, 24 hour."}},
    ["date", "time"], post=CLOSE_POST)

verify = api_tool(
    "verify_identity",
    "Check one security answer. CALL it every time the customer gives an answer to a security question, once per answer. Then obey what_to_do_next in the result.",
    {"field": {"type": "string", "enum": ["date_of_birth", "phone_last4"], "default": "{{field}}", "description": "Which question this answer is for: date_of_birth or phone_last4."},
     "answer": {"type": "string", "default": "{{answer}}", "description": "date_of_birth as YYYY-MM-DD (convert spoken dates; digits only means day, then month, then year). phone_last4 as four digits."}},
    ["field", "answer"], post=VERIFY_POST)

promise = api_tool(
    "create_promise",
    "Record the payment promise. CALL it only after the customer said a clear yes to your read-back of product, amount and date. Then obey what_to_do_next in the result.",
    {"amount": {"type": "number", "default": "{{amount}}", "description": "The confirmed amount, a number such as 420.0."},
     "date": {"type": "string", "default": "{{date}}", "description": "The confirmed date as YYYY-MM-DD, copied from the calendar."},
     "product_id": {"type": "string", "default": "{{product_id}}", "description": "product_id from the account facts."}},
    ["amount", "date", "product_id"], post=PROMISE_POST)

get_account = api_tool("get_account", "Get the late products.", {}, [], retries=2)

# ---------------------------------------------------------------- transitions
def var_any(var, values):
    return {"logic": "or", "conditions": [{"variable": var, "operator": "equals", "operand": v} for v in values]}

TO_END = {"target_node": "end", "description": "close_call was called",
          "condition": {"logic": "or", "conditions": [
              {"variable": "close_call_success_count", "operator": "greater_than", "operand": 0},
              {"variable": "close_call_failure_count", "operator": "greater_than", "operand": 0}]}}

def code_node(name, nxt):
    return {
        "name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": nxt,
        "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
        "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
            "parameters": {"type": "object", "properties": {
                "code": {"type": "string", "default": FACTS_CODE},
                "timeout_ms": {"type": "number", "default": 10000}}}}}],
        "transitions": [{"target_node": nxt, "description": "always", "condition": {"operator": "always"}}],
    }

TOOL_RULE = ("Call one tool per message. After every tool result, speak to the customer or call the next tool. Never end a turn with nothing. "
             "When a rule says to use a tool, call the tool; saying it is not enough.")

SYSTEM = f"""You are the digital assistant of Freya Bank on an outbound phone call. Speak English. Keep every turn to one or two short sentences. Ask one question at a time.
The customer is {{{{title}}}} {{{{last_name}}}}. Address them as {{{{title}}}} {{{{last_name}}}}.
Rules for the whole call:
- If asked whether you are a robot or an AI: say you are Freya Bank's digital assistant, then continue.
- If asked whether this is a scam: say they can verify the call by phoning Freya Bank's customer service number, then continue.
- If asked something the facts and tools do not answer: say you do not have that information. Never invent figures, dates or reasons.
- Never offer a discount, a waiver, an instalment plan or any other term.
- Never ask the customer how much they can pay.
- Never say something is recorded, booked or transferred unless the tool result says ok true.
- To end the call: thank the customer and say goodbye, and in the same message call close_call. close_call is always the last tool call.
- {TOOL_RULE}"""

greeting_task = """Find out who is on the line. You have already said the opening line and asked whether you are speaking with {{title}} {{last_name}}.
Before identity is verified, never say why you are calling. Never say collections, debt, payment, amount, loan or card. This applies to everyone, including relatives.

- Confirmation counts only when the person says "yes", "that's me", "speaking" or says the customer's own name. Then call transition_to_identity at once, with no words.
- "Hello", "go ahead", "who is this" or anything else is NOT a confirmation. Answer a question first (for "who is this": you are Freya Bank's digital assistant), then ask again: "Am I speaking with {{title}} {{last_name}}?". You may ask this a second time only once. If it is still unclear after the second ask, close with not_reached / unclear.
- Someone else answers (a relative, a partner, a colleague): say nothing about the reason for the call, even if they ask or offer to pay. Do not ask them security questions. Ask when {{title}} {{last_name}} can be reached.
  Callback window: {{callback_facts}}
  If they give a day and a time inside the window, call schedule_callback with the date (YYYY-MM-DD) and the time (HH:MM). After it returns ok, thank them, say goodbye and close with not_reached / callback.
  If they give a day or time outside the window, say it is not possible and ask once for another time inside the window. If that is also outside, do not schedule; thank them, say goodbye and close with not_reached / no_callback.
  If they only give a vague time ("in the morning"), ask for an exact time.
- The number does not belong to the customer: close with not_reached / wrong_number.
- The customer has died: say exactly "I am sorry for your loss." Ask nothing else. Thank them, say goodbye and close with not_reached / deceased.
- The person asks for a human: ask once whether you can help first. If they insist, call transfer_to_agent with queue general, then close with transferred / human.
- The person says twice that they do not want to talk: close with not_verified / declined.
"Close with X / Y" means: thank them, say goodbye, and in the same message call close_call with outcome X and reason Y."""

identity_task = """Verify the customer's identity with two security questions, one at a time: first the date of birth, then the last four digits of the phone number on file.
Before identity is verified, never say why you are calling. Never say collections, debt, payment, amount, loan or card. If asked, say you can explain after the security check.

- Call verify_identity for every answer, then obey what_to_do_next in the result. Never decide yourself whether an answer is right.
- Date of birth: send it as YYYY-MM-DD, whatever way the customer said it. If the customer says only numbers, read them as day, then month, then year (for example 03/07/1990 is 1990-07-03).
- Phone: send the four digits only, field phone_last4.
- If the customer gives a partial answer, ask for the rest before you call the tool.
- If the customer does not want to answer, or asks what the call is about instead of answering: explain once that the questions protect their account, and ask again. If they refuse again or ask again, close with not_verified / declined.
- If the customer asks for a human: ask once whether you can help first. If they insist, call transfer_to_agent with queue general, then close with transferred / human.
- If the customer says twice that they do not want to talk: close with not_verified / declined.
"Close with X / Y" means: thank them, say goodbye, and in the same message call close_call with outcome X and reason Y."""

collect_task = """The customer is verified. You have already stated the debt and asked "Can you make this payment today?". Get a payment promise where you can, and close the call with the correct outcome.

FACTS (use only these; never compute a date or an amount yourself):
{{account_facts}}

TOOLS: create_promise records a promise. transfer_to_agent hands over. close_call ends the call. "Close with X / Y" means: thank the customer, say goodbye, and in the same message call close_call with outcome X and reason Y.

CHECK THESE FIRST, on every customer message. They come before any persuasion:
1. Illness, a death in the family or job loss: say one short sentence of sympathy. Make NO persuasion attempt. Offer once to connect them with the customer support team. If they accept, call transfer_to_agent with queue support, then close with transferred / support. If they decline, close with no_promise / hardship. If they still name a date or an amount themselves, handle it as a proposal below.
2. "I already paid" (this past-due amount): say that payments can take one business day to appear. Take no promise. Close with paid.
3. "This debt is not mine", "I never had this product", or the product was closed or paid off in the past: do not argue, take no promise. Close with no_promise / dispute.
4. A new payment plan or lower instalments: do not describe any plan. Call transfer_to_agent with queue restructuring, then close with transferred / restructuring.
5. A human: ask once whether you can help first. If they insist, call transfer_to_agent with queue general, then close with transferred / human.
6. The customer says twice that they do not want to talk: close with no_promise / refused.

DATES the customer proposes (look each one up in the calendar):
- "allowed": accept it.
- A weekend or holiday that is not after the deadline: say that day is not possible and offer the next business day shown in the calendar.
- After the deadline: say the latest date you can record is the deadline, and offer the deadline. If they refuse the deadline, that is a flat refusal.
- A vague period ("next week", "end of the month", "when my salary comes", "the week after next"): ask once for the exact day. If they still give none, propose the deadline.
- "Next <weekday>" and "this <weekday>": use the weekday words list.

AMOUNTS (you propose every amount; never ask how much they can pay):
- Ask for the full past-due amount first.
- If the customer says the full amount is too much: offer the floor once, and say that the rest stays overdue. If they refuse the floor, that is a flat refusal.
- If the customer proposes an amount from the floor up to the full amount, accept it. Below the floor: say it cannot be recorded and offer the floor once; if they do not accept, that is a flat refusal.

PERSUASION. A date or an amount the customer proposes is never a refusal. A flat refusal is a no with no date and no amount (for example a no to paying today), or a non-answer. Each flat refusal uses one attempt, in this order:
- Attempt 1 and attempt 2 are in the facts. Use them exactly. The customer's number of attempts is in the facts.
- When the attempts are used up, stop. Do not repeat an offer the customer already refused. Close with no_promise / refused.

CONFIRMING:
- When a product, amount and date are agreed, read them back: the product in words, the amount, and the date as weekday, day and month. Then ask "Do you confirm?".
- If they change the date or the amount, check it again with the rules above and read it back again.
- After a clear yes, call create_promise with the amount and the date (YYYY-MM-DD) from the calendar. Then obey what_to_do_next in the result.
- If create_promise fails: never say it is recorded. Call it once more with the same values. If it fails again, tell the customer you could not record the promise and close with no_promise / service_error."""

after_promise_task = """The promise is recorded. You have told the customer, and said the text message sentence.
- If the customer asks to change or cancel the promise: say they can change it in the mobile app. Do not record a new promise.
- If the customer asks for a new payment plan or lower instalments: call transfer_to_agent with queue restructuring, then close with transferred / restructuring.
- If the customer asks for a human and insists: call transfer_to_agent with queue general, then close with transferred / human.
- Otherwise, or when the customer says goodbye: thank them, say goodbye, and in the same message call close_call with outcome promise.
"Close with X / Y" means: thank them, say goodbye, and in the same message call close_call with outcome X and reason Y."""

wf = {
    "initial_node": "setup",
    "system_prompt": SYSTEM,
    "test_variables": {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"},
    "global_nodes": {},
    "nodes": {
        "setup": code_node("setup", "greeting"),
        "greeting": {
            "name": "greeting", "node_type": "conversation",
            "on_enter": {"type": "tts", "text": "Hello, I am a digital assistant calling from Freya Bank. Freya Bank records this call. Am I speaking with {{title}} {{last_name}}?"},
            "on_enter_first_entry_only": True,
            "task_message": greeting_task,
            "tools": [callback, transfer, close_call],
            "max_node_turns": 30, "max_turn_transition": "end",
            "transitions": [
                TO_END,
                {"target_node": "identity", "is_tool_call": True,
                 "description": "CALL this at once, with no words, when the person on the line clearly confirms they are {{title}} {{last_name}} (yes, that's me, speaking, or their own name).",
                 "condition": {"operator": "matches_intent", "description": "The person confirmed they are {{title}} {{last_name}}"}},
            ],
        },
        "identity": {
            "name": "identity", "node_type": "conversation",
            "on_enter": {"type": "tts", "text": "Thank you, {{title}} {{last_name}}. First I need to ask you two security questions. What is your date of birth?"},
            "on_enter_first_entry_only": True,
            "task_message": identity_task,
            "tools": [verify, transfer, close_call],
            "max_node_turns": 30, "max_turn_transition": "end",
            "transitions": [
                TO_END,
                {"target_node": "load_account", "description": "Both security answers passed",
                 "condition": var_any("verify_identity_response.data.all_verified", ["true", "True"])},
            ],
        },
        "load_account": {
            "name": "load_account", "node_type": "api_request", "passthrough": True,
            "passthrough_default_transition": "account_facts", "on_enter": {"type": "silent"},
            "disable_inactivity_monitor": True, "suppress_tool_results": True,
            "pre_actions": [get_account],
            "response_mapping": [{"path": "data.products", "variable": "products"}],
            "transitions": [{"target_node": "account_facts", "description": "always", "condition": {"operator": "always"}}],
        },
        "account_facts": code_node("account_facts", "collect"),
        "collect": {
            "name": "collect", "node_type": "conversation",
            "on_enter": {"type": "tts", "text": "{{debt_line}}"},
            "on_enter_first_entry_only": True,
            "task_message": collect_task,
            "tools": [promise, transfer, close_call],
            "max_node_turns": 40, "max_turn_transition": "end",
            "transitions": [
                TO_END,
                {"target_node": "after_promise", "description": "The promise was recorded",
                 "condition": var_any("create_promise_response.data.ok", ["true", "True"])},
            ],
        },
        "after_promise": {
            "name": "after_promise", "node_type": "conversation",
            "on_enter": {"type": "tts", "text": "Your payment promise is recorded. You will receive a text message confirming this promise. Is there anything else I can help you with?"},
            "on_enter_first_entry_only": True,
            "task_message": after_promise_task,
            "tools": [transfer, close_call],
            "max_node_turns": 10, "max_turn_transition": "end",
            "transitions": [TO_END],
        },
        "end": {
            "name": "end", "node_type": "end_call", "on_enter": {"type": "silent"},
            "disable_inactivity_monitor": True, "transitions": [],
            "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call",
                "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "none"}}}}},
        },
    },
}

if "{{" in FACTS_CODE or "}}" in FACTS_CODE:
    sys.exit("code contains braces")
json.dump(wf, open(sys.argv[1], "w"), indent=1)
print("written", sys.argv[1])
