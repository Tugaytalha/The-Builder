# final-case-c: persona test of build 4 (11 Oct, 19:45 UTC)

For the builder owner. The same 50 callers as in `final-case-persona-test.md` and `final-case-b-persona-test.md`, run against build 4, the submitted one. Same method: Haiku callers on the chat route, Sonnet judges, the same rules files.

- **Workflow**: `final-case-c`, `8ee3114d-0d5d-45d6-a44b-168830b30865`, agent `4533c0de-…`, built at `c752e23`.
- **Per call**: `notes/final-case-c-persona-test-calls.md`. "Before" there means build 3.
- **Raw data**: `runs/20261011-final-case-c-persona-test/`.

## Result: build 4 is the best of the three

| | Build 1 | Build 3 | **Build 4** |
|---|---|---|---|
| Pass, all 50 (45 chat + 5 simulation) | 17/50 (34 %) | 6/50 (12 %) | **27/50 (54 %)** |
| Pass, 45 chat calls | 13 | 3 | **23** |
| Critical errors, 45 chat calls | 28 | 1 | 4 |
| Average judge score | 5.1 | 5.3 | **6.7** |
| Happy | 2/4 | 0/4 | **4/4** |
| Edge | – | – | 14/30 chat, 4/5 sim |
| Adversarial | – | – | 5/11 |

### A test limit that affects all three notes

On the chat route the caller sends the first message, and the agent's first turn answers it. In the real simulation the agent speaks first: every simulation transcript opens with the agent. So a caller cannot name a card, ask for a person, or speak English before the agent's first turn.

These findings are therefore mostly artifacts of our test setup, in all three notes:
- the card name in the first sentence is ignored;
- the opening request for an agent is ignored;
- the English opener is missed.

The same findings in later turns are real. Removing the opener-only errors, build 4 passes about 27 of 45 chat calls instead of 23. That is a keyword count, not a judge verdict.

## Fixed since build 3

- Amounts are said in words again ("on iki bin Türk Lirası", "seksen beş euro yirmi sent"). This was build 3's main loss.
- Asking to hear part of the reading again works (p19).
- Angry caller: three calming replies, then "Sizi müşteri temsilcimize aktarıyorum." (p31).
- Everything build 3 got right is still right:
  - success sentences after a write;
  - the debt is read first when `contact.email.get` fails (p11);
  - a mail request to an unregistered address is refused (p47).

## Findings, worst first

### 1. A minus total is read as debt (p10, simulation, critical)

Customer 92311921 has `debtTL.totalDebt` `-1896`, which means the bank owes the customer. Build 4 says:

> "Gelecek dönemler dahil toplam borcunuz bin sekiz yüz doksan altı Türk Lirası."

That drops the sign and reads 1896 as debt. Spec 4.10: "A minus figure means the bank owes the customer; it is never read out as debt." Build 3 left this sentence out; build 1 said "sıfır".

**Fix**: in the no-debt reading, a total of 0 or below is not read as debt. Leave the sentence out, or use the no-debt wording. Add a test with a negative `totalDebt`.

### 2. A spoken full card number gets an extra digit (p08, p16, critical)

The caller says 16 digits ("beş dört yedi sıfır sıfır sıfır sıfır sıfır sıfır sıfır sıfır sıfır dört iki beş üç"). The `caller_said` tool receives `54700000000004253`, which is 17 digits with one zero too many. The agent then says "Bu numarayla eşleşen bir kartınız bulunmuyor".

In p08, the next line "Hayır, başka kartım yok" was then taken as "nothing else" and the call ended.

**Fix**: don't let the model transcribe digits. Pass the raw words to code and convert spoken Turkish digits there: "sıfır" → 0, pairs like "kırk iki" → 42, and so on. Match on the first six and last four only (the data is masked), and accept 15 to 17 digits when those six and four fit one card.

### 3. Cut-day call is back to the normal reading (p43; regression from build 3)

With `now` 9 Oct and `statementDate` 09.10.2026, the agent says "9 Ekim 2026 tarihinde kesilen ekstre…". Spec 4.10: "Hesap kesim tarihiniz bugün, ekstreniz saat 00.00 itibarıyla kesilecek.", then the total debt.

### 4. One figure only is still read in full (p17, p18)

"Sadece asgari ödeme tutarımı söyler misiniz?" and "Son ödeme tarihim ne zaman?" both get the whole reading. Spec 8.5: give that figure once the card is clear, then the offer.

### 5. The e-mail request after the offer is not acted on (p46, p50)

The caller says "Evet, ekstremi e-posta ile gönderebilir misiniz?", or names e-mail in the first sentence. The agent repeats the offer sentence word for word instead of reading the address and asking for the go-ahead.

In p46 the tool even returned `also=email, kind=yes`, and the offer was still repeated. When the request names e-mail, go to the e-mail step (spec 8.5).

### 6. Joint statement shows only one card (p23, p24)

The agent says "Bu kartınız ile bağlı olduğu Yıldız Pratik kartınız aynı ekstreyi paylaşıyor." but not the linked card's last four, week, next closing date and next due date. Spec 7 step 2 reads both cards.

### 7. Statement week choice (p44)

- "Ayın yirmisi olsun" was mapped by the model to week 3, and a preview was made. Spec 7: a day or a date gets the options read again.
- Then "2. hafta", the current week, got "Lütfen evet ya da hayır olarak yanıtlar mısınız?". It should be "nothing needs changing", then the options.

### 8. Smaller ones

- **p12**: the second "kartlarımın listesini okuyabilir misiniz?" was taken as out of scope, and the same transfer question came twice. The caller asked for their own card names; read them.
- **p37**: after "Hayır, devam edelim" (at the out-of-scope question) the whole reading was read again instead of going back to the offer.
- **p38**: after the caller volunteered a PIN, the password warning was said, and then said again on the next turn too. The whole reading was repeated.
- **p22**: a supplementary card got "Bu kart için borç sorgulaması yapamıyorum." The spec wording says there is no eligible card for this and asks for another one.
- **p28**: after the second card's reading, "Başka bir kartınızın borcunu öğrenmek ister misiniz?" was skipped.
- **Minor, most readings**: "-dır/-dir" is missing after the last figure of a currency sentence. The due date now has it.

## Test limits

- **Opener-only findings**: see "A test limit" above.
- **Silence (p39)**: "..." still gets no answer on the chat route. Not settled whether it is the agent or the route.
- **First-turn cases**: p10, p11, p15, p25 and p27 ran through the simulation route and were judged by hand.
