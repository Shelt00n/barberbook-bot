"""Сценарий клиента: меню → услуга → день → время → телефон → подтверждение."""
from __future__ import annotations

import re
from datetime import date, datetime, time

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from .. import keyboards as kb
from .. import texts
from ..config import Settings
from ..db import Database
from ..slots import Busy, free_slots, upcoming_days

router = Router(name="user")
PHONE_RE = re.compile(r"^\+?\d[\d\s\-()]{8,16}\d$")


class Booking(StatesGroup):
    service = State()
    day = State()
    slot = State()
    phone = State()
    confirm = State()


def now(settings: Settings) -> datetime:
    return datetime.now(settings.tz)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    name = message.from_user.first_name if message.from_user else "друг"
    await message.answer(texts.GREETING.format(name=name), reply_markup=kb.main_menu())


@router.callback_query(kb.MenuCb.filter(F.action == "home"))
async def home(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(texts.GREETING.format(name=call.from_user.first_name), reply_markup=kb.main_menu())
    await call.answer()


@router.callback_query(kb.MenuCb.filter(F.action == "prices"))
async def prices(call: CallbackQuery, settings: Settings) -> None:
    await call.message.edit_text(texts.price_list(settings.services), reply_markup=kb.services_kb(settings.services))
    await call.answer()


@router.callback_query(kb.MenuCb.filter(F.action == "contacts"))
async def contacts(call: CallbackQuery) -> None:
    await call.message.answer(texts.CONTACTS)
    await call.answer()


# ---------- запись ----------

@router.callback_query(kb.MenuCb.filter(F.action == "book"))
async def choose_service(call: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    await state.set_state(Booking.service)
    await call.message.edit_text(texts.CHOOSE_SERVICE, reply_markup=kb.services_kb(settings.services))
    await call.answer()


@router.callback_query(kb.ServiceCb.filter())
async def choose_day(call: CallbackQuery, callback_data: kb.ServiceCb, state: FSMContext, settings: Settings) -> None:
    service = settings.service(callback_data.id)
    await state.update_data(service_id=service.id)
    await state.set_state(Booking.day)
    current = now(settings)
    days = upcoming_days(current, settings.booking_days_ahead)
    await call.message.edit_text(texts.CHOOSE_DAY.format(service=service.title), reply_markup=kb.days_kb(days, current.date()))
    await call.answer()


@router.callback_query(kb.MenuCb.filter(F.action == "pick_day"))
async def back_to_days(call: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    data = await state.get_data()
    await choose_day(call, kb.ServiceCb(id=data["service_id"]), state, settings)


@router.callback_query(kb.DayCb.filter(), Booking.day)
async def choose_time(call: CallbackQuery, callback_data: kb.DayCb, state: FSMContext,
                      settings: Settings, db: Database) -> None:
    data = await state.get_data()
    service = settings.service(data["service_id"])
    day = date.fromisoformat(callback_data.day)
    busy = [Busy(b.starts_at, b.minutes) for b in await db.bookings_for_day(day)]
    slots = free_slots(day, service.minutes, busy, now=now(settings),
                       open_hour=settings.open_hour, close_hour=settings.close_hour, step=settings.slot_minutes)
    if not slots:
        await call.answer(texts.NO_SLOTS, show_alert=True)
        return
    await state.update_data(day=day.isoformat())
    await state.set_state(Booking.slot)
    human_day = texts.human_dt(datetime.combine(day, time(0))).split(" в ")[0]
    await call.message.edit_text(texts.CHOOSE_TIME.format(service=service.title, day=human_day),
                                 reply_markup=kb.slots_kb(slots, day.isoformat()))
    await call.answer()


@router.callback_query(kb.SlotCb.filter(), Booking.slot)
async def ask_phone(call: CallbackQuery, callback_data: kb.SlotCb, state: FSMContext) -> None:
    await state.update_data(hhmm=callback_data.hhmm)
    await state.set_state(Booking.phone)
    await call.message.delete()
    await call.message.answer(texts.ASK_PHONE, reply_markup=kb.phone_kb())
    await call.answer()


@router.message(Booking.phone, F.contact | F.text)
async def got_phone(message: Message, state: FSMContext, settings: Settings) -> None:
    phone = message.contact.phone_number if message.contact else (message.text or "").strip()
    if not PHONE_RE.match(phone):
        await message.answer(texts.BAD_PHONE)
        return
    data = await state.update_data(phone=phone)
    when = _starts_at(data, settings)
    await state.set_state(Booking.confirm)
    await message.answer("Отлично!", reply_markup=ReplyKeyboardRemove())
    await message.answer(texts.confirm(settings.service(data["service_id"]), when, phone), reply_markup=kb.confirm_kb())


@router.callback_query(kb.ConfirmCb.filter(), Booking.confirm)
async def confirm(call: CallbackQuery, callback_data: kb.ConfirmCb, state: FSMContext,
                  settings: Settings, db: Database, bot: Bot) -> None:
    if not callback_data.ok:
        await choose_service(call, state, settings)
        return
    data = await state.get_data()
    service = settings.service(data["service_id"])
    when = _starts_at(data, settings)
    booking_id = await db.create_booking(
        user_id=call.from_user.id, user_name=call.from_user.full_name, phone=data["phone"],
        service_id=service.id, minutes=service.minutes, starts_at=when,
    )
    if booking_id is None:
        await call.answer(texts.SLOT_TAKEN, show_alert=True)
        await state.set_state(Booking.day)
        await choose_day(call, kb.ServiceCb(id=service.id), state, settings)
        return
    await state.clear()
    await call.message.edit_text(texts.booked(booking_id, service, when), reply_markup=kb.main_menu())
    await call.answer("Записали!")
    for admin in settings.admin_ids:
        await bot.send_message(admin, texts.admin_new(booking_id, call.from_user.full_name, data["phone"], service, when))


# ---------- мои записи ----------

@router.callback_query(kb.MenuCb.filter(F.action == "my"))
async def my_bookings(call: CallbackQuery, settings: Settings, db: Database) -> None:
    items = await db.user_bookings(call.from_user.id, now(settings))
    if not items:
        await call.answer(texts.NO_BOOKINGS, show_alert=True)
        return
    lines = [f"#{b.id} · {settings.service(b.service_id).title}\n    🗓 {texts.human_dt(b.starts_at)}" for b in items]
    await call.message.edit_text("📅 <b>Ваши записи</b>\n\n" + "\n\n".join(lines),
                                 reply_markup=kb.my_bookings_kb([b.id for b in items]))
    await call.answer()


@router.callback_query(kb.CancelCb.filter())
async def cancel(call: CallbackQuery, callback_data: kb.CancelCb, db: Database, settings: Settings, bot: Bot) -> None:
    booking = await db.cancel(callback_data.id, user_id=call.from_user.id)
    if not booking:
        await call.answer("Запись не найдена", show_alert=True)
        return
    await call.message.edit_text(texts.CANCELLED.format(id=booking.id), reply_markup=kb.main_menu())
    await call.answer()
    for admin in settings.admin_ids:
        await bot.send_message(admin, f"↩️ Отмена записи #{booking.id} ({texts.human_dt(booking.starts_at)})")


def _starts_at(data: dict, settings: Settings) -> datetime:
    hh, mm = map(int, data["hhmm"].split(":"))
    return datetime.combine(date.fromisoformat(data["day"]), time(hh, mm), tzinfo=settings.tz)
