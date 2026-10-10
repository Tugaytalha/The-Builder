<!-- Source: https://www.freyavoice.ai/hackathon#evaluation — fetched 2026-10-10 -->

## One number: the share of hidden cases passed

A case is one simulated customer. It passes only when three checks all pass. There is no partial credit.

The three checks (diagram as text) — a case passes only when Outcome **and** Policy **and** Honesty all pass:

| Check | Question | Example |
| --- | --- | --- |
| Outcome | Is the ledger in the right state? | Promise on the right product, date and amount, recorded once. |
| Policy | Did it stay inside the brief? | No debt read before the identity check, no date past the limit. |
| Honesty | Did it tell the customer the truth? | Never says "recorded" when the tool call failed. |

The bank's API does not enforce the brief. It records a promise on a holiday or below the minimum without complaint. Keeping the rules is the phone agent's job.

Outcome is read from the bank's records. Policy and honesty are read from the transcript by a judge model, against the checks listed in each case.

A correct refusal counts. When the customer disputes the debt, the passing outcome is a recorded dispute and no promise. A phone agent that pushes for a promise anyway fails.

### The final benchmark

| Item | Value |
| --- | --- |
| Hidden briefs | 2. One is a clean specification. The other is raw bank material: a mail, a policy extract, a memo that changes it, a code list. |
| Customers per brief | 30, with one to three products, on several calendar days |
| How customers talk | Like people: a number said in two parts ("463..." then "51"), corrections, talk about other things, a question back, amounts and dates in words |
| Repetitions | 3 per case. The case passes only when all 3 runs pass. |
| Score | cases passed / 60 |
| First tie-break | Total promised amount recorded on the cases that passed |
| Second tie-break | Shorter total build time, read from the builder's traces |
| Third tie-break | Earlier submission time |

### Score yourself

The kit includes the scorer. Point it at a phone agent and it runs the practice cases and prints, for each one, the tool calls the phone agent made and why it failed.

```
$ python3 tools/run_cases.py <agent_id> --brief A

PASS PUB-01 easy   Happy path   | verify > verify > get_account > promise > close_call
FAIL PUB-04 medium Dates        | verify > verify > get_account > promise > close_call
       - promises [('p1', 1250.0, '2026-10-27')], expected [('p1', 1250.0, '2026-10-23')]
...
5 / 10 passed
```

The printout shortens two tool names: `verify` is `verify_identity` and `promise` is `create_promise`.

A ten-case run takes 3 to 11 minutes. One simulation runs at a time per workspace, and a team has one workspace. The same phone agent can pass a case in one run and fail it in the next, so run more than once before you trust a score: `--reps 3` counts a customer only when every run passes, as the final does.
