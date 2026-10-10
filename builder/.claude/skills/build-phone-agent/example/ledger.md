| id | rule | source | mechanism | where |
|---|---|---|---|---|
| R1 | First sentence is the fixed opening; nothing about the bill before identity | §1 | fixed-line | opening on_enter; lint forbidden words |
| R2 | Ask for the person; only a clear yes or own name counts; at most twice, then absent / unsure | §2 | route | opening: party enum, opening.total_turns > 1 |
| R3 | Someone else: callback on business day 1 or 2 after today, 09:00–17:00 | §3 | tool | third_party: schedule_callback with guard_hook on callback_days |
| R4 | No time in the window: absent / no_time | §3 | route | third_party: transition_to_close_no_time |
| R5 | Postcode, then year of birth, each answer to verify_identity | §4 | prompt | identity task; verify post-hook |
| R6 | Two wrong answers close as unverified / wrong | §4 | route | identity: tries_left equals 0 |
| R7 | Two refusals close as unverified / refused_check | §5 | code | customer_refuses counts id_refusals; route > 1 |
| R8 | After identity call get_account and state each item | §6 | code | fetch_account, prepare debt_statement |
| R9 | Business days and holidays | §7 | code | setup: datelib with spec holidays |
| R10 | Deadline 5th / 3rd business day by days overdue | §8 | code | setup deadline_<band>; prepare band |
| R11 | Attempts per band, offers fixed, then declined / said_no | §10 | code | customer_said state tool, close_key |
| R12 | Customer day and amount limits | §11 | code | customer_said proposes branch |
| R13 | Read back, record only after yes, only the agreed values | §12 | code | read_back guide; confirms sets agreed_*; record api node bakes them |
| R14 | Tool failure: declined / system_down | §12 | route | record_with_retry, 1 attempt, then close_system_down |
| R15 | Recorded promise: agreed | §13 | route | negotiate: create_promise ok |
| R16 | Request for a person: transfer team desk, handed_over | §14 | tool | transfer_to_agent baked team; route on ok |
| R17 | One close_call with result and code | Closing | code | close_tool end_of_call, close_sequence values |
