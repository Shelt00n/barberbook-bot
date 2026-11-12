"""Точка входа: python -m bot"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import BotCommand

from . import texts
from .config import Settings, load_settings
from .db import Database
from .handlers import admin, user

log = logging.getLogger("barberbook")


async def reminders_loop(bot: Bot, db: Database, settings: Settings, every: int = 60) -> None:
    """Раз в минуту ищет записи, до которых осталось ≤ 2 часов, и шлёт напоминание."""
    while True:
        try:
            for b in await db.due_reminders(datetime.now(settings.tz), settings.remind_before):
                with contextlib.suppress(TelegramForbiddenError):  # пользователь заблокировал бота
                    await bot.send_message(b.user_id, texts.reminder(settings.service(b.service_id), b.starts_at))
                await db.mark_reminded(b.id)
        except Exception:  # цикл не должен падать из-за одной ошибки
            log.exception("reminders loop error")
        await asyncio.sleep(every)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    db = Database(settings.db_path)
    await db.connect()

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(db=db, settings=settings)  # зависимости прокидываются в хендлеры по имени аргумента
    dp.include_routers(admin.router, user.router)

    await bot.set_my_commands([BotCommand(command="start", description="Главное меню")])
    task = asyncio.create_task(reminders_loop(bot, db, settings))
    log.info("BarberBook запущен")
    try:
        await dp.start_polling(bot)
    finally:
        task.cancel()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
