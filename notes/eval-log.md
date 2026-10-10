# Evaluation log

One row per measurement. Scores with `--reps 3` count a customer only when all three runs pass.

| time (UTC) | builder commit | brief | test | score | notes |
|---|---|---|---|---|---|
| 2026-10-10 23:21 | 6bfd4ea | A | kit cases, `--reps 3` | 6/10 (runs 7, 8, 7) | First build: 293 s, $1.67. Baseline 8/10. Fails: PUB-10 0/3 (bank 500 on create_promise, model did not retry, goodbye loop to the turn cap), PUB-06 0/3 (floor offered again after a question back), PUB-03 1 fail (answer with a complaint not sent to verify_identity), PUB-01 1 judge "no verdict". Fixes in 1228815: engine-run write with retry, goodbye router, offer-repeat rule, identity rule, tool-result words. |
