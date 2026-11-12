"""Асинхронный слой хранения на SQLite (aiosqlite)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    user_name   TEXT    NOT NULL,
    phone       TEXT    NOT NULL,
    service_id  TEXT    NOT NULL,
    minutes     INTEGER NOT NULL,
    starts_at   TEXT    NOT NULL,         -- ISO 8601 с часовым поясом
    status      TEXT    NOT NULL DEFAULT 'active',  -- active | cancelled
    reminded    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_bookings_start ON bookings(starts_at);
CREATE INDEX IF NOT EXISTS ix_bookings_user  ON bookings(user_id);
"""


@dataclass(frozen=True)
class Booking:
    id: int
    user_id: int
    user_name: str
    phone: str
    service_id: str
    minutes: int
    starts_at: datetime
    status: str

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "Booking":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            user_name=row["user_name"],
            phone=row["phone"],
            service_id=row["service_id"],
            minutes=row["minutes"],
            starts_at=datetime.fromisoformat(row["starts_at"]),
            status=row["status"],
        )


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._conn is not None, "Сначала вызовите connect()"
        return self._conn

    async def create_booking(self, *, user_id: int, user_name: str, phone: str,
                             service_id: str, minutes: int, starts_at: datetime) -> int | None:
        """Атомарно проверяет слот и создаёт запись. Возвращает None, если слот уже заняли.

        Lock защищает от гонки, когда два клиента одновременно жмут на одно и то же время.
        """
        end = starts_at + timedelta(minutes=minutes)
        async with self._lock:
            day = await self.bookings_for_day(starts_at.date())
            if any(b.starts_at < end and starts_at < b.starts_at + timedelta(minutes=b.minutes) for b in day):
                return None
            cur = await self.conn.execute(
                "INSERT INTO bookings(user_id, user_name, phone, service_id, minutes, starts_at) VALUES (?,?,?,?,?,?)",
                (user_id, user_name, phone, service_id, minutes, starts_at.isoformat()),
            )
            await self.conn.commit()
            return cur.lastrowid

    async def bookings_for_day(self, day: date) -> list[Booking]:
        cur = await self.conn.execute(
            "SELECT * FROM bookings WHERE status='active' AND substr(starts_at,1,10)=? ORDER BY starts_at",
            (day.isoformat(),),
        )
        return [Booking.from_row(r) for r in await cur.fetchall()]

    async def user_bookings(self, user_id: int, now: datetime) -> list[Booking]:
        cur = await self.conn.execute(
            "SELECT * FROM bookings WHERE status='active' AND user_id=? ORDER BY starts_at", (user_id,)
        )
        return [b for b in map(Booking.from_row, await cur.fetchall()) if b.starts_at >= now]

    async def cancel(self, booking_id: int, user_id: int | None = None) -> Booking | None:
        cur = await self.conn.execute("SELECT * FROM bookings WHERE id=? AND status='active'", (booking_id,))
        row = await cur.fetchone()
        if not row or (user_id is not None and row["user_id"] != user_id):
            return None
        await self.conn.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (booking_id,))
        await self.conn.commit()
        return Booking.from_row(row)

    async def due_reminders(self, now: datetime, before: timedelta) -> list[Booking]:
        cur = await self.conn.execute("SELECT * FROM bookings WHERE status='active' AND reminded=0")
        rows = [Booking.from_row(r) for r in await cur.fetchall()]
        return [b for b in rows if now <= b.starts_at <= now + before]

    async def mark_reminded(self, booking_id: int) -> None:
        await self.conn.execute("UPDATE bookings SET reminded=1 WHERE id=?", (booking_id,))
        await self.conn.commit()

    async def stats(self, since: datetime) -> dict[str, int]:
        cur = await self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM bookings WHERE created_at >= ? GROUP BY status",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        )
        return {r["status"]: r["n"] for r in await cur.fetchall()}
