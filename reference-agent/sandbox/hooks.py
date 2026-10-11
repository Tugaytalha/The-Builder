# Pre and post hooks of the bank tools. build.py cuts this file at the "## <name>" markers;
# each section becomes one hook, with SPEC_* and lib.py prepended.
# Pre-hooks see `vars` and `config` (the substituted request). Post-hooks see `vars` and `result`.
# Post-hooks run only when the API answers 200: on an HTTP error the model sees the raw error and no hook runs.
# So a write that breaks the brief is redirected to the read-only get_account route: nothing is recorded, the
# answer is 200, and the post-hook replaces it with what to do instead.

## verify_pre
MONTHS = [('jan', 1), ('feb', 2), ('mar', 3), ('apr', 4), ('may', 5), ('jun', 6), ('jul', 7), ('aug', 8), ('sep', 9), ('oct', 10), ('nov', 11), ('dec', 12)]


def parse_dob(s):
    s = str(s or '').strip().lower()
    if not s:
        return None
    if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', s):
        d = parse_iso(s)
        return d.isoformat() if d else None
    month = None
    for k, v in MONTHS:
        if re.search(r'\b' + k, s):
            month = v
            break
    nums = re.findall(r'\d+', s)
    try:
        if month:
            year = [int(n) for n in nums if len(n) == 4]
            day = [int(n) for n in nums if len(n) <= 2]
            if year and day:
                return datetime.date(year[0], month, day[0]).isoformat()
            return None
        if len(nums) == 1 and len(nums[0]) == 8:
            nums = [nums[0][:2], nums[0][2:4], nums[0][4:]]
        if len(nums) == 3:
            if len(nums[0]) == 4:                        # already year first
                return datetime.date(int(nums[0]), int(nums[1]), int(nums[2])).isoformat()
            y = int(nums[2])
            if len(nums[2]) == 2:
                y += 1900 if y > datetime.date.today().year % 100 else 2000
            return datetime.date(y, int(nums[1]), int(nums[0])).isoformat()   # numbers only: day, month, year
    except Exception:
        return None
    return None


try:
    b = config.get('body')
    if isinstance(b, dict):
        field = str(b.get('field') or '')
        spoken = str(b.pop('spoken_answer', '') or '')
        ans = str(b.get('answer') or '')
        if 'birth' in field and 'year' not in field:
            iso = parse_dob(spoken) or parse_dob(ans)
            if iso:
                b['answer'] = iso
        elif 'phone' in field or 'last4' in field:
            digits = re.sub(r'\D', '', ans) or re.sub(r'\D', '', spoken)
            if len(digits) >= 4:
                b['answer'] = digits[-4:]
        vars['st_req_verify'] = field
except Exception:
    pass

## verify_post
try:
    d = data_of(result)
    field = str(vars.get('st_req_verify') or vars.get('verify_identity_args.field') or '')
    if 'birth' in field:
        q, other = 'date of birth', 'Now ask for the last four digits of the phone number on file.'
    elif 'phone' in field:
        q, other = 'last four digits of the phone number on file', 'Now ask for the date of birth.'
    else:
        q, other = 'same question', 'Now ask the security question that is not answered yet.'
    if is_true(d.get('all_verified')):
        vars['st_verified'] = 'yes'
        msg = 'Both answers are verified. The identity check is complete.'
    elif str(d.get('hint') or '') == 'day_month_swapped':
        msg = ('The day and the month look swapped. Ask the customer to say the month of their date of birth as a word, '
               'then call verify_identity again. This retry does not count as a wrong answer.')
    elif not is_true(d.get('ok')) or d.get('verified') is None:
        msg = ('The answer could not be checked (' + str(d.get('error') or 'service problem') + '). It is not a wrong answer. '
               'Ask the customer to repeat the ' + q + ', then call verify_identity again.')
    elif is_true(d.get('verified')):
        msg = 'Correct. ' + other
    else:
        try:
            left = int(d.get('wrong_answers_left'))
        except Exception:
            left = None
        if left is not None and left <= 0:
            vars['st_verify_failed'] = 'yes'
            msg = ('Wrong answer. That was the third wrong answer, so the identity check has FAILED. Do not state the debt, '
                   'a product or an amount. Tell the customer to use the mobile app or visit a branch, thank them, say goodbye, '
                   'and call close_call with outcome not_verified and reason failed.')
        else:
            msg = ('Wrong answer' + ('' if left is None else ' (' + str(left) + ' wrong answers left in total)') +
                   '. Tell the customer it does not match and ask for the ' + q + ' again. Do not ask the other question again.')
    tell(result, msg)
except Exception:
    pass

## account_post
try:
    if isinstance(result, dict):
        result.pop('header', None)
    d = data_of(result)
    if isinstance(d.get('products'), list):
        vars['st_products'] = json.dumps(d['products'])
except Exception:
    pass

## promise_pre
try:
    b = config.get('body')
    meta = jload('st_meta', [])
    today = parse_now(vars.get('now')).date()
    problem, req = '', {}
    if isinstance(b, dict):
        pid = match_pid(b.get('product_id'), meta) if meta else str(b.get('product_id') or '')
        amount, date = num(b.get('amount')), parse_iso(b.get('date'))
        b['product_id'] = pid
        if amount is not None:
            b['amount'] = amount
        if date is not None:
            b['date'] = date.isoformat()
        req = {'product_id': pid, 'amount': amount, 'date': date.isoformat() if date else str(b.get('date'))}
        m = [x for x in meta if x['product_id'] == pid]
        promised = [p.get('product_id') for p in recorded(meta)[0]]
        if meta and not m:
            problem = 'unknown product_id ' + pid + '. Use one of: ' + ', '.join(x['product_id'] for x in meta)
        elif pid in promised:
            problem = 'this product already has a recorded promise. One promise per product, and it cannot be changed in this call (the customer can change it in the mobile app)'
        elif vars.get('st_transfer'):
            problem = 'the call was already transferred, so nothing more is recorded'
        elif amount is None:
            problem = 'the amount is not a number'
        elif date is None:
            problem = 'the date is not a date in YYYY-MM-DD form'
        elif m:
            m = m[0]
            dl = parse_iso(m['deadline'])
            if amount < m['floor'] - 0.005:
                problem = money(amount) + ' is below the floor of ' + money(m['floor']) + ' for the ' + m['name'] + '. Say it cannot be recorded and offer ' + money(m['floor']) + ' once'
            elif amount > m['past_due'] + 0.005:
                problem = money(amount) + ' is more than the past-due amount of ' + money(m['past_due']) + '. Offer ' + money(m['past_due'])
            elif date < today:
                problem = d_say(date) + ' is in the past. The earliest date is today, ' + d_say(today)
            elif date > dl:
                problem = d_say(date) + ' is after the deadline of the ' + m['name'] + '. The latest date you can record is ' + d_say(dl) + '. Offer that date'
            elif not is_bd(date):
                problem = d_say(date) + ' is not a business day. Offer the next business day, ' + d_say(next_bd(date))
        if problem:
            config['url'] = str(config.get('url') or '').rsplit('/', 1)[0] + '/get_account'
    vars['st_block_promise'] = problem
    vars['st_req_promise'] = json.dumps(req)
except Exception:
    pass

## promise_post
try:
    d = data_of(result)
    meta = jload('st_meta', [])
    req = jload('st_req_promise', {})
    pid = str(req.get('product_id') or vars.get('create_promise_args.product_id') or '')
    name = ([m['name'] for m in meta if m['product_id'] == pid] or [pid])[0]
    multi = SPEC_MULTI and len(meta) > 1
    block = str(vars.get('st_block_promise') or '')
    vars['st_block_promise'] = ''
    if block:
        if isinstance(result, dict):
            result['data'] = {'ok': False, 'error': 'not sent'}
        msg = ('NOT recorded, nothing was sent: ' + block + '. Do not say it is recorded. Offer what the rules allow, '
               'read it back, and call create_promise only after a clear yes.')
    elif is_true(d.get('ok')):
        vars['st_prom_' + pid] = json.dumps(req)
        promises, notes = recorded(meta)
        if pid not in [p.get('product_id') for p in promises]:
            promises.append(req)
        done = set(p.get('product_id') for p in promises) | set(n.get('product_id') for n in notes)
        left = [m['name'] + ' (' + m['product_id'] + ')' for m in meta if m['product_id'] not in done]
        if multi and left:
            msg = ('Recorded for the ' + name + '. Still without a promise or a note: ' + say_list(left) + '. '
                   'If the customer already confirmed a promise for one of them, call create_promise for it now, one call per message. '
                   'If one of them is not decided yet, go on with it in order: a refusal uses one persuasion attempt, so make the '
                   'attempt offers from the facts for that product before you accept the refusal. Call add_note only for a product '
                   'whose attempts are used up, or that ended in hardship, dispute or paid. '
                   'Say nothing about a text message until every agreed promise is recorded.')
        else:
            msg = ('The promise is recorded. Now say exactly: "You will receive a text message confirming this promise." '
                   'Then thank the customer, say goodbye, and call close_call with outcome promise.')
    else:
        fails = jload('st_fail', {})
        fails[pid] = int(fails.get(pid, 0)) + 1
        vars['st_fail'] = json.dumps(fails)
        if fails[pid] < 2:
            msg = ('The promise was NOT recorded: the service failed. Do not tell the customer it is recorded and do not ask '
                   'them again. Call create_promise again right now with exactly the same product_id, amount and date.')
        elif multi:
            msg = ('The promise for the ' + name + ' could NOT be recorded (second failure). Tell the customer you could not '
                   'record it. Call add_note for ' + pid + ' with reason service_error, then continue with the other products.')
        else:
            msg = ('The promise could NOT be recorded (second failure). Tell the customer you could not record the promise, '
                   'thank them, say goodbye, and call close_call with outcome no_promise and reason service_error.')
    tell(result, msg)
except Exception:
    pass

## note_pre
try:
    b = config.get('body')
    meta = jload('st_meta', [])
    problem, req = '', {}
    if isinstance(b, dict):
        pid = match_pid(b.get('product_id'), meta) if meta else str(b.get('product_id') or '')
        b['product_id'] = pid
        reason = str(b.get('reason') or '').strip()
        req = {'product_id': pid, 'reason': reason}
        if vars.get('st_transfer'):
            problem = 'the call was transferred: on any transfer no notes are added'
        elif meta and pid not in [m['product_id'] for m in meta]:
            problem = 'unknown product_id ' + pid
        elif pid in [p.get('product_id') for p in recorded(meta)[0]]:
            problem = 'this product has a recorded promise, so it gets no note'
        elif pid in [n.get('product_id') for n in recorded(meta)[1]]:
            problem = 'this product already has a note'
        elif reason not in SPEC_NOTE_REASONS:
            problem = 'reason must be one of ' + ', '.join(SPEC_NOTE_REASONS)
        if problem:
            config['url'] = str(config.get('url') or '').rsplit('/', 1)[0] + '/get_account'
    vars['st_block_note'] = problem
    vars['st_req_note'] = json.dumps(req)
except Exception:
    pass

## note_post
try:
    d = data_of(result)
    meta = jload('st_meta', [])
    req = jload('st_req_note', {})
    block = str(vars.get('st_block_note') or '')
    vars['st_block_note'] = ''
    if block:
        if isinstance(result, dict):
            result['data'] = {'ok': False, 'error': 'not sent'}
        msg = 'NOT recorded, nothing was sent: ' + block + '.'
    elif is_true(d.get('ok')):
        vars['st_note_' + str(req.get('product_id'))] = str(req.get('reason') or '')
        promises, notes = recorded(meta)
        if req.get('product_id') not in [n.get('product_id') for n in notes]:
            notes.append(req)
        done = set(p.get('product_id') for p in promises) | set(n.get('product_id') for n in notes)
        left = [m['name'] + ' (' + m['product_id'] + ')' for m in meta if m['product_id'] not in done]
        if left:
            msg = 'Noted. Still without a promise or a note: ' + say_list(left) + '. Continue with them.'
        else:
            msg = ('Noted. Every product is done. If a promise was recorded and you have not said it yet, say "You will '
                   'receive a text message confirming this promise." Then thank the customer, say goodbye, and call close_call.')
    else:
        msg = 'The note was NOT recorded (' + str(d.get('error') or 'service problem') + '). Call add_note again once.'
    tell(result, msg)
except Exception:
    pass

## transfer_pre
try:
    b = config.get('body')
    if isinstance(b, dict):
        q = str(b.get('queue') or '').strip().lower()
        b['queue'] = q
        vars['st_req_transfer'] = q
except Exception:
    pass

## transfer_post
try:
    d = data_of(result)
    q = str(vars.get('st_req_transfer') or vars.get('transfer_to_agent_args.queue') or '')
    if is_true(d.get('ok')):
        vars['st_transfer'] = q
        reason = dict(SPEC_TRANSFER_REASONS).get(q, q)
        msg = ('The transfer is done. Tell the customer you are transferring them now, thank them, say goodbye, and call '
               'close_call with outcome transferred and reason ' + reason + '. Do not call add_note.')
    else:
        msg = 'The transfer did NOT go through (' + str(d.get('error') or 'service problem') + '). Call transfer_to_agent again once.'
    tell(result, msg)
except Exception:
    pass

## callback_pre


def norm_time(t):
    s = str(t or '').strip().lower().replace('.', '').replace(' ', '')
    m = re.match(r'^(\d{1,2})(?::?(\d{2}))?(am|pm)?$', s)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if m.group(3) == 'pm' and h < 12:
        h += 12
    if m.group(3) == 'am' and h == 12:
        h = 0
    if h > 23 or mi > 59:
        return None
    return '%02d:%02d' % (h, mi)


try:
    b = config.get('body')
    problem = ''
    if isinstance(b, dict):
        now = parse_now(vars.get('now'))
        date, t = parse_iso(b.get('date')), norm_time(b.get('time'))
        if date is not None:
            b['date'] = date.isoformat()
        if t is not None:
            b['time'] = t
        allowed = jload('callback_dates', [])
        start, end = SPEC_CALLBACK_WINDOW
        if date is None or t is None:
            problem = 'the date must be YYYY-MM-DD and the time HH:MM'
        elif allowed and date.isoformat() not in allowed:
            problem = d_say(date) + ' is outside the window (today or the next business day only)'
        elif not (start <= t <= end):
            problem = t + ' is outside the window of ' + start + ' to ' + end
        elif date == now.date() and t <= now.strftime('%H:%M'):
            problem = t + ' today is not later than now'
        vars['st_callback_warning'] = problem
except Exception:
    pass

## callback_post
try:
    d = data_of(result)
    block = ''
    if block:
        if isinstance(result, dict):
            result['data'] = {'ok': False, 'error': 'not sent'}
        msg = ('NOT booked, nothing was sent: ' + block + '. If this was the first time outside the window, ask once for '
               'another time. If it was the second, do not schedule: thank them, say goodbye, and call close_call with '
               'outcome not_reached and reason no_callback.')
    elif is_true(d.get('ok')):
        vars['st_callback'] = 'yes'
        msg = ('The callback is booked. Tell the person the day and time, thank them, say goodbye, and call close_call with '
               'outcome not_reached and reason callback.')
    else:
        msg = 'The callback was NOT booked (' + str(d.get('error') or 'service problem') + '). Call schedule_callback again once.'
    tell(result, msg)
except Exception:
    pass

## close_pre
try:
    b = config.get('body')
    if isinstance(b, dict):
        out = str(b.get('outcome') or '').strip()
        rsn = str(b.get('reason') or '').strip()
        model_out = out
        meta = jload('st_meta', [])
        promises, notes = recorded(meta)
        fails = jload('st_fail', {})
        tq = str(vars.get('st_transfer') or '')
        # The records decide the outcome wherever they can. The model's choice stands only for what the records cannot show.
        if tq:
            out, rsn = 'transferred', dict(SPEC_TRANSFER_REASONS).get(tq, rsn)
        elif promises:
            out, rsn = 'promise', ''
        elif vars.get('st_callback') == 'yes':
            out, rsn = 'not_reached', 'callback'
        elif vars.get('st_verify_failed') == 'yes':
            out, rsn = 'not_verified', 'failed'
        elif SPEC_MULTI and notes:
            order = [m['product_id'] for m in meta]
            notes = sorted(notes, key=lambda n: order.index(n.get('product_id')) if n.get('product_id') in order else 99)
            noted = set(n.get('product_id') for n in notes)
            if all(n.get('reason') == 'paid' for n in notes) and noted >= set(order):
                out, rsn = 'paid', ''
            else:
                firsts = [n.get('reason') for n in notes if n.get('reason') != 'paid']
                if firsts:
                    out, rsn = 'no_promise', firsts[0]
        elif not SPEC_MULTI and (any(int(v) >= 2 for v in fails.values()) or num(vars.get('create_promise_failure_count') or 0) >= 2):
            out, rsn = 'no_promise', 'service_error'
        elif vars.get('st_verified') != 'yes' and out in ('promise', 'paid', 'no_promise'):
            out, rsn = 'not_verified', 'declined'
        b['outcome'] = out
        if out in SPEC_NO_REASON_OUTCOMES:
            b.pop('reason', None)
        else:
            b['reason'] = rsn
        vars['st_req_close'] = out + '/' + rsn
        # The model sometimes sends close_call in the same message as the action it closes on; both then run at once
        # and the bank closes first. After the identity check, hold the close back once while that action is unconfirmed.
        pending = ''
        if model_out == 'transferred' and not tq:
            pending = 'no transfer is confirmed yet. Call transfer_to_agent first if you have not, and wait for its result'
        elif model_out == 'promise' and not promises:
            pending = 'no promise is recorded yet. If the customer confirmed the read-back, call create_promise and wait for its result'
        elif SPEC_MULTI and not tq and meta:
            done = set(p.get('product_id') for p in promises) | set(n.get('product_id') for n in notes)
            missing = [m['name'] + ' (' + m['product_id'] + ')' for m in meta if m['product_id'] not in done]
            if missing:
                pending = ('these products have no promise and no note yet: ' + say_list(missing) +
                           '. Call create_promise or add_note for each, one per message, and wait for each result')
        blocks = int(num(vars.get('st_close_blocks') or 0) or 0)
        if pending and blocks < 2 and vars.get('st_verified') == 'yes':
            config['url'] = str(config.get('url') or '').rsplit('/', 1)[0] + '/get_account'
            vars['st_close_blocks'] = str(blocks + 1)
            vars['st_block_close'] = pending
        else:
            vars['st_block_close'] = ''
except Exception:
    pass

## close_post
try:
    d = data_of(result)
    block = str(vars.get('st_block_close') or '')
    vars['st_block_close'] = ''
    if block:
        if isinstance(result, dict):
            result['data'] = {'ok': False, 'error': 'not sent'}
        msg = 'The call is NOT closed yet: ' + block + '. Then say goodbye and call close_call again, alone in its message.'
    elif is_true(d.get('ok')):
        vars['st_closed'] = 'yes'
        msg = 'The call is closed. Say nothing more.'
    else:
        msg = 'close_call was NOT accepted (' + str(d.get('error') or 'service problem') + '). Call close_call again.'
    tell(result, msg)
except Exception:
    pass
