

from datetime import date, datetime, timedelta


def _as_date(value):
    return value.date() if isinstance(value, datetime) else value


def compute_streak(entry_dates, today=None):

    today = today or date.today()
    days = {_as_date(d) for d in entry_dates if d is not None}
    days = {d for d in days if d <= today}  

    if today in days:
        day = today
    elif (today - timedelta(days=1)) in days:
        day = today - timedelta(days=1)
    else:
        return 0

    count = 0
    while day in days:
        count += 1
        day -= timedelta(days=1)
    return count


def describe_streak(entry_dates, today=None):

    today = today or date.today()
    entry_dates = list(entry_dates)
    count = compute_streak(entry_dates, today)
    wrote_today = today in {_as_date(d) for d in entry_dates if d is not None}

    if count == 0:
        return "No streak yet. Write an entry today to start one!", False
    word = "day" if count == 1 else "days"
    if wrote_today:
        return "Streak: %d %s in a row. Keep it up!" % (count, word), True
    return "Streak: %d %s. Write today's entry to keep it going!" % (count, word), True
