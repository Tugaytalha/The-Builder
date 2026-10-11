"""Worked example: the generator for the invented Lumen Energy brief.

Run it in the run folder (cwd): it reads spec.json and tool_api.json and writes workflow.json.
Copy it, then change it to fit your ledger. Every value comes from spec.json; the code is the shape.
"""
import json

from builder.blocks.coderun import with_dates
from builder.blocks.nodes import (all_of, always, any_of, cond, conversation, field, go, intent, is_true, tts,
                                  workflow, api_node, code_node)
from builder.blocks.patterns import (answer_tool, close_sequence, close_tool, guard_hook, identity_check, negotiation_tool,
                                     start, state_tool, write_loop)
from builder.blocks.tools import load_api, make_tool

SPEC = json.load(open("spec.json"))
API = load_api("tool_api.json")
V = SPEC["vars"]
CUSTOMER = "{{" + V["title"] + "}} {{" + V["last_name"] + "}}"
BAKED_ID = {V["id"]: "{{" + V["id"] + "}}"}   # the call variable the bank needs in every body

# ---------------------------------------------------------------- code run by the engine (no template braces)

# Shared helpers for every snippet. with_dates() puts builder/blocks/datelib.py in front of them.
HELPERS = r'''
import json
HOLIDAYS = set(%r)
WD = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MON = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
def say(d):
    return WD[d.weekday()] + ' ' + str(d.day) + ' ' + MON[d.month - 1] + ' ' + str(d.year)
def iso_day(s):
    s = str(s)
    return date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
def money(x):
    return '%%.2f' %% float(x)
''' % (SPEC["holidays"],)

SETUP = HELPERS + r'''
now = str(vars.get('now') or '')
today = iso_day(now)
hhmm = now[11:16] if len(now) >= 16 else '00:00'
vars['today_iso'] = today.isoformat()
for name, n in %r:
    d = nth_business_day_after(today, n, HOLIDAYS)
    vars['deadline_' + name] = d.isoformat()
bd1 = nth_business_day_after(today, 1, HOLIDAYS)
vars['bd1'] = bd1.isoformat()
lines = ['Today is ' + say(today) + ' (' + today.isoformat() + '), time ' + hhmm + '.', 'Calendar:']
for i in range(36):
    d = today + timedelta(days=i)
    tag = 'business day' if is_business_day(d, HOLIDAYS) else 'NOT a business day'
    lines.append('- ' + d.isoformat() + ' ' + WD[d.weekday()] + ': ' + tag)
monday = this_weekday(today, 0)
for i in range(7):
    lines.append('this ' + WD[i] + ' = ' + this_weekday(today, i).isoformat() + ', next ' + WD[i] + ' = ' + next_weekday(today, i).isoformat())
vars['date_facts'] = '\n'.join(lines)
days = [nth_business_day_after(today, k, HOLIDAYS) for k in %r]
vars['callback_days'] = ','.join(d.isoformat() for d in days)
vars['callback_facts'] = ('A callback is allowed only on ' + ' or '.join(say(d) + ' (' + d.isoformat() + ')' for d in days)
                          + ', from %s to %s, both included.')
''' % ([[b["name"], b["deadline_business_days"]] for b in SPEC["bands"]],
       SPEC["callback"]["business_days_after_today"], SPEC["callback"]["from"], SPEC["callback"]["to"])

A = SPEC["account"]
PREPARE = HELPERS + r'''
import re
def load_list():
    v = vars.get(%(list)r)
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            import ast
            v = ast.literal_eval(v)
    if isinstance(v, list):
        return v
    found = dict()
    for k in list(vars.keys()):
        m = re.search(r'%(list)s[.\[](\d+)\]?\.(\w+)$', str(k))
        if m:
            found.setdefault(int(m.group(1)), dict())[m.group(2)] = vars.get(k)
    return [found[i] for i in sorted(found)]
BANDS = %(bands)r
WORDS = %(words)r
items, facts, said = [], [], []
for p in load_list():
    days_late = int(float(p.get(%(days)r)))
    band = [b for b in BANDS if days_late <= b[1]][0]
    full, floor = float(p.get(%(amount)r)), float(p.get(%(floor)r))
    deadline = vars.get('deadline_' + band[0])
    offers = []
    for amount_kind, date_kind in band[2]:
        offers.append([full if amount_kind == 'full' else floor, deadline if date_kind == 'deadline' else vars.get(date_kind)])
    word = WORDS.get(str(p.get(%(kind)r)), str(p.get(%(kind)r)))
    items.append(dict(id=str(p.get(%(id)r)), word=word, full=full, floor=floor, deadline=deadline, offers=offers, used=0,
                      status='open'))
    facts.append('Item ' + str(p.get(%(id)r)) + ': ' + word + ', overdue ' + money(full) + ', ' + str(days_late)
                 + ' days. Smallest payment ' + money(floor) + '. Deadline ' + say(iso_day(deadline)) + ' (' + deadline + ').')
    said.append('your ' + word + ' has ' + money(full) + ' overdue, ' + str(days_late) + ' days late')
items[0]['asked'] = 'yes'   # the debt statement asks about the first item
vars['neg_state'] = json.dumps(dict(items=items))
vars['item_count'] = str(len(items))
vars['account_facts'] = '\n'.join(facts)
first = items[0]
vars['debt_statement'] = ('Thank you. I am calling about an overdue bill: ' + '; '.join(said)
                          + '. Could you settle the full amount by ' + say(iso_day(first['deadline'])) + '?')
vars['guide'] = 'Wait for the answer. Say nothing new.'
''' % {"list": A["list_field"], "bands": [[b["name"], b["max_days"], b["offers"]] for b in SPEC["bands"]],
       "words": A["kind_words"], "days": A["days_field"], "amount": A["amount_field"], "floor": A["floor_field"],
       "kind": A["kind_field"], "id": A["id_field"]}

P = SPEC["promise"]
# The state tool: the model reports what the customer said, the code decides the next step (spikes S2, S9).
# The brief's policy for one item. patterns.negotiation_tool adds the engine: the state per item, several answers in
# one turn, one line per turn, no line said twice, and the end (spikes S2, S9, S12). The lines are only words for the
# customer: the engine puts them in quotes after SAY.
POLICY = HELPERS + r'''
def read_back(it, amount, day):
    it['agreed'] = [round(float(amount), 2), day]
    return money(amount) + ' for your ' + it['word'] + ' on ' + say(iso_day(day)) + '. Is that right?'
def ok_day(it, day):
    try:
        d = iso_day(day)
    except Exception:
        return False
    return is_business_day(d, HOLIDAYS) and vars.get('today_iso') <= day <= it['deadline']
def decide(it, kind, amount, day):
    if kind == 'refuses':
        it.pop('agreed', None)
        it['used'] = it['used'] + 1
        if it['used'] > len(it['offers']):
            it['status'] = 'stopped'
            return ''
        it['pending'] = it['offers'][it['used'] - 1]
        return 'Could you pay ' + money(it['pending'][0]) + ' for your ' + it['word'] + ' on ' + say(iso_day(it['pending'][1])) + '?'
    if kind == 'accepts' or (kind == 'confirms' and not it.get('agreed')):
        amount, day = it.get('pending') or [it['full'], it['deadline']]
        return read_back(it, amount, day)
    if kind == 'proposes':
        it.pop('agreed', None)
        pending = it.get('pending') or [it['full'], it['deadline']]
        amount = pending[0] if amount is None else amount
        day = day or pending[1]
        if not ok_day(it, day):
            it['pending'] = [amount, it['deadline']]
            return ('The latest business day I can record for your ' + it['word'] + ' is ' + say(iso_day(it['deadline']))
                    + '. Could you pay ' + money(amount) + ' on that day?')
        if amount < it['floor'] - 0.001 or amount > it['full'] + 0.001:
            it['pending'] = [it['floor'], day]
            return ('The amount must be from ' + money(it['floor']) + ' to ' + money(it['full']) + '. Could you pay '
                    + money(it['floor']) + ' for your ' + it['word'] + ' on ' + say(iso_day(day)) + '?')
        return read_back(it, amount, day)
    if kind == 'confirms':
        it['status'] = 'agreed'
        return ''
    if kind == 'wants_person':
        vars['negotiation_action'] = 'transfer'
        vars['guide'] = 'Call transfer_to_agent now.'
    return ''
def first_ask(it):
    return 'Could you settle ' + money(it['full']) + ' for your ' + it['word'] + ' by ' + say(iso_day(it['deadline'])) + '?'
def finish(items):
    agreed = [x for x in items if x['status'] == 'agreed']
    if agreed:
        return [dict(%(idf)s=x['id'], %(amf)s=x['agreed'][0], %(daf)s=x['agreed'][1]) for x in agreed]
    return 'close_said_no'
''' % {"idf": P["id_field"], "amf": P["amount_field"], "daf": P["date_field"]}

# After the promise writes: a code node picks the close from the statuses.
AFTER_WRITES = '''
import json
ws = json.loads(vars.get('promise_writes_list') or '[]')
vars['close_key'] = 'close_agreed' if any(w['status'] == 'ok' for w in ws) else 'close_system_down'
'''

# ---------------------------------------------------------------- tool result lines (post-hooks)

I = SPEC["identity"]
QUESTIONS = I["questions"]
# Runs after the engine-run check; r(field) is the bank's result field (spike S10). Sets the model's next step.
ID_GUIDE = r'''
ASKS = %(asks)r
order = [q for q, ask in ASKS]
q = str(vars.get('id_question') or '')
nxt = order[order.index(q) + 1] if q in order and order.index(q) + 1 < len(order) else ''
if r(%(passed)r) == 'true':
    vars['id_guide'] = 'Both answers are correct. Say thank you.'
elif r('ok') == 'false':
    vars['id_guide'] = 'The answer could not be read. It is not a wrong answer. Ask the same question again.'
elif r(%(correct)r) == 'true' and nxt:
    vars['id_guide'] = 'Correct. Now ask: ' + dict(ASKS)[nxt]
else:
    vars['id_guide'] = 'Say that the answer does not match. Ask the same question again. Give no hint.'
''' % {"asks": [[q["value"], q["ask"]] for q in QUESTIONS], "passed": I["passed_field"], "correct": I["correct_field"]}

PLAIN_POST = "d['what_to_do_next'] = 'Done. Tell the customer in one sentence.' if str(d.get('ok')).lower() == 'true' else 'It did not work. Say so in one sentence.'"

# ---------------------------------------------------------------- prompts

SYSTEM = ("You are the automated assistant of the caller company, on an outbound phone call. Speak English. "
          "Keep every turn to one or two short sentences. No lists, no brackets.\n"
          "You call " + CUSTOMER + ". The current date and time is {{" + V["now"] + "}}. Never use another clock.\n"
          "If asked whether you are a robot, say you are the company's automated assistant and continue.\n"
          "Never invent figures, dates or reasons. When a rule says to call a tool, call it. One tool per message. "
          "After every tool result, speak or call the next tool. A tool result can hold what_to_do_next: follow it.")

OPENING_TASK = ("You asked whether you speak with " + CUSTOMER + ". Do not say why you are calling. "
                "If the person did not clearly confirm, answer a question they asked in one sentence, then ask again: "
                "\"Is this " + CUSTOMER + "?\". Do not call a tool in this turn.")

THIRD_PARTY_TASK = ("The person is not " + CUSTOMER + ". Never say why you are calling. Ask when " + CUSTOMER
                    + " can be reached.\n{{callback_facts}}\nWhen the person names a day and a time, call schedule_callback "
                    "with the day as YYYY-MM-DD and the time as HH:MM. If it fails, the time is outside the window: say so "
                    "and ask once for another time. If there is still no time in the window, call transition_to_close_no_time.")

IDENTITY_TASK = ("NEXT STEP (obey it): {{id_guide}}\n\n"
                 "The person confirmed they are " + CUSTOMER + ". Check identity before anything else, one question at a "
                 "time, in this order: " + " ".join(f"({i + 1}) {q['value']}: \"{q['ask']}\"" for i, q in enumerate(QUESTIONS))
                 + ". Every time the customer says anything that is part of an answer, call answer_given with the parts said "
                 "in this message, also when it looks wrong, and also when the same message holds a complaint or a question. "
                 "Never guess a missing part. Never tell the right answer.\n"
                 "If the customer refuses to answer, call customer_refuses, then explain once that the questions protect "
                 "their account and ask again.")

NEGOTIATE_TASK = ("NEXT STEP: {{guide}}\n\n"
                  "Identity is verified. You stated the bill. Every time the customer answers about paying, call "
                  "customer_said with the item and the kind. If one message answers for several items, call customer_said "
                  "once per item. Then say the words in NEXT STEP after SAY, word for word, and nothing else about amounts "
                  "or days. Never say that something is recorded: the call says it at the end.\n\n"
                  "ACCOUNT\n{{account_facts}}\n\nDATES\n{{date_facts}}")

# ---------------------------------------------------------------- tools

answer = answer_tool({q["value"]: q["kind"] for q in QUESTIONS})
# The engine sends a complete answer (spike S10); the model never calls the identity tool.
verify = make_tool(API, I["tool"], baked={**BAKED_ID, I["question_field"]: "{{id_question}}", I["answer_field"]: "{{id_answer}}"})
refuses = state_tool("customer_refuses", "CALL it every time the customer refuses to answer a security question.", {},
                     "vars['id_refusals'] = int(float(vars.get('id_refusals') or 0)) + 1")
callback = make_tool(API, "schedule_callback", baked=BAKED_ID, post_code=PLAIN_POST,
                     description="Book a callback. CALL it when the person names a day and a time.")
callback["pre_process_code"] = guard_hook(
    "not (str(body.get('day')) in str(vars.get('callback_days')).split(',') and %r <= str(body.get('at'))[:5] <= %r)"
    % (SPEC["callback"]["from"], SPEC["callback"]["to"]))
said = negotiation_tool("negotiate", {
    "accepts": "yes to your last proposal.",
    "confirms": "a clear yes to the read-back, with no change, no correction word such as sorry or I mean, and not cut off mid-sentence.",
    "refuses": "no, with no day and no amount.",
    "proposes": "names a day or an amount.",
    "wants_person": "asks for a person.",
    "other": "anything else."}, with_dates(POLICY), "promise_writes_list")
transfer = make_tool(API, "transfer_to_agent", baked={**BAKED_ID, "team": "desk"}, post_code=PLAIN_POST,
                     description="Hand the call to a person. CALL it when NEXT STEP says so.")

# ---------------------------------------------------------------- nodes

closes = []
for key, (result, code, goodbye) in SPEC["closes"].items():
    closes += close_sequence(key, {"close_result": result, "close_code": code}, goodbye)

party = field("party", "string", "Who answered, from the latest message. customer: clearly confirms with yes or their own "
              "name. someone_else: another person, or the customer is not there. unclear: anything else, also hello or a "
              "question.", enum=["customer", "someone_else", "unclear"])
nodes = [
    start("setup"),
    code_node("setup", with_dates(SETUP) + "\nvars['id_guide'] = 'Wait for the answer to the first question.'", "opening",
              fallbacks={"date_facts": "Date facts are not available.", "callback_facts": "", "callback_days": "",
                         "id_guide": "Wait for the answer to the first question."}),
    conversation("opening", OPENING_TASK, on_enter=tts(SPEC["opening_line"]), first_entry_only=True, extract=[party],
                 max_turns=6, max_turn_target="close_unsure", transitions=[
                     go("identity", any_of(cond("party", "equals", "customer")), "the customer confirmed"),
                     go("third_party", any_of(cond("party", "equals", "someone_else")), "someone else answered"),
                     go("close_unsure", all_of(cond("party", "equals", "unclear"), cond("opening.total_turns", "greater_than", 1)),
                        "still unclear after the second ask"),
                     always("opening")]),
    conversation("third_party", THIRD_PARTY_TASK, tools=[callback], max_turns=10, max_turn_target="close_no_time", transitions=[
        go("close_call_later", is_true("schedule_callback_response.data.ok"), "callback booked"),
        {**intent("close_no_time", "no callback time inside the window"), "is_tool_call": True}]),
    # The first entry speaks a fixed line; every return from the check speaks the next step (on_enter llm).
    *[conversation(node, IDENTITY_TASK, tools=[answer, refuses], first_entry_only=(node == "identity"),
                   on_enter=tts("Thank you. First I need to ask two security questions. " + QUESTIONS[0]["ask"])
                   if node == "identity" else {"type": "llm"},
                   max_turns=16, max_turn_target="close_refused_check", transitions=[
                       go("id_check", any_of(cond("id_send", "equals", "yes")), "a complete answer"),
                       go("close_refused_check", any_of(cond("id_refusals", "greater_than", I["refusals_allowed"])), "refused")])
      for node in ("identity", "identity_next")],
    *identity_check("id_check", verify, "identity_next", [
        go("fetch_account", is_true("id_check_check_response.data." + I["passed_field"]), "identity passed"),
        go("close_wrong", any_of(cond("id_check_check_response.data." + I["left_field"], "equals", "0")), "check failed")],
        ID_GUIDE),
    api_node("fetch_account", make_tool(API, "get_account", baked=BAKED_ID), "prepare",
             mapping=[("data." + A["list_field"], A["list_field"])]),
    code_node("prepare", with_dates(PREPARE), "negotiate", fallbacks={"item_count": "0", "account_facts": "No data.",
              "debt_statement": "Thank you.", "guide": "Say you cannot see the account now."},
              transitions=[go("close_system_down", any_of(cond("item_count", "equals", "0")), "no account data")]),
    conversation("negotiate", NEGOTIATE_TASK, tools=[said, transfer], on_enter=tts("{{debt_statement}}"),
                 first_entry_only=True, max_turns=30, max_turn_target="end_router", transitions=[
                     go("promise_writes", any_of(cond("record_now", "equals", "yes")), "every item is agreed or stopped"),
                     go("close_handed_over", is_true("transfer_to_agent_response.data.ok"), "transferred"),
                     go("close_said_no", any_of(cond("close_key", "equals", "close_said_no")), "attempts used up"),
                     # the model's own goodbye does not end a call: only an end_call node does
                     intent("end_router", "The customer says goodbye or wants to end the call")]),
    # The engine writes each agreed promise (spike S10). 1 attempt: the example brief closes on a failure; a brief that
    # allows a retry gets attempts=2.
    *write_loop("promise_writes", API, P["tool"], [P["id_field"], P["amount_field"], P["date_field"]], BAKED_ID, 1,
                "after_writes"),
    code_node("after_writes", AFTER_WRITES, "end_router", fallbacks={"close_key": "close_system_down"}),
    code_node("end_router", "pass", "close_said_no",
              transitions=[go(k, any_of(cond("close_key", "equals", k)), k) for k in SPEC["closes"] if k != "close_said_no"]),
] + closes

close = close_tool(API, "close_call", {**BAKED_ID, "result": "{{close_result}}", "code": "{{close_code}}"})
test_vars = {k: v for k, v in SPEC["sample_vars"].items() if k in (V["id"], V["title"], V["last_name"], V["now"])}
WORKFLOW = workflow("start", SYSTEM, nodes, tools=[close], test_variables=test_vars)

if __name__ == "__main__":
    json.dump(WORKFLOW, open("workflow.json", "w"), indent=1)
    print("wrote workflow.json:", len(WORKFLOW["nodes"]), "nodes")
