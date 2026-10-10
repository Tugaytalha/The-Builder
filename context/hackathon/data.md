<!-- Source: https://www.freyavoice.ai/hackathon#data — fetched 2026-10-10 -->

## Thirteen practice cases and the kit

Everything here is synthetic. The bank, the customers, the debts and the payments do not exist.

[Download the kit (version 3)](https://www.freyavoice.ai/hackathon/build-the-builder-v3.zip)

Unzip it and read `README.md` first. The kit has a version number in its file name and at the top of `README.md`. To run it you need a Freya API key. Create one in your Freya workspace under API keys.

| File | What it is |
| --- | --- |
| briefs/brief-a.md | Freya Bank's specification for customers who are late on one product. 47 rules. |
| briefs/brief-b.md | The extra rules for customers with up to three products. Builds on Brief A. |
| tools/openapi.json | The bank's tool API that the phone agent calls. Seven tools: `verify_identity`, `get_account`, `create_promise`, `add_note`, `schedule_callback`, `transfer_to_agent`, `close_call`. |
| public-test-set.json | The thirteen cases below: who the customer is, what they do and what the bank's records must show afterwards. |
| docs/ | The Freya workflow format, tools and code nodes, and the API calls a builder needs. Written for a program to read. |
| freya.py | A small client for the Freya API. Creates a workflow once and updates it on later runs. Standard library only. |
| examples/base-agent.json | An example phone agent: two steps, four tools. The same one that is in your workspace. A place to start, not a good score. |
| examples/agent\_builder.py | An example builder on the Claude Agent SDK with one skill. Claude reads the brief, builds the agent, tests it and fixes what fails. |
| env.example | The two keys you set: your Freya API key, and a team key you make up for the practice bank. |
| tools/run\_cases.py | Runs the practice cases against your phone agent and prints pass or fail per case, with the reason. |

### How one case runs

The mock bank API stands in for the bank's own systems. The phone agent calls it to check identity, read the debt and record a promise. We host it, so we can see what was really recorded. The scorer reads that record, not what the phone agent says it did. You pick a team key, and your practice sessions and their records belong to that key.

Diagram (as text):

```
Simulated customer  --conversation (text, not audio)-->  The phone agent (your builder made)
  follows the case script                                  |
                                                           | tool calls
                                                           v
                                                   Mock bank API (identity, debts, promises; we host it)
                                                           |
                                                           v
                                                   Ledger (every call and its result)
                                                           |
                                         final state + transcript
                                                           v
                                                   Scorer (pass or fail per case)
```

### Practice cases

Ten cases use Brief A and three use Brief B. Every case runs on Wednesday 14 October 2026 at 11:00, so the dates are fixed. The details of each case follow the table.

| Case | Brief | Family | What happens | Level |
| --- | --- | --- | --- | --- |
| PUB-01 | A | Happy path | Confirms identity and pays the full amount today | easy |
| PUB-02 | A | Third party | A relative answers | medium |
| PUB-03 | A | Identity | Three wrong answers | medium |
| PUB-04 | A | Dates | Wants a date after the deadline | medium |
| PUB-05 | A | Hardship | Lost his job, declines the support team | medium |
| PUB-06 | A | Amounts | Full amount is too much, accepts the floor | hard |
| PUB-07 | A | Dates | A vague period, then a holiday | hard |
| PUB-08 | A | Already paid | Says she already paid | medium |
| PUB-09 | A | Restructuring | Asks for a new payment plan | medium |
| PUB-10 | A | Tool failure | The promise service fails on the first call | hard |
| PUB-11 | B | Multi-product | Three products, one date for all | medium |
| PUB-12 | B | Multi-product | Promises one product, refuses two | hard |
| PUB-13 | B | Multi-product | One date for both, but the deadlines differ | hard |

#### PUB-01 — Confirms identity and pays the full amount today

- **Customer:** Mr Daniel Reyes
- **Late products:**
  - credit card ending 4821: $420.00 past due, 6 days late, floor $126.00
- **What happens:** Confirms he is Daniel Reyes. Date of birth 14 March 1988, last four digits 4471. Says he can pay the full amount today. Confirms at the read-back.
- **Bank records after:**
  - closed as promise
  - promise on the credit card: $420.00 on Wed 14 Oct 2026
- **Also checked:**
  - both security questions passed before get_account
  - the word 'collections' is not said before identity is verified
  - create_promise called exactly once
  - text-message sentence said after the promise

#### PUB-02 — A relative answers

- **Customer:** Ms Maria Costa
- **Late products:**
  - personal loan: $310.50 past due, 11 days late, floor $103.50
- **What happens:** The person who answers is her husband. Asks what the call is about and offers to pay himself. Says Maria can be reached tomorrow morning around eleven.
- **Bank records after:**
  - closed as not_reached / callback
  - callback on Thu 15 Oct 2026 at 11:00
  - no promise
- **Also checked:**
  - the agent does not say why it is calling and names no product, amount or debt
  - verify_identity and get_account never called
  - callback scheduled for the next business day at 11:00

#### PUB-03 — Three wrong answers

- **Customer:** Mr Owen Park
- **Late products:**
  - credit card ending 0377: $95.00 past due, 4 days late, floor $28.50
- **What happens:** Confirms the name. Gives date of birth 12 July 1991, then 21 August 1992, then 21 July 1990. Gets annoyed and asks how much he owes.
- **Bank records after:**
  - closed as not_verified / failed
  - no promise
- **Also checked:**
  - the check ends after the third wrong answer
  - no amount or product disclosed
  - customer told to use the app or a branch

#### PUB-04 — Wants a date after the deadline

- **Customer:** Ms Lena Hoffmann
- **Late products:**
  - car loan: $1,250.00 past due, 14 days late, floor $400.00
- **What happens:** Verified. Says her salary arrives on 6 November and she can pay then. Asks whether she is talking to a robot. Accepts the latest possible date when it is offered.
- **Bank records after:**
  - closed as promise
  - promise on the car loan: $1,250.00 on Fri 23 Oct 2026
- **Also checked:**
  - her own date is not counted as a refusal
  - promise date is the late-band deadline, 23 October
  - agent says it is a digital assistant when asked

#### PUB-05 — Lost his job, declines the support team

- **Customer:** Mr Tomas Novak
- **Late products:**
  - personal loan: $780.00 past due, 21 days late, floor $260.00
- **What happens:** Verified. Says he lost his job last month and cannot pay anything. Asks for a discount. Does not want to be transferred.
- **Bank records after:**
  - closed as no_promise / hardship
  - no promise
- **Also checked:**
  - one sentence of sympathy
  - no persuasion attempt although the band is late
  - support team offered once
  - no discount, waiver or plan offered

#### PUB-06 — Full amount is too much, accepts the floor

- **Customer:** Ms Priya Nair
- **Late products:**
  - credit card ending 1903: $2,125.10 past due, 12 days late, floor $637.50
- **What happens:** Verified. Says the full amount is too much right now. If asked how much she can pay, says 'you tell me'. Accepts the minimum payment for this Friday.
- **Bank records after:**
  - closed as promise
  - promise on the credit card: $637.50 on Fri 16 Oct 2026
- **Also checked:**
  - agent never asks how much she can pay
  - minimum payment offered once, with the note that the rest stays overdue
  - promise for 637.50 on Friday 16 October

#### PUB-07 — A vague period, then a holiday

- **Customer:** Mr Samuel Ortiz
- **Late products:**
  - personal loan: $540.00 past due, 5 days late, floor $180.00
- **What happens:** Verified. Cannot pay today. Says 'the week after next'. When asked for the exact day, says Monday the 26th. Accepts the next business day when it is offered.
- **Bank records after:**
  - closed as promise
  - promise on the personal loan: $540.00 on Tue 27 Oct 2026
- **Also checked:**
  - agent asks once for the exact day
  - the agent does not accept 26 October and offers the next business day
  - promise recorded for Tuesday 27 October, inside the early-band deadline

#### PUB-08 — Says she already paid

- **Customer:** Ms Hannah Schmidt
- **Late products:**
  - credit card ending 5512: $180.00 past due, 5 days late, floor $54.00
- **What happens:** Verified. Says she paid it in the app this morning.
- **Bank records after:**
  - closed as paid
  - no promise
- **Also checked:**
  - agent says payments can take one business day to appear
  - no promise recorded

#### PUB-09 — Asks for a new payment plan

- **Customer:** Mr Victor Ionescu
- **Late products:**
  - personal loan: $2,100.00 past due, 28 days late, floor $700.00
- **What happens:** Verified. Says he cannot pay this amount and wants lower instalments.
- **Bank records after:**
  - closed as transferred / restructuring
  - transfer to restructuring
  - no promise
- **Also checked:**
  - transfer_to_agent called with queue restructuring
  - agent does not describe a plan of its own
  - no promise recorded

#### PUB-10 — The promise service fails on the first call

- **Customer:** Ms Grace Lin
- **Late products:**
  - credit card ending 7740: $365.00 past due, 8 days late, floor $109.50
- **What happens:** Verified. Cannot pay today. Agrees to pay the full amount this Friday and confirms.
- **Bank records after:**
  - closed as promise
  - promise on the credit card: $365.00 on Fri 16 Oct 2026
- **Also checked:**
  - exactly one promise in the ledger after the retry
  - agent does not say 'recorded' before a successful call
- **Injected fault:**
  - create_promise fails its first 1 call

#### PUB-11 — Three products, one date for all

- **Customer:** Ms Sofia Almeida
- **Late products:**
  - credit card ending 2288: $220.00 past due, 9 days late, floor $66.00
  - personal loan: $640.00 past due, 9 days late, floor $213.00
  - car loan: $75.00 past due, 3 days late, floor $25.00
- **What happens:** Verified. Cannot pay today. Agrees to pay all three this Friday. Confirms once.
- **Bank records after:**
  - closed as promise
  - promise on the credit card: $220.00 on Fri 16 Oct 2026
  - promise on the personal loan: $640.00 on Fri 16 Oct 2026
  - promise on the car loan: $75.00 on Fri 16 Oct 2026
- **Also checked:**
  - all three products stated before any ask
  - one read-back and one confirmation for all three
  - one create_promise per product

#### PUB-12 — Promises one product, refuses two

- **Customer:** Mr Marcus Bell
- **Late products:**
  - credit card ending 9015: $510.00 past due, 16 days late, floor $153.00
  - personal loan: $1,320.00 past due, 16 days late, floor $440.00
  - car loan: $140.00 past due, 7 days late, floor $46.00
- **What happens:** Gives the date of birth correctly. Gives last four digits 4401 first, then 4410. Will pay the credit card tomorrow. Flatly refuses to pay the personal loan or the car loan, whatever is offered.
- **Bank records after:**
  - closed as promise
  - promise on the credit card: $510.00 on Thu 15 Oct 2026
  - note on the personal loan: refused
  - note on the car loan: refused
- **Also checked:**
  - the phone question is asked again once, the date of birth is not
  - exactly one promise, on the credit card
  - one 'refused' note for each of the other two products
  - two attempts on the personal loan (late band), one on the car loan (early band)

#### PUB-13 — One date for both, but the deadlines differ

- **Customer:** Ms Elena Rossi
- **Late products:**
  - credit card ending 6604: $300.00 past due, 4 days late, floor $90.00
  - personal loan: $900.00 past due, 20 days late, floor $300.00
- **What happens:** Verified. Cannot pay today. Wants to pay both on 30 October. Accepts when told the loan has an earlier latest date.
- **Bank records after:**
  - closed as promise
  - promise on the credit card: $300.00 on Fri 30 Oct 2026
  - promise on the personal loan: $900.00 on Fri 23 Oct 2026
- **Also checked:**
  - credit card recorded on 30 October (early band, inside its deadline)
  - loan recorded on its own deadline, 23 October
  - the read-back names both dates
