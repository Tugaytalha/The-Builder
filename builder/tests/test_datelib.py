from datetime import date

from builder.blocks.datelib import (last_business_day_of_week, next_business_day_on_or_after,
                                    next_weekday, nth_business_day_after, this_weekday)

H = {"2031-03-10"}  # a Monday holiday


def test_nth_business_day_skips_weekend_and_holiday():
    assert nth_business_day_after(date(2031, 3, 5), 1, H) == date(2031, 3, 6)
    assert nth_business_day_after(date(2031, 3, 5), 3, H) == date(2031, 3, 11)
    assert nth_business_day_after(date(2031, 3, 5), 5, H) == date(2031, 3, 13)


def test_year_end():
    assert nth_business_day_after(date(2031, 12, 31), 1, {"2032-01-01"}) == date(2032, 1, 2)


def test_next_business_day_from_saturday():
    assert next_business_day_on_or_after(date(2031, 3, 8), H) == date(2031, 3, 11)


def test_last_business_day_of_week():
    assert last_business_day_of_week(date(2031, 3, 5), H) == date(2031, 3, 7)


def test_this_and_next_weekday():
    assert this_weekday(date(2031, 3, 5), 4) == date(2031, 3, 7)
    assert next_weekday(date(2031, 3, 7), 4) == date(2031, 3, 14)
