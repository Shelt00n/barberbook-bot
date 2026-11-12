"""Тексты сообщений — отдельно от логики, чтобы их легко правил заказчик."""
from __future__ import annotations

from datetime import datetime

from .config import Service
from .keyboards import WEEKDAYS

GREETING = (
    "Привет, {name}! 👋\n\n"
    "Это бот барбершопа <b>BarberBook</b>. Здесь можно за минуту записаться на стрижку, "
    "посмотреть свои записи и отменить визит.\n\n"
    "Что делаем?"
)

CONTACTS = (
    "📍 <b>BarberBook</b>\n"
    "ул. Крещатик, 22, Киев\n"
    "🕙 Пн–Сб: 10:00–20:00, Вс — выходной\n"
    "☎️ +380 00 000 00 00 (демо)"
)

CHOOSE_SERVICE = "Выберите услугу 👇"
CHOOSE_DAY = "<b>{service}</b>\nНа какой день записать?"
CHOOSE_TIME = "<b>{service}</b> · {day}\nСвободное время:"
NO_SLOTS = "😔 На этот день свободного времени не осталось. Выберите другой день."
ASK_PHONE = "Оставьте номер телефона — мастер позвонит, если что-то изменится."
BAD_PHONE = "Похоже, в номере ошибка. Пример: +380 67 123 45 67"
SLOT_TAKEN = "⚡ Это время только что заняли. Выберите другое, пожалуйста."
CANCELLED = "Запись #{id} отменена. Будем ждать вас в другой раз!"
NO_BOOKINGS = "У вас пока нет предстоящих записей."


def human_dt(dt: datetime) -> str:
    return f"{WEEKDAYS[dt.weekday()]}, {dt:%d.%m} в {dt:%H:%M}"


def price_list(services: tuple[Service, ...]) -> str:
    rows = "\n".join(f"• {s.title} — <b>{s.price} ₴</b> ({s.minutes} мин)" for s in services)
    return f"💈 <b>Услуги и цены</b>\n\n{rows}"


def confirm(service: Service, when: datetime, phone: str) -> str:
    return (
        "Проверьте запись:\n\n"
        f"✂️ {service.title}\n"
        f"🗓 {human_dt(when)}\n"
        f"⏱ {service.minutes} мин · 💵 {service.price} ₴\n"
        f"📱 {phone}"
    )


def booked(booking_id: int, service: Service, when: datetime) -> str:
    return (
        f"🎉 Готово! Запись <b>#{booking_id}</b> подтверждена.\n\n"
        f"{service.title}, {human_dt(when)}.\n"
        "За 2 часа до визита пришлю напоминание."
    )


def reminder(service: Service, when: datetime) -> str:
    return f"⏰ Напоминаем: сегодня в <b>{when:%H:%M}</b> — {service.title.lower()}. До встречи в BarberBook!"


def admin_new(booking_id: int, name: str, phone: str, service: Service, when: datetime) -> str:
    return f"🆕 Новая запись #{booking_id}\n{name}, {phone}\n{service.title} — {human_dt(when)}"
