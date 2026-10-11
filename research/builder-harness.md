# Building the Builder: what harness wins this hackathon

Research notes, Saturday 10 October 2026, 17:30 UTC. Updated Sunday 06:40 UTC with measured results (section 2.0). The hidden briefs open Sunday at 17:00 UTC.

Sources: everything in `context/` (briefs, kit docs, scorer, kickoff transcript, τ^τ-bench paper), the transcripts of our base-agent run, the hand-written agent in `reference-agent/`, the Freya API docs at docs.freyavoice.ai, and web research on voice-agent platforms, automated agent design, policy-following agents and the Claude SDKs. A claim marked **(verify)** is plausible but untested on the platform.

---

## 0. The answer on one page

1. **The main path should not be "a coding agent writes the workflow JSON".** τ^τ-bench measured exactly that setup. The best configuration (Opus 5 in Claude Code) passed 23.9% overall and 5.9% on banking, and 92% of the agents it built were a single LLM tool loop. Our setting is harsher: the phone agent runs on a fixed, weaker model (`experimental-5`), a case passes only if all 3 runs pass, and there is no partial credit.
2. **Build a compiler, not a writer.** The pipeline:
   - The LLM reads the brief into a typed **Policy IR**. It is schema-constrained, extracted twice and diffed, and every rule carries its source quote.
   - Our own Python generator turns the IR into a workflow from a **pattern library**.
   - The workflow then goes through static checks, unit tests of the generated code, LLM rule-coverage review and conversation self-play.
   - A **bounded repair loop edits the IR and node prompts, not the raw JSON**.
3. **The phone agent it emits should be a code-driven state machine.**
   - Code nodes and hooks compute every date, deadline, amount, counter, allowed option and the final outcome code.
   - The LLM does only two things: understand the customer (extraction, intent) and phrase what code decided.
   - Every sentence the brief mandates is a fixed TTS line.
   - Every write to the bank is guarded in code.

   Research agrees strongly here. STAGE compiles a policy into a graph with "deterministic control" and "policy-scoped nodes" and reports pass^3 gains of up to +55 points (τ²-telecom) and +66 points (a banking dispute benchmark). Rasa CALM, Salesforce Agent Script, Sierra's Agent SDK and Decagon's AOPs all split the work the same way.
4. **The hand-built agent in `reference-agent/` is a good target for the generator.** Its SPEC dict, sandbox library and hooks are exactly what the builder must produce from an unseen brief. Two parts of it do not generalize yet:
   - It cuts the prompts out of the brief by Brief A's section headings. A raw-material brief has no such headings.
   - The hooks assume Brief A's identity fields.

   Section 5 says what to change.
5. **Testing ladder, cheapest first:**
   1. A linter for the platform's silent pitfalls.
   2. A dry run, then reading the saved workflow back.
   3. Local unit tests of every generated Python snippet against examples taken from the brief.
   4. An LLM critic that checks rule by rule how each rule is enforced.
   5. Self-play through `POST /api/v2/chat/message`, with our own simulated customers, branching with `fromMessageId` or `/chat/fork`.
   6. Platform simulations, which are only possible on the public practice cases.
6. **The harness itself should be a Python orchestrator** that calls the Anthropic Messages API (structured outputs, prompt caching, parallel async calls). Use the Claude Agent SDK only for the bounded repair or "escape hatch" step. The orchestrator owns the clock, the trace and the best-so-far checkpoint.
7. **Build a meta-test set before Sunday.** Write mutated briefs whose correct IR we know: other identity questions, holidays, bands, outcome table and tool enums, plus one written as raw bank material with a superseding memo. This is the only way to measure whether the builder reads a brief or remembers Brief A.

---

## 1. What the event actually rewards, and what follows for the design

| Fact (source) | Consequence for the builder |
|---|---|
| A case passes only if outcome, policy and honesty all pass, in all 3 runs. 60 hidden cases (evaluation.md) | Every free-form LLM decision is a risk taken 3 times over. Move decisions into code and routes. A flaky case scores the same as a wrong one. |
| The phone agent runs on `experimental-5`, the same for everyone (freya.py `AGENT_LLM`) | Short prompts, one job per node, few tools per node. Customers hang up when a turn is slow (README: medians above 10 s), so latency budgets matter. |
| Hidden briefs differ in identity questions, limits, deadlines, outcome table and calendar. One brief is raw material: a mail, a policy extract, a memo that changes it, a code list. Tool names stay the same but fields and enums may change (overview.md, README) | The builder must *read*. The IR must cover these variation axes, and tool bindings must come from the OpenAPI file. Superseded rules must be resolved. |
| Up to 3 products, several calendar days (different `now`), customers speak in pieces, correct themselves, chat, ask questions back, and say amounts in words (README "The final") | Per-product state, date math relative to `now` (never the real clock), and robust parsing of numbers and dates. Test with `--style pieces/corrects/talkative/asks_back/in_words`. |
| One command, a brief in, an agent out, ≤ 30 min including self-tests. A trace is required (submit.md) | The orchestrator needs a wall clock with a hard deadline, a best-so-far checkpoint and structured trace logging. |
| The top 10 are rebuilt and rerun by the organizers. "If our run scores clearly below yours, the entry is removed." (submit.md) | **Variance in the builder is a disqualification risk.** A deterministic generator and self-consistent extraction reduce it. Free-form agentic JSON writing increases it. |
| Ties: total promised amount on passed cases, then build time (evaluation.md) | Prefer full-amount promises whenever the rules allow. Do not idle; finish early once the tests are green. |
| One simulation at a time per workspace, 3–11 min per 10 cases. The practice bank serves only PUB-01..13. There is a usage limit on the platform during the 17:00–20:00 window (kickoff) | Platform simulations are scarce and impossible for hidden briefs. Self-testing must come mostly from chat-API self-play and offline checks. |
| Nothing from a hidden brief may be written into the builder. Fixing a parser crash is allowed (rules.md) | Generic code written before the event is fine, and values must come from the brief at run time. Avoid anything that could look like tuning after 17:00. |
| The organizers hinted at the kickoff: "your system should also simulate some personas … in itself. Actually, this is a tactic." They also called it "a multi-agent system which determines routing" | They expect self-play and deterministic routing. |

---

## 2. Evidence

### 2.0 Measured since the first version (notes/example-builder-baseline.md and the reference-agent work)

**The kit's agentic example builder:**
- 10/10 on A and 3/3 on B in one run.
- **8/10 with `--reps 3`**.
- 6–10/10 (A) and 1–2/3 (B) under the speech styles. `talkative` and `pieces` hurt most.

The weak points are identity under real speech and attempt limits that nobody counts. Both are free-form decisions that code and routes would fix. This supports the compiler design over the agentic one.

These platform facts are now measured, and they replace the matching **(verify)** items below:
- **A post-hook does not run when the API returns an HTTP error.** The model then sees only the raw error, so `what_to_do_next` cannot help on a 500. Route on `<tool>_failure_count`, and also state in the prompt what to do on failure.
- **A pre-hook's changes to `body` reach the request, and values it writes to `vars` reach the post-hook.** To block a write that breaks the rules, the reference agent now sends the request to the read-only `get_account` instead.
- **The chat API skips the first code step.** Chat tests of a workflow whose `initial_node` is a code node see empty facts. Make the opening a TTS conversation node and run `setup` after it.
- **The judge reads the exact words.** A greeting that said "this call is recorded" failed PUB-10, whose check says the agent must not say "recorded" before a successful `create_promise`. **Phrase mandatory sentences so that no checked word appears early**, for example "we record this call". This applies to every fixed line the generator emits: scan them against the forbidden-word list in the IR.

### 2.1 Our base-agent run: 0/10 (workspace log, 10 Oct)

I read the transcripts through `freya.get_call`. Each failure points to a mechanism:

| Case | What happened (transcript) | Mechanism that prevents it |
|---|---|---|
| PUB-03 | After one wrong date of birth (`verified:false`) and a correct phone answer (`all_verified:false`), the model said **"your identity has been verified"**, then refused the customer's next answers. | Route only on tool results. Add a `what_to_do_next` post-hook. Never let the model narrate a verification state. |
| PUB-08, PUB-10 | `close_call` ran at end of call with LLM-filled fields. The model sent a free-text reason ("system error prevented recording promise"). The mock replied `ok:false, "this outcome needs one of these reasons: refused, hardship, dispute, service_error"`, and the ledger outcome stayed empty. | Compute the outcome and reason in code and **bake** them into the `close_call` arguments. Never let the model fill them. |
| PUB-10 | `create_promise` returned 500 (`function_call_error`) and was never retried. | A retry in the graph, or in a hook, as the brief prescribes ("try once more"). |
| PUB-04, PUB-07 | Recorded 6 Nov (after the deadline) and 26 Oct (a holiday). | Date validity computed in code. Guard the write. |
| PUB-05, PUB-09 | Persuaded a hardship customer. Never transferred the restructuring request. | A data-driven intent-handler table with precedence (hardship comes before persuasion). |
| PUB-01, PUB-06, PUB-08 | Left out the mandatory sentence about the text message, the note that the rest stays overdue, and the line that payments can take one business day to appear. | Fixed TTS lines entered only on the right state. |
| PUB-02 | No callback path. | A third-party subgraph with a code-checked callback window. |
| All | Amounts spoken as "dollars365". | Format amounts and dates in code ("$365.00", "Friday 16 October"). |

The mock bank checks some things itself, such as the reason required for each outcome and identity before `get_account`, but **not the brief** (dates, floors, attempts). Its error strings are useful to surface during self-tests.

### 2.2 τ^τ-bench (context/tt-bench-paper.md): failure modes and counter-measures

| Failure the paper measured | Counter-measure in our builder |
|---|---|
| **Greps the corpus instead of reading it** (banking: 1.1%) | Our briefs are small (10–40 KB), so every extraction call gets the **whole brief**. The rule ledger must quote its source, and a coverage check flags any brief sentence that no rule claims. |
| **Never asks the client** (builds that ask score about 3×) | There is no client here, so the brief is the only source. When a rule is ambiguous, the builder records the ambiguity, makes the *safest* choice for compliance, and tests both readings if time allows. |
| **Ships the first architecture that runs**, a single tool loop. A one-line hint ("route by intent, review tool calls") took a probe from 31% to 67% | Ship a *proven* architecture as the default. Don't search over architectures in 30 min (see 2.4). |
| **Quiet API defects missed** | Test explicitly for tool failure (PUB-10). Compare the hidden OpenAPI with the public one and surface every changed field or enum to the generator and the tests. |
| **Tests that cannot fail; tests weakened to match the agent** | Expected outcomes come from the IR and code oracles, generated **before** the agent and **frozen** (hashed). The repair loop may not edit tests. Run mutation checks: break a guard and confirm a test fails. |
| **Budget mismanaged, early stopping** | Plan the time budget explicitly (section 4.7). Stop early only when the tests are green. |

### 2.3 Freya engine facts that decide the architecture

All of these come from the kit docs. The ones marked "verified" there come from a working builder.

- **Three model calls per turn: extraction, routing, dialogue.** Routing never sees `task_message`. Deterministic conditions skip the routing model entirely.
- **`pre_actions` (engine-run) versus `tools` (model-run).** Writes whose arguments code already knows belong in `api_request` nodes with baked `default`s, which the model cannot skip or mis-fill. Use model tools only where the model must decide.
- **Baking happens at node entry.** A `{{var}}` default is resolved when the node is entered. So a code node can set `rec_product_id`, `rec_amount` and `rec_date` immediately before entering a record node.
- **A post-hook can add `what_to_do_next` to a result**, and the model obeys it (verified). Pop the `header`. Booleans arrive as strings: test both `"true"` and `"True"`, or write string flags.
- **Everything is silently stripped.** That covers `tools` on non-conversation nodes, `pre_actions` on conversation nodes, `response_mapping` in the wrong place, and `context_variables`. **Read every saved workflow back and compare it with what we sent.**
- **Date extraction is anchored on the real clock, not on `now`.** The docs say the system dates are the real clock and that `date`-typed extraction gets "today's date". The calls run on fixed `now` values (14 Oct for practice). Relative dates such as "tomorrow" or "this Friday" can therefore resolve to the wrong day **(verify)**. Safer: extract the **raw phrase** as a string, then resolve it in code against `now`, or give the dialogue model a calendar computed in code (the reference agent does this).
- **The chat route may skip a code node that is the first step** (api.md, "seen in tests"). The reference agent's `initial_node` is `setup`, a code node, so chat-API self-tests may see empty facts **(verify)**. One option is to make the opening a TTS conversation node that needs only call variables and run `setup` right after it.
- **`max_node_turns` + `max_turn_transition`** is a deterministic per-node turn counter. Use it for "ask once more, then close" rules. Its order relative to the other transitions is **(verify)**.
- **`end_call` with an auto-trigger phrase** works: the base agent says "Have a good day." and `end_call` fires. A lifecycle `close_call` with `alwaysRunsAt: end_of_call` runs after hang-up, so it is reliably the last tool call. If its arguments are all baked it runs without a model call. If one is unresolved, an LLM fills it, which is what broke PUB-08 and PUB-10.
- **Tool-level `config.maxRetries`.** Whether it retries on HTTP 500 and how the ledger shows the attempts is **(verify)**. If it does, `maxRetries: 1` on `create_promise` implements "try once more". If it does not, retry in the graph.
- **Chat API:** `POST /api/v2/chat/message` accepts `versionId` and `fromMessageId`, and branches from an earlier assistant turn. `POST /api/v2/chat/fork` copies a call up to an anchor and can point it at another version. This allows **conversation-tree testing**: fork after identity has passed, then try 10 different customer moves without replaying the opening. Simulations accept `agentVersionId`, so an unpublished candidate version can be tested **(verify)**.
- There is a unit-test API (`/unit-tests/...`). Its tests take a message prefix plus `routing`, `extraction` and `tool_call` assertions and a judge expectation. None of its fields mock tools, and it is not documented how runs are triggered or how fast they are. Interesting, but not needed.

### 2.4 Automated agent design literature: what transfers to 30 minutes

These numbers come from the research agent's reading of the papers. The STAGE and JourneyBench headline claims are checked against the arXiv abstracts. The finer numbers are as reported, not independently verified.

- **Search methods do not fit:** ADAS, AFlow, MASS, Darwin Gödel Machine, EvoAgent. They need tens to hundreds of evaluated candidates.
  - "Inefficiencies of Meta Agents" (arXiv 2510.06711) finds that automated design paid off only after more than 15k deployments.
  - Meta-Agent Challenge (2606.04455) finds that *sparse, deliberate* evaluation beat many evaluations, and that the common failures were "early convergence, plumbing fixes inside a flawed design, ignoring the clock". A timeout scored zero.
  - **Conclusion:** hard-code a strong prior architecture and spend the budget on reading the spec and making targeted fixes.
- **What does transfer:**
  - GEPA-style reflective edits (read the trace, diagnose in words, edit only the node responsible).
  - SIMBA's focus on *high-variance* cases (a case that flips between runs is a free-form decision that should become code).
  - TextGrad-style per-node blame.
  - An ACE-style lessons "playbook", maintained across our practice runs *before* Sunday.
- **Compiled-graph results:**
  - **STAGE (arXiv 2608.22538).** It confines model judgment to policy-scoped nodes, with procedural control in deterministic code. Pass^3 rose by up to +55.0 (τ²-telecom) and +65.7 (Smart Dispute, banking). In its ablations, giving each node the full policy cost 5.7–34.3 points of pass^3, and letting the LLM choose the next node cost 2.5–17.5.
  - **JourneyBench / "Beyond IVR" (2601.00596).** A dynamic-prompt agent that models policy control lets GPT-4o-mini beat GPT-4o, and it holds up under tool failures.
  - **COVENANT (2607.25400).** A runtime check of each action against the extracted requirements raised success from 50% to 83%.
  - **ToolGuard (2507.16459) / PolicyGuard (2606.29225).** Guards compiled per tool, plus a verifier that sees the dialogue for *process* rules ("the user must confirm first"), which argument guards miss.
  - **RuleArena (2412.08972).** LLMs apply real rule sets at 21–68%. One arithmetic slip ruins the result, so compute in code.
- **The same split in industry:**
  - Rasa CALM: the LLM emits commands only, and flows are deterministic.
  - Salesforce Agent Script: a DSL compiled to a graph, with deterministic if/else next to prompt blocks.
  - Sierra Agent SDK: deterministic guardrails, supervisors, and a bypass of the LLM where regulators need fixed wording.
  - Decagon AOPs: natural-language SOPs compiled into structured logic.
  - Parlant: guidelines plus journeys, with canned responses.

### 2.5 Mechanisms production voice agents use to keep rules reliable

From the compliance-architecture research agent, ranked by reliability gained per unit of effort:

1. **A facts code node:** business days, deadline, the *list of allowed dates*, callback slots, caps and formatted amounts, all injected as speakable text. The model picks from a list and code checks membership. It never does arithmetic.
2. **Compliance gates route only on string flags written by code** (`verified`, `ptp_check=valid`, `write_ok`), never on `matches_intent`.
3. **Withhold the data.** No amount, product or debt variable appears in any prompt before identity is verified. The model cannot leak what it was never given. This is the strongest protection against forbidden words and prompt injection.
4. **Fixed TTS** for the opening, the security questions, the debt statement, the read-back, "recorded", the line to a third party, and the close. In other products: Pipecat `tts_say`, Retell "static sentence", Sierra "bypass the LLM", Parlant strict canned responses.
5. **A code validator before every write.** On failure, code returns `what_to_do_next` naming the allowed option.
6. **Counters in variables:** wrong answers, persuasion attempts per product, floor already offered, write attempts, "does not want to talk". Branch on them with `greater_than`.
7. **A confirmation node with an enum:** `yes|no|correction|unclear`, default `unclear`. Only `yes` proceeds, and any changed slot resets `confirmed`.
8. **"Recorded" gated by graph structure.** The sentence exists only in the node entered when `write_ok` is set.
9. **One outcome code, computed once by code:** the outcome table plus its precedence rules, so there is exactly one `close_call` by construction.
10. **Extract the raw span, normalize in code** (digits in pieces, "double four", "oh" for 0, "nineteen eighty-eight", ordinals, "this/next Friday"), and read back absolute dates with the weekday.
11. **One question per node, short prompts, few tools, few global nodes.** Retell warns that each global node adds a transition option to every node.
12. **An adversarial persona regression suite**, run at least 3 times per case and scored on the final ledger state.

### 2.6 The ElevenLabs analogy, and what the voice platforms advise

| ElevenLabs Agent Workflows | Freya equivalent | Note |
|---|---|---|
| Subagent node (overrides the prompt, tools, LLM) | `conversation` node (`task_message`, `tools`, `extraction_schema`) | Freya cannot change the model per node; `reasoning_override` is the only knob |
| **Say** node ("legal disclosures, read-back confirmations") | `on_enter: {"type":"tts"}` / terminal `spoken_message` | Fixed wording, no model call |
| **Dispatch tool** node ("guarantees the tool is called", success and failure edges) | `api_request` node with `pre_actions` + routes on `<tool>_failure_count` / result variables | Use it for every write whose arguments code knows |
| **Update state** (atomic expressions) | `code` node writing `vars` | Freya's version is full Python |
| Edge conditions: `llm` / `expression` / unconditional | `matches_intent` / variable operators in an OR-of-AND group / `always` | Same advice: expressions first, LLM conditions for genuinely fuzzy intent only |
| Backward edges for retries and loops | A transition back to an earlier node, or a self-transition | Supported |
| Agent tests: Simulation (with **tool mocking**), Next Reply, Tool Call (exact/regex/LLM argument match), `repeat_count` | Simulations with personas (no tool mocking), the chat API with fork/branch, the unit-test API (routing/extraction/tool_call assertions) | Freya has no tool mocking, which is why we need simbank (6.3) |
| CLI "agents as code" (pull/diff/push), "Procedures" drafted from SOP documents | `freya.save_workflow` / `export_workflow`; our builder | — |

Advice that recurs across the voice platforms (ElevenLabs, Retell, Pipecat Flows, Vapi, LiveKit, Bland):
- **Narrow nodes:** 1–3 goals, a prompt under about 2k tokens, and only the tools the node needs. The prompt says what to do; edges say when to leave. A node's prompt should never tell it to transition.
- **Fewer outgoing edges.** Retell: "the more transitions available from a node, the less likely the node transition model is to choose the correct one". Each global node adds an option to every node, so use few globals and give them re-trigger guards.
- **Conditions exclusive and exhaustive,** with deterministic ones first and an explicit fallback.
- **Business-critical values come from tools or code, never from extraction.** Vapi: extraction is "LLM-based, best-effort, and not deterministic".
- **Format plus an example in every tool parameter description,** because speech-to-text leaks spoken forms into arguments. Never put a placeholder date in a prompt: a Vapi report shows the agent reading back the prompt's example date.
- **Tool failure:** acknowledge, never guess, retry (once or twice), then a scripted outcome.
- **Test probabilistically.** ElevenLabs: "A single pass shows the agent can succeed; probabilistic testing shows how often it will". Change one thing at a time and rerun the same failing tests.
- **Collections vendors** (Bland's write-up on collections) say "rules live in the graph, not in agent judgment" and "every sentence is in the approved path or the call routes out", with a finite menu of arrangements. Brief A is built the same way.
- **Generating workflows automatically.** Vapi's migration from Workflows to Squads ships an "agent-ready spec" for coding agents. It has input and output schemas, a worked example, "ask the human rather than guess", and a validation checklist ("JSON is valid and matches the shapes", "don't invent endpoints"). ElevenLabs "Procedures" drafts structured procedures from uploaded SOPs. Both are skeleton-plus-spec designs, like ours.

---

## 3. Harness options

| | A. Agentic builder (the kit's `agent_builder.py` + skills) | B. Pure compiler pipeline | **C. Compiler + bounded agentic repair (recommended)** |
|---|---|---|---|
| How it works | Claude, through the Agent SDK, reads the brief, writes the JSON, runs tests and fixes them | Python orchestrator: LLM extraction into the IR, then a deterministic generator, then tests | B as the backbone. Then an Agent SDK or Messages loop that may edit only the IR, prompt slots and custom-code slots, under time and tool limits |
| Strength | Most flexible on surprises. The kit says v3 passed 10/10 on Brief A once | Fast, reproducible, testable, easy to trace | B's reliability with an escape hatch for rules the template cannot express |
| Weakness | High variance between runs, which risks disqualification at the rebuild check. The τ^τ failure modes. A 600–1500-line JSON with silent stripping risks. The clock is hard to enforce (the SDK has no wall-clock option, only `interrupt()`) | Breaks when a hidden brief has a mechanism the IR lacks | More engineering before Sunday |
| Build time | 15–30 min | 3–6 min without tests | 10–25 min |

Why C: the scoring (pass^3, rebuild verification, ties broken by build time) rewards **low variance**, and the hidden briefs reward **flexibility**. C gets both by giving the LLM the reading and phrasing work, and code the structure.

Keep A runnable as **plan B**. If C crashes on a hidden brief in an unexpected way, run A (with improved skills) and submit whichever passes more self-tests.

---

## 4. The builder in detail (option C)

```
brief.md + tools.openapi.json
        │
  [1] ingest ── normalize text; split documents (mail / extract / memo / code list); parse OpenAPI into tool contracts
        │
  [2] spec recovery (LLM, parallel) ── rule ledger with quotes → Policy IR (JSON schema) ×2 → diff → adjudicate
        │                               coverage check: every brief sentence → rule → IR field / prompt slot / "judge-only"
  [3] tool binding ── for each tool field: source = call var | code var | model-filled(enum) | constant
        │
  [4] generate ── pattern library + IR → workflow JSON + sandbox code (SPEC constants + lib + hooks)
        │
  [5] verify ── lint → dry-run → save+publish → read back + diff → code unit tests → LLM coverage critic
        │        → chat self-play (parallel, forked) → platform simulation (public briefs only)
  [6] repair ── failures → diagnosis → IR / prompt-slot / code-slot patch → regenerate → re-verify (best-so-far kept)
        │
  [7] export + trace
```

### 4.1 Ingest
- Read the whole brief. The raw-material brief arrives as one Markdown file (FAQ). Split it into its parts: headers, mail, memo, code list.
- Parse the OpenAPI file into contracts: path, method, required fields, enums, formats, response fields, documented error semantics ("500: nothing was recorded, may be repeated").
- **Diff it against the public `openapi.json`** and keep the list of changed fields and enums. These are the likeliest traps.

### 4.2 Spec recovery: rule ledger → Policy IR
- **Step 1: rule ledger.** One call with the whole brief, schema-constrained. Each rule gets:
  - an id and a type (precondition, computation, limit, disclosure, prohibition, mandatory sentence, intent handler, outcome mapping);
  - its scope (before or after verification; which band or product);
  - the exact **source quote**;
  - a `status`: active, superseded or amended, with a `superseded_by` link.
- **Conflict resolution for raw material**, in this order:
  1. An explicit amendment ("replaces …").
  2. The later effective date at equal or higher authority.
  3. The more specific rule.
  4. The compliance-safe default.
  5. Otherwise, flag it.

  Watch for partial amendments that change one number only. Email chatter and opinions are not rules. A code list ("PTP = promise", "RTP = refused") maps onto the `close_call` enums from the OpenAPI file.
- **Step 2: Policy IR.** Use structured outputs (Messages API `output_config.format` with a JSON schema, or `client.messages.parse` with a Pydantic model; supported on Opus, Sonnet and Haiku 5.5). Run **two independent extractions**, for example Opus 5.5 and Sonnet 5.5, or two prompt variants. Diff them field by field, and have a third call settle each disagreement *with quotes*.
- **Step 3: coverage.** Every rule in the ledger maps to an IR field, a prompt slot of a named node, a custom-code slot or "judge-only". Unmapped rules go to the repair stage.

A sketch of the IR, with names not fixed. Every value comes from the brief, at run time:

```yaml
call_vars: [customer_id, first_name, last_name, title, now]   # names and meanings
persona: {bank, self_description, recorded_notice, address_form}
forbidden_before_verification: [words…, product names, amounts]
right_party: {question_template, confirm_phrases, non_confirm_examples, max_asks, answer_question_first: true,
              outcomes: {unclear, wrong_number, deceased}, condolence_line}
third_party: {disclose: nothing, ask_reachability: true,
              callback: {days: [today, next_business_day], window: ["10:00","19:00"], inclusive: true, after_now: true,
                         reasks: 1, outcome_ok, outcome_none}}
identity: {questions: [{field_enum_value, ask_text, normalize: date_iso|digits:4|postcode|year|free, numeric_date_order: DMY}],
           max_wrong_total, per_question_retry: true, hints: {day_month_swapped: {action, counts_as_wrong: false}},
           on_fail: {line, outcome}, on_decline: {explain_once_line, outcome}}
disclosure: {template, product_names: {type: template}, fields: [past_due, days_late]}
calendar: {business_weekdays: [0..4], holidays: [...], timezone}
bands: [{days_late: [min,max], name, deadline: {kind: nth_business_day|calendar_days|end_of_month|…, n}, attempts}]
floor: {by_type: {credit_card: minimum_payment, …}} | {formula: custom_code_slot}
negotiation: {first_ask, never_ask_how_much, attempts: [{n, amount: full|floor|floor_if_too_much, date: last_bd_this_week|deadline|…, bands}],
              vague_date: {ask_once, then: propose_deadline}, weekday_semantics: {next: following_week, this: current_week},
              non_business_day: next_business_day_if_not_after_deadline, after_deadline: offer_deadline,
              partial_amount: accept_between_floor_and_full, below_floor: offer_floor_once, floor_note_line}
intents: [{name: hardship|paid|dispute|restructuring|human|scam|robot|unknown_info|not_want_to_talk|…,
           trigger, applies: before|after|both, line, actions: [transfer(queue)|add_note(reason)|none],
           ask_first_once?, close: {outcome, reason} | continue, precedence, counts_as_attempt}]
confirmation: {readback_template, question: "Do you confirm?", change_handling}
recording: {one_per_product, retries, success_line, mandatory_after_success, failure_line, failure_outcome}
multi_product: {state_all_first, order: account_order, ask_all_today_first, per_product_attempts, one_date_clamp, single_readback,
                notes_for_unpromised: {reasons}, transfer_drops_unrecorded, no_notes_on_transfer}
closing: {outcome_table: [{outcome, reason, when}], precedence: [...], farewell: thank_and_goodbye, close_is_last: true}
custom_code_slots: {deadline_fn?, floor_fn?, band_fn?, callback_fn?}   # LLM-written Python for rules the declarative IR can't say
residual_rules: [{text, quote, node}]                                  # routed verbatim into one node's prompt
```

### 4.3 Tool binding
For each tool field in the OpenAPI file, choose a source: a call variable (`customer_id`), a code variable (`rec_amount`), a constant, or model-filled (only with an `enum` plus a description). Write tools are always fully baked from code variables.

When fields change in a hidden brief (for example `create_promise` gains a `channel`, or `verify_identity.field` gets new enum values), the binding step must handle them. The validator fails the build when a required field has no source.

### 4.4 Generator and pattern library
These are our own Python functions, written before the event. Each one emits a correct node group and encodes the kit's "verified" rules once:
- `code_node`, `api_node(tool, baked_args)`, `tts_conversation`, `extract_enum_node`;
- `guarded_write(tool)`, `retry_once(tool)`, `counter`, `ask_n_times_then(outcome)`;
- `end_call(farewell)`, `lifecycle_close_call(baked)`.

The **sandbox library** (`reference-agent/sandbox/lib.py` is the start) holds business days, the n-th business day, week logic, money and date formatting, parsing of digits, numbers and dates in words, the "this/next weekday" semantics, membership checks and outcome resolution. It must stay pure `re`/`json`/`datetime`, never raise, and contain no `{{`/`}}`.

The **linter** encodes every pitfall from the docs' checklists:
- no `null`; `default` and never `const`;
- body leaves under `body.properties`; mapping paths that start with `data.`;
- booleans tested both ways; passthrough nodes ending with `always`;
- `max_node_turns` paired with `max_turn_transition`; `min_confidence` set on every extracted variable; `date` types;
- no `agent_config`; every path reaching an `end_call`;
- every write tool baked or guarded; no amount or product variable in any node before verification.

### 4.5 Verification ladder
1. **Lint, then dry run** (`?dryRun=true`), then save and publish (`freya.save_workflow` publishes; a plain PUT does not). Then **GET it back and diff** to catch silent stripping.
2. **Unit tests of the code**, run locally, with the same snippets executed in Python on synthetic `vars`:
   - every `now` in a grid: weekdays, Fridays, the day before a holiday, month end, 18:59 against the callback window;
   - every band boundary (7/8, 45/46);
   - one to three products.

   The expected values come from the brief's own worked examples. Brief A, for example, says "next Friday said on a Friday" means the following week. Add property checks: a deadline is a business day and is not before today.
3. **LLM coverage critic.** Give it the rule ledger and a human-readable rendering of the workflow (each node's prompt, tools, transitions and code summary). For each rule it answers: enforced by code, by route, by fixed line, by prompt, missing, or contradicted. Anything missing or contradicted becomes a repair item. This is cheap (one call) and catches most omissions.
4. **Chat self-play.** Our customer simulator talks to the *real* engine and model through the chat API, with tree-forking (section 6). Scoring uses our ledger and a rubric judge that answers one yes/no question per check, quotes the evidence and allows "not applicable".
5. **Platform simulation.** `tools/run_cases.py --reps 3` and `--style …` work only for public briefs. It is the ground truth for developing the builder before Sunday.

### 4.6 Repair loop
- **Input:** the failing checks with transcript excerpts and `route_evaluated`/`variable_table` events (they show exactly which branch failed and why).
- **Diagnosis:** one LLM call. It names the faulty layer: IR value, binding, generator, prompt slot, or a rule the template cannot express.
- **Allowed edits:** IR fields, prompt slots, the custom-code slots (which must pass their unit tests), and adding an intent handler. The repair loop never edits raw JSON and never edits tests.
- **Acceptance:** keep a candidate only if it passes at least as many frozen self-tests as the best one so far. Re-run any case that flips between runs.

### 4.7 Time budget for a 30-minute run

| t (min) | Work |
|---|---|
| 0–1 | Ingest; diff the OpenAPI file; start the trace |
| 1–5 | Rule ledger + 2× IR extraction (parallel), adjudication, coverage |
| 5–6 | Binding, generation, lint, dry run, save, read back. **Checkpoint 1 (submittable)** |
| 6–8 | Code unit tests + coverage critic (parallel) → repair round 0 → checkpoint 2 |
| 8–18 | Chat self-play: about 15–25 scenarios × styles, in parallel, forked from shared prefixes. Judge, repair round 1 |
| 18–25 | Rerun the failures and a regression sample, 2× each. Repair round 2 only if the gain is clear |
| 25–26 | **Hard stop.** Export the best-so-far with `freya.export_workflow`; write the trace |

Make the deadline a constant (for example 26 min) that the orchestrator checks before *starting* any step longer than the time left.

### 4.8 Trace and reproducibility
Write the trace from the orchestrator, not from the model's chatter. Each line is JSON with:
- the timestamp;
- the phase;
- for every LLM call: the model, a one-line purpose, the token usage (including cache fields) and the duration;
- every Freya call: create, update, publish, the workflow id, the agent id, the version, and the node and tool counts;
- every test with its result.

The run also keeps every draft (IR, workflow) as a file with its sha256. Remove API keys. This covers every row of the "In the trace" table in submit.md.

---

## 5. The phone agent the generator should emit

This is the target topology for a collections call. The node *count* comes from the IR (for example the number of identity questions). The *pattern* is fixed.

```
opening (conversation, TTS: identity line + recorded notice + "Am I speaking with {{title}} {{last_name}}?")
  extraction: line_status = customer | someone_else | wrong_number | deceased | unclear | question
  ├─ customer ───────────► setup (code: now-relative facts, counters, close defaults) ─► id_q1
  ├─ someone_else ───────► third_party ─► callback_check (code) ─► schedule_callback (api, baked) ─► close
  ├─ wrong_number/deceased ► (TTS condolence line if deceased) ─► close
  └─ unclear ×max_asks ──► close (not_reached/unclear)

id_q1 … id_qN (one conversation node per question, field baked)
  tool verify_identity (answer model-filled, normalized in pre-hook; post-hook adds what_to_do_next, writes st_* flags)
  routes on flags: all_verified → load_account | wrong_answers_left==0 → id_failed (TTS app/branch line → close)
                   declined twice → close (not_verified/declined) | hint swapped → ask month as a word (not counted)

load_account (api_request: get_account, maxRetries≥1 on reads) ─► facts (code: per-product band, deadline, floor, attempt plan,
   allowed-date calendar, speakable debt statement) ─► disclose (TTS statement + first ask)

negotiate (conversation): the LLM classifies the customer's move and phrases code's next line
  ⇄ dm (code: applies sections 7–9 / Brief B per product; writes next_line, readback_text, handler, counters)
  ├─ agreed terms valid ─► readback (TTS {{readback_text}} "Do you confirm?"; extraction yes|no|change|unclear)
  │       yes ─► record loop: set rec_* (code) ─► create_promise (api, baked) ─► result check (code; retry once)
  │              ─► recorded (TTS "…recorded. You will receive a text message confirming this promise.")
  ├─ intent handler ─► transfer_to_agent / add_note (api, baked) ─► line ─► close
  └─ attempts used up ─► close (no_promise/refused)

close (code: outcome table + precedence → close_outcome/close_reason) ─► goodbye (end_call, fixed farewell)
close_call = lifecycle tool, alwaysRunsAt end_of_call, every argument baked → always last, exactly once

global nodes (few, excluded from identity and terminal nodes): robot/AI question, scam question, unknown-info → line → __previous__
```

**The choice inside `negotiate`.** The reference agent makes `negotiate` one big LLM node that holds the facts, the calendar and the brief's rules. Its hooks guard `create_promise`, `add_note`, `schedule_callback` and `close_call`, and a pre-hook strips `customer_id` from an invalid request so nothing reaches the ledger. That is the "policy guards" design. It is quick to build, and the guards protect the ledger. It does not protect the *conversation*. The judge still fails these:
- an offer of the wrong attempt;
- a second persuasion attempt in the early band;
- a floor offered twice;
- "how much can you pay?";
- one read-back per product where the brief wants one for all.

Per STAGE's ablations, the full policy in one node and LLM-chosen steps are what cost pass^3. My recommendation is to start from the reference design, because it works now. Then move the counting rules into a `dm` code step: which attempt comes next, whether the floor was already offered, which product is current, whether the read-back is complete. The LLM keeps the language. Do it rule family by rule family, keeping each change only when self-play shows it is not worse.

**Generalizing the reference agent:**
- **Prompts.** Today `build.py` cuts them from Brief A by section heading (`a["5. Identity"]`). The builder must instead route *ledger rules* to nodes by their scope tags, so a raw-material brief works.
- **Identity hooks** check for `'birth'`/`'phone'` in the field name. They must be driven by the IR (`normalize` per question), so that postcode, birth year, company number or founded year work.
- **SPEC.** It needs a band rule per kind (`nth_business_day`, calendar days, …) instead of a hard-coded n-th-business-day formula. It needs product naming and floor rules for unseen product types. It needs outcome and reason tables taken from the OpenAPI enums plus the brief.
- **The code size of each hook.** Every hook currently prepends the whole of `lib.py` (the workflow is 197–214 KB). That is fine if the platform accepts it. Check that latency is not affected **(verify)**.

---

## 6. Self-testing without hidden cases

### 6.1 Scenario generation (frozen before the agent is built)
- Derive the scenarios from the **rule ledger**:
  - at least one scenario per rule family (third party, identity failures, decline, each band, vague date, weekend or holiday, after the deadline, too much → floor, below the floor, hardship accepted or declined, paid, dispute, restructuring, human after one ask, scam, robot, does not want to talk twice, tool failure);
  - Brief B families (all today, one date for all with a clamped deadline, mixed promise and refusal, dispute on one product, transfer after a recorded promise).
- Cross them with the **styles** `pieces`, `corrects`, `talkative`, `asks_back` and `in_words`, plus prompt injection.
- Use several `now` values (a Friday, the day before a holiday, late in the day).
- Expected ledger states come from the IR through a **separate oracle in code**, never from the agent. Hash the scenario file; the repair loop may not change it.
- **Rubric:** one yes/no check per rule, with quoted evidence, and "not applicable" allowed. Never a holistic judge. A case passes only if the ledger matches exactly and every check passes.

### 6.2 Customer simulator
Reuse the persona template and the `STYLES` in `tools/run_cases.py`, which is how the organizers prompt their simulator. Run it on a cheap fast model, and keep it consistent with the case script.

Research (Sim2Real, arXiv 2603.11245) finds LLM simulators too cooperative and too uniform. Add stubborn and noisy variants on purpose.

### 6.3 The bank problem
For hidden briefs there are no practice customers: the practice bank serves PUB-01..13 only (FAQ). Options:

**Case mutation on the real practice bank is the cheapest end-to-end generalization test, for use before Sunday.** The practice bank stores the PUB customers' data but does not enforce the brief. `run_cases.py --cases <file>` takes any cases file. So:
1. Write a mutated brief: other holidays, band limits, deadline numbers or attempt counts, the question order, or a raw-material rewrite of Brief A.
2. Copy `public-test-set.json` and **recompute `expected` and `checks` under the mutated rules**, keeping the same `PUB-xx` ids so the bank opens the same customers.
3. Build an agent from the mutated brief and run it on that file.

**Overriding `now` in the session variables** in our copy of `run_cases.py` tests other calendar days, such as a Friday or the day before a holiday, which the kit cannot otherwise test. It needs the expected dates recomputed. Both changes run on the real engine, the real model, and the same persona and judge model as the final (`gemini-3-flash-preview`). Mutations that the bank's fixed data or enums cannot express (new identity fields, renamed outcome codes) still need simbank (c) or the IR-only check.

| Option | Fidelity | Effort |
|---|---|---|
| a. Static tests only (lint, code unit tests, critic) | Low for dialogue | None |
| b. Practice-bank customers (PUB sessions) when the hidden OpenAPI file stays compatible | High, but only when compatible | Low |
| c. **"simbank"**: our own generic mock of the 7 tools, driven by the scenario (identity answers per field, products in whatever shape the OpenAPI file declares, `fail_first_n` faults, a ledger), served at a public URL. The *test variant* of the workflow differs only in the base URL; the export always uses the real URL | High | Medium: a small Cloudflare Worker or Vercel Function with a key-value store, or a local server behind a quick tunnel |
| d. A test variant whose bank calls are replaced by code nodes that write fake responses | Medium (different wiring) | Medium |

Recommendation: c, built before Sunday, with a fallback to a+b when it is unreachable. The organizers rebuild the top-10 builders themselves, so self-play must **degrade gracefully** when simbank or the tunnel is missing.

### 6.4 Running it fast
- **Speed:** chat turns are synchronous and take seconds, and the one-simulation-per-workspace limit applies to *simulations*. Run 10–20 conversations in parallel **(verify the concurrency and whether it is rate-limited; stay polite, "do not probe or load-test")**.
- **Fork shared prefixes:** run the opening and identity once, then fork after verification (`/chat/fork` or `fromMessageId`) for each negotiation scenario. This saves about half the turns.
- **Diagnose from events:** read `route_evaluated.branches` and `variable_table` from `freya.get_call(call_id)["messages"]` to see why a route did not fire.

---

## 7. Generalizing to the hidden briefs

Variation axes the organizers named, with evidence, and how the IR covers each:

| Axis | Evidence | Coverage |
|---|---|---|
| Other identity questions | Overview; `run_cases.py` already supports `postcode`, `birth_year`, `company_number` and `founded_year`, which suggests a **business-customer brief** | A list of questions with a `normalize` kind for each; enum values from the OpenAPI file; generic digit, number and postcode parsers |
| Other limits and deadlines | Overview | Band rows with a deadline *kind*, plus a custom-code slot for formulas |
| Another outcome table | Overview | Outcomes and reasons from the brief table plus the OpenAPI enums; the code list maps codes onto enums |
| Another calendar | Overview | Weekdays and holidays as data; `now` is the only clock |
| Changed tool fields and enums | README | Binding step + OpenAPI diff + a validator for required fields without a source |
| Raw material + superseding memo + code list | evaluation.md | Rule ledger with status, supersession and provenance; extract twice and diff |
| 1–3 products, several calendar days, human speech | README, evaluation.md | Per-product state in code; a test grid over `now`; robust parsers; style personas |
| A product type not seen before (an overdraft, a business loan…) | Not stated, but likely if customers are businesses | Product naming and floor rules from the brief; the generic fallback says the type in words |

**A meta-test set before Sunday.** Write 4–6 mutated briefs with a known IR:
- A with other holidays and bands;
- A with postcode and birth-year identity;
- B with a different outcome table and different reason codes;
- **a raw-material rewrite of A**: an email, a policy extract, a memo changing two values, a code list.

Score IR extraction field by field against the ground truth. This takes seconds per brief and needs no platform. It is the most direct measure of "reads a brief, not this brief".

**The legal boundary.** All parsers, patterns and generic mechanisms are written before 17:00 Sunday. After it, change only crash fixes with no brief content. Keep a git commit at 16:59 as proof.

---

## 8. Platform behaviors to verify (a few targeted tests, not load)

1. Does `date`-typed extraction resolve "tomorrow" or "this Friday" against the real clock or against the `now` call variable? (Decides between raw-phrase extraction plus our parser and trusting `date`.)
2. Does `config.maxRetries: 1` retry an HTTP 500 from `create_promise`? What do the ledger and transcript show?
3. Does a lifecycle `close_call` (`end_of_call`) with every argument baked from code variables run with no model call, and always as the last ledger entry, including when the customer hangs up?
4. Does the chat route skip a code node used as `initial_node`?
5. Do `max_node_turns` + `max_turn_transition` fire before or after the node's other transitions on the capped turn?
6. Can a pre-hook block a call outright? The reference agent strips `customer_id` instead: does the ledger stay clean, and does the judge see a failed tool call?
7. Is an `on_enter` TTS line on an `api_request` node spoken before its `pre_actions` run?
8. Does hook size (the full `lib.py` in every hook) affect turn latency?
9. How many chat-API conversations can safely run in parallel, and does `/chat/fork` work on simulated calls?

---

## 9. Build order until Sunday 17:00

1. **P0. Make the reference agent pass reliably.** Run `run_cases.py --reps 3` on A and B, and at least one run with each `--style`. Fix it through the generator, never by hand. This is the target the builder must reproduce.
2. **P0. Turn `reference-agent/build.py` into a generator driven by the IR.** Its SPEC, the prompt slots routed by rule scope, and the identity hooks should all be driven by the IR. Wire the Policy IR schema and the extraction calls in front of it. Run it on Brief A and A+B, and compare with the hand-written SPEC.
3. **P1. Meta-test set** (section 7) and the IR extraction scorer. Iterate on the extraction prompts and schema until the mutants score 100%.
4. **P1. Verification ladder steps 1–3:** the linter, the read-back diff, the code unit-test grid and the coverage critic.
5. **P2. Self-play:** scenario generation, simulator, judge, chat runner with forking, and simbank.
6. **P2. Orchestrator:** time budget, checkpoints, repair loop, trace, and the exact submission command `python3 builder/build.py {brief_path} {tool_api_path}`.
7. **P3. Plan B:** the kit's agentic builder with our skills, which are the pattern library documentation, the reference agent and the platform pitfalls.
8. **Dress rehearsal:** run the full builder in 30 minutes on a mutant brief *as if it were hidden*: one command, no hands, then export and write the trace.

---

## 10. Sources

**Local**
- `context/`: the hackathon tabs, `kit/README.md`, `kit/docs/*.md`, `kit/tools/run_cases.py`, `kit/tools/score.py`, `kickoff-transcript.md`, `tt-bench-paper.md`
- `reference-agent/`
- `runs/20261010-context-kit-results/base-brief-a.json`, and the call transcripts read through `freya.get_call`

**Freya docs**
- https://docs.freyavoice.ai/llms.txt
- https://docs.freyavoice.ai/api-reference/chat/send-a-chat-message.md
- https://docs.freyavoice.ai/api-reference/chat/fork-a-chat-call-at-an-anchor.md
- https://docs.freyavoice.ai/api-reference/simulations/create-simulation.md
- https://docs.freyavoice.ai/api-reference/unit-tests/unit-tests-overview.md
- https://docs.freyavoice.ai/guides/learning-freyavoice-ai/best-practices.md

**Papers** (abstract-level claims checked for STAGE and Beyond IVR; other figures as reported by the research agent)
- STAGE: arXiv 2608.22538
- Beyond IVR / JourneyBench: 2601.00596
- COVENANT: 2607.25400
- ToolGuard: 2507.16459
- PolicyGuard: 2606.29225
- RuleArena: 2412.08972
- Inefficiencies of Meta Agents: 2510.06711
- Meta-Agent Challenge: 2606.04455
- GEPA: 2507.19457
- MASS: 2502.02533
- ACE: 2510.04618
- τ-bench: 2406.12045
- τ²-bench: 2506.07982
- τ-knowledge: 2603.04370
- SOPBench: 2503.08669
- SOP-Bench: 2506.08119
- FlowBench: 2406.14884
- IntellAgent: 2501.11067
- Sim2Real: 2603.11245
- Lost in Simulation: 2601.17087
- DRAGged into Conflicts: 2506.08500
- StateFlow: 2403.11322
- Rasa CALM: 2402.12234

**Industry**
- ElevenLabs Agent Workflows: https://elevenlabs.io/docs/agents-platform/customization/agent-workflows
- ElevenLabs prompting guide: https://elevenlabs.io/docs/agents-platform/best-practices/prompting-guide
- ElevenLabs agent testing: https://elevenlabs.io/docs/agents-platform/customization/agent-testing
- Retell transition conditions: https://docs.retellai.com/build/conversation-flow/transition-condition
- Pipecat Flows: https://docs.pipecat.ai/guides/features/pipecat-flows
- Vapi prompting guide: https://docs.vapi.ai/prompting-guide
- Vapi Workflows → Squads migration: https://docs.vapi.ai/workflows/legacy-migration
- LiveKit workflows: https://docs.livekit.io/agents/build/workflows/
- Bland on collections: https://www.bland.ai/blog/ai-voice-agents-debt-collection
- Salesforce Agent Script (hybrid reasoning): https://developer.salesforce.com/blogs/2025/10/introducing-hybrid-reasoning-with-agent-script
- Decagon AOPs: https://decagon.ai/blog/from-sops-to-agent-operating-procedures
- Sierra: https://sierra.ai/blog/meet-the-ai-agent-engineer
- Parlant journeys: https://next.parlant.io/docs/engine-internals/journeys
- LiveKit (keeping the conversation on track): https://livekit.com/blog/keeping-your-agent-conversation-on-track
- Pipecat Flows actions: https://docs.pipecat.ai/pipecat-flows/guides/actions
- Retell global nodes: https://docs.retellai.com/build/conversation-flow/global-node
- Rasa conversation repair: https://rasa.com/docs/rasa-pro/concepts/conversation-repair/

**Claude**
- Agent SDK (Python): https://code.claude.com/docs/en/agent-sdk/python
- Custom tools: https://code.claude.com/docs/en/agent-sdk/custom-tools
- Hooks: https://code.claude.com/docs/en/agent-sdk/hooks
- Cost tracking: https://code.claude.com/docs/en/agent-sdk/cost-tracking
- Structured outputs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- Prompt caching: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
