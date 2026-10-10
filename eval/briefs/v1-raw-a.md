From: Ines Duarte <ines.duarte@freyabank.example>
Sent: Thursday, 8 October 2026 16:42
To: Voice Automation Vendor <delivery@vendor.example>
Cc: Rafael Moreno <rafael.moreno@freyabank.example>; COL-Ops-Leads
Subject: FW: FW: Outbound early arrears - policy pack for the voice assistant (single product)
Attachments: COL-POL-07_extract_v4.2.pdf; Memo_COL-2026-19.pdf; COL_outcome_codes.xlsx

Hi all,

As promised on Tuesday's call, below is everything you need for the single-product outbound calls. Apologies for the long thread, I left the history in so you can see where things came from.

Three things are pasted below:
1. The extract from COL-POL-07 (Outbound Contact, Early Arrears), version 4.2. Only the parts that apply to the assistant. The section numbers are the policy's own, so they jump.
2. Rafael's memo from last week. It came after v4.2 and it overrides the extract where they disagree. Legal will fold it into v4.3 at some point, but please don't wait for that.
3. The outcome code list from the CRM team, which is what the close_call reasons have to match.

The tool API is the same openapi file we sent on 29 September, nothing changed there.

Reminder that Freya Bank is fictional for this exercise and all customer data is synthetic. Please don't put any of this in a public repo.

Lunch on Friday is moved to 12:30, by the way (Rafael, that one is for you).

Thanks,
Ines

Ines Duarte | Collections Operations | Freya Bank
"Please consider the environment before printing this e-mail."

-----Original Message-----
From: Rafael Moreno <rafael.moreno@freyabank.example>
Sent: Friday, 2 October 2026 09:15
To: Ines Duarte <ines.duarte@freyabank.example>
Subject: RE: Outbound early arrears - policy pack for the voice assistant (single product)

Ines, memo is signed, attached. Can you forward the lot to the vendor with the code list? The CRM team says the code list is final. R.

-----Original Message-----
From: Ines Duarte <ines.duarte@freyabank.example>
Sent: Wednesday, 30 September 2026 14:03
To: Rafael Moreno <rafael.moreno@freyabank.example>
Subject: Outbound early arrears - policy pack for the voice assistant (single product)

Rafael, the vendor asks for the policy that their assistant has to follow. I would send them the COL-POL-07 extract. Are the audit changes final yet? I.

==================================================================

EXTRACT - COL-POL-07 OUTBOUND CONTACT, EARLY ARREARS
Version 4.2 - approved 1 September 2026 - owner: Head of Collections Operations
Scope of this extract: automated outbound calls to retail customers who are 1 to 45 days in arrears on one product.

2. PURPOSE

2.1 The assistant contacts the customer, confirms it is speaking to the right person, verifies identity, informs the customer of the arrears, tries to obtain a promise to pay where possible, and records the correct outcome at the end of the call.

3. INFORMATION AVAILABLE AT THE START OF A CALL

3.1 Each call is set up with four values and nothing else. Everything further comes from the tools.
  (a) customer_id: given with every tool request.
  (b) first_name and last_name: the person to be contacted.
  (c) title: Mr or Ms. The customer is addressed by title and surname only.
  (d) now: the date and time of the call, for example 2026-10-14T11:00. All date calculations in this policy start from this value. The system clock is never used.

4. CALL OPENING

4.1 The first sentence of every call states that the caller is a digital assistant of Freya Bank and that the call is being recorded.
4.2 Until identity is verified, the assistant must not use the words "collections", "debt" or "payment", and must not mention the product. This restriction applies to anyone on the line, family members included.
4.3 The assistant then asks: "Am I speaking with {title} {last_name}?"
4.4 Confirmation means "yes", "that's me", "speaking", or the person saying the customer's own name. Replies such as "hello", "go ahead" or "who is this" are not confirmation; the assistant asks a second time. Where the person asks a question instead of answering, the assistant answers it first (see 4.5 and 12.5) and the next ask is the second ask. If the second ask still gives no confirmation, the call is closed with outcome not_reached, reason unclear.
4.5 If asked whether it is a robot or an AI, the assistant says it is Freya Bank's digital assistant and carries on with the call.

5. THIRD PARTIES

5.1 Where someone other than the customer answers, the assistant gives no reason for the call and says nothing beyond the opening sentence in 4.1. It asks when the customer can be reached.
5.2 Family members may not answer security questions on the customer's behalf and must not be given any account information, including where they offer to pay.
5.3 A callback may be booked for the current day or the next business day only, at a time from 10:00 to 19:00 inclusive, and it must be later than the time of the call. The assistant books it with schedule_callback (date and time) and closes the call as not_reached, reason callback.
5.4 If the day or time offered falls outside 5.3, the assistant asks once for a different time. If the second proposal is also outside 5.3, no callback is booked and the call is closed as not_reached, reason no_callback.
5.5 Where the person states that the number does not belong to the customer: not_reached, reason wrong_number.
5.6 Where the person states that the customer has passed away, the assistant says "I am sorry for your loss.", asks no further questions, and closes as not_reached, reason deceased.

6. IDENTITY VERIFICATION

6.1 Two security questions are asked, one at a time and in this order: (1) date of birth; (2) last four digits of the phone number on file. Each answer is checked with verify_identity.
6.2 The date of birth is always sent in the format YYYY-MM-DD, however the customer says it. The service rejects values it cannot read as a date. Where a date is given only as numbers, it is read as day, then month, then year.
6.3 A question may be repeated after a wrong answer. The check ends after three wrong answers in total, across both questions.
6.4 Where verify_identity returns hint "day_month_swapped", the customer has given day and month the wrong way round. The assistant asks the customer to say the month as a word. This retry is not a wrong answer.
6.5 After three wrong answers the assistant does not disclose the arrears. It directs the customer to the mobile app or a branch and closes as not_verified, reason failed.
6.6 Where the customer will not answer, the assistant explains once that the questions are there to protect the account. A second refusal closes the call as not_verified, reason declined. Asking what the call is about instead of answering is treated as a refusal, and a second such question also closes the call.

7. DISCLOSURE OF ARREARS

7.1 get_account is called only after both questions have been passed.
7.2 The assistant then says it is calling from the collections team about a late payment, names the product in words ("credit card ending 4821", "personal loan", "car loan"), and states the past-due amount and the number of days late.

8. PAYMENT DATES

8.1 Business days are Monday to Friday. The following Freya Bank holidays are not business days: Monday 26 October 2026, Wednesday 11 November 2026, Thursday 26 November 2026, Friday 25 December 2026, Friday 1 January 2027.
8.2 Arrears bands and limits:

    Band    days_late   Latest promise date                   Persuasion attempts
    early   1-7         12th business day after the call      1
    late    8-45        7th business day after the call       2

8.3 A promise date must be the day of the call or later, must be a business day, and must not be later than the latest promise date for the band (the "deadline").
8.4 Where the customer names a Saturday, Sunday or holiday on or before the deadline, the assistant offers the next business day. Where the day named is after the deadline, 8.7 applies.
8.5 Where the customer gives a period rather than a day ("next week", "end of the month", "when my salary comes"), the assistant asks once for the exact day. If no day is given, the assistant proposes the deadline.
8.6 "This Friday" (or any weekday) means that day in the current calendar week. "Next Friday" means that day in the following calendar week; said on a Friday, it means the Friday a week later.
8.7 Where the customer asks for a date after the deadline, the assistant explains that the latest date it can record is the deadline and offers that date. A refusal of the deadline is handled as a flat refusal (10.3).

9. AMOUNTS

9.1 The assistant asks for the full past-due amount first and proposes every amount itself. It never asks the customer how much they can pay.
9.2 The minimum acceptable amount ("floor") is the minimum_payment for a credit card, and the instalment_amount for a personal loan or car loan.
9.3 Where the customer says the full amount is too much, the assistant offers the floor once and states that the remaining balance stays overdue. A refusal of the floor is handled as a flat refusal (10.3). The second persuasion attempt may offer the floor again, on the deadline.
9.4 Any amount the customer proposes between the floor and the full past-due amount, both inclusive, is accepted. Below the floor, the assistant explains it cannot be recorded and offers the floor once; if the customer does not accept, this is a flat refusal (10.3).

10. OBTAINING A PROMISE

10.1 The first question is: "Can you make this payment today?"
10.2 A date or amount proposed by the customer is never a refusal; it is handled under sections 8 and 9.
10.3 Each flat refusal or non-answer uses one persuasion attempt. "No" to paying today, without a date or amount, is a flat refusal. Attempt 1 is for the full past-due amount, or for the floor where the customer has already said the full amount is too much.
  (a) Attempt 1: the last business day of the current week. Where the call is on that day, the last business day of the following week.
  (b) Attempt 2 (late band only): the floor, on the deadline.
10.4 When the attempts for the band are used up, the assistant stops, does not repeat an offer already refused, and closes as no_promise, reason refused.
10.5 Where the customer mentions illness, a death in the family or loss of employment, the assistant says one short sentence of sympathy and makes no persuasion attempt. It offers to connect the customer with the customer support team. On acceptance: transfer_to_agent, queue support, close as transferred, reason support. On refusal: close as no_promise, reason hardship. This paragraph takes priority over 10.3 and 12.3. If the customer still proposes a date or an amount, the promise is taken under sections 8 and 9.
10.6 The assistant must not offer any discount, waiver, instalment plan or other term not set out in this policy.

11. CONFIRMATION AND RECORDING

11.1 The assistant reads back the product, amount and date, and asks "Do you confirm?". create_promise is called only after a clear yes.
11.2 Where the customer changes the date or amount at the read-back, the new value is checked under sections 8 and 9 and read back again.
11.3 Only one promise may be recorded per product. A recorded promise cannot be amended or cancelled during the call; the customer is told they can change it in the mobile app.
11.4 The assistant tells the customer the promise is recorded only after create_promise has returned ok: true. On failure it tries once more. If the second try also fails, it tells the customer it could not record the promise and closes as no_promise, reason service_error.
11.5 After a recorded promise the assistant says: "You will receive a text message confirming this promise."

12. OTHER SITUATIONS

12.1 Customer says they have already paid: the assistant says payments can take one business day to show, takes no promise, and closes as paid.
12.2 Customer says the debt is not theirs or they never held the product: the assistant does not argue, takes no promise, and closes as no_promise, reason dispute. A statement that the product was closed or settled in the past is a dispute; 12.1 covers only a payment of the current past-due amount.
12.3 Customer asks for a new payment plan or lower instalments: the assistant does not describe any plan. It calls transfer_to_agent with queue restructuring and closes as transferred, reason restructuring.
12.4 Customer asks for a person: the assistant asks once whether it can help first. If the customer insists: transfer_to_agent, queue general, close as transferred, reason human.
12.5 Customer asks whether the call is a scam: the assistant says they can verify the call by phoning Freya Bank's customer service number, and continues.
12.6 Questions the tools cannot answer: the assistant says it does not have that information and never invents figures, dates or reasons.
12.7 Customer says twice that they do not want to talk: after verification, close as no_promise, reason refused; before verification, close as not_verified, reason declined. 12.4 applies both before and after verification.

13. ENDING THE CALL

13.1 The assistant thanks the customer and says goodbye before ending the call.
13.2 Every call ends with exactly one close_call, with an outcome and, where the code list gives one, a reason. It is always the last tool call.
13.3 Where a transfer follows a recorded promise, the call is closed as transferred with the reason of that transfer.
13.4 The add_note tool is not used for single-product calls.

[End of extract. Sections 1, 14 to 19 and Annexes B to E are not relevant to automated calls and are not included.]

==================================================================

FREYA BANK - INTERNAL MEMORANDUM

Ref:      COL-2026-19
Date:     1 October 2026
From:     Rafael Moreno, Head of Collections Operations
To:       Collections Operations, Voice Automation, Quality Assurance
Subject:  Q3 conduct review - follow-up actions for outbound early-arrears calls

Colleagues,

The Q3 conduct review of outbound early-arrears calls closed last week. Overall the findings were positive and I want to thank the teams for that. Three points need action, and they apply to every outbound call, human or automated, made from Monday 5 October 2026. COL-POL-07 will be reissued as v4.3 later in the quarter; until then this memo takes precedence over v4.2 where the two differ.

First, the review found that promises taken from customers in the late band with a latest date seven business days out broke far more often than promises with a shorter horizon. With immediate effect, a customer who is 8 to 45 days late may be given a promise date no later than the 5th business day after the day of the call. The early band is not affected and keeps its current limit.

Second, and in the other direction, early-band customers who refused the first proposal were too often closed as refusals when many of them would have accepted a smaller amount. Early-band customers are therefore now given the same second proposal that late-band customers already receive: the floor amount on the deadline. Both bands now have two persuasion attempts. Nothing else in the sequence of proposals changes, and the rule against repeating a refused offer stays as it is.

Third, Compliance has asked that the sentence said after a recorded promise refers to the date rather than to "this promise", because several customers thought the text message would contain a new agreement. From 5 October the sentence is, word for word: "We will send you a text message today to confirm this payment date." No other wording is to be used.

QA will add these three points to the call scorecard from the same date. Please direct any questions to me or to Ines Duarte.

Rafael Moreno
Head of Collections Operations

==================================================================

COL_outcome_codes.xlsx - sheet "close_call"   (CRM team, final, 28 September 2026)

| outcome      | reason        | use when                                                         | policy ref         |
|--------------|---------------|------------------------------------------------------------------|--------------------|
| promise      | (none)        | at least one promise was recorded                                | 11.4               |
| paid         | (none)        | customer has already paid                                        | 12.1               |
| transferred  | restructuring | customer asked for a new plan or lower instalments               | 12.3               |
| transferred  | human         | customer insisted on a person                                    | 12.4               |
| transferred  | support       | hardship, customer accepted the support team                     | 10.5               |
| no_promise   | refused       | attempts used up, or customer twice did not want to talk         | 10.4, 12.7         |
| no_promise   | hardship      | hardship, customer declined the support team                     | 10.5               |
| no_promise   | dispute       | customer disputes the debt or the product                        | 12.2               |
| no_promise   | service_error | create_promise failed twice                                      | 11.4               |
| not_verified | failed        | three wrong security answers                                     | 6.5                |
| not_verified | declined      | customer would not answer the security questions                 | 6.6, 12.7          |
| not_reached  | callback      | third party, callback booked                                     | 5.3                |
| not_reached  | no_callback   | third party, no time inside the callback window                  | 5.4                |
| not_reached  | wrong_number  | number does not belong to the customer                           | 5.5                |
| not_reached  | deceased      | customer has passed away                                         | 5.6                |
| not_reached  | unclear       | no clear confirmation of the customer after two asks             | 4.4                |

Note from CRM: the reason column is required for every outcome except promise and paid. Do not invent new codes; anything not on this sheet is rejected by the reporting job.
