<!-- Source: https://www.freyavoice.ai/hackathon#overview — fetched 2026-10-10 -->

# Build the Builder — Freya × Y Combinator

Build an AI agent that builds other agents on Freya. First place gets a Y Combinator interview.
October 10 and 11, online. Solo or in teams of two.

> You build an agent. It builds an agent. We test that agent.

Tabs: Overview · Data · Evaluation · Submit · Leaderboard · Rules · FAQ

## What this is

A bank has customers who are late on a payment. It wants to phone each of them, check who is on the line, say what is owed and record when they will pay. On Freya, software makes that call instead of a person.

> **Phone agent:** Your credit card has 420 dollars past due. Can you pay today?
> **Customer:** Not today. I can do it on Friday.
> **Phone agent:** 420 dollars on Friday the sixteenth. Do you confirm?
> **Customer:** Yes.
>
> `create_promise  420.00  2026-10-16` — *recorded in the bank's system*

A piece of one call. The last line is what the bank's system keeps. We check that record, and we check the conversation.

That software does not know the bank's rules by itself. Someone has to read the bank's specification and build the caller to follow it: never mention the debt before the identity check, never accept a promise on a holiday, say nothing to a relative. Today a person does this by hand, and one bank takes days.

The question of this hackathon: can a program do that work instead?

### Three words used on this page

**Phone agent**
The software that talks to the customer. It lives on Freya as a workflow: steps, prompts and tools.

**Brief**
The bank's specification for these calls: who to ask for, how to check identity, which payment dates are allowed, how to close the call.

**Builder**
The program you write. It reads a brief and creates the phone agent. Nobody edits the phone agent by hand.

You write the builder. We score the phone agent it creates.

Diagram (one run, as text):

```
Brief                 ->  Your builder              ->  Phone agent            ->  Our benchmark
- policies                - reads the brief             - a workflow on Freya      - simulated customers
- tool API docs           - creates the phone agent     - conditional routes       - talk to the phone agent
- practice customers      - tests and improves it       - tool calls               - we read the bank's records
                          (the part you write)                                     - score = cases passed / cases run
```

A new brief goes in, a different phone agent comes out, no edits by hand.

One run. You write the orange box ("Your builder" in the diagram above). Everything else is provided.

### How the weekend goes

Timeline diagram (as text):

| When | What |
| --- | --- |
| Sat 10:00 UTC — Start | Kit and keys. Build against the 13 practice cases. |
| Sun 17:00 UTC — Hidden briefs open | Run your builder. The page marks 17:00–20:00 in orange: these are the "three hours in orange". |
| Sun 20:00 UTC — Close | Submit. |
| After review — Results | |

1. **You download the kit** from the Data tab. Two briefs, the bank's tool API, thirteen practice customers, the Freya workflow reference and a small working builder.
2. **You run the sample builder.** It creates a phone agent on Freya in your workspace.
3. **You test that phone agent.** Simulated customers talk to it in text. You see which ones it handled correctly and why the others failed.
4. **You write your own builder** and repeat steps 2 and 3 as often as you like.
5. **On Sunday we publish briefs you have not seen.** Same kind of call, different rules: other identity questions, other limits and deadlines, another outcome table, another calendar. The seven tool names stay the same. Their fields and allowed values can change.
6. **You run your builder once on each new brief** and submit the phone agents it created, your code and the builder's trace.
7. **We test those phone agents** on customers nobody has seen. The share they handle correctly is your score.

The three hours in orange are for running the builder and fixing bugs, not for tuning it to the new briefs.

### What counts

- **Only the phone agents are scored.** Your rank comes from their score. We also rerun the builders of the top entries to verify them. Build time is the second tie-break.
- **A customer counts as handled** when the bank's records are right afterwards and the conversation followed the brief. There is no partial credit.
- **The builder must work alone.** One command, a brief as input, a phone agent as output. No manual edits after it runs.
- **The final briefs are hidden** so that a builder tuned to the two public briefs does not win. It has to read a brief it has never seen.
- **After the hidden briefs open** you may fix a bug in your builder. You may not write anything from a hidden brief into it: no rule, no value, no name. Fixing a crash on a table your parser did not expect is allowed. Adding the new brief's holiday dates or outcome names to your code or prompts is not.
- **Calls are in English.** The phone agent gets the date and time of the call as a variable, `now`. Every date rule uses it.
- **Every phone agent runs on the same Freya model.** Your builder may use any model or coding agent you like.

### Inside a phone agent

A phone agent on Freya is a workflow. Each step has its own prompt and tools. Conditional routes decide which step takes the conversation next. Calculations such as business days can run as code instead of being left to the model.

Diagram (abstract example): six steps as nodes, each with tools, joined by conditional routes marked "if". Legend: one step · a tool it calls · a route with a condition.

What a phone agent can look like inside. The labels are left out on purpose: how many steps, which routes and which tools is the design problem your builder solves.
