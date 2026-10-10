from datetime import date, timedelta


def is_business_day(day, holidays):
    return day.weekday() < 5 and day.isoformat() not in holidays


def nth_business_day_after(day, n, holidays):
    while n > 0:
        day = day + timedelta(days=1)
        if is_business_day(day, holidays):
            n = n - 1
    return day


def next_business_day_on_or_after(day, holidays):
    while not is_business_day(day, holidays):
        day = day + timedelta(days=1)
    return day


def last_business_day_of_week(day, holidays):
    friday = day + timedelta(days=4 - day.weekday())
    for back in range(5):
        candidate = friday - timedelta(days=back)
        if is_business_day(candidate, holidays):
            return candidate
    return None


def this_weekday(day, weekday):
    return day + timedelta(days=weekday - day.weekday())


def next_weekday(day, weekday):
    return this_weekday(day, weekday) + timedelta(days=7)
