"""Generator for Brief A+B (Freya Bank, one to three products). Reads spec.json and tool_api.json, writes workflow.json."""
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
L = SPEC["lines"]
CUSTOMER = "{{" + V["title"] + "}} {{" + V["last_name"] + "}}"
BAKED_ID = {V["id"]: "{{" + V["id"] + "}}"}

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
vars['now_hhmm'] = hhmm
for name, n in %r:
    vars['deadline_' + name] = nth_business_day_after(today, n, HOLIDAYS).isoformat()
w = last_business_day_of_week(today, HOLIDAYS)
if w == today:
    w = last_business_day_of_week(today + timedelta(days=7), HOLIDAYS)
vars['week_end'] = w.isoformat()
lines = ['Today is ' + say(today) + ' (' + today.isoformat() + '), time ' + hhmm + '.', 'Calendar:']
for i in range(36):
    d = today + timedelta(days=i)
    tag = 'business day' if is_business_day(d, HOLIDAYS) else 'NOT a business day'
    lines.append('- ' + d.isoformat() + ' ' + WD[d.weekday()] + ': ' + tag)
for i in range(7):
    lines.append('this ' + WD[i] + ' = ' + this_weekday(today, i).isoformat() + ', next ' + WD[i] + ' = ' + next_weekday(today, i).isoformat())
vars['date_facts'] = '\n'.join(lines)
bd1 = nth_business_day_after(today, 1, HOLIDAYS)
vars['callback_days'] = today.isoformat() + ',' + bd1.isoformat()
vars['callback_facts'] = ('A callback is allowed only today ' + say(today) + ' (' + today.isoformat() + ') after ' + hhmm
                          + ', or on ' + say(bd1) + ' (' + bd1.isoformat() + '), from %s to %s, both included.')
''' % ([[b["name"], b["deadline_business_days"]] for b in SPEC["bands"]], SPEC["callback"]["from"], SPEC["callback"]["to"])

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
FLOORS = %(floors)r
items, facts, said = [], [], []
for p in load_list():
    days_late = int(float(p.get(%(days)r)))
    band = [b for b in BANDS if days_late <= b[1]][0]
    kind = str(p.get(%(kind)r))
    full, floor = float(p.get(%(amount)r)), float(p.get(FLOORS.get(kind, '')) or 0)
    word = WORDS.get(kind, kind)
    if kind == 'credit_card':
        word = word + str(p.get(%(card)r) or '')
    deadline = vars.get('deadline_' + band[0])
    items.append(dict(id=str(p.get(%(id)r)), word=word, full=full, floor=floor, deadline=deadline, attempts=band[2],
                      used=0, status='open', refused=[]))
    facts.append('Product ' + str(p.get(%(id)r)) + ': ' + word + ', past due ' + money(full) + ', ' + str(days_late)
                 + ' days late.')
    said.append('your ' + word + ' has ' + money(full) + ' past due and is ' + str(days_late) + ' days late.')
items[0]['asked'] = 'yes'
vars['neg_state'] = json.dumps(dict(items=items))
vars['item_count'] = str(len(items))
vars['account_facts'] = '\n'.join(facts)
ask = %(ask1)r if len(items) == 1 else %(askn)r
vars['debt_statement'] = ('Thank you. I am calling from the collections team about a late payment. '
                          + ' '.join(s[0].upper() + s[1:] for s in said) + ' ' + ask)
vars['guide'] = 'Wait for the answer. Say nothing new.'
''' % {"list": A["list_field"], "bands": [[b["name"], b["max_days"], b["attempts"]] for b in SPEC["bands"]],
       "words": A["kind_words"], "floors": A["floor_fields"], "days": A["days_field"], "amount": A["amount_field"],
       "kind": A["kind_field"], "id": A["id_field"], "card": A["card_field"],
       "ask1": L["first_ask_one"], "askn": L["first_ask_many"]}

P = SPEC["promise"]
POLICY = HELPERS + r'''
LINES = %(lines)r
def offer(it, amount, day):
    it['pending'] = [round(float(amount), 2), day]
    return 'Could you pay ' + money(amount) + ' for your ' + it['word'] + ' on ' + say(iso_day(day)) + '?'
def agree(it, amount, day):
    it['agreed'] = [round(float(amount), 2), day]
    it['status'] = 'agreed'
    return ''
def attempt(it):
    # a flat refusal: uses one attempt; never repeats a refused offer
    if it.get('pending'):
        it['refused'].append(it['pending'])
    it.pop('pending', None)
    while it['used'] < it['attempts']:
        it['used'] = it['used'] + 1
        if it['used'] == 1:
            o = [it['floor'] if it.get('too_much') else it['full'], vars.get('week_end')]
        else:
            o = [it['floor'], it['deadline']]
        if o not in it['refused']:
            return offer(it, o[0], o[1])
    it['status'] = 'refused'
    return ''
def decide(it, kind, amount, day):
    if kind == 'confirms' and it.get('agreed'):
        return ''
    if it.get('hardship_offer') and kind in ('accepts', 'confirms'):
        vars['negotiation_action'] = 'transfer'
        vars['transfer_queue'] = 'support'
        vars['guide'] = 'Say: I will connect you now.'
        return ''
    if it.get('hardship_offer') and kind == 'refuses':
        it['status'] = 'hardship'
        return ''
    if kind == 'hardship':
        it['hardship_offer'] = 'yes'
        it.pop('pending', None)
        return LINES['sympathy']
    if kind == 'wants_plan':
        vars['negotiation_action'] = 'transfer'
        vars['transfer_queue'] = 'restructuring'
        vars['guide'] = 'Say: I will connect you now.'
        return ''
    if kind == 'wants_person':
        n = int(float(vars.get('person_asks') or 0)) + 1
        vars['person_asks'] = str(n)
        if n >= 2:
            vars['negotiation_action'] = 'transfer'
            vars['transfer_queue'] = 'general'
            vars['guide'] = 'Say: I will connect you now.'
            return ''
        return LINES['person_first']
    if kind == 'paid':
        it['status'] = 'paid'
        vars['carry'] = LINES['paid'] + ' '
        return ''
    if kind == 'dispute':
        it['status'] = 'dispute'
        vars['carry'] = 'I understand. '
        return ''
    if kind == 'no_talk':
        n = int(float(vars.get('no_talk') or 0)) + 1
        vars['no_talk'] = str(n)
        if n >= 2:
            it['status'] = 'refused'
            return ''
        return 'I understand. ' + (it.get('pending') and offer(it, it['pending'][0], it['pending'][1]) or 'Can you make this payment today?')
    if kind == 'too_much':
        if it.get('too_much'):
            return attempt(it)
        it['too_much'] = 'yes'
        day = (it.get('pending') or [0, vars.get('today_iso')])[1]
        return 'The rest stays overdue. ' + offer(it, it['floor'], day)
    if kind == 'vague':
        if it.get('vague'):
            return offer(it, (it.get('pending') or [it['full']])[0], it['deadline'])
        it['vague'] = 'yes'
        return 'Which exact day can you pay?'
    if kind in ('accepts', 'confirms'):
        a, d = it.get('pending') or [it['full'], vars.get('today_iso')]
        return agree(it, a, d)
    if kind == 'proposes':
        pending = it.get('pending') or [it['full'], vars.get('today_iso')]
        a = pending[0] if amount is None else amount
        d = day or pending[1]
        if it['status'] == 'agreed':
            it['status'] = 'open'
        try:
            dd = iso_day(d)
        except Exception:
            return 'Which exact day can you pay?'
        if d > it['deadline']:
            if int(vars.get('item_count') or 1) > 1 and day:
                it['late_note'] = 'yes'
                return agree(it, a, it['deadline']) if it['floor'] - 0.001 <= a <= it['full'] + 0.001 else offer(it, it['floor'], it['deadline'])
            return 'The latest date I can record is ' + say(iso_day(it['deadline'])) + '. ' + offer(it, a, it['deadline'])
        if d < vars.get('today_iso'):
            dd = iso_day(vars.get('today_iso'))
        if not is_business_day(dd, HOLIDAYS):
            nd = next_business_day_on_or_after(dd, HOLIDAYS).isoformat()
            if nd > it['deadline']:
                return 'The latest date I can record is ' + say(iso_day(it['deadline'])) + '. ' + offer(it, a, it['deadline'])
            return 'That day is not a business day. ' + offer(it, a, nd)
        d = dd.isoformat()
        if a < it['floor'] - 0.001:
            if it.get('floor_offered'):
                return attempt(it)
            it['floor_offered'] = 'yes'
            return 'That amount cannot be recorded. ' + offer(it, it['floor'], d)
        if a > it['full'] + 0.001:
            a = it['full']
        return agree(it, a, d)
    if kind == 'refuses':
        return attempt(it)
    return ''
def first_ask(it):
    c = vars.get('carry') or ''
    vars['carry'] = ''
    return c + attempt(it) if it['used'] == 0 else c + 'Can you make this payment today?'
def finish(items, confirmed):
    agreed = [x for x in items if x['status'] == 'agreed']
    if agreed and not confirmed:
        c = vars.get('carry') or ''
        vars['carry'] = ''
        parts = []
        for x in agreed:
            s = money(x['agreed'][0]) + ' for your ' + x['word'] + ' on ' + say(iso_day(x['agreed'][1]))
            if x.get('late_note'):
                s = s + ', the latest date I can record for it'
            parts.append(s)
        return dict(say=c + 'To read it back: ' + '; '.join(parts) + '. ' + LINES['confirm_q'])
    if agreed:
        return [dict(%(idf)s=x['id'], %(amf)s=x['agreed'][0], %(daf)s=x['agreed'][1]) for x in agreed]
    return 'go_notes'
''' % {"lines": L, "idf": P["id_field"], "amf": P["amount_field"], "daf": P["date_field"]}

N = SPEC["note"]
AFTER_PROMISES = r'''
import json
items = json.loads(vars.get('neg_state'))['items']
ws = json.loads(vars.get('promise_writes_list') or '[]')
status = dict()
for w in ws:
    status[str(w['fields'].get(%(pid)r))] = w['status']
notes = []
for x in items:
    s = x.get('status')
    if s == 'agreed' and status.get(x['id']) == 'ok':
        continue
    reason = s if s in ('refused', 'hardship', 'dispute', 'paid') else ('service_error' if s == 'agreed' else 'refused')
    notes.append(dict(fields=dict(%(nid)s=x['id'], %(nreason)s=reason), status='pending'))
vars['note_writes_list'] = json.dumps(notes)
vars['promise_ok'] = 'yes' if any(w['status'] == 'ok' for w in ws) else 'no'
''' % {"pid": P["id_field"], "nid": N["id_field"], "nreason": N["reason_field"]}

FINAL_CLOSE = r'''
import json
notes = json.loads(vars.get('note_writes_list') or '[]')
reasons = [n['fields'][%r] for n in notes]
if vars.get('promise_ok') == 'yes':
    vars['close_key'] = 'close_promise'
elif reasons and all(r == 'paid' for r in reasons):
    vars['close_key'] = 'close_paid'
else:
    first = [r for r in reasons if r != 'paid']
    vars['close_key'] = 'close_' + (first[0] if first else 'refused')
''' % (N["reason_field"],)

I = SPEC["identity"]
QUESTIONS = I["questions"]
ID_GUIDE = r'''
ASKS = %(asks)r
order = [q for q, ask in ASKS]
q = str(vars.get('id_question') or '')
nxt = order[order.index(q) + 1] if q in order and order.index(q) + 1 < len(order) else ''
if r(%(passed)r) == 'true':
    vars['id_guide'] = 'Both answers are correct. Say thank you.'
elif r(%(hint)r) == %(swapped)r:
    vars['id_guide'] = 'Ask the customer to say the date of birth again with the month as a word.'
elif r('ok') == 'false':
    vars['id_guide'] = 'The answer could not be read. It is not a wrong answer. Ask the same question again.'
elif r(%(correct)r) == 'true' and nxt:
    vars['id_guide'] = 'Correct. Now ask: ' + dict(ASKS)[nxt]
else:
    vars['id_guide'] = 'Say that the answer does not match. Ask the same question again. Give no hint.'
''' % {"asks": [[q["value"], q["ask"]] for q in QUESTIONS], "passed": I["passed_field"], "correct": I["correct_field"],
       "hint": I["hint_field"], "swapped": I["swapped_hint"]}

PLAIN_POST = "d['what_to_do_next'] = 'Done. Tell the person in one sentence.' if str(d.get('ok')).lower() == 'true' else 'It did not work: the time is outside the window. Say so and ask once for another time.'"

SYSTEM = ("You are the digital assistant of Freya Bank, on an outbound phone call. Speak English. "
          "Keep every turn to one or two short sentences. No lists, no brackets.\n"
          "You call " + CUSTOMER + ". The current date and time is {{" + V["now"] + "}}. Never use another clock.\n"
          "If asked whether you are a robot or an AI, say you are Freya Bank's digital assistant and continue.\n"
          "If asked whether this is a scam, say they can verify this call by phoning Freya Bank's customer service number, and continue.\n"
          "If you cannot answer a question from the tools, say you do not have that information. "
          "Never invent figures, dates or reasons. Never offer a discount, a waiver or a plan. "
          "After every tool result, speak or call the next tool. A tool result can hold what_to_do_next: follow it.")

OPENING_TASK = ("You asked whether you speak with " + CUSTOMER + ". Do not say why you are calling. "
                "If the person did not clearly confirm, answer a question they asked in one sentence, then ask again: "
                "\"Am I speaking with " + CUSTOMER + "?\". Do not call a tool in this turn.")

THIRD_PARTY_TASK = ("The person is not " + CUSTOMER + ". Never say why you are calling and tell nothing about the account, "
                    "even if they offer to pay. Do not ask security questions. Ask when " + CUSTOMER
                    + " can be reached.\n{{callback_facts}}\nWhen the person names a day and a time, call schedule_callback "
                    "with the day as YYYY-MM-DD and the time as HH:MM. If it fails, the time is outside the window: say so "
                    "and ask once for another time. If there is still no time in the window, call transition_to_close_no_callback.")

IDENTITY_TASK = ("NEXT STEP (obey it): {{id_guide}}\n\n"
                 "The person confirmed they are " + CUSTOMER + ". Check identity before anything else, one question at a "
                 "time, in this order: " + " ".join(f"({i + 1}) {q['value']}: \"{q['ask']}\"" for i, q in enumerate(QUESTIONS))
                 + ". Every time the customer says anything that is part of an answer, call answer_given with the parts said "
                 "in this message, also when it looks wrong, and also when the same message holds a complaint or a question. "
                 "A date said only in numbers is day, then month, then year. Never guess a missing part. Never tell the right answer.\n"
                 "If the customer refuses to answer, asks what the call is about instead of answering, or says they do not "
                 "want to talk, call customer_refuses, then explain once that the questions protect their account and ask again. "
                 "Do not say why you are calling.")

NEGOTIATE_TASK = ("NEXT STEP: {{guide}}\n\n"
                  "Identity is verified. You stated the late products. Every time the customer answers about paying, call "
                  "customer_said with the product id and the kind. If one message answers for several products, call "
                  "customer_said once, with one entry per product in answers. A day or an amount the customer names is always proposes, never refuses. "
                  "Then say the words in NEXT STEP after SAY, word for word, and nothing else about amounts or days. "
                  "Never say that something is recorded: the call says it at the end. Never ask how much they can pay.\n\n"
                  "ACCOUNT\n{{account_facts}}\n\nDATES\n{{date_facts}}")

answer = answer_tool({q["value"]: q["kind"] for q in QUESTIONS})
verify = make_tool(API, I["tool"], baked={**BAKED_ID, I["question_field"]: "{{id_question}}", I["answer_field"]: "{{id_answer}}"})
refuses = state_tool("customer_refuses", "CALL it every time the customer refuses a security question or asks what the call is about.", {},
                     "vars['id_refusals'] = int(float(vars.get('id_refusals') or 0)) + 1")
callback = make_tool(API, "schedule_callback", baked=BAKED_ID, post_code=PLAIN_POST,
                     description="Book a callback. CALL it when the person names a day and a time.")
CB = SPEC["callback"]
callback["pre_process_code"] = guard_hook(
    "not (str(body.get('date')) in str(vars.get('callback_days')).split(',') and %r <= str(body.get('time'))[:5] <= %r "
    "and (str(body.get('date')) != str(vars.get('today_iso')) or str(body.get('time'))[:5] > str(vars.get('now_hhmm'))))"
    % (CB["from"], CB["to"]))
said = negotiation_tool("negotiate", {
    "accepts": "yes to your last proposal.",
    "confirms": "a clear yes to the read-back, with no change, no correction word such as sorry or I mean, and not cut off mid-sentence.",
    "refuses": "no, with no day and no amount, or no answer.",
    "too_much": "says the amount is too much.",
    "proposes": "names a day or an amount.",
    "vague": "names a vague period such as next week or when my salary comes.",
    "hardship": "mentions illness, a death in the family or job loss.",
    "wants_plan": "asks for a new payment plan or lower instalments.",
    "wants_person": "asks for a human.",
    "paid": "says they already paid this past-due amount.",
    "dispute": "says the debt or product is not theirs, or was closed or paid off in the past.",
    "no_talk": "says they do not want to talk.",
    "other": "anything else."}, with_dates(POLICY), "promise_writes_list")

T = SPEC["transfer"]
transfer = make_tool(API, T["tool"], baked={**BAKED_ID, T["queue_field"]: "{{transfer_queue}}"})

closes = []
for key, (outcome, reason, goodbye) in SPEC["closes"].items():
    closes += close_sequence(key, {"close_outcome": outcome, "close_reason": reason}, goodbye)

party = field("party", "string", "Who answered, from the latest message. customer: clearly confirms with yes, that's me, "
              "speaking or their own name. someone_else: another person, or the customer is not there. wrong_number: says "
              "the number does not belong to the customer. deceased: says the customer has died. unclear: anything else, "
              "also hello, go ahead, who is this, or a question.",
              enum=["customer", "someone_else", "wrong_number", "deceased", "unclear"])
tp_case = field("tp_case", "string", "wrong_number: the number does not belong to the customer. deceased: the customer "
                "has died. other: anything else.", enum=["wrong_number", "deceased", "other"])
nodes = [
    start("setup"),
    code_node("setup", with_dates(SETUP) + "\nvars['id_guide'] = 'Wait for the answer to the first question.'", "opening",
              fallbacks={"date_facts": "Date facts are not available.", "callback_facts": "", "callback_days": "",
                         "id_guide": "Wait for the answer to the first question."}),
    conversation("opening", OPENING_TASK, on_enter=tts(SPEC["opening_line"]), first_entry_only=True, extract=[party],
                 max_turns=6, max_turn_target="close_unclear", transitions=[
                     go("identity", any_of(cond("party", "equals", "customer")), "the customer confirmed"),
                     go("close_wrong_number", any_of(cond("party", "equals", "wrong_number")), "wrong number"),
                     go("close_deceased", any_of(cond("party", "equals", "deceased")), "deceased"),
                     go("third_party", any_of(cond("party", "equals", "someone_else")), "someone else answered"),
                     go("close_unclear", all_of(cond("party", "equals", "unclear"), cond("opening.total_turns", "greater_than", 1)),
                        "still unclear after the second ask"),
                     always("opening")]),
    conversation("third_party", THIRD_PARTY_TASK, tools=[callback], extract=[tp_case], max_turns=10,
                 max_turn_target="close_no_callback", transitions=[
                     go("close_callback", is_true("schedule_callback_response.data.ok"), "callback booked"),
                     go("close_wrong_number", any_of(cond("tp_case", "equals", "wrong_number")), "wrong number"),
                     go("close_deceased", any_of(cond("tp_case", "equals", "deceased")), "deceased"),
                     {**intent("close_no_callback", "no callback time inside the window"), "is_tool_call": True}]),
    *[conversation(node, IDENTITY_TASK, tools=[answer, refuses], first_entry_only=(node == "identity"),
                   on_enter=tts("Thank you. First I need to ask two security questions. " + QUESTIONS[0]["ask"])
                   if node == "identity" else {"type": "llm"},
                   max_turns=16, max_turn_target="close_declined", transitions=[
                       go("id_check", any_of(cond("id_send", "equals", "yes")), "a complete answer"),
                       go("close_declined", any_of(cond("id_refusals", "greater_than", I["refusals_allowed"])), "refused")])
      for node in ("identity", "identity_next")],
    *identity_check("id_check", verify, "identity_next", [
        go("fetch_account", is_true("id_check_check_response.data." + I["passed_field"]), "identity passed"),
        go("close_failed", any_of(cond("id_check_check_response.data." + I["left_field"], "equals", "0")), "check failed")],
        ID_GUIDE),
    api_node("fetch_account", make_tool(API, "get_account", baked=BAKED_ID), "prepare",
             mapping=[("data." + A["list_field"], A["list_field"])]),
    code_node("prepare", with_dates(PREPARE), "negotiate", fallbacks={"item_count": "0", "account_facts": "No data.",
              "debt_statement": "Thank you.", "guide": "Say you cannot see the account now."},
              transitions=[go("close_service_error", any_of(cond("item_count", "equals", "0")), "no account data")]),
    conversation("negotiate", NEGOTIATE_TASK, tools=[said], on_enter=tts("{{debt_statement}}"),
                 first_entry_only=True, max_turns=30, max_turn_target="after_promises", transitions=[
                     go("promise_writes", any_of(cond("record_now", "equals", "yes")), "every product is agreed or finished"),
                     go("transfer", any_of(cond("negotiation_action", "equals", "transfer")), "transfer"),
                     go("after_promises", any_of(cond("close_key", "equals", "go_notes")), "no promise"),
                     intent("after_promises", "The customer says goodbye or wants to end the call")]),
    api_node("transfer", transfer, "transfer_route"),
    code_node("transfer_route", "q = str(vars.get('transfer_queue') or '')\n"
              "vars['close_key'] = 'close_human' if q == 'general' else 'close_' + q", "end_router",
              fallbacks={"close_key": "close_human"}),
    *write_loop("promise_writes", API, P["tool"], [P["id_field"], P["amount_field"], P["date_field"]], BAKED_ID,
                P["attempts"], "after_promises"),
    code_node("after_promises", AFTER_PROMISES, "note_writes", fallbacks={"note_writes_list": "[]", "promise_ok": "no"}),
    *write_loop("note_writes", API, N["tool"], [N["id_field"], N["reason_field"]], BAKED_ID, N["attempts"], "final_close"),
    code_node("final_close", FINAL_CLOSE, "end_router", fallbacks={"close_key": "close_refused"}),
    code_node("end_router", "pass", "close_refused",
              transitions=[go(k, any_of(cond("close_key", "equals", k)), k) for k in SPEC["closes"] if k != "close_refused"]),
] + closes

close = close_tool(API, "close_call", {**BAKED_ID, "outcome": "{{close_outcome}}", "reason": "{{close_reason}}"})
test_vars = {k: v for k, v in SPEC["sample_vars"].items() if k in (V["id"], V["title"], V["last_name"], V["now"])}
WORKFLOW = workflow("start", SYSTEM, nodes, tools=[close], test_variables=test_vars)

if __name__ == "__main__":
    json.dump(WORKFLOW, open("workflow.json", "w"), indent=1)
    print("wrote workflow.json:", len(WORKFLOW["nodes"]), "nodes")
