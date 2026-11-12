"""Панель администратора: расписание по дням и статистика."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command, Filter
from aiogram.types import CallbackQuery, Message, TelegramObject

from .. import keyboards as kb
from .. import texts
from ..config import Settings
from ..db import Database

router = Router(name="admin")


class IsAdmin(Filter):
    async def __call__(self, event: TelegramObject, settings: Settings) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and user.id in settings.admin_ids)


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


async def render_day(day: date, db: Database, settings: Settings) -> str:
    items = await db.bookings_for_day(day)
    head = f"🗓 <b>Расписание на {texts.human_dt(datetime.combine(day, datetime.min.time())).split(' в ')[0]}</b>\n"
    if not items:
        return head + "\nЗаписей нет — можно выдохнуть ☕"
    revenue = sum(settings.service(b.service_id).price for b in items)
    rows = [
        f"<b>{b.starts_at:%H:%M}</b>–{(b.starts_at + timedelta(minutes=b.minutes)):%H:%M} · "
        f"{settings.service(b.service_id).title}\n      {b.user_name}, {b.phone} · #{b.id}"
        for b in items
    ]
    return head + "\n" + "\n".join(rows) + f"\n\nИтого: {len(items)} записей · ~{revenue} ₴"


@router.message(Command("admin"))
async def admin(message: Message, db: Database, settings: Settings) -> None:
    today = datetime.now(settings.tz).date()
    await message.answer(await render_day(today, db, settings), reply_markup=kb.admin_kb(today))


@router.callback_query(kb.AdminCb.filter(F.action == "day"))
async def admin_day(call: CallbackQuery, callback_data: kb.AdminCb, db: Database, settings: Settings) -> None:
    day = date.fromisoformat(callback_data.day) if callback_data.day else datetime.now(settings.tz).date()
    await call.message.edit_text(await render_day(day, db, settings), reply_markup=kb.admin_kb(day))
    await call.answer()


@router.callback_query(kb.AdminCb.filter(F.action == "stats"))
async def admin_stats(call: CallbackQuery, db: Database, settings: Settings) -> None:
    since = datetime.now(settings.tz) - timedelta(days=7)
    stats = await db.stats(since)
    active, cancelled = stats.get("active", 0), stats.get("cancelled", 0)
    total = active + cancelled
    rate = f"{cancelled / total:.0%}" if total else "—"
    await call.answer()
    await call.message.answer(
        f"📊 <b>Статистика за 7 дней</b>\n\nНовых записей: {total}\nАктивных: {active}\nОтмен: {cancelled} ({rate})"
    )


@router.message(Command("cancel_booking"))
async def admin_cancel(message: Message, db: Database) -> None:
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /cancel_booking <номер>")
        return
    booking = await db.cancel(int(parts[1]))
    await message.answer(f"Запись #{parts[1]} отменена" if booking else "Активная запись не найдена")
    if booking:
        await message.bot.send_message(booking.user_id, f"К сожалению, запись #{booking.id} отменена администратором. "
                                                        "Выберите другое время в меню /start")
