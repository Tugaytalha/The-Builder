# Shared helpers for every snippet that runs in Freya's code sandbox.
# build.py prepends the SPEC_* constants and this file to each snippet.
# Sandbox rules: read and write only through `vars`, never raise, no double braces anywhere.
import datetime, json, re

WD = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MO = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
DAY = datetime.timedelta(days=1)


def d_say(d):
    return WD[d.weekday()] + ' ' + str(d.day) + ' ' + MO[d.month - 1] + ' ' + str(d.year)


def d_full(d):
    return d_say(d) + ' (' + d.isoformat() + ')'


def money(x):
    return format(float(x), ',.2f') + SPEC_CURRENCY


def is_bd(d):
    return d.weekday() < 5 and d.isoformat() not in SPEC_HOLIDAYS


def next_bd(d):
    x = d + DAY
    while not is_bd(x):
        x = x + DAY
    return x


def nth_bd_after(d, n):
    x = d
    for _ in range(int(n)):
        x = next_bd(x)
    return x


def parse_now(s):
    m = re.match(r'\s*(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ](\d{1,2}):(\d{2}))?', str(s or ''))
    if m:
        return datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4) or 0), int(m.group(5) or 0))
    return datetime.datetime.utcnow()


def parse_iso(s):
    m = re.match(r'\s*(\d{4})-(\d{1,2})-(\d{1,2})', str(s or ''))
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except Exception:
        return None


def week_monday(d):
    return d - datetime.timedelta(days=d.weekday())


def last_bd_of_week(monday):
    for k in range(4, -1, -1):
        x = monday + datetime.timedelta(days=k)
        if is_bd(x):
            return x
    return None


def attempt1_date(today):
    x = last_bd_of_week(week_monday(today))
    if x is None or x <= today:
        x = last_bd_of_week(week_monday(today) + datetime.timedelta(days=7))
    return x


def band_for(days_late):
    # SPEC_BANDS rows: [min_days, max_days, name, deadline_business_days, persuasion_attempts]
    try:
        n = int(float(days_late))
    except Exception:
        n = 0
    for row in SPEC_BANDS:
        if row[0] <= n <= row[1]:
            return row
    return SPEC_BANDS[-1] if n > SPEC_BANDS[-1][1] else SPEC_BANDS[0]


def jload(name, default):
    v = vars.get(name)
    if isinstance(v, (list, dict)):
        return v
    try:
        out = json.loads(v) if v not in (None, '') else default
        return out if out is not None else default
    except Exception:
        return default


def is_true(v):
    return str(v).strip().lower() == 'true'


def data_of(res):
    # The api_call result is an envelope; the API's JSON body is result['data'].
    if isinstance(res, dict):
        d = res.get('data')
        if isinstance(d, dict):
            return d
        if isinstance(d, str):
            try:
                d2 = json.loads(d)
                if isinstance(d2, dict):
                    return d2
            except Exception:
                pass
    return {}


def num(x):
    try:
        return round(float(re.sub(r'[^0-9.\-]', '', str(x))), 2)
    except Exception:
        return None


def match_pid(raw, meta):
    # The model may send a name or an index instead of the id; one product cannot be wrong.
    ids = [m['product_id'] for m in meta]
    raw = str(raw or '').strip()
    if len(ids) == 1:
        return ids[0]
    if raw in ids:
        return raw
    low = raw.lower().replace('_', ' ')
    for m in meta:
        if low and (low in m['name'].lower() or m['type'].replace('_', ' ') in low):
            return m['product_id']
    return raw


def tell(result, msg):
    # Put one plain instruction into the tool result. The prompts tell the model to obey it.
    vars['st_last_tell'] = msg[:120]
    if not isinstance(result, dict):
        return
    result.pop('header', None)
    d = result.get('data')
    if isinstance(d, dict):
        d['what_to_do_next'] = msg
    else:
        result['data'] = {'ok': False, 'raw': str(d)[:300], 'what_to_do_next': msg}


def recorded(meta):
    """Promises and notes per product. Each post-hook writes its own key (st_prom_<id>, st_note_<id>), because parallel
    tool calls run their hooks at the same time and a shared JSON list loses one of two writes."""
    proms, notes = [], []
    seen_p, seen_n = set(), set()
    for m in meta:
        pid = m['product_id']
        p = jload('st_prom_' + pid, None)
        if isinstance(p, dict):
            proms.append(p); seen_p.add(pid)
        r = str(vars.get('st_note_' + pid) or '')
        if r:
            notes.append({'product_id': pid, 'reason': r}); seen_n.add(pid)
    for p in jload('st_promises', []):
        if isinstance(p, dict) and p.get('product_id') not in seen_p:
            proms.append(p); seen_p.add(p.get('product_id'))
    for n in jload('st_notes', []):
        if isinstance(n, dict) and n.get('product_id') not in seen_n:
            notes.append(n); seen_n.add(n.get('product_id'))
    return proms, notes


def say_list(items):
    items = [x for x in items if x]
    if len(items) <= 1:
        return ''.join(items)
    return ', '.join(items[:-1]) + ' and ' + items[-1]
