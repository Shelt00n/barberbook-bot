"""Чистая логика расписания: какие слоты свободны. Покрыта тестами."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class Busy:
    start: datetime
    minutes: int

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.minutes)


def free_slots(
    day: date,
    duration: int,
    busy: list[Busy],
    *,
    now: datetime,
    open_hour: int = 10,
    close_hour: int = 20,
    step: int = 30,
) -> list[datetime]:
    """Возвращает время начала, на которое можно записать услугу длительностью `duration` минут.

    Слот подходит, если:
      * услуга целиком помещается в рабочий день;
      * не пересекается ни с одной существующей записью;
      * начинается не раньше, чем через 30 минут от текущего момента.
    """
    tz = now.tzinfo
    cursor = datetime.combine(day, time(open_hour), tzinfo=tz)
    close = datetime.combine(day, time(close_hour), tzinfo=tz)
    earliest = now + timedelta(minutes=30)
    result: list[datetime] = []
    while cursor + timedelta(minutes=duration) <= close:
        end = cursor + timedelta(minutes=duration)
        overlaps = any(cursor < b.end and b.start < end for b in busy)
        if cursor >= earliest and not overlaps:
            result.append(cursor)
        cursor += timedelta(minutes=step)
    return result


def upcoming_days(now: datetime, days: int) -> list[date]:
    """Ближайшие дни для записи, без воскресений (выходной)."""
    out: list[date] = []
    d = now.date()
    while len(out) < days:
        if d.weekday() != 6:
            out.append(d)
        d += timedelta(days=1)
    return out
