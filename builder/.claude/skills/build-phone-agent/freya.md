# Freya platform knowledge for the builder

Read this once, in full, before you write `build_agent.py`. It holds what is true for every brief: how the platform behaves, what our library does, and the shape that works. It holds no rule of any brief. The values in the examples are invented.

The worked example is in `example/` next to this file: an invented brief, its tool API, `ledger.md`, `spec.json`, `build_agent.py` and `test_rules.py`. It passes every check. Copy `build_agent.py` and `test_rules.py` into the run folder and change them to fit your ledger. Do not copy the example's values or rules.

## 1. The library (`builder/blocks/`)

Import it in `build_agent.py`. `PYTHONPATH` already points at the repository.

| Module | Use |
|---|---|
| `tools.load_api(path)` | Reads the tool API file. Returns operation name → `url`, `method`, `fields` (name → schema), `required`, `response`. |
| `tools.make_tool(api, name, baked=..., post_code=..., description=...)` | An `api_call` tool. `baked` maps a body field to a fixed value or a `"{{variable}}"` the workflow sets. Every other field is filled by the model (its type, description and enum come from the API file). `post_code` runs in the post-hook with `d` = the API's JSON body; set `d['what_to_do_next']`. |
| `tools.field_values(api, name, field)` | The enum of a field, or `[]`. |
| `nodes.conversation / code_node / api_node / end_node / workflow` | Valid nodes. `code_node` wraps the code in `try`, writes the `fallbacks` and `<node>_code_error` on an exception, and refuses `{{` or `}}`. `workflow` refuses an unknown target or a duplicate name. |
| `nodes.cond / any_of / all_of / is_true / go / always / intent / field / tts` | Conditions, transitions, extraction fields, fixed lines. `is_true` tests `"true"` and `"True"`. |
| `patterns.start(next)` | The empty initial code node. Always use it (fact 3.6). |
| `patterns.close_tool(api, name, baked)` | The closing tool as an end-of-call tool. Put it in `workflow(..., tools=[...])`. Empty fields are not sent. |
| `patterns.close_sequence(name, values, goodbye)` | A code node that sets the closing variables, then an `end_call` node that says the goodbye. |
| `patterns.state_tool(name, description, params, body)` | A `code_exec` tool the model calls. The body reads the model's arguments from `params` and writes `vars`. |
| `patterns.record_with_retry(name, tool, attempts, ok_target, fail_target)` | An engine-run write: a reset code node and one `api_request` node per attempt. Bake every body field of `tool` from variables the code set. Route to `name` when the code says so. Use it for every write whose values the code decided (a promise). |
| `patterns.answer_tool(questions)` | The state tool for identity answers. The model reports the parts said in each message (day, month, year, digits, text); the code joins parts over turns and sets `id_send = "yes"`, `id_question`, `id_answer` when an answer is complete. It writes `id_guide` every turn. |
| `patterns.identity_check(name, verify_tool, back_node, routes, guide_code)` | The engine-run identity check: reset node, `api_request` node `<name>_check`, and a code node that runs `guide_code` with `r(field)` = the bank's result field, then the `routes` (passed, failed), else back to `back_node`. |
| `patterns.guard_hook(condition)` | A `pre_process_code` that makes the call fail when the condition is true, so the bank records nothing. The condition can read `vars` and `body` (the request body). |
| `coderun.with_dates(body)` | Puts the date helpers in front of a snippet: `is_business_day(d, holidays)`, `nth_business_day_after(d, n, holidays)` (counts from the day after `d`), `next_business_day_on_or_after`, `last_business_day_of_week` (Monday–Sunday week of `d`), `this_weekday(d, wd)`, `next_weekday(d, wd)` (0 = Monday). Also `date` and `timedelta`. |
| `coderun.node_code / tool_code / run_snippet / run_tool` | For `test_rules.py`: get a node's or a tool's code from the workflow and run it locally with `vars` (and `params`). |

Commands (run them from the run folder):

```
$BUILDER_PYTHON build_agent.py                                   # writes workflow.json
$BUILDER_PYTHON -m builder.blocks.check <run_dir>                # loop-1 checks, incl. the platform dry run
$BUILDER_PYTHON -m builder.blocks.deploy <run_dir> <slot>        # gate, save, publish; writes deployed.json
$BUILDER_PYTHON -m builder.blocks.smoke <workflow_id> script.json  # scripted chat turns
```

## 2. How a turn works

After each customer message the platform makes three separate model calls: extraction (fills `extraction_schema` variables), routing (reads only the transitions and the last messages), dialogue (reads `system_prompt` + `task_message` + history + the node's tools). So:

- A routing rule in `task_message` does nothing. Routing reads only `transitions`.
- The dialogue model can call only the tools of the current node.
- Variable conditions run in code, before any intent check. Put them first.
- The prompt is rendered again after every tool result, with the new variable values (spike S9).

## 3. Facts the blocks do not enforce

1. **Booleans arrive as strings**, `"true"` or `"True"`. Use `is_true`. Prefer string flags such as `yes` / `no` that your code writes.
2. **Every tool result is in the variable table without a mapping**: `<tool>_response.data.<field>`, plus `<tool>_success_count` and `<tool>_failure_count`. A list in the response is flattened (`<tool>_response.data.<list>.0.<field>`), so map it with `api_node(..., mapping=[("data.<list>", "<var>")])` and read it defensively (list, JSON string or flattened keys; the example's `load_list` does this).
3. **`<node>.total_turns`** counts the customer's messages in that node over the whole call; `<node>.current_turns` since the last entry. Use them to count "asked twice".
4. **A `{{var}}` default that has a value when the node is entered is baked** and the model never sees the field. So a model-filled field must have a default that names a variable that is never set; `make_tool` uses `{{<tool>__<field>}}`.
5. **Unresolved placeholders**: in a prompt or a fixed line, `{{x}}` stays literal and is spoken. Every variable a prompt or a fixed line uses must be set by an earlier code node, also in the `except` branch (use `fallbacks`).
6. **Chat skips the code of the initial node** (spike S6). Start every workflow with `patterns.start("setup")`.
7. **A `code_exec` tool returns only "success" to the model** (spike S8). Its effect comes from the variables it writes: show them in `task_message` (`NEXT STEP: {{guide}}`) or route on them.
8. **The model's arguments to a `code_exec` tool are in `params`** while the code runs (spike S2). `vars['<tool>_args.<param>']` exists only after the call.
9. **A failed call gives the model nothing to act on.** A bank error (HTTP 500) arrives as `function_call_error`: the post-hook does not run, there is no `what_to_do_next`, and in our test the model did not retry. So a write that may need a retry is engine-run (`record_with_retry`), never a model tool. An `api_request` node leaves `<node>_response.status` (`success` / `error`), `<node>_response.data.<field>`, `<node>_status_code` and `<node>_failure_count`, named after the node, not the tool (spike S10).
10. **A pre-hook can make a call fail** (spike S1): `guard_hook`. The post-hook does not run then, so the model gets only an error; the prompt must say what a failure means. `<tool>_failure_count` goes up.
11. **The goodbye comes from the `end_call` node** (`spoken_message`). A line in an `api_request` node is spoken after its call (spike S4). So the closing tool runs at the end of the call (`close_tool`), and the goodbye is said before it.
12. **Only an `end_call` node ends a call.** When the model says goodbye in a conversation node, the call goes on: in our test the customer and the agent then said goodbye to each other until the turn cap. Every conversation node needs a route for "the customer says goodbye or wants to end the call" to a router code node that picks the close from the state (`close_key`), and its `max_turn_transition` goes to the same router.
13. **End-of-call tools** run once, after the call ended, also when the customer hung up. Their `{{var}}` fields take the values the closing code node set.
14. **`is_tool_call: true`** on a transition offers the model a tool named `transition_to_<target>`. Use it when the model must decide to leave, and name that tool in `task_message`.
15. **`matches_intent`** judges only the last customer message. To leave a node after an action, route on the tool result, not on the customer's earlier intent.
16. **Extraction**: set `min_confidence` (the default 0.95 drops most values; `field` uses 0.6). Type dates as `date`. Fork on an extracted enum with `equals`, not on competing intents.
17. **`on_enter_first_entry_only`**: set it on nodes that can be re-entered and must not repeat their fixed line.
18. **`max_node_turns`** needs `max_turn_transition`, or the cap does nothing.
19. **Global nodes** fire from any node after its own transitions found nothing. List end nodes and nodes where an interrupt does harm (identity) in `excluded_nodes`. A rule that holds everywhere (a robot question, a scam question) is often simpler as a sentence in `system_prompt`.
20. **Code**: no `{{` or `}}` anywhere in code (a nested dict literal ends in `}}`: use `dict(...)`). Read values from `vars`, never splice them in. Modules `json`, `re`, `datetime` work.
21. **Writes are not retried** (`maxRetries: 0`). A retry rule from the brief is a prompt or route rule, counted with `<tool>_failure_count`.
22. **The judge reads the exact words.** A word the brief forbids must not be in any fixed line, not even in a negation. Put brief wording that must be said word for word into a fixed line (`tts`, `spoken_message`) or into a `guide` text the code writes.
23. **Brief values in `spec.json` reach code through `%r`** in the generator, as in the example. A dict repr has single braces, which is fine; a nested dict can end in `}}` and `code_node` refuses it.

## 4. The blueprint

Adapt it to the ledger. Add or remove steps. Every step below exists in the example except where it says "not in the example".

1. **`start`** — empty initial code node (fact 6).
2. **`setup`** — code node. From `now` and the brief's calendar: today, business days, every deadline the brief defines, every date an offer uses, the callback window, a calendar of the next five weeks with business days marked, and a "this / next weekday" table. Write `date_facts`, `callback_facts` and one variable per date.
3. **`opening`** — conversation node with the brief's first sentence as a fixed line. Extract who answered as an enum. Route on the enum. Count re-asks with `opening.total_turns`.
4. **`third_party`** — callback, and the other cases the brief names for a person who is not the customer. Guard the callback tool so that a time outside the window is not recorded. Say nothing about the reason of the call.
5. **`identity`** — the identity loop, engine-run (spike S11). Two conversation nodes with the same task and tools: `identity` (first entry, fixed line with the first question) and `identity_next` (`on_enter` llm: it speaks `{{id_guide}}` after each check). Their tool is `answer_tool`; a route on `id_send = "yes"` goes to `identity_check`, which sends the joined answer with the question and answer fields baked. `guide_code` turns the bank's result into the next step (next question, ask again, a hint the API returns such as a swapped day and month). Routes on the bank's own result fields (passed, wrong answers left) go on or close. Count refusals with a state tool. The model never calls the identity tool, so it cannot send half an answer or skip one.
6. **`fetch_account`** — `api_node`, reached only by the verified route. Then **`prepare`**: a code node that computes per product the facts the rules use (band, deadline, floor, attempts, offers) and the opening statement of the debt, and stores the negotiation state as JSON in a variable.
7. **`negotiate`** — conversation node. `task_message` starts with `NEXT STEP (obey it): {{guide}}`. A state tool (`customer_said`) takes what the customer said as an enum plus a date and an amount. Its code applies the brief's attempt, date and amount rules and writes the next step into `guide` and the end into `close_key`. The model proposes only what `guide` says.
8. **Confirm and record** — the code writes the read-back sentence and keeps the values. When the customer says yes to the read-back, the model calls the state tool with `confirms`; the code sets the agreed variables and `record_now = "yes"`; a route goes to `record_with_retry`, which writes with those baked values. The number of attempts comes from the brief (one try plus the retries it allows). Its `ok_target` is the close that says the promise is recorded; its `fail_target` is the close for a failed write. The model never says "recorded": the close line does, after the bank said `ok`.
9. **Close** — one `close_sequence` per row of the brief's outcome table, and `close_tool` with the outcome and reason fields baked from the closing variables.
10. **More than one product** (not in the example): keep a list of products in the state JSON with a `cur` index and per-product attempts. The state tool moves `cur` on when a product is finished. One read-back for all promises if the brief asks for it. Then record in a loop of engine-run nodes: a code node `next_write` picks the next agreed product that is not written yet and sets the baked variables (or routes on when none is left) → `record_with_retry(..., ok_target="mark_written", fail_target="mark_failed")` → a code node that marks the product in the state and goes back to `next_write`. Notes per product the same way: engine-run `api_node`s whose fields the code set, in a loop, never a model tool. When the loop is done, a code node computes the closing outcome from the state and routes to its close.
11. **Branches that end the call from anywhere in the negotiation** (a transfer, a claim that was paid, a dispute, hardship — whatever the brief names): an enum value of `customer_said`, and the code sets `close_key` or tells the model to call the transfer tool. The closing outcome comes from the code, never from the model.

## 5. Lessons from our measurements

1. **Identity fails most often under real speech.** In round 1 the model sent each half of an answer given in two parts ("14 March", then "1988") and invented a year (`1900-03-14`): the bank counted both halves as wrong answers. `answer_tool` + `identity_check` fix it: the code joins the parts and sends only complete answers, also when they look wrong. Convert dates in words to the format the API wants. After small talk or a question back, ask the same question again; do not restart the check.
2. **Count attempts in code, and count every time an offer is said.** A prompt that says "one more offer" is forgotten under pressure. The state tool counts, and the model sees only the next step. The judge counts an offer every time the agent says it: when the customer asks back, hesitates or is vague, the next step must not repeat an amount or a day already offered. It asks for a yes or a no, or moves to the next allowed offer. Test this in `test_rules.py`.
2b. **An answer with a complaint is still an answer.** "21 July 1990. This is ridiculous, how much do I owe?" holds an identity answer: send it to the tool first. In our test the model called it a refusal, the bank counted one wrong answer too few, and an unverified customer got through.
3. **No forbidden word in a fixed line.** The judge reads exact words. If the brief forbids a word until a condition, keep it out of every fixed line spoken before that condition. The words that name a tool result ("recorded", "booked", "confirmed") are a trap: a check such as "the agent does not say recorded before the promise tool succeeded" also catches "this call is recorded". When the brief wants such a fact said early, say it with another form of the word ("we record this call") and keep the exact word for after the tool result.
4. **A confirmation is a clear yes and nothing else.** "I can pay that on Thursday, sorry" was taken as a yes in round 1 while the customer was correcting the day. A yes with a change, a correction word ("sorry", "I mean", "actually") or a sentence cut off in the middle is not a confirmation: the state tool gets `proposes` or `other`, and the next step asks again. Simulated customers sometimes send half a sentence; treat it as not finished.
4b. **Read back numbers after a correction.** When the customer changes an amount or a day at the read-back, the code checks the new value and writes a new read-back.
5. **Tool honesty.** Never say something is recorded before the tool said `ok`. The post-hook line says what happened.
6. **Speak after every tool result.** A bare result makes the model go silent and the customer hangs up. `what_to_do_next` fixes it.
7. **Code beats prompts** for anything counted, calculated or ordered. Prompts hold only what needs language.
