| id | rule | source | mechanism | where |
|---|---|---|---|---|
| A1 | Opening: digital assistant of Freya Bank, call recorded; no collections/debt/payment/product before identity | A3.1 | fixed-line | opening tts, lint |
| A2 | Ask "Am I speaking with {title} {last_name}?"; only clear yes/name confirms; ask twice, then not_reached/unclear | A3.2-3 | route | opening party enum, total_turns |
| A3 | Robot question: Freya Bank's digital assistant, continue | A3.4 | prompt | SYSTEM |
| A4 | Third party: say nothing, ask when reachable | A5, A10 | prompt | third_party |
| A5 | Callback today or next business day, 10:00-19:00, after now; else ask once, then no_callback | A6-7 | code | callback guard_hook, third_party |
| A6 | Wrong number → not_reached/wrong_number; deceased → "I am sorry for your loss." → deceased | A8-9 | route | opening/third_party enum, closes |
| A7 | DOB then phone last4; DOB as YYYY-MM-DD, numbers day-month-year | A11 | code | answer_tool, identity_check |
| A8 | Three wrong in total → app/branch, not_verified/failed | A12,A14 | route | identity_check left=0 |
| A9 | day_month_swapped hint → ask month as a word, not counted | A13 | code | ID_GUIDE |
| A10 | Refusal or "what is it about": explain once; second → not_verified/declined | A15, A45 | code | customer_refuses |
| A11 | get_account after both pass; state each product, amount, days late | A16-17, B2 | code | fetch_account, prepare |
| A12 | Deadline per product: 1-7 days 12th bd, 8-45 days 7th bd; attempts 1/2 | A18, B3, B5 | code | setup, prepare |
| A13 | Promise date today+, business day, ≤ deadline; weekend → next bd; after deadline → offer deadline | A19-20, A23 | code | POLICY decide |
| A14 | Vague period: ask once, then propose deadline | A21 | code | POLICY vague |
| A15 | this/next weekday table | A22 | code | setup date_facts |
| A16 | Full amount first; too much → floor once, rest stays overdue; below floor → offer floor once | A24-27 | code | POLICY |
| A17 | First ask "Can you make this payment today?" / all of them today | A28, B4 | fixed-line | debt_statement |
| A18 | Attempt 1 last bd of week (or next week); attempt 2 late only floor on deadline; no repeated offer | A30-31 | code | POLICY offers |
| A19 | Hardship: sympathy, offer support; yes → support transfer; no → hardship | A32 | code | POLICY hardship |
| A20 | One read-back of all, "Do you confirm?", writes after clear yes | A34-35, B7 | code | finish, write_loop |
| A21 | Write retry once; failed → service_error note / close | A37, B11 | code | write_loop attempts 2, after_writes |
| A22 | After recorded: text message sentence | A38 | fixed-line | close_promise |
| A23 | Paid / dispute on a product: note and continue | A39-40, B9 | code | POLICY, notes |
| A24 | Restructuring → transfer, close transferred/restructuring, no notes | A41, B10 | code | transfer route |
| A25 | Human: ask once, then transfer general | A42 | code | POLICY wants_person |
| A26 | Scam → customer service number; unknown → no info | A43-44 | prompt | SYSTEM |
| A27 | Notes per product without promise; close outcome from notes | B8, B closing | code | after_writes, final_close |
| A28 | One close_call, goodbye before it | A46-47 | code | close_sequence, close_tool |
