# Handoff: `eval/persona_sim.py` (chat-route customer simulator)

A fast filter that runs without the simulation slot. It talks to a published workflow through `POST /api/v2/chat/message`, plays the customer, and scores the bank's ledger. It is not the official score: the judge is a small model.

## Run

```
source env.sh && unset ANTHROPIC_API_KEY CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SESSION_ID
.venv/Scripts/python eval/persona_sim.py <workflow_id> --cases kit/public-test-set.json --style talkative --reps 3
```

| Option | Use |
|---|---|
| `--style talkative+pieces` | One kit style, or several joined by `+` |
| `--cases eval/cases/injection-a.json` | Injection and scam cases (A: PUB-01..04, 07; A+B: PUB-11, 13), before and after identity |
| `--cases eval/cases/regress-a.json --mode script` | Scripted customers (no model) for past root causes; `regress-ab.json` for A+B |
| `--only PUB-04,PUB-06` | Run chosen cases |
| `--reps 3` | A case passes only when all reps pass |
| `--parallel N` | Default and maximum 8 |
| `--no-judge` | Ledger only |

Results go to `eval/results/sim/<time>/` (git-ignored): `summary.json` and `failures/<case>-rep<n>.txt` with the transcript.

## What it does not do

- The customer is Haiku (`claude-haiku-5-5`), not the final's `gemini-3-flash-preview`. Cut-off talkative messages may look different.
- The judge reads the case `checks` only; it is a hint. Calibrate against `eval/results/5/*.json` before you trust a number.
- The chat route skips the initial code node (empty setup values) and answers 502 on the turn that ends a call (handled).
- Expected values of `injection-*.json` and `regress-*.json` were computed by hand from the briefs; no second model checked them yet. A failing case may be a wrong `expected`: read the transcript first.

## Builder changes for the builder owner (not made here)

1. `builder/blocks/patterns.py:233`: the line `'I understand. ' + ask` is said after a message with no answer. The honesty judge counts an "I understand" after small talk as a sympathy sentence (measured in `reference-agent/README.md`). Brief A allows sympathy only for illness, death or job loss. Use a neutral lead-in or only the question.
2. Identity kinds: the library knows `date` and `digits`; everything else is one `text` answer. `run_cases.py` has persona lines for `postcode`, `birth_year`, `company_number` and `founded_year`, so a hidden brief may ask them. Add an `alnum(n)` kind (letters and digits, joined across turns, upper case, no spaces) with tests.
3. `builder/.claude/skills/build-phone-agent/SKILL.md`, step 3: say how to order raw documents. Sort them by date and authority first; a memo that changes a rule is not marked "old", the date shows it.
4. `reference-agent/README.md` measured the platform turning `$420.00` into `dollars420.00` in text. `example/build_agent.py` `money()` returns a bare number; check that the library writes amounts as `420.00 dollars`.
