"""Inline- и reply-клавиатуры + типизированные callback-данные."""
from __future__ import annotations

from datetime import date, datetime

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .config import Service

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class MenuCb(CallbackData, prefix="menu"):
    action: str


class ServiceCb(CallbackData, prefix="svc"):
    id: str


class DayCb(CallbackData, prefix="day"):
    day: str


class SlotCb(CallbackData, prefix="slot"):
    hhmm: str


class ConfirmCb(CallbackData, prefix="confirm"):
    ok: bool


class CancelCb(CallbackData, prefix="cancel"):
    id: int


class AdminCb(CallbackData, prefix="adm"):
    action: str
    day: str = ""


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✂️ Записаться", callback_data=MenuCb(action="book"))
    kb.button(text="📅 Мои записи", callback_data=MenuCb(action="my"))
    kb.button(text="💈 Услуги и цены", callback_data=MenuCb(action="prices"))
    kb.button(text="📍 Как нас найти", callback_data=MenuCb(action="contacts"))
    kb.adjust(1, 1, 2)
    return kb.as_markup()


def services_kb(services: tuple[Service, ...]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in services:
        kb.button(text=f"{s.title} · {s.price} ₴ · {s.minutes} мин", callback_data=ServiceCb(id=s.id))
    kb.button(text="← В меню", callback_data=MenuCb(action="home"))
    kb.adjust(1)
    return kb.as_markup()


def days_kb(days: list[date], today: date) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for d in days:
        label = "Сегодня" if d == today else WEEKDAYS[d.weekday()]
        kb.button(text=f"{label} {d:%d.%m}", callback_data=DayCb(day=d.isoformat()))
    kb.button(text="← Назад", callback_data=MenuCb(action="book"))
    kb.adjust(3, 3, 3, 1)
    return kb.as_markup()


def slots_kb(slots: list[datetime], day: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in slots:
        kb.button(text=f"{s:%H:%M}", callback_data=SlotCb(hhmm=f"{s:%H:%M}"))
    kb.button(text="← Другой день", callback_data=MenuCb(action="pick_day"))
    rows = [4] * (len(slots) // 4) + ([len(slots) % 4] if len(slots) % 4 else []) + [1]
    kb.adjust(*rows)
    return kb.as_markup()


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="или введите номер вручную",
    )


def confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data=ConfirmCb(ok=True))
    kb.button(text="✏️ Изменить", callback_data=ConfirmCb(ok=False))
    kb.adjust(2)
    return kb.as_markup()


def my_bookings_kb(ids: list[int]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for i in ids:
        kb.button(text=f"❌ Отменить запись #{i}", callback_data=CancelCb(id=i))
    kb.button(text="← В меню", callback_data=MenuCb(action="home"))
    kb.adjust(1)
    return kb.as_markup()


def admin_kb(day: date) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️", callback_data=AdminCb(action="day", day=date.fromordinal(day.toordinal() - 1).isoformat()))
    kb.button(text="Сегодня", callback_data=AdminCb(action="day", day=""))
    kb.button(text="▶️", callback_data=AdminCb(action="day", day=date.fromordinal(day.toordinal() + 1).isoformat()))
    kb.button(text="📊 Статистика за 7 дней", callback_data=AdminCb(action="stats"))
    kb.adjust(3, 1)
    return kb.as_markup()
