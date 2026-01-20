from datetime import datetime, timedelta, date, time

def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()

def parse_time(s: str) -> time:
    s = (s or "").strip()
    if not s:
        raise ValueError("Empty time string")
    # Accept HH:MM or HH:MM:SS
    if len(s) == 5:
        return datetime.strptime(s, "%H:%M").time()
    return datetime.strptime(s, "%H:%M:%S").time()

def _coerce_time(t) -> time:
    # MySQL TIME can arrive as datetime.time or datetime.timedelta (mysql-connector)
    if isinstance(t, time):
        return t
    if isinstance(t, timedelta):
        # Most MySQL TIME values are within 0..24h; this keeps the clock part.
        return (datetime.min + t).time()
    if isinstance(t, str):
        return parse_time(t)
    raise TypeError(f"Unsupported time type: {type(t)}")

def add_minutes_to_dt(d: date, t: time, minutes: int):
    t = _coerce_time(t)
    dt = datetime.combine(d, t) + timedelta(minutes=minutes)
    return dt.date(), dt.time()

def hours_until(d: date, t, now=None) -> float:
    now = now or datetime.now()
    tt = _coerce_time(t)
    dt = datetime.combine(d, tt)
    return (dt - now).total_seconds() / 3600.0
