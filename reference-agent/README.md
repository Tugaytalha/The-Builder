# Reference agent

A phone agent for the public briefs, written by hand as a generator. It is not the builder. It is the target the builder should be able to produce, and the place where platform behaviour was measured.

```bash
source env.sh
python reference-agent/test_sandbox.py           # sandbox code against the 13 practice cases, offline, seconds
python reference-agent/build.py A --save         # Brief A  -> slot ref-brief-a
python reference-agent/build.py B --save         # Brief A+B -> slot ref-brief-b
python kit/tools/run_cases.py <agent_id> --brief A --out reference-agent/results/run.json
python reference-agent/show_call.py --results reference-agent/results/run.json --failed
```

## Layout

| File | What it is |
|---|---|
| `build.py` | `SPEC` (every brief value code needs), the rules routed to steps, tools generated from `tools/openapi.json`, the 8 nodes |
| `sandbox/lib.py` | Calendar, money and result helpers prepended to every snippet |
| `sandbox/setup.py` | Code node at call start: today, the callback window, the state variables |
| `sandbox/account.py` | Code node after `get_account`: facts per product, attempt offers, a calendar checked per product, the debt sentence |
| `sandbox/hooks.py` | Pre and post hooks of the bank tools, one `## name` section each |
| `test_sandbox.py` | Runs the snippets locally the way Freya does, on the practice cases |
| `show_call.py` | A call as text: what each side said, tool calls, results, node changes |

## The workflow

`setup` (code) → `opening` → `identity` or `third_party` → `load_account` (api_request) → `account_facts` (code) → `negotiate` → `end`

- Fixed lines (TTS) for the opening, the first identity question and the debt statement. No model call can get them wrong.
- The model never computes a date or a limit. It reads deadlines, attempt offers and a calendar where every day already says "allowed" or what to offer instead.
- The brief's own rules are pasted verbatim into the step where they apply.
- Hooks: date of birth to ISO, a promise guard (floor, past due, deadline, business day, one per product), one `what_to_do_next` line in every tool result, and the outcome of `close_call` taken from the records (transfer, promise, callback, failed check, notes) instead of the model's guess.

## Platform behaviour measured on 10 October

| Finding | Consequence |
|---|---|
| A pre-hook's change to `config['body']` is what gets sent, and the `function_call_start` event shows the changed body | Normalising model output in a pre-hook works |
| A pre-hook's write to `vars` is there for the post-hook and later prompts | Hooks can share state through `vars` |
| **A post-hook does not run when the API answers with an HTTP error.** The model sees `API request failed: {...}` raw | Instructions for failures must also be in the prompt. Count failures with the engine's `<tool>_failure_count`. To refuse a write, redirect it to the read-only `get_account` route (answers 200, records nothing) so the post-hook can explain |
| Do not redirect before the identity check: a `get_account` then fails the case in the scorer | Before verification, normalise only |
| The model can send two tool calls in one message despite the prompt. They run at the same time, and `close_call` can reach the bank before the transfer it closes on | `close_call`'s pre-hook holds the close back once while the action it names is unconfirmed |
| The platform turns `$420.00` into `dollars420.00` in the text | Write amounts as `420.00 dollars` |
| The honesty judge counted "this call is recorded" in the opening as saying "recorded" before a successful call | Keep words the checks look for out of fixed lines |
| The chat route (`/api/v2/chat/message`) skips a code node that is the first node | Chat tests see empty setup values. Simulations do not |
| The API accepted the 200 KB workflow; every hook, extraction and transition was stored | Embedding a helper library in each hook is fine |
| In `--style talkative` the simulated customer often sends a turn that breaks off mid-sentence, and sends the real answer one turn later | A broken-off turn is not an answer and not a refusal. Prompt briefly without restating the offer, except while a read-back waits for its yes: then repeat the read-back |
| The judge counts every restated offer as one more offer ("floor offered once" fails if it is repeated) | Offers must follow a fixed ladder per product, with an explicit STOP |
| The judge counts any "I understand" after small talk as a sympathy sentence | No sympathy phrases except for illness, a death or job loss |

## Scores on the practice cases

| Run | Brief A | Brief A, talkative | Brief B |
|---|---|---|---|
| Kit example agent (`examples/base-agent.json`) | 0 / 10 | | |
| First version | 7 / 10 | | 2 / 3 |
| Calendar, opening wording, identity completeness | 9 / 10 | | |
| Close-call race guard | 10 / 10 | 7 / 10 | 2 / 3 |
| Offer ladder per product, no "today" per product (B rule 4) | 9 / 10 | 6 / 10 | 3 / 3 |
| Read-back repeat, per-product state keys (parallel add_note lost a note) | 8 / 10 | 6 / 10 | 3 / 3 |

Still failing now and then: PUB-07 (offers the deadline instead of the next business day after a holiday, about 3 runs in 8)
and PUB-06 (names the floor a second time). Both are choices the model makes in free text from a correct table. The next step is
a model-called check (the customer's date in, the one allowed answer out) or one node per offer, not more prompt text.

One run each. A green run is a hint, not proof: the final runs every customer three times. Prompt fixes for one speaking style
moved failures to other cases more than once. That is the argument for putting the negotiation itself in structure (an offer
counter in code, one step per offer) instead of in more prompt text.
