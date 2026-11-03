

import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation


class ValidationError(ValueError):


    def __init__(self, message, field=None):
        super().__init__(message)
        self.message = message
        self.field = field


def _as_text(value):

    return "" if value is None else str(value).strip()


def clean_text(value, label, required=False, max_length=None):

    text = _as_text(value)
    if not text:
        if required:
            raise ValidationError("%s is required." % label)
        return None
    if max_length and len(text) > max_length:
        raise ValidationError(
            "%s is too long (maximum %d characters)." % (label, max_length)
        )
    return text


def _check_range(number, label, minimum, maximum):
    if minimum is not None and number < minimum:
        raise ValidationError("%s must be at least %s." % (label, minimum))
    if maximum is not None and number > maximum:
        raise ValidationError("%s must be at most %s." % (label, maximum))


_INT_RE = re.compile(r"^[+-]?\d+$")
_DECIMAL_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)$")


def parse_int(value, label, required=True, minimum=None, maximum=None):

    text = _as_text(value)
    if not text:
        if required:
            raise ValidationError("%s is required." % label)
        return None
    if not _INT_RE.match(text):
        raise ValidationError("%s must be a whole number (for example 12)." % label)
    number = int(text)
    _check_range(number, label, minimum, maximum)
    return number


def parse_decimal(value, label, required=True, minimum=None, maximum=None):

    text = _as_text(value)
    if not text:
        if required:
            raise ValidationError("%s is required." % label)
        return None
    if not _DECIMAL_RE.match(text):
        raise ValidationError(
            "%s must be a number (for example 550.00). Use a dot, not a comma." % label
        )
    try:
        number = Decimal(text)
    except InvalidOperation:
        raise ValidationError("%s must be a number (for example 550.00)." % label) from None
    _check_range(number, label, minimum, maximum)
    return number


_DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")


def parse_date(value, label, required=True):

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _as_text(value)
    if not text:
        if required:
            raise ValidationError("%s is required." % label)
        return None
    match = _DATE_RE.match(text)
    if not match:
        raise ValidationError(
            "%s must be a date written as YYYY-MM-DD (for example 2026-10-14)." % label
        )
    year, month, day = (int(x) for x in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        raise ValidationError("%s is not a real calendar date (%s)." % (label, text)) from None


def parse_time(value, label, required=True):

    if isinstance(value, time):
        return value
    if isinstance(value, timedelta):  
        total = int(value.total_seconds())
        return time((total // 3600) % 24, (total % 3600) // 60)
    text = _as_text(value)
    if not text:
        if required:
            raise ValidationError("%s is required." % label)
        return None
    match = _TIME_RE.match(text)
    if not match:
        raise ValidationError(
            "%s must be a time written as HH:MM, 24-hour (for example 06:30)." % label
        )
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        raise ValidationError(
            "%s is not a real time (hours 00-23, minutes 00-59)." % label
        )
    return time(hours, minutes)


_COLOR_RE = re.compile(r"^#?([0-9A-Fa-f]{6})$")


def parse_color(value, label, required=True):

    text = _as_text(value)
    if not text:
        if required:
            raise ValidationError("%s is required." % label)
        return None
    match = _COLOR_RE.match(text)
    if not match:
        raise ValidationError(
            "%s must be a color code like #4C9F50 (use the Choose button)." % label
        )
    return "#" + match.group(1).upper()


def check_time_order(start, end, end_label="The finish time", start_label="the start time"):

    if start is not None and end is not None and end <= start:
        raise ValidationError("%s must be after %s." % (end_label, start_label))


def check_harvest_after_planting(plant_date, harvest_date):

    if plant_date is not None and harvest_date is not None and harvest_date <= plant_date:
        raise ValidationError(
            "The expected harvest date must be after the planting date."
        )


def check_date_range(date_from, date_to):

    if date_from is not None and date_to is not None and date_to < date_from:
        raise ValidationError("The 'to' date cannot be before the 'from' date.")


def date_to_text(value):

    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def time_to_text(value):

    if value is None or value == "":
        return ""
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        return "%02d:%02d" % ((total // 3600) % 24, (total % 3600) // 60)
    if isinstance(value, time):
        return "%02d:%02d" % (value.hour, value.minute)
    text = str(value).strip()
    match = _TIME_RE.match(text)
    if match:
        return "%02d:%s" % (int(match.group(1)), match.group(2))
    return text


def time_to_minutes(value):

    parsed = parse_time(value, "Time")
    return parsed.hour * 60 + parsed.minute


def format_money(value):
    if value is None or value == "":
        return ""
    return "\u20b1{:,.2f}".format(Decimal(str(value)))
