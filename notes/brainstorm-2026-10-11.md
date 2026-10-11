# Brainstorm input: Sunday 11 October, 08:30 UTC (v2, measured)

A review of the repository at commit `5919f73`, for the brainstorming session. It says what we have, what we measured, which ideas pay off before the deadlines, and which decisions we must take.

**Evidence legend.** Every number or claim carries a tag:
- **[M]** measured: from our result files or the platform's own records. The method is named.
- **[E]** estimate: computed from measured inputs. The method is named. Not tested directly.
- **[A]** assumption: plausible, but not measured. Test it before relying on it.

v1 of this file (08:00) had wrong timing numbers ("6–16 min per simulation", "2–4 h per round", "batching 3–4× faster"). They came from the gaps between simulation start times, which include other work. Section 2 has the measured values.

Read this first. Then read:
- `notes/handoff.md`: the builder owner's live state;
- `notes/eval-log.md`: every round and its root causes;
- `notes/platform-spikes.md`: what the platform does;
- `research/builder-harness.md` (Tugay's machine, untracked): background research.

Deadlines (UTC):
- **14:00**: freeze and rehearsal.
- **17:00**: hidden briefs open.
- **20:00**: submission closes.

Platform rule: **one simulation at a time per workspace.** Conversations inside one simulation run in parallel, up to `maxConcurrentCalls` (the kit uses 5).

---

## 1. What we have

### 1.1 The builder (`builder/`): one agent run on tested blocks

`python3 builder/build.py <brief> <tool_api>`:
1. A Python shell starts the trace and a 27-minute watchdog.
2. One Claude Agent SDK run (Opus 5.5) follows the skill `build-phone-agent`. It writes, in a run folder:
   - `ledger.md`: rules and mechanisms;
   - `spec.json`: values;
   - `build_agent.py`: composes `builder/blocks/`;
   - `test_rules.py`.

   Then it runs the checks (ledger, lint, code tests, dry run), deploys through the gate, runs the chat smoke tests and asks the `reviewer` subagent.
3. The shell exports `submission/<slot>.workflow.json` and ends the trace.

Builds take 445–806 s and cost $1.67–2.92 **[M: eval-log, build logs]**.

The phone agent's mechanisms are all proven in `notes/platform-spikes.md`:
- an empty initial node (chat skips the initial code);
- identity answers joined in code, with an engine-run `verify_identity`;
- a negotiation state tool, where code chooses every line and a TTS node speaks it;
- engine-run writes with retry;
- a guard hook for invalid writes;
- `close_call` as an end-of-call tool with baked fields;
- a 13-rule linter.

### 1.2 The evaluation loop (`eval/`)

| Set | Entry | Cases |
|---|---|---|
| dev | `brief-a` | 10 PUB cases |
| dev | `brief-ab` | 3 PUB-B cases |
| dev | `v2-values-a` | 10 cases, other values and other days (`now` override) |
| dev | `edge-a` | 10 generated hard cases, **never scored yet [M]** (DNS outage in round 5) |
| held-out | `v1-raw-a` | 10 cases, raw material |
| held-out | `v3-raw-b` | 3 cases, raw multi-product material |

`run_eval.py` scores each entry with `--reps 3` (plain) and the 5 styles at 1 rep, one simulation after the other.

### 1.3 Scores (`--reps 3` plain; styles at 1 rep) [M: eval/results/*/summary.json]

| Round (builder) | A /10 | A+B /3 | V2 /10 | V1 held-out /10 | V3 held-out /3 | A styles p/c/t/a/w | A+B styles | V2 styles |
|---|---|---|---|---|---|---|---|---|
| baseline (kit example builder) | 8 | 3 | – | – | – | 7/7/6/9/10 | 1/2/2/2/2 | – |
| 1 (1228815) | 10 | 2 | 8 | **10** | **0** | 5/7/7/9/10 | invalid | 5/7/3/6/8 |
| 2 (85fcc69) | 9 | 1 | – | – | – | 10/10/6/6/9 | 1/1/–/–/– | – |
| 3 (998050d) | 8 | 1 | 8 | **8** | **0** | 9/8/8/9/10 | 1/0/1/1/1 | 7/6/5/8/7 |
| 4 (998050d+) | 8 | 2 | 8 | – | – | 10/9/8/10/9 | 3/2/2/2/3 | – |
| 5 / 5b (0fc03e8) | 9 | **3** | 8 | – | – | 9/10/7/10/10 | 3/2/2/3/3 | pieces 8 |

Five fixes made after the round 5 builds are not measured yet. Round 6 is next.

---

## 2. Measurements made for this review

### 2.1 Where the test time goes [M: `GET /api/v2/simulations` + iteration runs, 52 simulations 05:00–08:17 UTC; score logs]

| Measure | Value |
|---|---|
| Queue time from create to the first call | 1–3 s |
| One conversation (call), median per simulation | 28–112 s (mostly 30–60 s) |
| Calls running at the same time inside one simulation | always 5, which is `maxConcurrentCalls` |
| One 10-case simulation, start to end | 1.5–3 min (up to 8.5 min when the agent model was slow, 07:00–07:45) |
| One 3-case simulation | 1–2 min |
| Gap between two simulations of one scoring run | 20–40 s more than the simulation itself |
| A full dev round: 3 entries × (3 reps + 5 styles) + edge-a 3 reps = 27 simulations | about 60 min of scoring, plus builds of 8–13 min that run in parallel before it |
| `reference-agent` simulations (`ref-brief-a/b`, agents `76ed8678`, `282c9130`) during round 5b | 10 simulations between 05:54 and 06:16. The 5b A+B scoring took about 38 min against about 16 min without them, with 19 "another simulation is running" waits: **about 20 min lost** |

So the slot itself is not slow. A round is slow because it runs about 27 small simulations one after another. The handoff's "another agent (`76ed8678…`, not ours)" is **ours**: the hand-built `reference-agent/` on Tugay's machine (`.freya-agents.json`, slot `ref-brief-a`). It has run no simulation since 06:16.

### 2.2 One run against three runs [M: every `--reps 3` result file, 128 case-slots]

| Measure | Value |
|---|---|
| Pass rate of single runs | 0.846 (0.861 without round 2's judge outage run) |
| Pass rate when all 3 runs must pass (the final's rule) | 0.734 (0.788 without round 2) |
| Ratio, 3-of-3 to single | about 0.87–0.92 |
| Cases that passed 1 or 2 of 3 runs | 24 case-slots: brief-a 14, v2 4, v3 3, brief-ab 2, v1 1 |

Consequence **[E]**: a score measured at 1 rep overstates the final's 3-of-3 score by about 8–13%.

### 2.3 Speech styles [M: style result files of rounds 3, 4, 5, 5b; 1 rep each]

| Style | Passed |
|---|---|
| talkative | **33/49 = 0.67** |
| corrects | 37/49 = 0.76 |
| pieces | 50/59 = 0.85 |
| asks_back | 42/49 = 0.86 |
| in_words | 43/49 = 0.88 |
| *all styles* | 0.69 (58 runs over all rounds) |

| Entry, all styles | Passed |
|---|---|
| brief-a (the brief the fixes were developed against) | 136/150 = **0.91** |
| v2-values-a (the same rules with other values and other days) | 41/60 = **0.68** |
| brief-ab (multi-product) | 28/45 = **0.62** |

Two consequences:
1. **There is a generalization gap of about 23 points [M].** The builder does much better on the brief we tune against than on the same brief with other values. The hidden briefs are "other values" at least.
2. **[E] An estimate of the final.** If the hidden briefs behave like V2 and A+B (0.62–0.68 at 1 rep) and 3-of-3 removes about 10%, a hidden-like case passes with about 0.56–0.61, which is about 34–37 of 60. This rests on assumption [A]: the final's customers use these 5 styles about as often as our style runs do.

### 2.4 Recurring failure classes on dev, rounds 5 and 5b [M: `all_rows[].failed`]

| Class | Seen in | Possible fix status |
|---|---|---|
| "Are you a robot?" during negotiation got "Sorry, please go on." | A PUB-04 (plain, 1 of 3 runs, and pieces), V2 PUB-04 | Maybe fixed by 3e76500, not measured |
| Talkative: the call ends with no outcome (empty turn, customer hangs up) | A talkative PUB-01, PUB-04 | Maybe fixed by 317d3e5, not measured |
| Talkative: identity closed as `declined`, not `failed` | A talkative PUB-03 | Open |
| A correction in a multi-product message recorded the wrong day | A+B corrects PUB-12 | Open |
| An amount in pieces recorded partly (400 against 1250) | A pieces PUB-04 | Maybe 3939bb6 (worked in 1 of 2 chat tests) |
| Read-back loop until the turn cap | V2 PUB-06 | Maybe fixed by e3f7897 |
| Identity closed as `unclear` | V2 pieces PUB-08 | Open |

### 2.5 Things not measured

| Item | Status |
|---|---|
| Build-to-build variance (same commit, two builds) | **No data.** `builder/` changed between every pair of rounds (for example `ac699da..998050d` changed `patterns.py`), so no pair of rounds is a clean repeat |
| Effect of `maxConcurrentCalls` above 5 on the agent model's speed | No data **[A]** |
| V3 on the current builder | Last measured in round 3 |
| Identity questions other than date of birth and phone | Not testable on the practice bank. The only evidence that they come is the kit's own `run_cases.py`, which has persona lines for `postcode`, `birth_year`, `company_number` and `founded_year` **[M: file]**. Whether a hidden brief uses them is **[A]** |

---

## 3. Our ideas, judged against the current system and the measurements

| Idea | Verdict | Reason |
|---|---|---|
| **Multi-agent red team / jailbreak agent** | Small, offline only. Do not build a separate system | Prompt injection is one behaviour among many. Structure already blocks most of it: no debt data before identity, writes engine-run and guarded, the model cannot change an offer. `edge-a` already has prompt-injection and scam cases (PUB-04, PUB-09) and has never been scored, so scoring it is the cheap version of this idea. The measured weak points are talkative, corrects, multi-product and other values, not jailbreaks **[M 2.3]**. |
| **GAN-style loop (an attacker against our agent, repeated)** | Not before the deadline | One full dev round costs about 60 min of the only slot **[M 2.1]**: only a few rounds fit before the 14:00 freeze. An attacker loop needs several rounds to be worth anything. An unconstrained attacker also finds attacks that no scripted customer makes. |
| **Test-case generator agent** | **Yes. It exists: extend it** | `gen_edge_cases.py` writes new cases on the PUB customers and checks `expected` with a second model. Point it at the weak areas: multi-product (A+B bases) and other values (V2), because that is where the measured gap is **[M 2.3]**. |
| **Agents that speak in styles** | **Yes. Measure talkative and corrects at 3 reps before adding styles** | The 5 kit styles are the organizers' simulator styles. Talkative (0.67) and corrects (0.76) are the weakest **[M]**. Add combined styles only after that. |
| **A free or fast LLM, or Freya's LLM, as the customer** | First use Freya's own simulator better (section 5). For our own chat simulator, use the final's model `gemini-3-flash-preview`, or Haiku | The final's persona and judge run `gemini-3-flash-preview` **[M: kit/freya.py SIM_LLM]**. Free models: rate-limited, other behaviour. `experimental-5` is the phone agent's model, and it slows the shared GPU. |

---

## 4. Ranked actions

Value is the expected effect on the hidden score. **All value and effort cells are [E]**, from the measurements in section 2.

### 4.1 Quick wins (under 1 hour)

| # | Action | Value | Effort | builder/? | Evidence |
|---|---|---|---|---|---|
| Q1 | Keep the slot for the eval runner: no `ref-brief-*` simulations, one person schedules simulations. Tell the builder owner that `76ed8678` is ours | About 20 min per round when both run **[M 2.1]** | 5 min | no | 2.1 |
| Q2 | Score `edge-a` in the next round (never scored) | Finds failures in 10 hard cases, about 2 min of slot time | 0 | no | 1.2 |
| Q3 | Targeted reruns for fix verification: `--only PUB-xx`, and a style only where it failed | Saves most of the 60 min per round for single fixes | 0 | no | 2.1 |
| Q4 | Two builds per hidden brief, a selection rule fixed in advance (section 7) | Protects against an unlucky build. Size unknown: variance not measured **[2.5]** | 30 min | no | – |
| Q5 | 16:30 preflight list: login, `.venv`, env, pytest, contamination, empty `traces/` and `submission/`, commit id | Avoids losing the 17:00 start | 15 min | no | – |
| Q6 | `alnum(n)` identity kind (letters and digits, joined across turns, upper case, no spaces), with unit tests | Large *if* a hidden brief asks for a postcode or company number **[A]**, else nothing | 45 min | yes | 2.5 |

### 4.2 Real difference-makers (pick at most two)

| # | Action | Why, with evidence | Effort | builder/? |
|---|---|---|---|---|
| D1 | **Close the generalization gap.** Design the next fixes from V2 and A+B failures, not from A's (A is at 0.91, V2 at 0.68, A+B at 0.62). Add more dev material that is *not* Brief A: run `gen_edge_cases.py` on V2 and on A+B bases | The hidden briefs are "other values" at least; the gap is 23 points **[M 2.3]** | 1–3 h | yes (fixes) |
| D2 | **Talkative and corrects first.** They are the weakest styles (0.67, 0.76) **[M]**. The final's customers "talk like people". Verify the pending talkative fixes (317d3e5, 3e76500, 3939bb6) and then fix the open classes in 2.4 | 2.3, 2.4 | 1–2 h | yes |
| D3 | **Renew the held-out set.** After round 6 measures V3, move V3 to dev so we may read its failures. Write a new held-out V4 (raw material, multi-product, other values) in a session that does not edit `builder/`. V3 was 0/3 twice, and multi-product raw material is the form we fear most | 1.3 | 1.5 h | no |
| D4 | **Measure build variance once:** two builds of V2 from the same commit, each scored plain at 3 reps (3 simulations × about 2.3 min, so about 7 min of slot time per build) | Tells us whether Q4 matters, and the rebuild-verification risk **[2.5]** | 30 min of work + about 15 min of slot | no |
| D5 | **Batched scoring:** one simulation per entry with every case × style × rep as its own persona, each with its own practice session | **[E]** Saves about 25% of slot time at concurrency 5 and up to about 60% at 10, *if* the agent model stays fast at 10 **[A, 2.5]**. Its real use is to make styles at 3 reps affordable: about 345 calls for the 3 dev entries. The current way is 45 simulations × 1.5–2.3 min plus about 0.5 min of gap each, so 90–110 min. Batched: about 52 min at concurrency 5 (69 waves × about 45 s), about 26 min at 10. Not a must if we score only what we fix (Q3) | 1–1.5 h | no (`eval/`) |

### 4.3 Not now

A hosted mock bank, a local Freya engine copy, a GAN loop, an architecture change, new styles beyond combinations. No `builder/` change after the 14:00 freeze except a crash fix. No fixes designed from held-out failures.

---

## 5. Making tests faster (measured basis in 2.1)

| Option | Gain | Fidelity | Effort | Risk |
|---|---|---|---|---|
| **B0. One slot owner, no other simulations** | About 20 min per round when both run **[M]** | Same | none | – |
| **B3. Score only what a fix touches** (`--only`, one style) | Most of a 60-min round, per fix | Same | none | Can miss regressions; keep one full round as a checkpoint |
| **B1. Batched simulation** (D5) | 25–60% of slot time **[E]** | Same as the final: Freya's engine, `experimental-5`, the gemini persona and judge | 1–1.5 h | Above concurrency 5 untested **[A]**. Watch the "slowest agent turn" median that `run_cases` prints, and stay at 8–10 or below ("do not load-test"). Do not use `runsPerPersona`: it would reuse one practice customer for several calls and mix the ledgers |
| **B2. Our own customer simulator over the chat API** | Runs outside the slot | Real engine and model; our own persona and judge | 2 h | Chat-route quirks (502 on the last turn, initial code skipped: both known). Chat-route parallelism is unknown **[A]** |

The customer model for B2, best first:
1. `gemini-3-flash-preview`, the final's model, through a paid Google AI Studio or OpenRouter key; cents per round.
2. Claude Haiku 5.5.
3. A free OpenRouter model: smoke tests only.
4. Never `experimental-5`.

---

## 6. Proposed plan for today (3 workers: builder owner, Tugay, Claude)

| UTC | Builder owner (`builder/`) | Tugay + Claude (`eval/`, notes; no `builder/` while builds run) |
|---|---|---|
| 08:30–08:45 | – | Q1. Brainstorm: decide 8.1–8.6 |
| 08:45–10:00 | Round 6 as planned (held-out + styles, about 75 min) | Write V4 (D3) in a separate session. Run `gen_edge_cases.py` on V2 and A+B bases (D1 material). Optional: D5 |
| 10:00–12:00 | Fixes from round 6, weighted to V2, A+B, talkative and corrects (D1, D2). Q6 if decided. Targeted reruns (Q3) | D4 variance check when the slot is free. Q4 runbook and selection script. Q5 preflight list |
| 12:00–14:00 | More fixes, verified with targeted reruns and `persona_sim`; round 7: full dev + V4 held-out, checkpoint | Read the round 7 results; prepare the freeze notes |
| 14:00–15:30 | Freeze (Task 16): tests, contamination, rehearsal on V4 (and V1) with two builds each, as if hidden; reviewer pass | Check the rehearsal traces against the submit rules; key grep |
| 15:30–17:00 | Merge to `main`, push, note the commit id | 16:30 preflight |
| 17:00–20:00 | 2 builds × 2 hidden briefs. Crash fixes only. Select, commit, push, send the form | Watch time, traces and keys; fill in the form |

---

## 7. Hidden-brief protocol additions (decide before 17:00, then do not change)

1. **Two builds per brief in parallel,** from the frozen commit. `build.py` names the slot, trace and export after the brief file, so build from copies `briefs/hidden-<n>a.md` and `briefs/hidden-<n>b.md`, each with its tool API file. Check in the 14:00 rehearsal that four parallel agent runs do not hit a rate limit **[A]**.
2. **The selection rule, written before 17:00:**
   1. Every loop-1 check green.
   2. Fewer confirmed reviewer defects left.
   3. If the hidden tool API and identity questions match the practice bank: score both with the same generated cases on PUB customers, if the platform's evening limit allows it.
   4. Otherwise, the shorter build time.
3. **Submit the chosen run's own export and trace.** The form takes any path, so do not rename files and never mix two runs.
4. **After 17:00:** crash fixes only. Nothing from a hidden brief goes into `builder/`.

---

## 8. Decisions for the brainstorm

1. **Fix priority.** Weight the next fixes to V2, A+B, talkative and corrects (D1, D2), rather than to Brief A failures? (Recommendation: yes, because of the measured 23-point gap.)
2. **Held-out.** Move V3 to dev after round 6 and write V4 as the new held-out? Who writes V4, in a session without builder access?
3. **The `alnum` identity kind** (Q6): in or out? Cheap, but its value rests on an assumption.
4. **Two builds per hidden brief** (Q4) and the selection rule: yes or no? D4 tells us how much it matters.
5. **Batched scoring** (D5): build it, or stay with targeted reruns (Q3) plus one full checkpoint round?
6. **Slot owner:** who schedules all simulations from now on?
7. **`reference-agent/` and `research/`:** commit to a side branch for the record, or keep them local? The submitted repo should show `builder/` as the builder.

---

## 9. How the measurements were made (to repeat them)

| What | How |
|---|---|
| Simulation timeline | `freya.api("GET", "/api/v2/simulations", workspaceId=…, limit=100, offset=…)`, then for each one `…/iterations` and `freya.get_iteration` (each run's `startedAt`, `endedAt`). Match each simulation to a round through the "Last simulation <id>" line in `eval/results/*/*.score.log` |
| Single run against 3 of 3 | Every result JSON with `runs == 3`: the per-run sums of `all_rows[k][i].pass` against `passed` |
| Style and entry rates | Every `*-<style>.json` of rounds 3, 4, 5, 5b: sums of `passed` and `total` |
| Failure classes | `all_rows[].failed` of rounds 5 and 5b (dev entries only; held-out failures were not read) |
