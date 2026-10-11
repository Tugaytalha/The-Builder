# Multi-product review (11 October 2026, 16:00–16:40 UTC)

This review is read-only: it changed no `builder/` file. It asks why the phone agents look weak on multi-product cases (Brief B, V3). It has three inputs:

- the transcripts of 72 failed multi-product calls (rounds 1–6, 5b, the rehearsals), plus 117 A and B calls from the rehearsals for timing;
- a code review of `builder/blocks/patterns.py`, the skill, and the policy code inside `submission/brief-ab.workflow.json` and `submission/v3-raw-b.workflow.json`;
- an audit of the cases and their expected values.

Line numbers are at commit `e12bd58`.

## Summary

1. **Much of the measured B weakness is measurement noise.**
   - Since round 5b, no multi-product failure came from product order, bands, attempt counts, notes or the single read-back. Round 5b plain was 9/9.
   - The last two B scores (1/3 at 14:19, 0/3 at 15:00) are 3 cases each, from one run.
2. **Two failures that the handoff calls "platform" are our own design** (see the label fixes below).
   - The `close_call` fields are not set when a customer hangs up.
   - After the final "yes", the agent is silent while it writes.
3. **The engine has generic defects that the 3 official B cases never trigger.**
   - Local runs of the exported agents reproduced them (`eval/repro_multi_product.py`).
   - A hidden case with a correction at the read-back, a product named by its type, or "all of them today" will hit them.

## 1. Agent defects, by expected impact

| # | Defect | Where | Evidence | Fix idea | Risk |
|---|---|---|---|---|---|
| D1 | **`close_call` is not set when the customer hangs up during the flow.** The model fills the fields itself (`"UNKNOWN"`, `"PTP"`, free text), and the bank rejects them. | `close_sequence` sets `close_result` / `close_code` only on the close path (`example/build_agent.py:299`, `:354`) | 10 of 10 customer hang-ups in A and B, including the frozen build (A PUB-06 `9da9acbd`). In B `833bd090` and `bb217265`, every promise was right; **outcome was the only failed check**. | Set the close values after each successful write (`promise`). Set a safe default at setup (`close_reason = 'none'`). | medium; also helps A |
| D2 | **Silent write chain after "Yes, I confirm".** Each product costs 4–5 node hops (code, api, code). At 4–5 s per code exec, 2–3 products give 22–52 s of silence, and the customer hangs up. This grows with the number of products. | `write_loop` / `record_with_retry` (`patterns.py`), "One moment, please." said once | 14:19 PUB-11 `5f431e80`: confirm at 75 s, writes at 93 s and 117 s, hang-up at 135 s. Median of each call's slowest turn: A 11.6 s, B 30.1 s. | Speak a short line between the writes ("I am recording the next one."). Or do all writes in one code node. | medium–high (node change) |
| D3 | **A change at the final read-back goes to the wrong product.** `picked` is searched only among open items. At the read-back no item is open, so the fallback is always `items[0]`. | `patterns.py:248-249` | Repro scenario 1: "P2 to the 20th" moved **P1** to the 20th. Scenario 2: a P1 noted `paid` came back as a 300.00 promise. | When `item` is not empty, look it up in **all** items first; use the open items only when `item` is empty. | low |
| D4 | **A stored line is spoken but the item is not marked `asked`.** A later question on that product calls `first_ask`, which spends one more attempt. An early-band product (1 attempt) then ends as `refused` with no refusal from the customer. | `patterns.py:270-271` | Repro scenario 4: P2 went `open` → `refused` (used 2) after a question. | Add `todo[0]['asked'] = 'yes'`. | low |
| D5 | **No product resolver.** Only an exact id matches. Any other name falls back to the first open item. Two entries that fall back to the same item: one is lost. | `patterns.py:248-249`; the `item` description at `:322` | Repro scenario 5: "personal loan paid" (`item='personal_loan'`) noted the **credit card** as paid. | Match the id, the type and the words case-insensitively. In the `item` description, say: "the product id exactly as in ACCOUNT, also at the read-back". | low |
| D6 | **A "yes" at the read-back sent as `accepts` re-agrees a stale offer.** It depends on the build: v3 had it, brief-ab has a workaround. | `decide()` in the policy; the engine calls it before `finish` | Repro scenario 3 on v3-raw-b: an agreed 250 on 19 Oct went back to 300 on 16 Oct. | In the engine: when no item is open, the read-back was shown, and the answer is `accepts` with no day and no amount, count it as `confirms` and do not call `decide`. | low |
| D7 | **"Yes, all of them today" as one entry agrees only P1.** P2 then gets an attempt-1 offer. | engine plus the `answers` description | Repro scenario 6 | Description: "a yes for all products is one entry per product". Or the engine applies an empty-item `accepts` after the today question to every open item. | low |
| D8 | **A missing date falls back to today** (`day or vars.get('today_iso')`, `pending … or [full, today_iso]` in the generated policies). | per build | Rounds 1/3: about 15 calls recorded today or looped. `54fb6e1` made `date` required, but the fallback remains. | Never default to today: ask for the day again. | low (docs) |
| D9 | **One date for all depends on the model's choice of kind** (`proposes_all` vs one `proposes` per product). | per build | Repro scenario 7 on v3: the memo rule (earliest deadline for all) was skipped; P2 stayed on the 30th. | Document the pattern in `freya.md`. | medium (docs) |
| D10 | **`get_account` has no retry.** An `ok:false` inside a 200 is read as a wrong identity answer. | identity check after code | Rehearsal 2 PUB-12 `74f87f77`: a 10 s timeout, then "I could not record the promise" with no promise discussed. R6 PUB-12 `40173950`. | Retry the read once. Check `ok`, not only `status`. | low–medium |

What works in both exports:
- the today question is asked once;
- each product starts at attempt 1;
- attempts are counted per product (repro scenario 8: three `refused` notes, then the close);
- one combined read-back and one confirmation;
- `create_promise` with a retry, and a `service_error` note;
- after a paid or dispute claim on one product, the call continues;
- no notes on a transfer;
- unrecorded promises are dropped on restructuring;
- the closing precedence.

Fixed already, seen only in old rounds:
- the negotiation model spoke its own offer (about 17 calls, rounds 1–4; fixed in `ca0e8c5`, no case since);
- answers were applied to every product (round 1);
- parallel `customer_said` calls lost updates (fixed in `ac699da`).

## 2. Label fixes for `notes/handoff.md` and `notes/eval-log.md`

| Run | Old label | Verified cause |
|---|---|---|
| 14:19 B PUB-11 (`5f431e80`) | "agent turn 75–78 s, platform" | D2 silent write chain plus D1. The 75 s is the write chain, not a model turn. |
| 14:19 B PUB-13 (`bb217265`) | same | D1 only. Both promises were recorded; `close_call` had `reason:"PTP"`. |
| 15:00 B PUB-12 (`351c3f2f`) | "the scorer's customer gave the right digits first (simulator)" | Harness: the practice session was reused. The bank ledger has 5 `verify_identity` and 2 `get_account` calls; the transcript has 2 and 1. The customer said "4401" and the bank answered `verified:true`. |
| 15:00 B PUB-13 (`9f6923fc`) | test mismatch, `service_error` correct | The test mismatch is true: the V3 memo says one date for all, and the kit expects two dates. **Open:** the ledger shows one `create_promise` (card) and a `service_error` note on the loan, with no failed bank call logged. Read the transcript before you call this correct. |
| Rehearsal 3 B PUB-11 (`833bd090`) | – | D1 only: all 3 promises recorded, `close_call` `{"reason":"UNKNOWN"}` rejected. |

## 3. Latency, multi-product against single-product (rehearsal calls)

| | A (n=73) | B (n=15) |
|---|---|---|
| Agent turns per call, median | 6 | 6 |
| Code executions per call, median | 11 | 22 |
| Slowest turn per call, median | 11.6 s | 30.1 s |
| Call length, median | 48 s | 118 s |
| Silence after "Yes, I confirm" | 9.8 s | 22.4 s (max 52 s) |

The model's think time before a tool call is about the same (median 3.1 s vs 3.6 s). The B delay is the code and node chain, not the prompt size. The kit's example builder had 1–5 s slowest turns on B.

## 4. Test and measurement gaps

- **The frozen builder (`ead33c1`) was never scored on clean `brief-ab`.** The round 5 and 6 `brief-ab` logs hold only DNS tracebacks. The last clean score was round 5 (`0fc03e8`): 3/3.
- **Rehearsal 6 scored V3 with the kit cases** (`eval/results/rehearsal/v3-raw-b-6.json`). PUB-13 can only fail there: the memo moves both products to 23 Oct. Use `eval/cases/v3.json` for V3. The V1 rehearsals 5 and 6 have the same problem on PUB-04 (21 Oct vs 23 Oct).
- **Style checks against fixed checks** (test artifacts, not agent defects):
  - `corrects` PUB-12: the customer corrects in the same message, so there is no second phone ask.
  - `asks_back` PUB-12: the style asks "why" about the date of birth.
  - talkative PUB-12: the judge counted the today question as attempt 1.
- **3 cases are too few.**
  - A case that passes one run 80% of the time passes 3 reps 51% of the time. Three such cases give 0/3 11%, 1/3 37%, 2/3 38%, 3/3 13%.
  - The 95% interval for 1/3 is [0.06, 0.79].
  - About 60 case-runs give ±10 points.
- **Brief B rules that no official case checks:**
  - B8 reasons `hardship`, `dispute`, `paid`, `service_error`, and "no product gets a promise";
  - B9: continue after a paid or dispute claim;
  - B10: restructuring before and after recording, no notes;
  - B11: two failed writes on one product (the practice bank cannot inject it);
  - closing: all paid → `paid`, and the first non-paid reason;
  - a single-product customer under a B agent.
- **Open question (decide before you trust a B score):** Brief B rule 8 says "this also applies when no product gets a promise". Does a B agent write `add_note` for a single-product customer who refuses? The kit's A expectations have `notes: []`, and `score.py` compares notes exactly.

## 5. New cases (this commit series)

| File | Case | Targets | Expected |
|---|---|---|---|
| `eval/cases/multi-b-engine.json` | PUB-11 | D3: a change at the read-back for the car loan only | p1 220 and p2 640 on 16 Oct, p3 75 on 20 Oct |
| | PUB-12 | D7: "all three today" | p1 510, p2 1320, p3 140 on 14 Oct |
| | PUB-13 | D5: "the personal loan is paid" | p1 300 on 16 Oct, note p2 `paid` |
| `eval/cases/multi-b-rules.json` | PUB-11 | B8, B9: paid + dispute + promise | p3 75 on 16 Oct, notes p1 `paid`, p2 `dispute` |
| | PUB-12 | B10: restructuring before recording | no promise, no note, transfer `restructuring` |
| | PUB-13 | B8 + closing: paid + hardship, support declined | notes p1 `paid`, p2 `hardship`; `no_promise` / `hardship` |

All cases use the kit rules (Brief A + Brief B, `now` = Wed 14 Oct 2026). The deadlines are 23 Oct (late band) and 2 Nov (early band); attempt 1 is Fri 16 Oct. Run them on a `brief-ab` agent, not on a V3 agent.

```
# our simulator, scripted (no model customer); outcome checks fail on the chat route (no close_call), read the rest
.venv/Scripts/python eval/persona_sim.py <workflow_id> --cases eval/cases/multi-b-engine.json --mode script --out <dir>
# our simulator, model customer from each case's `script`
.venv/Scripts/python eval/persona_sim.py <workflow_id> --cases eval/cases/multi-b-rules.json --reps 3
# official scorer (closing checks work here)
.venv/Scripts/python eval/run_cases_at.py <agent_id> --cases eval/cases/multi-b-rules.json --brief B --out <file>.json
# local engine repro on an export, no platform
.venv/Scripts/python eval/repro_multi_product.py brief-ab
```

The expected values were computed by hand; no second model checked them. Read the transcript before you call a failure an agent defect.

## 6. Suggested order of work

1. **Low-risk engine fixes, each with a failing test first in `builder/tests/test_patterns.py`:** D3 + D5 (one change at `patterns.py:248-249`), D4, D6, then the D7 description. Run the full suite and `eval/contamination.py`.
2. **D1:** set the close values after each successful write. This also fixes A hang-ups.
3. **D2:** speak between the writes, or write in one node. It changes the node layout: chat-test it first.
4. **Score:** the frozen builder on `brief-ab` (plain, `--reps 3`), then the two new case files. Report the ledger pass and the judge pass apart, with the platform failures marked.
5. **Docs:** `freya.md` step 10 still describes a `cur` index that the engine does not use. Describe the real contract: the policy may read and change `items`; one-kind-for-all (`proposes_all`, a yes to all); keep the `get_account` index if items are sorted; writes happen only after every product is closed. Add the D8 rule (never default a missing day to today).

Not now: a new multi-product worked example (large change).

## Evidence

- Call IDs above. Read one with `.venv/Scripts/python runs/session-tools/txc.py <call_id>`.
- The repro: `eval/repro_multi_product.py` (scenarios 1–8 match D3, D3, D6, D4, D5, D7, D9, and a control).
