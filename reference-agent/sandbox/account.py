# Code node after get_account: per-product facts, offers, a checked calendar and the debt statement.


def find_products():
    # The get_account post-hook stores the list as JSON. Fall back to mapped and flattened forms.
    for name in ('st_products', 'products', 'get_account_response.data.products', 'load_account_response.data.products'):
        v = vars.get(name)
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except Exception:
                v = None
        if isinstance(v, list) and v:
            return v
    rows = {}
    for k, v in list(vars.items()):
        m = re.match(r'^(?:[A-Za-z_]+_response\.data\.)?products\.(\d+)\.(\w+)$', str(k))
        if m:
            rows.setdefault(int(m.group(1)), {})[m.group(2)] = v
    return [rows[i] for i in sorted(rows)]


try:
    now = parse_now(vars.get('now'))
    today = now.date()
    products = find_products()
    meta = []
    for i, p in enumerate(products):
        typ = str(p.get('type') or '')
        name = typ.replace('_', ' ') or 'product'
        for row in SPEC_PRODUCT_NAMES:              # [type, words, field appended after the words]
            if row[0] == typ:
                name = row[1] + (str(p.get(row[2]) or '') if row[2] else '')
        floor_field, floor_label = 'minimum_payment', 'minimum payment'
        for row in SPEC_FLOORS:                     # [type, field, spoken label]
            if row[0] == typ:
                floor_field, floor_label = row[1], row[2]
        band = band_for(p.get('days_late'))
        deadline = nth_bd_after(today, band[3])
        meta.append({
            'product_id': str(p.get('product_id') or ('p' + str(i + 1))), 'name': name, 'type': typ,
            'past_due': num(p.get('past_due')), 'days_late': p.get('days_late'),
            'floor': num(p.get(floor_field)), 'floor_label': floor_label,
            'band': band[2], 'attempts': band[4], 'deadline': deadline.isoformat()})

    a1 = attempt1_date(today)
    multi = SPEC_MULTI and len(meta) > 1
    lines = []
    for k, m in enumerate(meta):
        dl = parse_iso(m['deadline'])
        lines.append('Product ' + str(k + 1) + ': ' + m['name'] + ' (product_id ' + m['product_id'] + ')')
        lines.append('- Full past-due amount: ' + money(m['past_due']) + '. Days late: ' + str(m['days_late']) + ', so the ' + m['band'] + ' band.')
        lines.append('- Floor (' + m['floor_label'] + '): ' + money(m['floor']) + '. An amount from ' + money(m['floor']) + ' to ' + money(m['past_due']) + ', both included, can be accepted.')
        lines.append('- Deadline (latest promise date): ' + d_full(dl) + '. Earliest: today, ' + d_full(today) + '.')
        n_att = int(m['attempts'])
        lines.append('- Persuasion attempts allowed: ' + str(n_att) + '. The offers for this product, in order:')
        if multi:
            lines.append('  a) Today was already asked for all products together. Do not ask about today again for this product.')
        else:
            lines.append('  a) The full ' + money(m['past_due']) + ' today (the first ask).')
        lines.append('  b) Only if the customer says the full amount is too much: ' + money(m['floor']) + ' (the floor), once, saying that the rest stays overdue. This is not a persuasion attempt.')
        lines.append('  c) After a flat refusal or a non-answer, attempt 1: ' + money(m['past_due']) + ' on ' + d_say(a1) +
                     ' (or ' + money(m['floor']) + ' on ' + d_say(a1) + ' if the customer already said the full amount is too much).')
        if n_att >= 2:
            lines.append('  d) After the next refusal, attempt 2: ' + money(m['floor']) + ' on ' + d_say(dl) + ' (the deadline).')
        lines.append('  STOP: after attempt ' + str(n_att) + ' is refused, make no more offers for this product. It is refused.')
    vars['products_text'] = '\n'.join(lines)

    # Calendar from today to a week past the latest deadline, each day checked against every product.
    last = max([parse_iso(m['deadline']) for m in meta] or [today]) + datetime.timedelta(days=10)
    cal, d = [], today
    while d <= last:
        tag = ' (today)' if d == today else (' (tomorrow)' if d == today + DAY else '')
        if not is_bd(d):
            why = 'bank holiday' if d.weekday() < 5 else 'weekend'
            offers = []
            for m in meta:
                dl, nb = parse_iso(m['deadline']), next_bd(d)
                if d > dl:
                    offers.append((m['name'], 'the deadline ' + d_say(dl) + ' (rule 23)'))
                else:
                    offers.append((m['name'], 'the next business day ' + d_say(nb)))
            if len(set(o[1] for o in offers)) == 1:
                status = why + ', NOT allowed. Offer ' + offers[0][1] + ' instead'
            else:
                status = why + ', NOT allowed. Offer instead: ' + '; '.join('for the ' + n + ', ' + o for n, o in offers)
        else:
            late_for = [m for m in meta if d > parse_iso(m['deadline'])]
            if not late_for:
                status = 'business day, allowed'
            elif len(meta) == 1:
                status = 'business day but AFTER the deadline. Offer the deadline ' + d_say(parse_iso(meta[0]['deadline'])) + ' instead (rule 23)'
            else:
                ok_for = [m['name'] for m in meta if m not in late_for]
                status = ('allowed for ' + say_list(ok_for) + '; ' if ok_for else '') + 'AFTER the deadline for ' + say_list(
                    [m['name'] + ' (deadline ' + d_say(parse_iso(m['deadline'])) + ')' for m in late_for])
        cal.append(d_say(d) + ' = ' + d.isoformat() + tag + ': ' + status)
        d = d + DAY
    vars['calendar_text'] = '\n'.join(cal)

    mon = week_monday(today)
    words = ['tomorrow = ' + d_full(today + DAY)]
    for w in range(7):
        this_d, next_d = mon + datetime.timedelta(days=w), mon + datetime.timedelta(days=7 + w)
        note = ' (already past)' if this_d < today else (' (today)' if this_d == today else '')
        words.append('this ' + WD[w] + ' = ' + d_full(this_d) + note + '; next ' + WD[w] + ' = ' + d_full(next_d))
    vars['date_words_text'] = '\n'.join(words)

    said = []
    for m in meta:
        said.append('Your ' + m['name'] + ' has ' + money(m['past_due']) + ' past due and is ' + str(m['days_late']) + ' days late.')
    if multi:
        ask = 'Can you pay all of them today?'
        intro = 'Thank you, you are verified. I am calling from the collections team about late payments on ' + (['one', 'two', 'three', 'four', 'five'] + [str(len(meta))])[min(len(meta), 6) - 1] + ' of your products. '
    else:
        ask = 'Can you make this payment today?'
        intro = 'Thank you, you are verified. I am calling from the collections team about a late payment. '
    vars['debt_statement'] = intro + ' '.join(said) + ' ' + ask
    vars['st_meta'] = json.dumps(meta)
    vars['product_count'] = str(len(meta))
    vars['account_state'] = 'known' if meta else 'unknown'
except Exception as e:
    vars['account_state'] = 'unknown'
    vars['account_error'] = str(e)[:200]
    for k in ('products_text', 'calendar_text', 'date_words_text'):
        if not vars.get(k):
            vars[k] = 'Not available.'
    if not vars.get('debt_statement'):
        vars['debt_statement'] = 'Thank you, you are verified. I am sorry, I cannot open your account details right now.'
