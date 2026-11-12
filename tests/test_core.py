from datetime import date, datetime, timedelta, timezone

import pytest

from bot.db import Database
from bot.slots import Busy, free_slots, upcoming_days

TZ = timezone(timedelta(hours=2))
DAY = date(2026, 11, 16)  # понедельник
MORNING = datetime(2026, 11, 16, 8, 0, tzinfo=TZ)


def at(h: int, m: int = 0) -> datetime:
    return datetime(2026, 11, 16, h, m, tzinfo=TZ)


def test_empty_day_has_all_slots():
    slots = free_slots(DAY, 60, [], now=MORNING)
    assert slots[0] == at(10) and slots[-1] == at(19)
    assert len(slots) == 19  # 10:00 … 19:00 с шагом 30 минут


def test_busy_interval_is_excluded():
    slots = free_slots(DAY, 60, [Busy(at(12), 60)], now=MORNING)
    assert at(11, 30) not in slots  # пересекается с 12:00
    assert at(12, 30) not in slots
    assert at(11) in slots and at(13) in slots


def test_long_service_must_fit_before_close():
    slots = free_slots(DAY, 90, [], now=MORNING)
    assert slots[-1] == at(18, 30)


def test_past_and_too_soon_slots_hidden():
    slots = free_slots(DAY, 30, [], now=at(14, 10))
    assert slots[0] == at(15)  # 14:30 ближе, чем 30 минут → скрыт


def test_sunday_is_skipped():
    days = upcoming_days(datetime(2026, 11, 14, 9, tzinfo=TZ), 3)  # суббота
    assert [d.weekday() for d in days] == [5, 0, 1]


async def test_double_booking_prevented(tmp_path):
    db = Database(tmp_path / "t.sqlite3")
    await db.connect()
    common = dict(user_name="Тест", phone="+380671234567", service_id="cut", minutes=60)
    first = await db.create_booking(user_id=1, starts_at=at(12), **common)
    clash = await db.create_booking(user_id=2, starts_at=at(12, 30), **common)
    ok = await db.create_booking(user_id=3, starts_at=at(13), **common)
    assert first and ok and clash is None
    assert [b.id for b in await db.bookings_for_day(DAY)] == [first, ok]
    await db.close()


async def test_cancel_only_own_booking(tmp_path):
    db = Database(tmp_path / "t.sqlite3")
    await db.connect()
    bid = await db.create_booking(user_id=1, user_name="A", phone="+380000000000",
                                  service_id="beard", minutes=30, starts_at=at(15))
    assert await db.cancel(bid, user_id=999) is None
    assert (await db.cancel(bid, user_id=1)).id == bid
    assert await db.bookings_for_day(DAY) == []
    await db.close()


@pytest.mark.parametrize("window,expected", [(timedelta(hours=2), 1), (timedelta(minutes=30), 0)])
async def test_due_reminders(tmp_path, window, expected):
    db = Database(tmp_path / "t.sqlite3")
    await db.connect()
    await db.create_booking(user_id=1, user_name="A", phone="+380000000000",
                            service_id="cut", minutes=60, starts_at=at(16))
    assert len(await db.due_reminders(at(14, 30), window)) == expected
    await db.close()
