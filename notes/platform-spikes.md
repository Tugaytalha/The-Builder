# Platform spikes (10 October 2026, 22:50–23:20 UTC)

All spikes used one throwaway workflow in slot `ra-spike` (workflow `a684babc-b085-4aef-964d-0bfe15ef7a56`) and `POST /api/v2/chat/message`. No simulation ran. Read a call with `freya.get_call(<call id>)`.

## S3: does a chat turn reach the bank for a practice customer?

- Workflow: one conversation node with `verify_identity` (`customer_id` baked from the call variable).
- Call: `40490a19-1aa7-4bf7-a4c6-d989241f72f9`, session for PUB-01.
- Result: the ledger shows both `verify_identity` calls, `all_verified: true`.
- Verdict: **works**.
- Consequence: smoke tests can go past identity on the practice customers when the tool API matches the practice bank.

## S1: can a pre-hook stop a write so that the bank records nothing?

- Workflow: `schedule_callback` with a `pre_process_code` that sets `config['url'] = 'https://blocked.invalid/refused'` when a flag is `"yes"`.
- Calls: `451a7ebf-98ec-4081-8d69-6a494c885a20` (flag set), `06090966-cf23-4fd6-b2a0-cc1e59e47e66` (control, no flag).
- Result: with the flag, the event is `function_call_error` "DNS resolution failed for 'blocked.invalid'". The ledger has no call and no callback. The model said "I couldn't book the callback". The control recorded the callback.
- First try failed: the flag came from the initial code node, which did not run in chat (see S6). With the flag in a call variable, the hook worked.
- Verdict: **works**. The post-hook does not run on this error, so the model gets no `what_to_do_next` line. The guard must therefore come with a prompt rule or a variable the model can read.

## S2: does a `code_exec` tool change `vars`, and does a route fire on the new value?

- Workflow: tool `note_refusal` (`code_exec`, top-level param `event` with no default) whose code increments `vars['refusals']`. Transition `refusals greater_than 1` to an `api_request` close node.
- Call: `5e8661a8-c9a2-4e4b-b51b-51bef138e631`.
- Result: after the second "no", `refusals` was 2, and the route to `close` fired in the same turn.
- Finding: the model's argument is **not** in `vars['event']`. While the code runs, the arguments are in a global dict named `params` (`params['event']`). The engine writes `vars['<tool>_args.<param>']` only after the code ended (call `6c0eb395-9d21-420b-abb2-c3bd0558e629`, follow-up spike S7). Code in a `code_exec` tool must read `params.get('<param>')`.
- A `code_exec` tool always returns `{"status": "success", "data": null}` to the model. Assigning `_result` or `result`, or printing, changes nothing (spike S8, call `7ace8294-2ec6-4960-9f13-05ecf98fcfca`). So a state tool cannot tell the model what to say. Its effect must come from the variables it writes: a route on them, or a node whose fixed line uses them.
- Other globals in the sandbox: `vars`, `params`, `_json`, `_sys`, `_tools`, `_traceback`, `_result`, `_error`.
- Verdict: **works**.

## S4: does an `api_request` node's `on_enter` line come before its `close_call`?

- Workflow: `api_request` node with `on_enter` tts "Goodbye." and `close_call` in `pre_actions`, then an `end_call` node with `message_mode: none`.
- Call: `5e8661a8-c9a2-4e4b-b51b-51bef138e631` (the same call as S2).
- Result: `function_call_start` of `close_call` at 13.087 s. The assistant message "Goodbye." is logged at 13.277 s, after `close_call` completed. The transcript text shows only "Assistant (13.3s): Goodbye."
- The chat route answered this last turn with HTTP 502, but the call ended and the ledger has `close_call`. A smoke script must treat a 502 on the last turn as "the call ended".
- Verdict: **fails** (the line comes after the call).
- Consequence: the goodbye is the `spoken_message` of the `end_call` node. `close_call` runs as a workflow-level tool with `alwaysRunsAt: ["end_of_call"]`, with `outcome` and `reason` baked from variables that a code node sets before the end node. The kit's example builder used this form and its ledger always ended with `close_call`.

## S5: does the bank accept a `now` that is not the session's own?

- Workflow: the spike workflow plus `get_account` and `create_promise`.
- Call: `1c774c0c-d049-476f-bace-98e9ca63b34c`, session for PUB-01 with `now` replaced by `2026-10-19T11:00`.
- Result: the promise for `2026-10-21` is in the ledger. The ledger's own `now` stays `2026-10-14T11:00`. The session route ignores a `now` in its request body.
- Verdict: **works**. The bank does not check dates, so the eval runner can replace `now` in the session variables and compute `expected` for that day.

## S6 (extra): which code nodes run in chat?

- Workflow: initial code node `pre`, then code node `setup`, then the conversation node.
- Call: `436a73bb-2f6d-40f3-b963-e618acb72760`.
- Result: `setup` ran (`setup_ran` set). `pre` did not (`pre_ran` absent).
- Verdict: chat skips the code of the **initial** node only.
- Consequence: every blueprint starts with an empty initial code node `start`, then the setup code node. Chat smoke tests then see the same variables as a simulation.

## S9 (extra): does a variable that a state tool writes reach the model in the same turn?

- Workflow: `task_message` starts with `GUIDANCE (obey it in every reply): {{guide}}`. The setup node sets `guide` to "Reply normally.". The state tool `note_refusal` sets `guide` to "Say exactly these words: banana split <count>".
- Call: `8f75adf8-3e90-4d65-affb-9bd213133514`.
- Result: in the turn in which the model called the tool, its reply was "banana split 1".
- Verdict: **works**. The prompt is rendered again after a tool result. A state tool can therefore steer the model: the code decides the next step and writes it into a variable that `task_message` shows.

## S10 (extra): what does an engine-run write leave, after a bank error and after a success?

- Workflow: identity on a conversation node, then `get_account`, then two `api_request` nodes `record1` and `record2` with `create_promise` (all fields baked), for practice customer PUB-10, whose first `create_promise` fails.
- Result: the bank recorded exactly one promise (the second try). `record1` left `record1_response.status = error`, `record1_status_code = 500`, `record1_failure_count = 1` and no `data.ok`. `record2` left `record2_response.data.ok = true`. The keys are named after the node, not the tool. The event shows the function as `api_call`.
- Background: in the first Brief A build, `create_promise` was a model tool. The bank's 500 arrived as `function_call_error`, the post-hook did not run, the model did not retry, and the call looped on "goodbye" until the turn cap (PUB-10, 0 of 3).
- Verdict: **works**. Writes with retries are engine-run (`patterns.record_with_retry`).

## S11 (extra): engine-run identity check with answers in pieces

- Workflow: `identity` and `identity_next` conversation nodes with `patterns.answer_tool`, a route on `id_send` to `patterns.identity_check` (engine-run `verify_identity`), and back to `identity_next` (`on_enter` llm, task starts with `NEXT STEP: {{id_guide}}`).
- Customer lines: "14 March.", "1988.", "44", "71" (practice customer PUB-01).
- Result: the agent asked "What is the year?", then "Correct. What are the last four digits…", then "What are the rest of the digits?". The bank got exactly `1988-03-14` and `4471`, both verified, 0 wrong answers. In eval round 1, the model-called tool sent `1900-03-14` and `44` for the same speech style and the case failed.
- Verdict: **works**. `identity_next` with `on_enter` llm speaks after an engine-run step.

## S12 (extra): can a `code_exec` tool read the node's turn counter?

- Workflow: one conversation node `talk` with a state tool that appends `vars.get('talk.total_turns')` to a variable on every call.
- Result: the values were 0 ("Hello?"), 1, 2, 3, one per customer message.
- Verdict: **works**. State code can tell turns apart, so it knows which line it chose in an earlier turn (and the model spoke).

## S13 (extra): two tool calls in one model message, and a list parameter

- Evidence: round 2, A+B, PUB-13, call ada7bb09. The model called `customer_said` twice in one message (p1 and p2). Both calls started at 22.94 s and ended at 23.91 s and 24.13 s. The p2 update was lost: the agent offered p2 again and recorded the wrong day.
- Result: the platform runs the calls of one message at the same time. Each reads the variables from before the message; the last write wins.
- Test: the A+B build with `customer_said(answers=[...])` on the chat route. PUB-13: one call with two entries, bank p1 300 on 30 Oct and p2 900 on 23 Oct (expected). PUB-12: one call with three entries, bank one promise and two `refused` notes (expected).
- Verdict: **parallel calls lose updates; a list parameter works**. A state tool takes every answer of one message in one call.

## Summary for the blueprint

| Spike | Verdict | Use |
|---|---|---|
| S1 guard hook | works | `guard_hook` blocks a write that breaks a rule; tell the model in the prompt what a failure means |
| S2 state tool | works | `state_tool` keeps counts per call; read the model's arguments from the global `params` |
| S3 chat past identity | works | smoke tests may go past identity on practice customers |
| S4 line before close | fails | goodbye in `end_call` `spoken_message`; `close_call` as an `end_of_call` tool |
| S5 other `now` | works | eval cases can run on other days |
| S6 initial code node in chat | skipped | empty initial node before setup |
| S9 tool-written variable in the prompt | works | the state tool writes the next step into a `{{variable}}` of `task_message` |
| S10 engine-run write with retry | works | `record_with_retry`; results are `<node>_response.*` |
| S11 engine-run identity check | works | `answer_tool` + `identity_check`; the model never calls the identity tool |
| S12 turn counter in tool code | works | the state tool plans one line per turn from the whole state |
| S13 two calls in one message | lose an update | one state-tool call per message, with a list parameter (`answers`) |
