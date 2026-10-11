"""Worked example: the generator for the invented Lumen Energy brief.

Run it in the run folder (cwd): it reads spec.json and tool_api.json and writes workflow.json.
Copy it, then change it to fit your ledger. Every value comes from spec.json; the code is the shape.
"""
import json

from builder.blocks.coderun import with_dates
from builder.blocks.nodes import (all_of, always, any_of, cond, conversation, field, go, intent, is_true, tts,
                                  workflow, api_node, code_node)
from builder.blocks.patterns import (answer_tool, close_sequence, close_tool, identity_check, negotiation_nodes,
                                     negotiation_tool, record_with_retry, start, state_tool, write_loop)
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
    # no floor and no deadline here: given them, the model made its own offers (round 3); only the policy offers
    facts.append('Item ' + str(p.get(%(id)r)) + ': ' + word + ', overdue ' + money(full) + ', ' + str(days_late) + ' days.')
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
def finish(items, confirmed):   # each item had its own read-back, so no final one
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
          "If the customer's message stops in the middle of a sentence and holds no full answer to your question, say only: "
          "\"Sorry, please go on.\" Do not repeat your question or your offer: the customer has not answered yet. "
          "A full answer before the cut ('21 July 1990. This is getting') is an answer: use it as usual.\n"
          "Never invent figures, dates or reasons. When a rule says to call a tool, call it. One tool per message. "
          "After every tool result, speak or call the next tool. A tool result can hold what_to_do_next: follow it.")

OPENING_TASK = ("You asked whether you speak with " + CUSTOMER + ". Do not say why you are calling. "
                "If the person did not clearly confirm, answer a question they asked in one sentence, then ask again: "
                "\"Is this " + CUSTOMER + "?\". Do not call a tool in this turn.")

THIRD_PARTY_TASK = ("NEXT STEP: {{tp_guide}}\n\n"
                    "The person is not " + CUSTOMER + ". Never say why you are calling, and give no hint of it. If the person asks what it "
                    "is about, offers to pay or offers to take a message, say only that you can speak about it with "
                    + CUSTOMER + " only. Do not say what you can or cannot accept.\n{{callback_facts}}\nEvery time the person "
                    "names a day or a time, also a vague one ('Saturday morning', 'after eight'), call time_named FIRST with the "
                    "day as YYYY-MM-DD and the time as HH:MM, each empty when not named; the code checks the window and counts. "
                    "Then follow NEXT STEP. If the person gives no time at all after NEXT STEP asked again, call "
                    "transition_to_close_no_time.")

IDENTITY_TASK = ("NEXT STEP (obey it): {{id_guide}}\n\n"
                 "NEXT STEP is about the answer checked last. A new answer is not checked yet: call answer_given with it first, also right after you said that an answer does not match, and also after messages that were cut off.\n"
                 "The person confirmed they are " + CUSTOMER + ". Check identity before anything else, one question at a "
                 "time, in this order: " + " ".join(f"({i + 1}) {q['value']}: \"{q['ask']}\"" for i, q in enumerate(QUESTIONS))
                 + ". Every time the customer says anything that is part of an answer, call answer_given with the parts said "
                 "in this message, also when it looks wrong, and also when the same message holds a complaint or a question. "
                 "Never guess a missing part. Never tell the right answer.\n"
                 "If the customer refuses to answer, call customer_refuses, then explain once that the questions protect "
                 "their account. When the customer asks something back, answer in one sentence and stop: do not repeat "
                 "the question, the customer answers next. Ask it again only after a message with no answer and no question.")

NEGOTIATE_TASK = ("NEXT STEP: {{guide}}\n\n"
                  "Identity is verified. You stated the bill. Every time the customer answers about paying, call "
                  "customer_said FIRST, before you say anything, with the item and the kind. A message that stops in the "
                  "middle of a sentence is kind unfinished. If one message answers for several items, call customer_said "
                  "once, with one entry per item in answers. The call then speaks the next line itself. "
                  "If NEXT STEP has no line, follow it. Never name an amount or a day yourself: the code chose them. "
                  "Never say that something is recorded: the call says it at the end.\n\n"
                  "ACCOUNT\n{{account_facts}}\n\nDATES\n{{date_facts}}")

# ---------------------------------------------------------------- tools

answer = answer_tool({q["value"]: q["kind"] for q in QUESTIONS})
# The engine sends a complete answer (spike S10); the model never calls the identity tool.
verify = make_tool(API, I["tool"], baked={**BAKED_ID, I["question_field"]: "{{id_question}}", I["answer_field"]: "{{id_answer}}"})
refuses = state_tool("customer_refuses", "CALL it every time the customer refuses to answer a security question.", {},
                     "vars['id_refusals'] = int(float(vars.get('id_refusals') or 0)) + 1")
# The code checks the window and counts the asks (edge case: the model judged the window itself and asked twice).
TIME_NAMED = """
day = str(params.get('day') or '').strip()[:10]
at = str(params.get('at') or '').strip()[:5]
if (day and day not in str(vars.get('callback_days')).split(',')) or (at and not (%r <= at <= %r)):
    n = int(float(vars.get('cb_outside') or 0)) + 1
    vars['cb_outside'] = n
    vars['tp_guide'] = 'That time is outside the window. Say so in one sentence, and ask for a day and time inside it.'
    if n > %d:
        vars['cb_close'] = 'yes'
elif day and at:
    vars['cb_day'], vars['cb_at'], vars['cb_book'] = day, at, 'yes'
    vars['tp_guide'] = 'Say only: one moment, please.'
else:
    vars['tp_guide'] = 'Ask only for the ' + ('time' if day else 'day') + ' of the callback.'
""" % (SPEC["callback"]["from"], SPEC["callback"]["to"], SPEC["callback"]["asks_after_outside"])
time_named = state_tool("time_named", "CALL it every time the person names a day or a time for a callback.", {
    "day": {"type": "string", "description": "The day named, YYYY-MM-DD, or empty."},
    "at": {"type": "string", "description": "The time named, HH:MM in 24 hours, or empty."}}, TIME_NAMED)
book = make_tool(API, "schedule_callback", baked={**BAKED_ID, "day": "{{cb_day}}", "at": "{{cb_at}}"})
said = negotiation_tool({
    "accepts": "yes to your last proposal.",
    "confirms": "a clear yes to the read-back, with no change, no correction word such as sorry or I mean, and not cut off mid-sentence.",
    "refuses": "no, with no day and no amount; also a goodbye or a wish to end the call.",
    "proposes": "names a day or an amount, also inside a question ('What is the minimum for Friday?').",
    "wants_person": "asks for a person.",
    "other": "anything else, with no day and no amount."}, with_dates(POLICY), "promise_writes_list")
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
    code_node("setup", with_dates(SETUP) + "\nvars['id_guide'] = 'Wait for the answer to the first question.'\nvars['tp_guide'] = 'Ask when the customer can be reached.'", "opening",
              fallbacks={"date_facts": "Date facts are not available.", "callback_facts": "", "callback_days": "", "tp_guide": "Ask when the customer can be reached.",
                         "id_guide": "Wait for the answer to the first question."}),
    conversation("opening", OPENING_TASK, on_enter=tts(SPEC["opening_line"]), first_entry_only=True, extract=[party],
                 max_turns=20, max_turn_target="close_unsure", transitions=[
                     go("identity", any_of(cond("party", "equals", "customer")), "the customer confirmed"),
                     go("third_party", any_of(cond("party", "equals", "someone_else")), "someone else answered"),
                     go("close_unsure", all_of(cond("party", "equals", "unclear"), cond("opening.total_turns", "greater_than", 1)),
                        "still unclear after the second ask"),
                     always("opening")]),
    conversation("third_party", THIRD_PARTY_TASK, tools=[time_named], max_turns=20, max_turn_target="close_no_time", transitions=[
        go("book_callback", any_of(cond("cb_book", "equals", "yes")), "a time inside the window"),
        go("close_no_time", any_of(cond("cb_close", "equals", "yes")), "outside the window after the one more ask"),
        {**intent("close_no_time", "no callback time inside the window"), "is_tool_call": True}]),
    *record_with_retry("book_callback", book, 1, "close_call_later", "close_no_time"),
    # The first entry speaks a fixed line; every return from the check speaks the next step (on_enter llm).
    *[conversation(node, IDENTITY_TASK, tools=[answer, refuses], first_entry_only=(node == "identity"),
                   on_enter=tts("Thank you. First I need to ask two security questions. " + QUESTIONS[0]["ask"])
                   if node == "identity" else {"type": "llm"},
                   max_turns=30, max_turn_target="close_refused_check", transitions=[
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
    # The code speaks each line it chose (negotiate_next); the model speaks only to answer a question.
    *negotiation_nodes("negotiate", NEGOTIATE_TASK, [said, transfer], "{{debt_statement}}", [
        go("promise_writes", any_of(cond("record_now", "equals", "yes")), "every item is agreed or stopped"),
        go("close_handed_over", is_true("transfer_to_agent_response.data.ok"), "transferred"),
        go("close_said_no", any_of(cond("close_key", "equals", "close_said_no")), "attempts used up")], 30, "end_router"),
    # No intent route here (lint rule 12): a goodbye is the kind refuses, and the policy closes the call.
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
