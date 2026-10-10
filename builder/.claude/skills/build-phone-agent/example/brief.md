# Example brief: Lumen Energy, overdue bills (invented for the builder's worked example)

Lumen Energy is fictional. This brief exists only to show the builder how a brief becomes a workflow. Its rules are not the rules of any real brief.

## Call variables

`client_ref`, `given_name`, `family_name`, `salutation` (`Mx`, `Dr`), `now` (for example `2031-03-05T11:00`).

## Opening

1. First sentence: "Good morning, this is the automated assistant of Lumen Energy." Do not mention a bill, money or an amount before identity is checked.
2. Ask "Is this {salutation} {family_name}?". Only a clear yes or their own name counts. Ask at most twice, then close as `absent` / `unsure`.
3. Someone else: ask for a callback time on one of the next two business days (not today), 09:00 to 17:00. Book it with `schedule_callback` and close as `absent` / `call_later`. If they give no time in the window, close as `absent` / `no_time`.

## Identity

4. Ask the postcode, then the year of birth. Send each answer to `verify_identity`. Two wrong answers in total close the call as `unverified` / `wrong`.
5. A customer who refuses the questions twice is closed as `unverified` / `refused_check`.

## The bill

6. After identity, call `get_account`. Say each overdue item: its kind, the overdue amount, the days overdue.
7. Business days are Monday to Friday except the Lumen holidays 2031-03-10 and 2031-04-18.
8. Deadline: up to 20 days overdue, the 5th business day after today; more than 20 days, the 3rd business day after today.
9. Ask "Could you settle the full amount by the deadline?".
10. A refusal uses one attempt. Up to 20 days overdue: 1 attempt, propose the smallest payment on the deadline. More than 20 days: 2 attempts, first the full amount on the 1st business day after today, then the smallest payment on the deadline. When the attempts are used up, close as `declined` / `said_no`.
11. A customer date must be a business day, not before today and not after the deadline. A customer amount must be from the smallest payment up to the overdue amount.
12. Read the amount and the date back and ask "Is that right?". Record with `create_promise` only after a yes. If the tool fails, say so and close as `declined` / `system_down`.
13. After a recorded promise, close as `agreed`.
14. A request for a person: `transfer_to_agent` with team `desk`, close as `handed_over`.

## Closing

Every call ends with one `close_call` with a `result` and, except for `agreed`, a `code`.
