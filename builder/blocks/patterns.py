"""Sub-graphs and tool shapes that the platform spikes proved (notes/platform-spikes.md)."""
from builder.blocks.nodes import any_of, api_node, code_node, cond, conversation, end_node, go, is_true, tts
from builder.blocks.tools import make_tool

BLOCKED_URL = "https://blocked.invalid/refused-by-guard"


def start(next_node):
    """An empty initial code node. Chat skips the initial node's code (spike S6), so real setup comes after it."""
    return code_node("start", "pass", next_node)


def close_tool(api, name, baked):
    """The closing tool as an end-of-call lifecycle tool (spike S4: a line in an api_request node is spoken after its
    call). `baked` maps each body field to a "{{variable}}" that a closing code node sets. Empty fields are not sent."""
    tool = make_tool(api, name, baked=baked)
    tool["config"]["alwaysRunsAt"] = ["end_of_call"]
    tool["pre_process_code"] = (
        "try:\n    b = config.get('body')\n    if isinstance(b, dict):\n        for k in list(b.keys()):\n"
        "            v = b.get(k)\n            if v is None or str(v).strip() in ('', 'none', 'None') or '{' in str(v):\n"
        "                b.pop(k, None)\nexcept Exception:\n    pass\n")
    return tool


def close_sequence(name, values, goodbye):
    """A code node that sets the closing variables, then an end_call node that says `goodbye`.
    The call's endedReason is `name`."""
    body = "\n".join("vars[%r] = %r" % (k, v) for k, v in values.items())
    return [code_node(name, body, name + "_end"), end_node(name + "_end", name, goodbye)]


def state_tool(name, description, params, body):
    """A code_exec tool the model calls. The model's arguments are in the global dict `params` (spike S2).
    The model sees only "success" (spike S8): the effect must come from the variables `body` writes."""
    code = "try:\n" + "\n".join("    " + line for line in body.splitlines()) + "\n    pass\n"
    code += "except Exception as exc:\n    vars[%r] = repr(exc)[:300]\n" % (name + "_code_error")
    if "{{" in code or "}}" in code:
        raise ValueError(f"state tool {name}: code must not contain template braces")
    return {"type": "function", "function": {
        "name": name, "handler": "__function__:code_exec", "description": description,
        "parameters": {"type": "object", "properties": {**params, "code": {"type": "string", "default": code}},
                       "required": list(params)}}}


def guard_hook(condition_code):
    """A pre_process_code that sends the call to an unreachable URL when `condition_code` is true, so the bank records
    nothing (spike S1). The condition can read `vars` and `config['body']`. The model sees a failed call."""
    return ("try:\n    body = config.get('body') if isinstance(config.get('body'), dict) else dict()\n"
            "    if " + condition_code + ":\n        config['url'] = %r\nexcept Exception:\n    pass\n" % BLOCKED_URL)


def record_with_retry(name, tool, attempts, ok_target, fail_target):
    """An engine-run write (spike S10): the model never calls the tool, so it cannot skip a retry or send other values.
    `tool` comes from make_tool with every body field baked from variables the code set (the agreed values).
    Returns [reset code node `name`, api nodes `name_1` .. `name_<attempts>`]. Route to `name`. A success goes to
    `ok_target`; when every attempt failed, the call goes to `fail_target`.

    An api_request node leaves `<node>_response.data.ok` and `<node>_failure_count`. The reset node sets each
    `<node>_response.data.ok` to "pending" first, so a value left from an earlier product does not count."""
    steps = [f"{name}_{i}" for i in range(1, attempts + 1)]
    reset = code_node(name, "\n".join(f"vars[{s + '_response.data.ok'!r}] = 'pending'" for s in steps), steps[0])
    nodes = [reset]
    for i, step in enumerate(steps):
        nxt = steps[i + 1] if i + 1 < len(steps) else fail_target
        nodes.append(api_node(step, tool, nxt, transitions=[go(ok_target, is_true(step + "_response.data.ok"), "recorded")]))
    return nodes


ANSWER_CODE = r'''
import json
MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
KINDS = %r
q = str(params.get('question') or '')
kind = KINDS.get(q, ['text', 0])
parts = json.loads(vars.get('id_parts') or '[]')
parts = dict(parts) if isinstance(parts, list) else parts
mine = parts.get(q) or dict()
def num(x):
    s = ''.join(ch for ch in str(x or '') if ch.isdigit())
    return int(s) if s else None
for key in ('day', 'month', 'year'):
    v = str(params.get(key) or '').strip()
    if v:
        m = [i + 1 for i, name in enumerate(MONTHS) if v.lower().startswith(name[:3])] if key == 'month' else []
        mine[key] = m[0] if m else num(v)
new_digits = ''.join(ch for ch in str(params.get('digits') or '') if ch.isdigit())
if new_digits:
    have = mine.get('digits') or ''
    mine['digits'] = new_digits if (len(new_digits) >= kind[1] or not have) else have + new_digits
if str(params.get('text') or '').strip():
    mine['text'] = str(params.get('text')).strip()
answer, missing = '', ''
if kind[0] == 'date':
    missing = ', '.join(k for k in ('day', 'month', 'year') if not mine.get(k))
    if not missing and mine.get('year', 0) >= 1000:
        answer = '%%04d-%%02d-%%02d' %% (mine['year'], mine['month'], mine['day'])
    elif not missing:
        missing = 'the year with four digits'
elif kind[0] == 'digits':
    have = mine.get('digits') or ''
    if len(have) >= kind[1]:
        answer = have
    else:
        missing = 'the rest of the digits (' + str(kind[1] - len(have)) + ' more)'
else:
    answer = mine.get('text') or ''
    missing = '' if answer else 'the answer'
if answer:
    parts[q] = dict()
    vars['id_question'] = q
    vars['id_answer'] = answer
    vars['id_send'] = 'yes'
    vars['id_guide'] = 'Say only: one moment, please.'
else:
    parts[q] = mine
    vars['id_guide'] = ('The answer is not complete yet. Ask only for the missing part: ' + missing
                        + '. Do not repeat the question in full, and do not say the parts back.')
vars['id_parts'] = json.dumps(parts)
vars['id_refusals'] = 0     # refusals count in a row: an answer ends the row
'''


def answer_tool(questions):
    """The model reports the parts of an identity answer; the code joins them over several turns and says when an
    answer is complete. `questions` maps each question value (as the tool API names it) to ["date", 0],
    ["digits", <count>] or ["text", 0]. A part given after a partial answer is joined to it. On a complete answer it sets id_question, id_answer and id_send = "yes".
    Every turn it writes id_guide, the next step for the model, and sets id_refusals to 0: a customer who asks back
    and then answers has not refused twice."""
    names = list(questions)
    return state_tool("answer_given", "CALL it every time the customer says anything that is part of a security answer.", {
        "question": {"type": "string", "enum": names, "description": "Which question this is for. One of: " + ", ".join(names) + "."},
        "day": {"type": "string", "description": "Day of the month the customer said in this message, as digits, or empty."},
        "month": {"type": "string", "description": "Month the customer said in this message, as a word or digits, or empty."},
        "year": {"type": "string", "description": "Year the customer said in this message, four digits, or empty. Never guess it."},
        "digits": {"type": "string", "description": "Digits the customer said in this message, digits only, or empty."},
        "text": {"type": "string", "description": "Any other kind of answer, as said, or empty."}},
        ANSWER_CODE % (questions,))


def identity_check(name, verify_tool, back_node, routes, guide_code):
    """The engine-run identity check. Route to `name` when id_send is "yes". `verify_tool` comes from make_tool with the
    question field baked as "{{id_question}}" and the answer field as "{{id_answer}}". After the call, `guide_code` runs
    with `r(field)` = the result field as a string and must set vars['id_guide'] (the next step for the model).
    `routes` are transitions on `<name>_check_response.data.<field>` (passed, failed); otherwise the call goes back to
    `back_node`, whose task shows {{id_guide}}."""
    prefix = name + "_check_response."
    after = ("def r(f):\n    return str(vars.get(%r + f))\n" % (prefix + "data.")
             + "if str(vars.get(%r)) != 'success':\n" % (prefix + "status")
             + "    vars['id_guide'] = 'The check is not available. Ask the same question again.'\n"
             + "else:\n" + "\n".join("    " + line for line in guide_code.splitlines()) + "\n")
    return [code_node(name, "vars['id_send'] = 'no'", name + "_check"),
            api_node(name + "_check", verify_tool, name + "_after"),
            code_node(name + "_after", after, back_node, transitions=routes,
                      fallbacks={"id_guide": "Ask the same question again."})]


def write_loop(name, api, tool_name, fields, baked, attempts, done_target):
    """Engine-run writes for a list of items, one call per item (for example one promise or one note per product).
    The code fills vars['<name>_list'] with a JSON list of {"fields": {field: value}, "status": "pending"} and routes
    to `name`. Each pending item is written with `attempts` tries; its status becomes "ok" or "failed". When no item is
    pending, the call goes to `done_target`, whose code reads the statuses."""
    tool = make_tool(api, tool_name, baked={**baked, **{f: "{{" + name + "_" + f + "}}" for f in fields}})
    pick = ("import json\nws = json.loads(vars.get(%r) or '[]')\ntodo = [i for i, w in enumerate(ws) if w.get('status') == 'pending']\n"
            "vars[%r] = 'yes' if todo else 'no'\nif todo:\n    vars[%r] = todo[0]\n"
            "    for f, v in ws[todo[0]].get('fields', dict()).items():\n        vars[%r + f] = v\n"
            % (name + "_list", name + "_more", name + "_index", name + "_"))
    def mark(status):
        return ("import json\nws = json.loads(vars.get(%r) or '[]')\ni = vars.get(%r)\nif i is not None and int(i) < len(ws):\n"
                "    ws[int(i)]['status'] = %r\n    vars[%r] = json.dumps(ws)\n" % (name + "_list", name + "_index", status, name + "_list"))
    return [code_node(name, pick, name + "_rec", transitions=[go(done_target, any_of(cond(name + "_more", "equals", "no")), "all written")],
                      fallbacks={name + "_more": "no"}),
            *record_with_retry(name + "_rec", tool, attempts, name + "_ok", name + "_failed"),
            code_node(name + "_ok", mark("ok"), name), code_node(name + "_failed", mark("failed"), name)]


NEGOTIATION_ENGINE = r'''
import json
st = json.loads(vars.get('neg_state'))
items = st['items']
vars['say_turn'] = 'no'
reply = str(params.get('reply') or '').strip()
def speak_line(text):
    text = (reply + ' ' + text).strip()     # the model's answer to a question, then the code's line
    vars['guide'] = 'SAY: "' + text + '"'
    vars['say_now'], vars['say_turn'] = text, 'yes'     # the next node speaks it with fixed text
answers = params.get('answers') or []
answers = json.loads(answers) if isinstance(answers, str) else answers
answers = [answers] if isinstance(answers, dict) else answers
kinds = [str(a.get('kind') or '') for a in answers]
unfinished = bool(kinds) and all(k == 'unfinished' for k in kinds)
done = []
for a, kind in zip(answers, kinds):
    if kind == 'unfinished':
        continue
    want = str(a.get('item') or '')
    open_items = [x for x in items if x.get('status') == 'open']
    picked = [x for x in open_items if str(x.get('id')) == want]
    it = picked[0] if picked else (open_items or items)[0]
    if it['id'] in done:
        continue                            # one answer per product and message: the first is the main point
    done.append(it['id'])
    amount = a.get('amount')
    amount = float(amount) if str(amount or '').strip() not in ('', 'None') else None
    line = decide(it, kind, amount, str(a.get('date') or '')[:10])
    it['line'] = line or ''
    if vars.get('close_key') or vars.get('negotiation_action'):
        break
if unfinished:
    speak_line('Please go on.' if reply else 'Sorry, please go on.')     # a cut-off message changes nothing
elif vars.get('close_key') or vars.get('negotiation_action'):
    pass
else:
    open_items = [x for x in items if x.get('status') == 'open']
    todo = [x for x in open_items if x.get('line')]
    if todo:
        speak_line(todo[0]['line'])
        todo[0]['line'] = ''                # said now
    elif open_items:
        nx = open_items[0]
        if not nx.get('asked'):
            nx['asked'] = 'yes'
            speak_line(first_ask(nx))
        elif reply:
            speak_line('')
        else:
            vars['guide'] = ('No new line. If the customer asked something, answer in one sentence from ACCOUNT. '
                             'Name no amount and no day.')
    else:
        confirmed = 'confirms' in kinds and bool(st.get('final_shown'))
        end = finish(items, confirmed)
        if isinstance(end, dict) and end.get('say'):
            st['final_shown'] = 'yes'
            speak_line(end['say'])
        elif isinstance(end, list) and end:
            vars[%(list_var)r] = json.dumps([dict(fields=f, status='pending') for f in end])
            vars['record_now'] = 'yes'
            vars['guide'] = 'SAY: "One moment, please."'
        else:
            vars['close_key'] = str(end or '')
vars['neg_state'] = json.dumps(st)
'''


def negotiation_tool(kinds, policy, list_var):
    """The state tool of the negotiation node. The model reports what the customer said about one product; the brief's
    policy decides for that product; the engine plans the next line from the whole state.

    `kinds` maps each kind value to its description for the model. `policy` is code that defines, using any helpers:
      decide(it, kind, amount, day) -> the exact words to say next about product `it` ('' for none). It updates `it`:
          set it['status'] to something other than 'open' when the product is finished. To end the talk or act at once,
          set vars['close_key'] or vars['negotiation_action'] (and vars['guide']).
      first_ask(it) -> the words of the first question about a product nobody asked about yet.
      finish(items, confirmed) -> when no product is open: dict(say=<one read-back of all promises, ending in the
          brief's question>) to ask for one final confirmation; or a list of write-field dicts (one per promise, written
          by the write loop `list_var`); or the close key to route to. `confirmed` is True when the customer said
          `confirms` after the final read-back was shown. A change at the final read-back reaches `decide` for that
          product, which can set its status back to 'open'.
    The state is vars['neg_state'] = JSON {"items": [...]}; each item has "id" and "status" ("open" at the start) and the
    one asked about in the debt statement has "asked": "yes". One message can answer for several products: the model calls
    the tool once with one entry per product in `answers`; a second entry for the same product is ignored. Two calls in one message run at the same time and only the
    last write is kept (round 2, PUB-13), so the tool must never need two calls. A chosen line goes to vars['say_now'] with
    vars['say_turn'] = 'yes', and `negotiation_nodes` speaks it with fixed text, so it is said once and word for word (round 4:
    the model said its own offer instead of NEXT STEP). The guide holds only words in quotes. The engine adds the kind
    "unfinished" (a message cut off mid-sentence): it changes nothing and asks the customer to go on."""
    engine = NEGOTIATION_ENGINE % {"list_var": list_var}
    answer = {"type": "object", "required": ["item", "kind", "date", "amount"], "properties": {
        "item": {"type": "string", "description": "The product id this answer is about, or empty for the one you asked about."},
        "kind": {"type": "string", "enum": list(kinds) + ["unfinished"],
                 "description": "What the customer said. " + " ".join(f"{k}: {d}" for k, d in kinds.items())
                 + " unfinished: the message stops in the middle of a sentence; nothing is decided yet. A full question before "
                 "the cut-off still gets its answer in reply."},
        "date": {"type": "string", "description": "The day the customer named in full in this message, YYYY-MM-DD, "
                 "or empty. Never a day from an earlier message that was cut off, and never a day from a message that only "
                 "ends an earlier one ('of November.' after 'on the sixth'): that day was already answered."},
        "amount": {"type": "string", "description": "The amount the customer named in full in this message, digits only, "
                   "or empty. Never an amount from an earlier message that was cut off: '120' from 'I can pay the 120' "
                   "can be the start of 1250."}}}
    return state_tool("customer_said", "CALL it ONCE every time the customer answers about paying. Put one entry in "
                      "answers for each product the customer talked about in this message.", {
        "answers": {"type": "array", "items": answer, "description": "One entry per product the message is about, "
                    "never two for the same product: pick the kind of the main point. A message that only ends the sentence "
                    "of an earlier one adds no new answer: send the kind for anything else, with no day and no amount, "
                    "and answer any question in reply."},
        "reply": {"type": "string", "description": "If the customer asked a question in this message, your answer in one "
                  "sentence from ACCOUNT, with no amount and no day; else empty. Also when the kind is unfinished: 'Which loan is "
                  "this? I' needs the answer. The call says it before the next line."}},
        policy + "\n" + engine)


def negotiation_nodes(name, task, tools, statement, transitions, max_turns, max_turn_target):
    """The negotiation node `name` (first entry speaks `statement`) and its loop: after each call of the negotiation tool
    that chose a line, `name`_say marks it spoken and `name`_next speaks vars['say_now'] with fixed text, so the model
    cannot change an offer. With no line chosen, the model answers in its own words. `transitions` go first, on both nodes."""
    to_say = go(name + "_say", any_of(cond("say_turn", "equals", "yes")), "the code chose the next line")
    done = "vars['say_turn'] = 'no'\nvars['guide'] = 'The line was said. Wait for the answer.'"
    return [conversation(name, task, tools=tools, on_enter=tts(statement), first_entry_only=True, max_turns=max_turns,
                         max_turn_target=max_turn_target, transitions=[to_say, *transitions]),
            code_node(name + "_say", done, name + "_next"),
            conversation(name + "_next", task, tools=tools, on_enter=tts("{{say_now}}"), max_turns=max_turns,
                         max_turn_target=max_turn_target, transitions=[to_say, *transitions])]
