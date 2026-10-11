# Evaluation log

One row per measurement. Scores with `--reps 3` count a customer only when all three runs pass.

| time (UTC) | builder commit | brief | test | score | notes |
|---|---|---|---|---|---|
| 2026-10-10 23:21 | 6bfd4ea | A | kit cases, `--reps 3` | 6/10 (runs 7, 8, 7) | First build: 293 s, $1.67. Baseline 8/10. Fails: PUB-10 0/3 (bank 500 on create_promise, model did not retry, goodbye loop to the turn cap), PUB-06 0/3 (floor offered again after a question back), PUB-03 1 fail (answer with a complaint not sent to verify_identity), PUB-01 1 judge "no verdict". Fixes in 1228815: engine-run write with retry, goodbye router, offer-repeat rule, identity rule, tool-result words. |
| 2026-10-11 01:40 | 1228815 | round 1: A, A+B, V2 (dev), V1, V3 (held-out) | `run_eval --round 1 --heldout --styles` | A 10/10, A+B 2/3, V2 8/10, V1 10/10, V3 0/3 | Builds 332–547 s, all exit 0. Styles A: pieces 5, corrects 7, talkative 7, asks_back 9, in_words 10 (/10). V2: 5, 7, 3, 6, 8. A+B styles are not valid: the A+B slot was rebuilt at 00:25 while its styles were scored, so they mix two agents. Lesson: never build a slot while it is scored. Main failure classes (dev): identity under pieces (half answers sent), per-product answers applied to all products, offers said twice, a line from the guide read aloud. Fixed after the round: engine-run identity with joined answers, negotiation engine in the library, write loop. |
