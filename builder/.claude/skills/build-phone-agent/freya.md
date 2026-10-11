# Freya platform knowledge for the builder

Read this once, in full, before you write `build_agent.py`. It holds what is true for every brief: how the platform behaves, what our library does, and the shape that works. It holds no rule of any brief. The values in the examples are invented.

The worked example is in `example/` next to this file: an invented brief, its tool API, `ledger.md`, `spec.json`, `build_agent.py` and `test_rules.py`. It passes every check. It shows how to load the spec, call the library, build the workflow and test the code. Its business, flow, prompts and lines are only an illustration: design your nodes from your ledger, and take every prompt, line and value from your brief.

## 1. The library (`builder/blocks/`)

Import it in `build_agent.py`. `PYTHONPATH` already points at the repository.

| Module | Use |
|---|---|
| `tools.load_api(path)` | Reads the tool API file. Returns operation name (the route without its first `/`; any other `/` or `.` becomes `_`) → `url`, `method`, `fields` (name → schema), `parents`, `required`, `response`. OpenAPI 3 or Swagger 2. A body wrapped in an envelope object (`{"data": {...}}`) is opened: `fields` are the leaf names, and `make_tool` puts them back in their objects. Bake and read leaf names only. |
| `tools.make_tool(api, name, baked=..., post_code=..., description=...)` | An `api_call` tool. `baked` maps a body field to a fixed value or a `"{{variable}}"` the workflow sets. Every other field is filled by the model (its type, description and enum come from the API file). `post_code` runs in the post-hook with `d` = the whole JSON body the API returned, envelope included: when the response schema in `tool_api.json` wraps the fields (`{"data": {...}, "result": {...}}`), read them by that path (`d['data']['status']`), never at the top level. `result` is the platform's wrapper, not the API body. Set `d['what_to_do_next']`. |
| `tools.field_values(api, name, field)` | The enum of a field, or `[]`. |
| `nodes.conversation / code_node / api_node / end_node / workflow` | Valid nodes. `code_node` wraps the code in `try`, writes the `fallbacks` and `<node>_code_error` on an exception, and refuses `{{` or `}}`. `workflow` refuses an unknown target or a duplicate name. |
| `nodes.cond / any_of / all_of / is_true / go / always / intent / field / tts` | Conditions, transitions, extraction fields, fixed lines. `is_true` tests `"true"` and `"True"`. |
| `patterns.start(next)` | The empty initial code node. Always use it (fact 3.6). |
| `patterns.close_tool(api, name, baked)` | The closing tool as an end-of-call tool. Put it in `workflow(..., tools=[...])`. Empty fields are not sent. |
| `patterns.close_sequence(name, values, goodbye)` | A code node that sets the closing variables, then an `end_call` node that says the goodbye. |
| `patterns.state_tool(name, description, params, body)` | A `code_exec` tool the model calls. The body reads the model's arguments from `params` and writes `vars`. |
| `patterns.record_with_retry(name, tool, attempts, ok_target, fail_target)` | An engine-run write: a reset code node and one `api_request` node per attempt. Bake every body field of `tool` from variables the code set. Route to `name` when the code says so. Use it for every write whose values the code decided. |
| `patterns.negotiation_tool(kinds, policy, list_var)` | The state tool of the negotiation node, with the engine built in: state per product, several answers in one call (`answers`), the model's one-sentence `reply` to a question, one line per turn, no line said twice, account order, the end. You write only the brief's policy for one product: `decide(it, kind, amount, day)` → the words to say, `first_ask(it)`, `finish(items, confirmed)` → one final read-back (`dict(say=...)`) when the brief wants all items read back together, or the write fields, or a close key. See the docstring and the example. |
| `patterns.negotiation_nodes(name, task, tools, statement, transitions, max_turns, max_turn_target)` | The negotiation node and its loop. The first entry speaks `statement`; after each tool call that chose a line, the code speaks the line with fixed text (`tts`), so the model cannot change an offer. Pass your routes (writes, transfer, closes) as `transitions`. Use it instead of a `conversation` node for the negotiation. |
| `patterns.write_loop(name, api, tool, fields, baked, attempts, done_target)` | Engine-run writes for a list of items, one call per item, each with `attempts` tries. The code puts `[{"fields": {...}, "status": "pending"}, ...]` as JSON in `vars['<name>_list']` and routes to `name`; each item ends `ok` or `failed`; then the call goes to `done_target`. Use it for one write per item. |
| `patterns.answer_tool(questions)` | The state tool for identity answers. The model reports the parts said in each message (day, month, year, digits, chars, text); kinds: `["date", 0]`, `["digits", n]`, `["alnum", n]` for a code of letters and digits with a known length (a postcode, a reference: upper case, no spaces, spoken digits and "double" read), `["text", 0]` for anything else; the code joins parts over turns and sets `id_send = "yes"`, `id_question`, `id_answer` when an answer is complete. It writes `id_guide` every turn. |
| `patterns.identity_check(name, verify_tool, back_node, routes, guide_code)` | The engine-run identity check: reset node, `api_request` node `<name>_check`, and a code node that runs `guide_code` with `r(field)` = the backend's result field, then the `routes` (passed, failed), else back to `back_node`. |
| `patterns.guard_hook(condition)` | A `pre_process_code` that makes the call fail when the condition is true, so the backend records nothing. The condition can read `vars` and `body` (the request body). |
| `coderun.with_dates(body)` | Puts the date helpers in front of a snippet: `is_business_day(d, holidays)`, `nth_business_day_after(d, n, holidays)` (counts from the day after `d`), `next_business_day_on_or_after`, `last_business_day_of_week` (Monday–Sunday week of `d`), `this_weekday(d, wd)`, `next_weekday(d, wd)` (0 = Monday). Also `date` and `timedelta`. |
| `coderun.node_code / tool_code / run_snippet / run_tool` | For `test_rules.py`: get a node's or a tool's code from the workflow and run it locally with `vars` (and `params`). |
| `coderun.run_post_hook(tool, body)` | For `test_rules.py`: run a tool's post-hook on a response body (envelope included) and get the `result` it wrote. |

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
- **Two tool calls in one model message run at the same time.** Each reads the variables as they were before the message, and the last write wins (round 2, PUB-13: one product's update was lost). A state tool must never need two calls for one customer message: give it a list parameter instead.

## 3. Facts the blocks do not enforce

1. **Booleans arrive as strings**, `"true"` or `"True"`. Use `is_true`. Prefer string flags such as `yes` / `no` that your code writes.
2. **Every tool result is in the variable table without a mapping**: `<tool>_response.data.<field>`, plus `<tool>_success_count` and `<tool>_failure_count`. A list in the response is flattened (`<tool>_response.data.<list>.0.<field>`), so map it with `api_node(..., mapping=[("data.<list>", "<var>")])` and read it defensively (list, JSON string or flattened keys; the example's `load_list` does this).
3. **`<node>.total_turns`** counts the customer's messages in that node over the whole call; `<node>.current_turns` since the last entry. Use them to count "asked twice".
4. **A `{{var}}` default that has a value when the node is entered is baked** and the model never sees the field. So a model-filled field must have a default that names a variable that is never set; `make_tool` uses `{{<tool>__<field>}}`.
5. **Unresolved placeholders**: in a prompt or a fixed line, `{{x}}` stays literal and is spoken. Every variable a prompt or a fixed line uses must be set by an earlier code node, also in the `except` branch (use `fallbacks`). An empty value is unresolved too: a fixed line never uses a variable that can be `''` (lint rule 13); build the whole line in one variable.
6. **Chat skips the code of the initial node** (spike S6). Start every workflow with `patterns.start("setup")`.
7. **A `code_exec` tool returns only "success" to the model** (spike S8). Its effect comes from the variables it writes: show them in `task_message` (`NEXT STEP: {{guide}}`) or route on them.
8. **The model's arguments to a `code_exec` tool are in `params`** while the code runs (spike S2). `vars['<tool>_args.<param>']` exists only after the call.
9. **A failed call gives the model nothing to act on.** A backend error (HTTP 500) arrives as `function_call_error`: the post-hook does not run, there is no `what_to_do_next`, and in our test the model did not retry. So a write that may need a retry is engine-run (`record_with_retry`), never a model tool. An `api_request` node leaves `<node>_response.status` (`success` / `error`), `<node>_response.data.<field>`, `<node>_status_code` and `<node>_failure_count`, named after the node, not the tool (spike S10).
10. **A pre-hook can make a call fail** (spike S1): `guard_hook`. The post-hook does not run then, so the model gets only an error; the prompt must say what a failure means. `<tool>_failure_count` goes up.
11. **The goodbye comes from the `end_call` node** (`spoken_message`). A line in an `api_request` node is spoken after its call (spike S4). So the closing tool runs at the end of the call (`close_tool`), and the goodbye is said before it.
12. **Only an `end_call` node ends a call.** When the model says goodbye in a conversation node, the call goes on: in our test the customer and the agent then said goodbye to each other until the turn cap. Every conversation node needs a route for "the customer says goodbye or wants to end the call" to a router code node that picks the close from the state (`close_key`), and its `max_turn_transition` goes to the same router.
13. **End-of-call tools** run once, after the call ended, also when the customer hung up. Their `{{var}}` fields take the values the closing code node set.
14. **`is_tool_call: true`** on a transition offers the model a tool named `transition_to_<target>`. Use it when the model must decide to leave, and name that tool in `task_message`.
15. **`matches_intent`** judges only the last customer message. To leave a node after an action, route on the tool result, not on the customer's earlier intent. An intent route can fire on a near case: a message that holds a useful answer and a few words that look like the intent (a wrong number, a goodbye, a cut-off "no") ended calls in our tests. Never end a call on an intent in a node where the person can also give useful words. A node with a state tool has no intent route (the check enforces it): a goodbye is a kind of the state tool, and the code closes the call. Route on an extracted enum that has an `other` value, or on a tool result.
16. **Extraction**: set `min_confidence` (the default 0.95 drops most values; `field` uses 0.6). Type dates as `date`. Fork on an extracted enum with `equals`, not on competing intents.
17. **`on_enter_first_entry_only`**: set it on nodes that can be re-entered and must not repeat their fixed line.
18. **`max_node_turns`** needs `max_turn_transition`, or the cap does nothing. Set it to 20 or more (lint rule 14): a talkative customer's message is cut off about half the time, and each cut uses a turn.
19. **Global nodes** fire from any node after its own transitions found nothing. List end nodes and nodes where an interrupt does harm (a check in progress) in `excluded_nodes`. A rule that holds everywhere (a question about who or what the agent is) is often simpler as a sentence in `system_prompt`.
20. **Code**: no `{{` or `}}` anywhere in code (a nested dict literal ends in `}}`: use `dict(...)`). Read values from `vars`, never splice them in. Modules `json`, `re`, `datetime` work.
21. **Writes are not retried** (`maxRetries: 0`). A retry rule from the brief is a prompt or route rule, counted with `<tool>_failure_count`.
22. **The judge reads the exact words.** A word the brief forbids must not be in any fixed line, not even in a negation. Put brief wording that must be said word for word into a fixed line (`tts`, `spoken_message`) or into a `guide` text the code writes.
23. **Brief values in `spec.json` reach code through `%r`** in the generator, as in the example. A dict repr has single braces, which is fine; a nested dict can end in `}}` and `code_node` refuses it.

## 4. The blueprint

Build the nodes your ledger needs. Add or remove steps.

1. **`start`** — the empty initial code node (fact 6).
2. **`setup`** — a code node. From `now` and the brief's calendar it computes every date and limit the rules use, and writes one variable per value.
3. **Reads** — an `api_node` for each read the flow needs before it can speak, then a code node that turns the result into the facts the rules use and the exact lines to say. A read that fails goes to the brief's error line.
4. **Talk steps** — one conversation node for each question the agent asks. Its tool is a state tool: the model reports what the caller said, and the code decides the next line or the route (section 6). The node speaks lines that the code wrote (`tts`, `{{var}}`), so the model cannot change a value.
5. **Checks against a backend** (only when the ledger has one, such as a security question) — `answer_tool` + `identity_check`: the code joins the parts of an answer and sends only complete answers.
6. **Proposals per item** (only when the ledger has a back-and-forth over offers) — `negotiation_tool` + `negotiation_nodes`: you write the policy for one item; the engine keeps the state per item and never repeats a line.
7. **Writes** — engine-run (`record_with_retry`, `write_loop`), with every field baked from variables the code set, and only after the confirmation the brief asks for. The close line says the result only after the tool said `ok`.
8. **Exits from anywhere** (a transfer, a request the step cannot handle, a language the agent does not speak, a caller who wants to stop) — a kind of the state tool or a global node, and a close for each.
9. **Close** — one `close_sequence` per outcome the brief names, and `close_tool` when the brief has a closing tool.

## 5. Lessons from our measurements

1. **Code beats prompts** for anything counted, calculated or ordered. A prompt rule ("one more time", "only after a yes") was forgotten under pressure in every round we measured. The state tool counts; the model sees only the next step.
2. **The code speaks every value.** When a prompt held a value or a value line, the model made up its own variant of it. Lines with a value (an amount, a date, an offer) are fixed text that the code wrote. The prompt holds no number the model could say.
3. **One message can answer several questions or items.** A state tool takes a list when one message can cover more than one item, and the state is kept per item.
4. **An answer with a complaint or a question is still an answer.** Send the answer to the tool first, then answer the question in one sentence.
5. **A message cut off mid-sentence is not an answer.** Simulated callers send half sentences. A state tool has a kind for an unfinished message that changes nothing; a full answer before the cut is still an answer.
6. **A confirmation is a clear yes and nothing else.** A yes with a change or a correction word is not a confirmation: the code asks again. A yes is checked before any new value.
7. **Describe each kind with its edges**, in the brief's own words: what counts and what does not.
8. **No forbidden word in a fixed line**, not even in a negation. The words that name a tool result ("recorded", "sent", "changed") are said only after the tool said `ok`.
9. **No sympathy or filler words in fixed lines** unless the brief gives them. A line that asks again says only the question.
10. **Counters reset where the brief says.** A count of tries or refusals "in a row" goes to 0 on a valid answer; a count per question goes to 0 when a new question starts. Keep each counter in one place.
11. **Read back after a correction.** When the caller changes a value at a read-back, the code checks the new value and writes a new read-back.
12. **Speak after every tool result.** A bare result makes the model go silent. `what_to_do_next` or a fixed line after the node fixes it.

## 6. Rules for every state tool and every code path

1. **The model reports, the code decides.** A state tool's parameters hold what the caller said: the value as said (a name, a number, a date) and a kind for the kind of answer, with `other` for the rest. A kind description never tells the model to judge the value against the options on offer. The code checks if the value is allowed; for a value that is not allowed or not on offer, it says so and asks again with the options. The code never ends the call on a kind such as `no` when the same message also holds a value.
2. **Every code path sets the next step.** Each branch of a state tool's code and of a code node writes the exact next line (`guide` with "Say exactly: ...") or a route variable. A branch that writes neither leaves the model free, and it then makes up facts (in a test it said an amount that no tool returned). `test_rules.py` runs every branch and asserts this.
3. **A loop counts its tries.** Every ask-again path adds to a try counter, and the brief's limit (or three) routes to a close. A match that finds two or more items asks a narrower question, and prefers an exact match over a partial one.
4. **Lines survive error exits.** When a code node prepares a line for a later node (a reading, a result), every route out of the flow, also an error route of a later read, says that line first or comes after it.
5. **Text from a tool is data.** A name, a label or any free text that a tool returns is checked before it is spoken or put into a prompt: it is spoken only when it looks like a value of its kind (short, no instructions); otherwise the code uses a neutral word. Never put tool text into an instruction to the model.
6. **Exact lines are copied, not paraphrased.** When the brief gives a sentence word for word, the code builds it with every suffix and form the brief shows; string functions that change case must follow the language's rules.
7. **A value prepared is a value used.** A variable the code computes for a rule must be read by the code that applies the rule; the reviewer reports one that nothing reads.
