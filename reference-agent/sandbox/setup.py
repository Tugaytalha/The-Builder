# Code node at call start: date facts for the opening steps and the call's state variables.
try:
    now = parse_now(vars.get('now'))
    today = now.date()
    vars['today_text'] = d_full(today)
    vars['now_time'] = now.strftime('%H:%M')
    # Callbacks: today or the next business day, inside the window, later than now.
    start, end = SPEC_CALLBACK_WINDOW
    slots = []
    if now.strftime('%H:%M') < end:
        first = max(start, now.strftime('%H:%M'))
        slots.append('today, ' + d_full(today) + ', at a time later than ' + first + ' and no later than ' + end)
    nb = next_bd(today)
    slots.append(d_full(nb) + ', from ' + start + ' to ' + end + ' (both included)')
    vars['callback_text'] = ('A callback can be booked only for: ' + ' or '.join(slots) +
                             '. Every other day or time is outside the window. '
                             'Tomorrow is ' + d_full(today + DAY) + '.')
    vars['callback_dates'] = json.dumps([today.isoformat(), nb.isoformat()])
except Exception as e:
    vars['today_text'] = str(vars.get('now') or '')
    vars['callback_text'] = 'Callback window: today or the next business day, ' + ' to '.join(SPEC_CALLBACK_WINDOW) + '.'
    vars['setup_error'] = str(e)[:200]

# State written by the tool hooks. Strings only: routing compares strings.
for k in ('st_verified', 'st_verify_failed', 'st_callback', 'st_closed'):
    vars[k] = 'no'
for k in ('st_transfer', 'st_block_promise', 'st_block_note', 'st_block_close'):
    vars[k] = ''
vars['st_close_blocks'] = '0'
vars['st_promises'] = '[]'
vars['st_notes'] = '[]'
vars['st_fail'] = '{}'
